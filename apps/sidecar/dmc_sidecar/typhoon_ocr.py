from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any, Callable, Literal, cast

from pydantic import BaseModel, ConfigDict

from .config import ocr_cache_dir
from .errors import DomainError


TYPHOON_OCR_MODEL: Literal["typhoon-ocr"] = "typhoon-ocr"
TYPHOON_OCR_BASE_URL = "https://api.opentyphoon.ai/v1"
TYPHOON_OCR_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
TYPHOON_OCR_MAX_SOURCE_PDF_BYTES = 100 * 1024 * 1024
TYPHOON_OCR_MAX_PAGES = 100
TYPHOON_OCR_CREDITS_PER_PAGE = 3
TYPHOON_OCR_PAGE_DELAY_SECONDS = 3.1
SUPPORTED_TYPHOON_OCR_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
_TYPHOON_RATE_LOCK = Lock()
_next_typhoon_request_at = 0.0


class TyphoonOcrDmcFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    api_key: str | None = None
    model: Literal["typhoon-ocr"] = TYPHOON_OCR_MODEL
    force_refresh: bool = False


class TyphoonOcrDmcFormResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["formConverter"] = "formConverter"
    engine: Literal["typhoonocr"] = "typhoonocr"
    model: Literal["typhoon-ocr"]
    source_path: str
    markdown_path: str
    cached: bool
    pages_processed: int
    pages_estimated: int
    credits_per_page: int = TYPHOON_OCR_CREDITS_PER_PAGE
    credits_charged: int = 0
    charged: bool = False
    credit_reservation_id: str | None = None
    average_confidence: float | None
    file_sha256: str
    created_at: str


@dataclass(frozen=True)
class TyphoonOcrPreparation:
    source_path: Path
    file_sha256: str
    markdown_path: Path
    metadata_path: Path
    pages_estimated: int
    cached_response: TyphoonOcrDmcFormResponse | None


@dataclass(frozen=True)
class TyphoonUploadPage:
    source_path: Path
    source_page_number: int
    upload_page_number: int


def prepare_typhoon_ocr_request(request: TyphoonOcrDmcFormRequest) -> TyphoonOcrPreparation:
    source_path = _validated_source_path(Path(request.source_path))
    file_sha256 = _sha256_file(source_path)
    markdown_path, metadata_path = _cache_paths(source_path, request.model, file_sha256)
    pages_estimated = _estimate_page_count(source_path)
    cached_response = None
    if not request.force_refresh:
        cached_response = _cached_response(
            metadata_path=metadata_path,
            markdown_path=markdown_path,
            source_path=source_path,
            model=request.model,
            file_sha256=file_sha256,
            pages_estimated=pages_estimated,
        )
    return TyphoonOcrPreparation(
        source_path=source_path,
        file_sha256=file_sha256,
        markdown_path=markdown_path,
        metadata_path=metadata_path,
        pages_estimated=pages_estimated,
        cached_response=cached_response,
    )


def ocr_dmc_form_with_typhoon(request: TyphoonOcrDmcFormRequest) -> TyphoonOcrDmcFormResponse:
    prepared = prepare_typhoon_ocr_request(request)
    if prepared.cached_response is not None:
        return prepared.cached_response

    api_key = _resolved_api_key(request.api_key)
    base_url = _resolved_base_url()
    pages = _ocr_pages_with_typhoon(
        prepared.source_path,
        api_key=api_key,
        base_url=base_url,
        model=request.model,
        pages_estimated=prepared.pages_estimated,
    )
    pages_processed = len(pages)
    created_at = datetime.now(timezone.utc).isoformat()

    prepared.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.markdown_path.write_text(
        _render_markdown(
            pages=pages,
            source_path=prepared.source_path,
            model=request.model,
            base_url=base_url,
            file_sha256=prepared.file_sha256,
            pages_processed=pages_processed,
            average_confidence=None,
            created_at=created_at,
        ),
        encoding="utf-8",
    )
    _write_metadata(
        prepared.metadata_path,
        source_path=prepared.source_path,
        markdown_path=prepared.markdown_path,
        model=request.model,
        base_url=base_url,
        file_sha256=prepared.file_sha256,
        pages_processed=pages_processed,
        pages_estimated=prepared.pages_estimated,
        average_confidence=None,
        created_at=created_at,
    )

    return TyphoonOcrDmcFormResponse(
        model=request.model,
        source_path=str(prepared.source_path),
        markdown_path=str(prepared.markdown_path),
        cached=False,
        pages_processed=pages_processed,
        pages_estimated=prepared.pages_estimated,
        average_confidence=None,
        file_sha256=prepared.file_sha256,
        created_at=created_at,
    )


