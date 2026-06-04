from __future__ import annotations

import hashlib
import importlib
import json
import mimetypes
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .config import ocr_cache_dir
from .errors import DomainError


GEMINI_OCR_FLASH_MODEL: Literal["gemini-3.5-flash"] = "gemini-3.5-flash"
GEMINI_OCR_PRO_MODEL: Literal["gemini-3-pro-preview"] = "gemini-3-pro-preview"
GEMINI_OCR_MODEL: Literal["gemini-3.5-flash"] = GEMINI_OCR_FLASH_MODEL
GEMINI_OCR_MODELS = {GEMINI_OCR_FLASH_MODEL, GEMINI_OCR_PRO_MODEL}
GEMINI_OCR_PROCESSING_MODE: Literal["batch"] = "batch"
GEMINI_OCR_PROCESSING_MODES = {"standard", "batch"}
GEMINI_OCR_MAX_SOURCE_BYTES = 200 * 1024 * 1024
GEMINI_OCR_MAX_PAGES = 1000
GEMINI_OCR_CREDITS_PER_PAGE = 3
GEMINI_OCR_FILE_PROCESSING_TIMEOUT_SECONDS = 180
GEMINI_OCR_BATCH_POLL_INTERVAL_SECONDS = 10
GEMINI_OCR_BATCH_TIMEOUT_SECONDS = 2 * 60 * 60
GEMINI_OCR_BATCH_PDF_PAGES_PER_REQUEST = 2
GEMINI_OCR_THINKING_LEVEL: Literal["low", "medium", "high"] | None = None
SUPPORTED_GEMINI_OCR_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
_LEGACY_MODEL_ALIASES = {
    "typhoon-ocr": GEMINI_OCR_FLASH_MODEL,
    "AksonOCR-preview": GEMINI_OCR_FLASH_MODEL,
    "AksonOCR-handwriting": GEMINI_OCR_FLASH_MODEL,
    "AksonOCR-1.0": GEMINI_OCR_FLASH_MODEL,
    "gemini-3.5": GEMINI_OCR_FLASH_MODEL,
    "gemini 3.5": GEMINI_OCR_FLASH_MODEL,
    "gemini-3.1-pro-preview": GEMINI_OCR_PRO_MODEL,
    "gemini 3.1 pro preview": GEMINI_OCR_PRO_MODEL,
    "gemini-3-pro": GEMINI_OCR_PRO_MODEL,
}


class GeminiOcrDmcFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    api_key: str | None = None
    model: str = GEMINI_OCR_MODEL
    processing_mode: str = GEMINI_OCR_PROCESSING_MODE
    force_refresh: bool = False


class GeminiOcrUsageMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    total_token_count: int | None = None
    cached_content_token_count: int | None = None
    thoughts_token_count: int | None = None
    input_tokens_per_page: float | None = None
    output_tokens_per_page: float | None = None
    total_tokens_per_page: float | None = None


class GeminiOcrDmcFormResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["formConverter"] = "formConverter"
    engine: Literal["gemini"] = "gemini"
    model: str
    processing_mode: str = GEMINI_OCR_PROCESSING_MODE
    source_path: str
    markdown_path: str
    structured_json_path: str | None = None
    output_format: Literal["structured_json"] = "structured_json"
    cached: bool
    pages_processed: int
    pages_estimated: int
    credits_per_page: int = GEMINI_OCR_CREDITS_PER_PAGE
    credits_charged: int = 0
    charged: bool = False
    credit_reservation_id: str | None = None
    average_confidence: float | None
    usage_metadata: GeminiOcrUsageMetadata | None = None
    batch_job_name: str | None = None
    batch_state: str | None = None
    file_sha256: str
    created_at: str


@dataclass(frozen=True)
class GeminiOcrPreparation:
    source_path: Path
    file_sha256: str
    markdown_path: Path
    metadata_path: Path
    pages_estimated: int
    processing_mode: str
    cached_response: GeminiOcrDmcFormResponse | None


@dataclass(frozen=True)
class _BatchSource:
    path: Path
    page_start: int
    page_end: int


@dataclass(frozen=True)
class _UploadedBatchSource:
    key: str
    uploaded_file: Any
    source_path: Path
    mime_type: str
    page_start: int
    page_end: int


def prepare_gemini_ocr_request(request: GeminiOcrDmcFormRequest) -> GeminiOcrPreparation:
    source_path = _validated_source_path(Path(request.source_path))
    model = _validated_model(request.model)
    processing_mode = _validated_processing_mode(request.processing_mode)
    file_sha256 = _sha256_file(source_path)
    markdown_path, metadata_path = _cache_paths(source_path, model, processing_mode, file_sha256)
    pages_estimated = _estimate_page_count(source_path)
    cached_response = None
    if not request.force_refresh:
        cached_response = _cached_response(
            metadata_path=metadata_path,
            markdown_path=markdown_path,
            source_path=source_path,
            model=model,
            processing_mode=processing_mode,
            file_sha256=file_sha256,
            pages_estimated=pages_estimated,
        )
    return GeminiOcrPreparation(
        source_path=source_path,
        file_sha256=file_sha256,
        markdown_path=markdown_path,
        metadata_path=metadata_path,
        pages_estimated=pages_estimated,
        processing_mode=processing_mode,
        cached_response=cached_response,
    )