def _validated_source_path(path: Path) -> Path:
    if not path.exists():
        raise DomainError("TYPHOONOCR_INPUT_NOT_FOUND", "Typhoon OCR source file was not found.")
    if not path.is_file():
        raise DomainError("TYPHOONOCR_INPUT_NOT_FILE", "Typhoon OCR source path is not a file.")
    if path.suffix.lower() not in SUPPORTED_TYPHOON_OCR_SUFFIXES:
        raise DomainError(
            "TYPHOONOCR_UNSUPPORTED_INPUT_TYPE",
            "Typhoon OCR accepts PDF, PNG, JPG, and JPEG files.",
        )
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise DomainError("TYPHOONOCR_INPUT_EMPTY", "Typhoon OCR source file is empty.")
    if path.suffix.lower() == ".pdf":
        if size_bytes > TYPHOON_OCR_MAX_SOURCE_PDF_BYTES:
            raise DomainError("TYPHOONOCR_FILE_TOO_LARGE", "Typhoon OCR PDF source is limited to 100 MB per run.")
    elif size_bytes > TYPHOON_OCR_MAX_UPLOAD_BYTES:
        raise DomainError("TYPHOONOCR_FILE_TOO_LARGE", "Typhoon OCR image input is limited to 10 MB per request.")
    return path


def _estimate_page_count(path: Path) -> int:
    if path.suffix.lower() != ".pdf":
        return 1
    page_count = _pypdf_page_count(path) or _regex_pdf_page_count(path)
    if page_count <= 0:
        raise DomainError("TYPHOONOCR_PAGE_COUNT_UNKNOWN", "Unable to estimate PDF page count before OCR.")
    if page_count > TYPHOON_OCR_MAX_PAGES:
        raise DomainError("TYPHOONOCR_PAGE_LIMIT_EXCEEDED", "Typhoon OCR is limited to 100 pages per run.")
    return page_count


def _pypdf_page_count(path: Path) -> int | None:
    classes = _pypdf_classes()
    if classes is None:
        return None
    PdfReader, _PdfWriter = classes
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def _pypdf_classes() -> tuple[Callable[..., Any], Callable[..., Any]] | None:
    try:
        pypdf = importlib.import_module("pypdf")
    except ModuleNotFoundError:
        return None
    return cast(Callable[..., Any], getattr(pypdf, "PdfReader")), cast(Callable[..., Any], getattr(pypdf, "PdfWriter"))


def _regex_pdf_page_count(path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))


def _resolved_api_key(api_key: str | None) -> str:
    value = (api_key or os.environ.get("TYPHOON_OCR_API_KEY") or os.environ.get("TYPHOON_API_KEY") or "").strip()
    if not value:
        raise DomainError(
            "TYPHOONOCR_API_KEY_REQUIRED",
            "Typhoon OCR API key is required. Enter one in the app or set TYPHOON_OCR_API_KEY.",
        )
    return value


def _resolved_base_url() -> str:
    return (os.getenv("TYPHOON_OCR_BASE_URL", "") or os.getenv("TYPHOON_BASE_URL", "") or TYPHOON_OCR_BASE_URL).strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_paths(source_path: Path, model: str, file_sha256: str) -> tuple[Path, Path]:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "-", source_path.stem).strip(" .")
    if not stem:
        stem = "ocr-source"
    stem = stem[:80]
    model_slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()
    base_name = f"{stem}-{model_slug}-{file_sha256[:16]}"
    markdown_path = ocr_cache_dir() / "typhoonocr" / f"{base_name}.md"
    return markdown_path, markdown_path.with_suffix(".meta.json")


def _cached_response(
    *,
    metadata_path: Path,
    markdown_path: Path,
    source_path: Path,
    model: Literal["typhoon-ocr"],
    file_sha256: str,
    pages_estimated: int,
) -> TyphoonOcrDmcFormResponse | None:
    if not metadata_path.exists() or not markdown_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            return None
        if metadata.get("engine") != "typhoonocr" or metadata.get("model") != model or metadata.get("file_sha256") != file_sha256:
            return None
        pages_processed = metadata.get("pages_processed")
        if not isinstance(pages_processed, int):
            return None
        stored_pages_estimated = metadata.get("pages_estimated")
        if not isinstance(stored_pages_estimated, int):
            stored_pages_estimated = pages_estimated
        average_confidence = _optional_float(metadata.get("average_confidence"))
        created_at = metadata.get("created_at")
        if not isinstance(created_at, str):
            return None
    except (OSError, json.JSONDecodeError):
        return None

    return TyphoonOcrDmcFormResponse(
        model=model,
        source_path=str(source_path),
        markdown_path=str(markdown_path),
        cached=True,
        pages_processed=pages_processed,
        pages_estimated=stored_pages_estimated,
        average_confidence=average_confidence,
        file_sha256=file_sha256,
        created_at=created_at,
    )


def _write_metadata(
    metadata_path: Path,
    *,
    source_path: Path,
    markdown_path: Path,
    model: str,
    base_url: str,
    file_sha256: str,
    pages_processed: int,
    pages_estimated: int,
    average_confidence: float | None,
    created_at: str,
) -> None:
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "typhoonocr",
                "model": model,
                "base_url": base_url,
                "source_path": str(source_path),
                "markdown_path": str(markdown_path),
                "file_sha256": file_sha256,
                "pages_processed": pages_processed,
                "pages_estimated": pages_estimated,
                "average_confidence": average_confidence,
                "created_at": created_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _ocr_pages_with_typhoon(
    source_path: Path,
    *,
    api_key: str,
    base_url: str,
    model: Literal["typhoon-ocr"],
    pages_estimated: int,
) -> list[dict[str, Any]]:
    if source_path.suffix.lower() != ".pdf":
        upload_pages = [TyphoonUploadPage(source_path=source_path, source_page_number=1, upload_page_number=1)]
        return _ocr_upload_pages_with_typhoon(
            upload_pages,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    with TemporaryDirectory(prefix="dmc-typhoon-ocr-pages-") as temp_dir:
        upload_pages = _split_pdf_into_upload_pages(
            source_path,
            temp_dir=Path(temp_dir),
            pages_estimated=pages_estimated,
        )
        return _ocr_upload_pages_with_typhoon(
            upload_pages,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )


def _ocr_upload_pages_with_typhoon(
    upload_pages: list[TyphoonUploadPage],
    *,
    api_key: str,
    base_url: str,
    model: Literal["typhoon-ocr"],
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for upload_page in upload_pages:
        _wait_for_typhoon_rate_limit()
        markdown = _ocr_page_with_typhoon(
            upload_page.source_path,
            api_key=api_key,
            base_url=base_url,
            model=model,
            page_number=upload_page.upload_page_number,
        ).strip()
        if not markdown:
            raise DomainError("TYPHOONOCR_RESPONSE_INVALID", "Typhoon OCR returned empty markdown.")
        pages.append({"index": upload_page.source_page_number, "markdown": markdown, "confidence": None})
    return pages


def _split_pdf_into_upload_pages(
    source_path: Path,
    *,
    temp_dir: Path,
    pages_estimated: int,
) -> list[TyphoonUploadPage]:
    classes = _pypdf_classes()
    if classes is None:
        raise DomainError(
            "TYPHOONOCR_PDF_SPLIT_UNAVAILABLE",
            "Typhoon OCR needs pypdf to split large PDFs into 10 MB page uploads.",
        )
    PdfReader, PdfWriter = classes
    try:
        reader = PdfReader(str(source_path))
    except Exception as exc:
        raise DomainError("TYPHOONOCR_PDF_SPLIT_FAILED", "Unable to split PDF into page uploads before OCR.") from exc

    actual_pages = len(reader.pages)
    if actual_pages != pages_estimated:
        raise DomainError("TYPHOONOCR_PAGE_COUNT_UNKNOWN", "PDF page count changed while preparing OCR uploads.")

    temp_dir.mkdir(parents=True, exist_ok=True)
    upload_pages: list[TyphoonUploadPage] = []
    for page_index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        page_path = temp_dir / f"page-{page_index:04d}.pdf"
        with page_path.open("wb") as handle:
            writer.write(handle)
        size_bytes = page_path.stat().st_size
        if size_bytes <= 0:
            raise DomainError("TYPHOONOCR_INPUT_EMPTY", f"PDF page {page_index} is empty after splitting.")
        if size_bytes > TYPHOON_OCR_MAX_UPLOAD_BYTES:
            raise DomainError(
                "TYPHOONOCR_PAGE_TOO_LARGE",
                f"PDF page {page_index} is larger than 10 MB after splitting. Rescan or compress this page.",
            )
        upload_pages.append(TyphoonUploadPage(source_path=page_path, source_page_number=page_index, upload_page_number=1))
    return upload_pages


def _wait_for_typhoon_rate_limit() -> None:
    global _next_typhoon_request_at
    interval_seconds = max(float(TYPHOON_OCR_PAGE_DELAY_SECONDS), 0.0)
    if interval_seconds <= 0:
        return
    with _TYPHOON_RATE_LOCK:
        now = time.monotonic()
        wait_seconds = max(_next_typhoon_request_at - now, 0.0)
        _next_typhoon_request_at = max(_next_typhoon_request_at, now) + interval_seconds
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def _ocr_page_with_typhoon(
    source_path: Path,
    *,
    api_key: str,
    base_url: str,
    model: Literal["typhoon-ocr"],
    page_number: int,
) -> str:
    ocr_document = _load_typhoon_ocr_document()
    try:
        return ocr_document(
            pdf_or_image_path=str(source_path),
            page_num=page_number,
            api_key=api_key,
            base_url=base_url,
            model=model,
            task_type="v1.5",
            figure_language="Thai",
        )
    except Exception as exc:
        raise _domain_error_from_exception(exc) from exc


def _load_typhoon_ocr_document() -> Callable[..., str]:
    try:
        typhoon_ocr = importlib.import_module("typhoon_ocr")
    except ModuleNotFoundError as exc:
        raise DomainError(
            "TYPHOONOCR_DEPENDENCY_MISSING",
            "Typhoon OCR dependency is missing. Install typhoon-ocr and rebuild the sidecar.",
        ) from exc
    return cast(Callable[..., str], getattr(typhoon_ocr, "ocr_document"))


def _domain_error_from_exception(exc: Exception) -> DomainError:
    message = str(exc).strip() or exc.__class__.__name__
    if isinstance(exc, ImportError) or "PDF utilities are not available" in message or "pdfinfo" in message or "pdftoppm" in message:
        return DomainError(
            "TYPHOONOCR_PDF_UTILS_MISSING",
            "Typhoon OCR PDF processing requires Poppler utilities: pdfinfo and pdftoppm.",
        )

    status_code = _status_code_from_exception(exc)
    if status_code is not None:
        return _domain_error_for_status(status_code, message)

    exception_name = exc.__class__.__name__.lower()
    if "timeout" in exception_name:
        return DomainError("TYPHOONOCR_NETWORK_ERROR", f"Typhoon OCR request timed out: {message}")
    if "connection" in exception_name or "network" in exception_name:
        return DomainError("TYPHOONOCR_NETWORK_ERROR", f"Unable to connect to Typhoon OCR: {message}")
    if message.startswith("Error processing document:"):
        return DomainError("TYPHOONOCR_PROCESSING_FAILED", message)
    return DomainError("TYPHOONOCR_RESPONSE_INVALID", f"Typhoon OCR failed: {message}")


def _status_code_from_exception(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _domain_error_for_status(status_code: int, detail: str) -> DomainError:
    message = detail.strip() or f"Typhoon OCR request failed with HTTP {status_code}."
    if status_code in {401, 403}:
        return DomainError("TYPHOONOCR_AUTH_FAILED", message)
    if status_code == 402:
        return DomainError("TYPHOONOCR_CREDITS_REQUIRED", message)
    if status_code == 413:
        return DomainError("TYPHOONOCR_FILE_TOO_LARGE", message)
    if status_code == 429:
        return DomainError("TYPHOONOCR_RATE_LIMITED", message)
    if 400 <= status_code < 500:
        return DomainError("TYPHOONOCR_UPLOAD_REJECTED", message)
    return DomainError("TYPHOONOCR_UPLOAD_FAILED", message)


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _render_markdown(
    *,
    pages: list[dict[str, Any]],
    source_path: Path,
    model: str,
    base_url: str,
    file_sha256: str,
    pages_processed: int,
    average_confidence: float | None,
    created_at: str,
) -> str:
    header = [
        "<!--",
        "Generated by DMC Assistant from Typhoon OCR.",
        f"Model: {model}",
        f"Base URL: {base_url}",
        f"Source: {source_path}",
        f"SHA256: {file_sha256}",
        f"Pages processed: {pages_processed}",
        f"Average confidence: {_confidence_text(average_confidence)}",
        f"Created at: {created_at}",
        "-->",
        "",
    ]
    rendered_pages: list[str] = []
    for page in pages:
        page_index = page["index"]
        confidence = _confidence_text(_optional_float(page.get("confidence")))
        rendered_pages.append(f"<!-- Page {page_index} confidence: {confidence} -->\n{page['markdown']}")
    return "\n\n".join(["\n".join(header), *rendered_pages]).strip() + "\n"


def _confidence_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4g}"