def ocr_dmc_form_with_gemini(request: GeminiOcrDmcFormRequest) -> GeminiOcrDmcFormResponse:
    prepared = prepare_gemini_ocr_request(request)
    if prepared.cached_response is not None:
        return prepared.cached_response

    api_key = _resolved_api_key(request.api_key)
    model = _validated_model(request.model)
    processing_mode = _validated_processing_mode(request.processing_mode)
    batch_job_name: str | None = None
    batch_state: str | None = None
    if processing_mode == "batch":
        structured_payload, usage_metadata, batch_job_name, batch_state = _generate_structured_json_with_gemini_batch(
            prepared.source_path,
            api_key=api_key,
            model=model,
            pages_estimated=prepared.pages_estimated,
        )
    else:
        structured_payload, usage_metadata = _generate_structured_json_with_gemini(
            prepared.source_path,
            api_key=api_key,
            model=model,
            pages_estimated=prepared.pages_estimated,
        )
    structured_payload = _normalized_structured_payload(structured_payload)
    pages_processed = prepared.pages_estimated
    created_at = datetime.now(timezone.utc).isoformat()
    structured_payload = _with_output_metadata(
        structured_payload,
        source_path=prepared.source_path,
        model=model,
        processing_mode=processing_mode,
        file_sha256=prepared.file_sha256,
        pages_processed=pages_processed,
        pages_estimated=prepared.pages_estimated,
        usage_metadata=usage_metadata,
        batch_job_name=batch_job_name,
        batch_state=batch_state,
        created_at=created_at,
    )

    prepared.markdown_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.markdown_path.write_text(
        json.dumps(structured_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_metadata(
        prepared.metadata_path,
        source_path=prepared.source_path,
        markdown_path=prepared.markdown_path,
        model=model,
        processing_mode=processing_mode,
        file_sha256=prepared.file_sha256,
        pages_processed=pages_processed,
        pages_estimated=prepared.pages_estimated,
        average_confidence=None,
        usage_metadata=usage_metadata,
        batch_job_name=batch_job_name,
        batch_state=batch_state,
        created_at=created_at,
    )

    return GeminiOcrDmcFormResponse(
        model=model,
        processing_mode=processing_mode,
        source_path=str(prepared.source_path),
        markdown_path=str(prepared.markdown_path),
        structured_json_path=str(prepared.markdown_path),
        cached=False,
        pages_processed=pages_processed,
        pages_estimated=prepared.pages_estimated,
        average_confidence=None,
        usage_metadata=usage_metadata,
        batch_job_name=batch_job_name,
        batch_state=batch_state,
        file_sha256=prepared.file_sha256,
        created_at=created_at,
    )


def _validated_model(model: str) -> str:
    normalized = (model or "").strip() or GEMINI_OCR_MODEL
    normalized = _LEGACY_MODEL_ALIASES.get(normalized, normalized)
    if normalized not in GEMINI_OCR_MODELS:
        raise DomainError("GEMINIOCR_MODEL_UNSUPPORTED", f"Unsupported Gemini OCR model: {model}")
    return normalized


def _validated_processing_mode(processing_mode: str) -> str:
    normalized = (processing_mode or "").strip().lower().replace("-", "_") or GEMINI_OCR_PROCESSING_MODE
    if normalized not in GEMINI_OCR_PROCESSING_MODES:
        raise DomainError("GEMINIOCR_PROCESSING_MODE_UNSUPPORTED", f"Unsupported Gemini OCR processing mode: {processing_mode}")
    return normalized


def _validated_source_path(path: Path) -> Path:
    if not path.exists():
        raise DomainError("GEMINIOCR_INPUT_NOT_FOUND", "Gemini OCR source file was not found.")
    if not path.is_file():
        raise DomainError("GEMINIOCR_INPUT_NOT_FILE", "Gemini OCR source path is not a file.")
    if path.suffix.lower() not in SUPPORTED_GEMINI_OCR_SUFFIXES:
        raise DomainError(
            "GEMINIOCR_UNSUPPORTED_INPUT_TYPE",
            "Gemini OCR accepts PDF, PNG, JPG, JPEG, and WEBP files.",
        )
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise DomainError("GEMINIOCR_INPUT_EMPTY", "Gemini OCR source file is empty.")
    if size_bytes > GEMINI_OCR_MAX_SOURCE_BYTES:
        raise DomainError("GEMINIOCR_FILE_TOO_LARGE", "Gemini OCR source is limited to 200 MB per run.")
    return path


def _estimate_page_count(path: Path) -> int:
    if path.suffix.lower() != ".pdf":
        return 1
    page_count = _pypdf_page_count(path) or _regex_pdf_page_count(path)
    if page_count <= 0:
        raise DomainError("GEMINIOCR_PAGE_COUNT_UNKNOWN", "Unable to estimate PDF page count before OCR.")
    if page_count > GEMINI_OCR_MAX_PAGES:
        raise DomainError("GEMINIOCR_PAGE_LIMIT_EXCEEDED", "Gemini OCR is limited to 1000 PDF pages per run.")
    return page_count


def _pypdf_page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def _regex_pdf_page_count(path: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))


def _resolved_api_key(api_key: str | None) -> str:
    value = (api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not value:
        raise DomainError(
            "GEMINIOCR_API_KEY_REQUIRED",
            "Gemini API key is required. Enter one in the app or set GOOGLE_API_KEY or GEMINI_API_KEY.",
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_paths(source_path: Path, model: str, processing_mode: str, file_sha256: str) -> tuple[Path, Path]:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "-", source_path.stem).strip(" .")
    if not stem:
        stem = "ocr-source"
    stem = stem[:80]
    model_slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()
    mode_slug = re.sub(r"[^A-Za-z0-9]+", "-", processing_mode).strip("-").lower()
    base_name = f"{stem}-{model_slug}-{mode_slug}-{file_sha256[:16]}"
    markdown_path = ocr_cache_dir() / "gemini" / f"{base_name}.json"
    return markdown_path, markdown_path.with_suffix(".meta.json")


def _cached_response(
    *,
    metadata_path: Path,
    markdown_path: Path,
    source_path: Path,
    model: str,
    processing_mode: str,
    file_sha256: str,
    pages_estimated: int,
) -> GeminiOcrDmcFormResponse | None:
    if not metadata_path.exists() or not markdown_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            return None
        if (
            metadata.get("engine") != "gemini"
            or metadata.get("model") != model
            or str(metadata.get("processing_mode") or "standard") != processing_mode
            or metadata.get("thinking_level") != GEMINI_OCR_THINKING_LEVEL
            or metadata.get("file_sha256") != file_sha256
        ):
            return None
        pages_processed = metadata.get("pages_processed")
        if not isinstance(pages_processed, int):
            return None
        stored_pages_estimated = metadata.get("pages_estimated")
        if not isinstance(stored_pages_estimated, int):
            stored_pages_estimated = pages_estimated
        average_confidence = _optional_float(metadata.get("average_confidence"))
        usage_metadata = _usage_metadata_from_mapping(metadata.get("usage_metadata"), pages=stored_pages_estimated)
        batch_job_name = metadata.get("batch_job_name")
        if not isinstance(batch_job_name, str):
            batch_job_name = None
        batch_state = metadata.get("batch_state")
        if not isinstance(batch_state, str):
            batch_state = None
        created_at = metadata.get("created_at")
        if not isinstance(created_at, str):
            return None
    except (OSError, json.JSONDecodeError):
        return None

    return GeminiOcrDmcFormResponse(
        model=model,
        processing_mode=processing_mode,
        source_path=str(source_path),
        markdown_path=str(markdown_path),
        structured_json_path=str(markdown_path),
        cached=True,
        pages_processed=pages_processed,
        pages_estimated=stored_pages_estimated,
        average_confidence=average_confidence,
        usage_metadata=usage_metadata,
        batch_job_name=batch_job_name,
        batch_state=batch_state,
        file_sha256=file_sha256,
        created_at=created_at,
    )


def _write_metadata(
    metadata_path: Path,
    *,
    source_path: Path,
    markdown_path: Path,
    model: str,
    processing_mode: str,
    file_sha256: str,
    pages_processed: int,
    pages_estimated: int,
    average_confidence: float | None,
    usage_metadata: GeminiOcrUsageMetadata | None,
    batch_job_name: str | None,
    batch_state: str | None,
    created_at: str,
) -> None:
    usage_payload = usage_metadata.model_dump(exclude_none=True) if usage_metadata is not None else None
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "gemini",
                "model": model,
                "processing_mode": processing_mode,
                "thinking_level": GEMINI_OCR_THINKING_LEVEL,
                "source_path": str(source_path),
                "markdown_path": str(markdown_path),
                "structured_json_path": str(markdown_path),
                "output_format": "structured_json",
                "file_sha256": file_sha256,
                "pages_processed": pages_processed,
                "pages_estimated": pages_estimated,
                "average_confidence": average_confidence,
                "usage_metadata": usage_payload,
                "batch_job_name": batch_job_name,
                "batch_state": batch_state,
                "created_at": created_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _generate_structured_json_with_gemini(
    source_path: Path,
    *,
    api_key: str,
    model: str,
    pages_estimated: int,
) -> tuple[dict[str, Any], GeminiOcrUsageMetadata | None]:
    response = _generate_content_with_gemini(
        source_path,
        api_key=api_key,
        model=model,
        prompt=_structured_ocr_prompt(),
        config_overrides={"response_mime_type": "application/json"},
    )
    payload = _response_json(response)
    usage_metadata = _usage_metadata_from_response(response, pages=pages_estimated)
    return _normalized_structured_payload(payload), usage_metadata


def _generate_structured_json_with_gemini_batch(
    source_path: Path,
    *,
    api_key: str,
    model: str,
    pages_estimated: int,
) -> tuple[dict[str, Any], GeminiOcrUsageMetadata | None, str | None, str | None]:
    batch_job = _generate_content_with_gemini_batch(
        source_path,
        api_key=api_key,
        model=model,
        prompt=_structured_ocr_prompt(),
        config_overrides={"response_mime_type": "application/json"},
        pages_estimated=pages_estimated,
    )
    responses = _batch_job_responses(batch_job)
    payloads: list[tuple[str | None, dict[str, Any]]] = []
    usages: list[GeminiOcrUsageMetadata] = []
    for key, response in responses:
        payloads.append((key, _response_json(response)))
        usage_metadata = _usage_metadata_from_response(response, pages=pages_estimated)
        if usage_metadata is not None:
            usages.append(usage_metadata)
    payload = _merge_batch_structured_payloads(payloads)
    usage_metadata = _combined_usage_metadata(usages, pages=pages_estimated)
    return _normalized_structured_payload(payload), usage_metadata, _batch_job_name(batch_job), _batch_job_state(batch_job)


def _generate_markdown_with_gemini(source_path: Path, *, api_key: str, model: str) -> str:
    response = _generate_content_with_gemini(
        source_path,
        api_key=api_key,
        model=model,
        prompt=_ocr_prompt(),
        config_overrides={},
    )
    markdown = _response_text(response).strip()
    if not markdown:
        raise DomainError("GEMINIOCR_RESPONSE_INVALID", "Gemini OCR returned empty markdown.")
    return markdown


def _generate_content_with_gemini(
    source_path: Path,
    *,
    api_key: str,
    model: str,
    prompt: str,
    config_overrides: dict[str, Any],
) -> Any:
    genai, types = _load_google_genai()
    client: Any | None = None
    uploaded_file: Any | None = None
    try:
        client = genai.Client(api_key=api_key)
        uploaded_file = client.files.upload(
            file=str(source_path),
            config={"mime_type": _mime_type(source_path)},
        )
        uploaded_file = _wait_for_uploaded_file(client, uploaded_file)
        response = client.models.generate_content(
            model=model,
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(**_generation_config(config_overrides)),
        )
    except Exception as exc:
        raise _domain_error_from_exception(exc) from exc
    finally:
        if client is not None and uploaded_file is not None:
            _delete_uploaded_file(client, uploaded_file)
        if client is not None:
            _close_client(client)
    return response


def _generate_content_with_gemini_batch(
    source_path: Path,
    *,
    api_key: str,
    model: str,
    prompt: str,
    config_overrides: dict[str, Any],
    pages_estimated: int,
) -> Any:
    genai, types = _load_google_genai()
    client: Any | None = None
    uploaded_files: list[Any] = []
    uploaded_batch_file: Any | None = None
    batch_job: Any | None = None
    result_file_name: str | None = None
    batch_request_path: Path | None = None
    delete_uploaded_file = False
    try:
        client = genai.Client(api_key=api_key)
        with tempfile.TemporaryDirectory(prefix="dmc-gemini-batch-") as temp_dir:
            batch_sources = _batch_sources(source_path, pages_estimated=pages_estimated, temp_dir=Path(temp_dir))
            uploaded_sources: list[_UploadedBatchSource] = []
            for batch_source in batch_sources:
                uploaded_file = client.files.upload(
                    file=str(batch_source.path),
                    config={"mime_type": _mime_type(batch_source.path)},
                )
                uploaded_file = _wait_for_uploaded_file(client, uploaded_file)
                uploaded_files.append(uploaded_file)
                uploaded_sources.append(
                    _UploadedBatchSource(
                        key=_batch_request_key(batch_source.page_start, batch_source.page_end),
                        uploaded_file=uploaded_file,
                        source_path=batch_source.path,
                        mime_type=_mime_type(batch_source.path),
                        page_start=batch_source.page_start,
                        page_end=batch_source.page_end,
                    )
                )
            batch_request_path = _write_batch_request_jsonl(
                uploaded_sources=uploaded_sources,
                prompt=prompt,
                config_overrides=config_overrides,
            )
            uploaded_batch_file = client.files.upload(
                file=str(batch_request_path),
                config=types.UploadFileConfig(display_name=_batch_request_display_name(source_path), mime_type="jsonl"),
            )
            batch_job = client.batches.create(
                model=model,
                src=uploaded_batch_file.name,
                config={"display_name": _batch_display_name(source_path, model)},
            )
            batch_job = _wait_for_batch_job(client, batch_job)
            result_file_name = _batch_result_file_name(batch_job)
            if result_file_name:
                batch_job = _batch_job_with_file_response(batch_job, client.files.download(file=result_file_name))
            delete_uploaded_file = True
    except Exception as exc:
        raise _domain_error_from_exception(exc) from exc
    finally:
        if batch_request_path is not None:
            try:
                batch_request_path.unlink()
            except OSError:
                pass
        if delete_uploaded_file and client is not None:
            for uploaded_file in uploaded_files:
                _delete_uploaded_file(client, uploaded_file)
        if delete_uploaded_file and client is not None and uploaded_batch_file is not None:
            _delete_uploaded_file(client, uploaded_batch_file)
        if delete_uploaded_file and client is not None and result_file_name is not None:
            try:
                client.files.delete(name=result_file_name)
            except Exception:
                pass
        if client is not None:
            _close_client(client)
    return batch_job


def _batch_sources(source_path: Path, *, pages_estimated: int, temp_dir: Path) -> list[_BatchSource]:
    if source_path.suffix.lower() != ".pdf":
        return [_BatchSource(path=source_path, page_start=1, page_end=1)]
    pages_per_request = _batch_pdf_pages_per_request()
    if pages_estimated <= pages_per_request:
        return [_BatchSource(path=source_path, page_start=1, page_end=pages_estimated)]
    return _split_pdf_batch_sources(source_path, pages_per_request=pages_per_request, temp_dir=temp_dir)


def _batch_pdf_pages_per_request() -> int:
    raw_value = os.environ.get("GEMINI_OCR_BATCH_PDF_PAGES_PER_REQUEST", "").strip()
    if not raw_value:
        return GEMINI_OCR_BATCH_PDF_PAGES_PER_REQUEST
    try:
        return max(1, int(raw_value))
    except ValueError:
        return GEMINI_OCR_BATCH_PDF_PAGES_PER_REQUEST


def _split_pdf_batch_sources(source_path: Path, *, pages_per_request: int, temp_dir: Path) -> list[_BatchSource]:
    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(source_path))
        page_count = len(reader.pages)
        sources: list[_BatchSource] = []
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source_path.stem).strip("-._") or "dmc-ocr"
        for page_index in range(0, page_count, pages_per_request):
            page_start = page_index + 1
            page_end = min(page_index + pages_per_request, page_count)
            writer = PdfWriter()
            for source_page_index in range(page_index, page_end):
                writer.add_page(reader.pages[source_page_index])
            chunk_path = temp_dir / f"{stem[:40]}-pages-{page_start:04d}-{page_end:04d}.pdf"
            with chunk_path.open("wb") as handle:
                writer.write(handle)
            sources.append(_BatchSource(path=chunk_path, page_start=page_start, page_end=page_end))
        if sources:
            return sources
    except Exception as exc:
        raise DomainError(
            "GEMINIOCR_PDF_SPLIT_FAILED",
            "Unable to split PDF into page-pair chunks before Gemini Batch OCR.",
        ) from exc
    raise DomainError("GEMINIOCR_PAGE_COUNT_UNKNOWN", "Unable to split PDF because it contained no readable pages.")


def _write_batch_request_jsonl(
    *,
    uploaded_sources: list[_UploadedBatchSource],
    prompt: str,
    config_overrides: dict[str, Any],
) -> Path:
    handle = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".jsonl")
    try:
        for uploaded_source in uploaded_sources:
            file_uri = getattr(uploaded_source.uploaded_file, "uri", None)
            if not isinstance(file_uri, str) or not file_uri:
                raise DomainError("GEMINIOCR_UPLOAD_FAILED", "Gemini uploaded file did not return a usable URI for Batch OCR.")
            request = {
                "key": uploaded_source.key,
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "file_data": {
                                        "file_uri": file_uri,
                                        "mime_type": uploaded_source.mime_type,
                                    }
                                },
                                {
                                    "text": _batch_prompt(
                                        prompt,
                                        page_start=uploaded_source.page_start,
                                        page_end=uploaded_source.page_end,
                                    )
                                },
                            ],
                        }
                    ],
                    "generation_config": _generation_config(config_overrides),
                },
            }
            handle.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
        return Path(handle.name)
    finally:
        handle.close()


def _batch_request_key(page_start: int, page_end: int) -> str:
    return f"dmc-ocr-pages-{page_start:04d}-{page_end:04d}"


def _batch_prompt(prompt: str, *, page_start: int, page_end: int) -> str:
    if page_start == page_end:
        page_text = f"original page {page_start}"
    else:
        page_text = f"original pages {page_start}-{page_end}"
    return (
        f"{prompt}\n\n"
        f"The attached file contains {page_text} of the source document. "
        "Use those original page numbers for page_start and page_end in every returned record."
    )


def _generation_config(config_overrides: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {"temperature": 0}
    if GEMINI_OCR_THINKING_LEVEL is not None:
        config["thinking_config"] = {"thinking_level": GEMINI_OCR_THINKING_LEVEL}
    config.update(config_overrides)
    return config


def _batch_request_display_name(source_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source_path.stem).strip("-._") or "dmc-ocr"
    return f"dmc-ocr-request-{stem[:40]}"


def _batch_display_name(source_path: Path, model: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source_path.stem).strip("-._") or "dmc-ocr"
    return f"dmc-ocr-{stem[:40]}-{model}"


def _wait_for_batch_job(client: Any, batch_job: Any) -> Any:
    name = _batch_job_name(batch_job)
    if not name:
        return batch_job
    completed_states = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
    deadline = time.monotonic() + _batch_timeout_seconds()
    current_job = batch_job
    while _batch_job_state(current_job) not in completed_states:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DomainError(
                "GEMINIOCR_BATCH_TIMEOUT",
                f"Timed out while waiting for Gemini Batch OCR job {name}. The job may still finish in Google AI Studio.",
            )
        time.sleep(min(GEMINI_OCR_BATCH_POLL_INTERVAL_SECONDS, remaining))
        current_job = client.batches.get(name=name)
    state = _batch_job_state(current_job)
    if state != "JOB_STATE_SUCCEEDED":
        error = _mapping_or_attr(current_job, "error")
        raise DomainError(
            "GEMINIOCR_BATCH_FAILED",
            f"Gemini Batch OCR job {name} finished with {state}: {_format_batch_error(error)}",
            details={"batch_job_name": name, "batch_state": state, "batch_error": _format_batch_error(error)},
        )
    return current_job


def _batch_timeout_seconds() -> int:
    raw_value = os.environ.get("GEMINI_OCR_BATCH_TIMEOUT_SECONDS", "").strip()
    if not raw_value:
        return GEMINI_OCR_BATCH_TIMEOUT_SECONDS
    try:
        return max(60, int(raw_value))
    except ValueError:
        return GEMINI_OCR_BATCH_TIMEOUT_SECONDS


def _batch_job_name(batch_job: Any) -> str | None:
    if isinstance(batch_job, dict):
        name = batch_job.get("name")
        return name if isinstance(name, str) and name else None
    name = getattr(batch_job, "name", None)
    return name if isinstance(name, str) and name else None


def _batch_job_state(batch_job: Any) -> str:
    state = getattr(batch_job, "state", None)
    if state is None and isinstance(batch_job, dict):
        state = batch_job.get("state")
    name = getattr(state, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(state, str):
        return state
    return str(state or "")


def _batch_job_responses(batch_job: Any) -> list[tuple[str | None, Any]]:
    dest = _mapping_or_attr(batch_job, "dest") or _mapping_or_attr(batch_job, "response")
    inline_responses = _mapping_or_attr(dest, "inlined_responses") or _mapping_or_attr(dest, "inlinedResponses")
    responses: list[tuple[str | None, Any]] = []
    if isinstance(inline_responses, list) and inline_responses:
        for inline_response in inline_responses:
            key = _mapping_or_attr(inline_response, "key")
            if not isinstance(key, str):
                key = None
            error = _mapping_or_attr(inline_response, "error")
            if error is not None:
                raise DomainError(
                    "GEMINIOCR_BATCH_FAILED",
                    f"Gemini Batch OCR request {key or ''} failed: {_format_batch_error(error)}",
                    details={"batch_request_key": key, "batch_error": _format_batch_error(error)},
                )
            response = _mapping_or_attr(inline_response, "response")
            if response is not None:
                responses.append((key, response))
    if responses:
        return responses
    raise DomainError("GEMINIOCR_BATCH_RESPONSE_MISSING", "Gemini Batch OCR completed but returned no inline response.")


def _batch_result_file_name(batch_job: Any) -> str | None:
    dest = _mapping_or_attr(batch_job, "dest") or _mapping_or_attr(batch_job, "response")
    file_name = (
        _mapping_or_attr(dest, "file_name")
        or _mapping_or_attr(dest, "fileName")
        or _mapping_or_attr(dest, "responses_file")
        or _mapping_or_attr(dest, "responsesFile")
    )
    return file_name if isinstance(file_name, str) and file_name else None


def _batch_job_with_file_response(batch_job: Any, file_content_bytes: bytes | str) -> dict[str, Any]:
    if isinstance(file_content_bytes, bytes):
        file_content = file_content_bytes.decode("utf-8")
    else:
        file_content = file_content_bytes
    inlined_responses: list[dict[str, Any]] = []
    for line in file_content.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DomainError("GEMINIOCR_BATCH_RESPONSE_MISSING", f"Gemini Batch OCR result JSONL is invalid: {exc}") from exc
        if not isinstance(payload, dict):
            continue
        key = payload.get("key")
        if not isinstance(key, str):
            key = None
        error = payload.get("error")
        if error is not None:
            raise DomainError(
                "GEMINIOCR_BATCH_FAILED",
                f"Gemini Batch OCR request {key or ''} failed: {_format_batch_error(error)}",
                details={"batch_request_key": key, "batch_error": _format_batch_error(error)},
            )
        response = payload.get("response")
        if response is not None:
            inlined_responses.append({"key": key, "response": response})
    if inlined_responses:
        return {
            "name": _batch_job_name(batch_job),
            "state": _batch_job_state(batch_job),
            "dest": {"inlined_responses": inlined_responses},
        }
    raise DomainError("GEMINIOCR_BATCH_RESPONSE_MISSING", "Gemini Batch OCR result file did not contain a response.")


def _format_batch_error(error: Any) -> str:
    if error is None:
        return "no error detail"
    dump = getattr(error, "model_dump", None)
    if callable(dump):
        try:
            value = dump(exclude_none=True)
        except TypeError:
            value = dump()
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(error, dict):
        return json.dumps(error, ensure_ascii=False, separators=(",", ":"))
    return str(error).strip() or error.__class__.__name__


def _mapping_or_attr(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _load_google_genai() -> tuple[Any, Any]:
    try:
        genai = importlib.import_module("google.genai")
        types = importlib.import_module("google.genai.types")
    except ModuleNotFoundError as exc:
        raise DomainError(
            "GEMINIOCR_DEPENDENCY_MISSING",
            "Gemini OCR dependency is missing. Install google-genai and rebuild the sidecar.",
        ) from exc
    return genai, types


def _mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _wait_for_uploaded_file(client: Any, uploaded_file: Any) -> Any:
    name = getattr(uploaded_file, "name", None)
    if not isinstance(name, str) or not name:
        return uploaded_file

    deadline = time.monotonic() + GEMINI_OCR_FILE_PROCESSING_TIMEOUT_SECONDS
    current_file = uploaded_file
    while time.monotonic() < deadline:
        state = _file_state(current_file)
        if not state or state in {"ACTIVE", "SUCCEEDED", "PROCESSED"}:
            return current_file
        if "FAILED" in state:
            raise DomainError("GEMINIOCR_FILE_PROCESSING_FAILED", "Gemini failed to process the uploaded file.")
        if "PROCESSING" not in state:
            return current_file
        time.sleep(2)
        current_file = client.files.get(name=name)

    raise DomainError("GEMINIOCR_FILE_PROCESSING_TIMEOUT", "Timed out while waiting for Gemini to process the file.")


def _file_state(uploaded_file: Any) -> str:
    state = getattr(uploaded_file, "state", None)
    if state is None:
        return ""
    name = getattr(state, "name", None)
    if isinstance(name, str):
        return name.rsplit(".", 1)[-1].upper()
    return str(state).rsplit(".", 1)[-1].upper()


def _delete_uploaded_file(client: Any, uploaded_file: Any) -> None:
    name = getattr(uploaded_file, "name", None)
    if not isinstance(name, str) or not name:
        return
    try:
        client.files.delete(name=name)
    except Exception:
        return


def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def _ocr_prompt() -> str:
    return (
        "You are doing OCR for Thai DMC student history forms and Thai civil registration documents. "
        "Return only Markdown text, without explanations, summaries, or code fences. "
        "Transcribe all visible Thai and English text, numbers, checked boxes, blank fields, dotted lines, and tables as faithfully as possible. "
        "Do not infer missing values. If a value is blank, keep the label and a blank marker such as '-' or the visible dotted line. "
        "For every source page, start that page with exactly this HTML comment format: '<!-- Page N confidence: n/a -->'. "
        "Keep field labels adjacent to their values so downstream parsers can extract citizen ID, student number, names, birth date, addresses, parents, guardian, travel, weight, and height. "
        "Preserve Thai citizen IDs and house IDs exactly, including hyphens or spaces when visible."
    )


def _structured_ocr_prompt() -> str:
    field_names = ", ".join(f'"{field_name}"' for field_name in _structured_ocr_field_names())
    return (
        "You are extracting data from Thai DMC student history forms and Thai civil registration documents. "
        "Read every visible page carefully, but return only compact JSON. Do not return Markdown, prose, comments, or code fences. "
        "Create one record per student/person. If one student spans multiple pages, merge those pages into one record and set page_start/page_end. "
        "Use record_type 'dmc_form' for DMC student history forms and 'civil_registration' for Thai house registration copies. "
        "Extract only fields that are visible and relevant to DMC import. Use null for blank, obscured, unreadable, or missing values. "
        "Do not infer values from context, names, title, or defaults. Preserve Thai spelling, English names, citizen IDs, house IDs, phone numbers, and dates exactly as visible. "
        "For checked boxes or selected choices, return the visible selected label only. "
        "Return this exact JSON shape: "
        '{"schema_version":"dmc_assistant_structured_ocr.v1","document_type":"dmc_form|civil_registration|mixed|unknown","records":[{"record_type":"dmc_form|civil_registration","page_start":1,"page_end":2,"fields":{"field_name":"value or null"},"needs_review":["short reason"]}]}. '
        f"The allowed field keys are: {field_names}. "
        "Omit fields that are irrelevant to the document type, but include any visible field value that maps to an allowed key."
    )


def _structured_ocr_field_names() -> tuple[str, ...]:
    from .current_students import FORM_JSON_FIELD_NAMES

    return FORM_JSON_FIELD_NAMES


def _structured_ocr_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "document_type": {"type": "string"},
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "record_type": {"type": "string"},
                        "page_start": {"type": "integer"},
                        "page_end": {"type": "integer"},
                        "fields": {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "boolean"},
                                    {"type": "null"},
                                ]
                            },
                        },
                        "needs_review": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["record_type", "fields"],
                },
            },
        },
        "required": ["records"],
    }


def _response_text(response: Any) -> str:
    if isinstance(response, dict):
        text = response.get("text")
        if isinstance(text, str):
            return text
        return _response_text_from_candidates(response.get("candidates"))
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return _response_text_from_candidates(getattr(response, "candidates", None))


def _response_text_from_candidates(candidates: Any) -> str:
    parts: list[str] = []
    if isinstance(candidates, list):
        for candidate in candidates:
            content = _mapping_or_attr(candidate, "content")
            candidate_parts = _mapping_or_attr(content, "parts")
            if isinstance(candidate_parts, list):
                for part in candidate_parts:
                    part_text = _mapping_or_attr(part, "text")
                    if isinstance(part_text, str):
                        parts.append(part_text)
    return "\n".join(parts)


def _response_json(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    text = _response_text(response).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        payload = _response_json_with_extra_closing_braces(text)
        if payload is None:
            raise DomainError("GEMINIOCR_RESPONSE_INVALID", f"Gemini OCR returned invalid structured JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DomainError("GEMINIOCR_RESPONSE_INVALID", "Gemini OCR structured JSON root must be an object.")
    return payload


def _response_json_with_extra_closing_braces(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    try:
        payload, end_index = decoder.raw_decode(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    trailing = text[end_index:].strip()
    if trailing and not re.fullmatch(r"}+", trailing):
        return None
    return payload


def _normalized_structured_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["schema_version"] = str(normalized.get("schema_version") or "dmc_assistant_structured_ocr.v1")
    if not isinstance(normalized.get("document_type"), str):
        normalized["document_type"] = "unknown"
    records = normalized.get("records")
    if not isinstance(records, list):
        raise DomainError("GEMINIOCR_RESPONSE_INVALID", "Gemini OCR structured JSON is missing records.")
    normalized_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        normalized_record = dict(record)
        if not isinstance(normalized_record.get("fields"), dict):
            normalized_record["fields"] = {}
        needs_review = normalized_record.get("needs_review")
        if not isinstance(needs_review, list):
            normalized_record["needs_review"] = []
        else:
            normalized_record["needs_review"] = [item for item in needs_review if isinstance(item, str)]
        normalized_records.append(normalized_record)
    normalized["records"] = normalized_records
    if not normalized["records"]:
        raise DomainError("GEMINIOCR_RESPONSE_INVALID", "Gemini OCR structured JSON returned no records.")
    return normalized


def _merge_batch_structured_payloads(payloads: list[tuple[str | None, dict[str, Any]]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    document_types: set[str] = set()
    for key, payload in payloads:
        normalized = _normalized_structured_payload(payload)
        document_type = normalized.get("document_type")
        if isinstance(document_type, str) and document_type:
            document_types.add(document_type)
        page_range = _page_range_from_batch_key(key)
        for record in normalized["records"]:
            if isinstance(record, dict):
                merged_record = dict(record)
                if page_range is not None:
                    _apply_original_page_range(merged_record, page_start=page_range[0], page_end=page_range[1])
                records.append(merged_record)
    if not records:
        raise DomainError("GEMINIOCR_RESPONSE_INVALID", "Gemini OCR structured JSON returned no records.")
    meaningful_document_types = {document_type for document_type in document_types if document_type != "unknown"}
    if len(meaningful_document_types) == 1:
        document_type = next(iter(meaningful_document_types))
    elif meaningful_document_types:
        document_type = "mixed"
    else:
        document_type = "unknown"
    return {
        "schema_version": "dmc_assistant_structured_ocr.v1",
        "document_type": document_type,
        "records": records,
    }


def _page_range_from_batch_key(key: str | None) -> tuple[int, int] | None:
    if not key:
        return None
    match = re.fullmatch(r"dmc-ocr-pages-(\d{4})-(\d{4})", key)
    if match is None:
        return None
    page_start, page_end = (int(value) for value in match.groups())
    if page_start <= 0 or page_end < page_start:
        return None
    return page_start, page_end


def _apply_original_page_range(record: dict[str, Any], *, page_start: int, page_end: int) -> None:
    chunk_length = max(1, page_end - page_start + 1)
    adjusted_start = _original_page_number(record.get("page_start"), page_start=page_start, page_end=page_end, chunk_length=chunk_length)
    adjusted_end = _original_page_number(record.get("page_end"), page_start=page_start, page_end=page_end, chunk_length=chunk_length)
    if adjusted_end < adjusted_start:
        adjusted_end = adjusted_start
    record["page_start"] = adjusted_start
    record["page_end"] = adjusted_end


def _original_page_number(value: Any, *, page_start: int, page_end: int, chunk_length: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return page_start
    if page_start <= number <= page_end:
        return number
    if 1 <= number <= chunk_length:
        return page_start + number - 1
    return page_start


def _with_output_metadata(
    payload: dict[str, Any],
    *,
    source_path: Path,
    model: str,
    processing_mode: str,
    file_sha256: str,
    pages_processed: int,
    pages_estimated: int,
    usage_metadata: GeminiOcrUsageMetadata | None,
    batch_job_name: str | None,
    batch_state: str | None,
    created_at: str,
) -> dict[str, Any]:
    output = dict(payload)
    output.update(
        {
            "engine": "gemini",
            "model": model,
            "processing_mode": processing_mode,
            "thinking_level": GEMINI_OCR_THINKING_LEVEL,
            "source_path": str(source_path),
            "file_sha256": file_sha256,
            "pages_processed": pages_processed,
            "pages_estimated": pages_estimated,
            "usage_metadata": usage_metadata.model_dump(exclude_none=True) if usage_metadata is not None else None,
            "batch_job_name": batch_job_name,
            "batch_state": batch_state,
            "created_at": created_at,
        }
    )
    return output


def _usage_metadata_from_response(response: Any, *, pages: int) -> GeminiOcrUsageMetadata | None:
    usage = _mapping_or_attr(response, "usage_metadata") or _mapping_or_attr(response, "usageMetadata")
    if usage is None:
        return None
    payload = _usage_metadata_mapping(usage)
    return _usage_metadata_from_mapping(payload, pages=pages)


def _combined_usage_metadata(usages: list[GeminiOcrUsageMetadata], *, pages: int) -> GeminiOcrUsageMetadata | None:
    if not usages:
        return None
    payload: dict[str, int] = {}
    for field_name in (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
    ):
        values = [getattr(usage, field_name) for usage in usages if getattr(usage, field_name) is not None]
        if values:
            payload[field_name] = int(sum(values))
    if not payload:
        return None
    return _usage_metadata_from_mapping(payload, pages=pages)


def _usage_metadata_mapping(usage: Any) -> dict[str, Any]:
    dump = getattr(usage, "model_dump", None)
    if callable(dump):
        value = dump(exclude_none=True)
        if isinstance(value, dict):
            return _normalized_usage_metadata_keys(value)
    if isinstance(usage, dict):
        return _normalized_usage_metadata_keys(usage)
    payload: dict[str, Any] = {}
    for field_name in (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
    ):
        value = getattr(usage, field_name, None)
        if isinstance(value, int):
            payload[field_name] = value
    return payload


def _normalized_usage_metadata_keys(usage: dict[str, Any]) -> dict[str, Any]:
    key_map = {
        "promptTokenCount": "prompt_token_count",
        "candidatesTokenCount": "candidates_token_count",
        "totalTokenCount": "total_token_count",
        "cachedContentTokenCount": "cached_content_token_count",
        "thoughtsTokenCount": "thoughts_token_count",
        "promptTokensDetails": "prompt_tokens_details",
        "cacheTokensDetails": "cache_tokens_details",
        "candidatesTokensDetails": "candidates_tokens_details",
    }
    return {key_map.get(str(key), str(key)): item for key, item in usage.items()}


def _usage_metadata_from_mapping(value: object, *, pages: int) -> GeminiOcrUsageMetadata | None:
    if not isinstance(value, dict):
        return None
    payload = {str(key): item for key, item in value.items()}
    usage = GeminiOcrUsageMetadata.model_validate(payload)
    if pages > 0:
        if usage.prompt_token_count is not None:
            usage.input_tokens_per_page = usage.prompt_token_count / pages
        if usage.candidates_token_count is not None:
            usage.output_tokens_per_page = usage.candidates_token_count / pages
        if usage.total_token_count is not None:
            usage.total_tokens_per_page = usage.total_token_count / pages
    return usage


def _domain_error_from_exception(exc: Exception) -> DomainError:
    if isinstance(exc, DomainError):
        return exc

    message = str(exc).strip() or exc.__class__.__name__
    status_code = _status_code_from_exception(exc)
    if status_code is not None:
        return _domain_error_for_status(status_code, message)

    upper_message = message.upper()
    exception_name = exc.__class__.__name__.lower()
    if "API_KEY" in upper_message or "API KEY" in upper_message or "UNAUTHENTICATED" in upper_message:
        return DomainError("GEMINIOCR_AUTH_FAILED", message)
    if "RESOURCE_EXHAUSTED" in upper_message or "QUOTA" in upper_message:
        return DomainError("GEMINIOCR_RATE_LIMITED", message)
    if "timeout" in exception_name or "timeout" in upper_message:
        return DomainError("GEMINIOCR_NETWORK_ERROR", f"Gemini OCR request timed out: {message}")
    if "connection" in exception_name or "network" in exception_name:
        return DomainError("GEMINIOCR_NETWORK_ERROR", f"Unable to connect to Gemini: {message}")
    return DomainError("GEMINIOCR_RESPONSE_INVALID", f"Gemini OCR failed: {message}")


def _status_code_from_exception(exc: Exception) -> int | None:
    for attribute in ("status_code", "code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _domain_error_for_status(status_code: int, detail: str) -> DomainError:
    message = detail.strip() or f"Gemini OCR request failed with HTTP {status_code}."
    if status_code in {401, 403}:
        return DomainError("GEMINIOCR_AUTH_FAILED", message)
    if status_code == 404 and "model" in message.lower():
        return DomainError("GEMINIOCR_MODEL_UNSUPPORTED", message)
    if status_code == 413:
        return DomainError("GEMINIOCR_FILE_TOO_LARGE", message)
    if status_code == 429:
        return DomainError("GEMINIOCR_RATE_LIMITED", message)
    if 400 <= status_code < 500:
        return DomainError("GEMINIOCR_UPLOAD_REJECTED", message)
    return DomainError("GEMINIOCR_PROCESSING_FAILED", message)


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _render_markdown(
    *,
    markdown_body: str,
    source_path: Path,
    model: str,
    file_sha256: str,
    pages_processed: int,
    average_confidence: float | None,
    created_at: str,
) -> str:
    header = [
        "<!--",
        "Generated by DMC Assistant from Gemini API.",
        f"Model: {model}",
        f"Source: {source_path}",
        f"SHA256: {file_sha256}",
        f"Pages processed: {pages_processed}",
        f"Average confidence: {_confidence_text(average_confidence)}",
        f"Created at: {created_at}",
        "-->",
        "",
    ]
    body = markdown_body.strip()
    if not re.search(r"<!--\s*Page\s+\d+\s+confidence:", body, flags=re.IGNORECASE):
        body = f"<!-- Page 1 confidence: n/a -->\n{body}"
    return "\n".join(header) + body + "\n"


def _confidence_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4g}"
