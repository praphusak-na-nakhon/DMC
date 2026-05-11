from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .config import ocr_cache_dir
from .errors import DomainError


AKSON_OCR_MODEL: Literal["AksonOCR-1.0"] = "AksonOCR-1.0"
AKSON_OCR_UPLOAD_URL = "https://backend.aksonocr.com/api/v2/upload"
AKSON_OCR_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
AKSON_OCR_TIMEOUT_SECONDS = 180
SUPPORTED_AKSON_OCR_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


class AksonOcrDmcFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    api_key: str | None = None
    model: Literal["AksonOCR-1.0"] = AKSON_OCR_MODEL
    force_refresh: bool = False


class AksonOcrDmcFormResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["formConverter"] = "formConverter"
    engine: Literal["aksonocr"] = "aksonocr"
    model: Literal["AksonOCR-1.0"]
    source_path: str
    markdown_path: str
    cached: bool
    pages_processed: int
    average_confidence: float | None
    file_sha256: str
    created_at: str


def ocr_dmc_form_with_akson(request: AksonOcrDmcFormRequest) -> AksonOcrDmcFormResponse:
    source_path = _validated_source_path(Path(request.source_path))
    file_sha256 = _sha256_file(source_path)
    markdown_path, metadata_path = _cache_paths(source_path, request.model, file_sha256)

    if not request.force_refresh:
        cached_response = _cached_response(
            metadata_path=metadata_path,
            markdown_path=markdown_path,
            source_path=source_path,
            model=request.model,
            file_sha256=file_sha256,
        )
        if cached_response is not None:
            return cached_response

    api_key = _resolved_api_key(request.api_key)
    payload = _upload_to_akson(source_path, api_key=api_key, model=request.model)
    pages = _extract_pages(payload)
    pages_processed = _pages_processed(payload, pages)
    average_confidence = _average_confidence(payload, pages)
    created_at = datetime.now(timezone.utc).isoformat()

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        _render_markdown(
            pages=pages,
            source_path=source_path,
            model=request.model,
            file_sha256=file_sha256,
            pages_processed=pages_processed,
            average_confidence=average_confidence,
            created_at=created_at,
        ),
        encoding="utf-8",
    )
    _write_metadata(
        metadata_path,
        source_path=source_path,
        markdown_path=markdown_path,
        model=request.model,
        file_sha256=file_sha256,
        pages_processed=pages_processed,
        average_confidence=average_confidence,
        created_at=created_at,
    )

    return AksonOcrDmcFormResponse(
        model=request.model,
        source_path=str(source_path),
        markdown_path=str(markdown_path),
        cached=False,
        pages_processed=pages_processed,
        average_confidence=average_confidence,
        file_sha256=file_sha256,
        created_at=created_at,
    )


def _validated_source_path(path: Path) -> Path:
    if not path.exists():
        raise DomainError("AKSONOCR_INPUT_NOT_FOUND", "AksonOCR source file was not found.")
    if not path.is_file():
        raise DomainError("AKSONOCR_INPUT_NOT_FILE", "AksonOCR source path is not a file.")
    if path.suffix.lower() not in SUPPORTED_AKSON_OCR_SUFFIXES:
        raise DomainError(
            "AKSONOCR_UNSUPPORTED_INPUT_TYPE",
            "AksonOCR upload accepts PDF, PNG, JPG, JPEG, and WEBP files.",
        )
    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise DomainError("AKSONOCR_INPUT_EMPTY", "AksonOCR source file is empty.")
    if size_bytes > AKSON_OCR_MAX_UPLOAD_BYTES:
        raise DomainError("AKSONOCR_FILE_TOO_LARGE", "AksonOCR v2 upload is limited to 10 MB per request.")
    return path


def _resolved_api_key(api_key: str | None) -> str:
    value = (api_key or os.getenv("AKSONOCR_API_KEY", "")).strip()
    if not value:
        raise DomainError(
            "AKSONOCR_API_KEY_REQUIRED",
            "AksonOCR API key is required. Enter one in the app or set AKSONOCR_API_KEY.",
        )
    return value


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
    markdown_path = ocr_cache_dir() / "aksonocr" / f"{base_name}.md"
    return markdown_path, markdown_path.with_suffix(".meta.json")


def _cached_response(
    *,
    metadata_path: Path,
    markdown_path: Path,
    source_path: Path,
    model: Literal["AksonOCR-1.0"],
    file_sha256: str,
) -> AksonOcrDmcFormResponse | None:
    if not metadata_path.exists() or not markdown_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            return None
        if metadata.get("model") != model or metadata.get("file_sha256") != file_sha256:
            return None
        pages_processed = metadata.get("pages_processed")
        if not isinstance(pages_processed, int):
            return None
        average_confidence = _optional_float(metadata.get("average_confidence"))
        created_at = metadata.get("created_at")
        if not isinstance(created_at, str):
            return None
    except (OSError, json.JSONDecodeError):
        return None

    return AksonOcrDmcFormResponse(
        model=model,
        source_path=str(source_path),
        markdown_path=str(markdown_path),
        cached=True,
        pages_processed=pages_processed,
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
    file_sha256: str,
    pages_processed: int,
    average_confidence: float | None,
    created_at: str,
) -> None:
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "aksonocr",
                "model": model,
                "source_path": str(source_path),
                "markdown_path": str(markdown_path),
                "file_sha256": file_sha256,
                "pages_processed": pages_processed,
                "average_confidence": average_confidence,
                "created_at": created_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _upload_to_akson(source_path: Path, *, api_key: str, model: str) -> dict[str, Any]:
    boundary = f"----DmcAssistantAksonOcr{uuid.uuid4().hex}"
    body = _multipart_body(
        boundary=boundary,
        fields={"model": model, "tokenConfidence": "false"},
        file_field_name="file",
        file_path=source_path,
    )
    request = urllib.request.Request(
        AKSON_OCR_UPLOAD_URL,
        data=body,
        headers={
            "X-API-Key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "DMC-Assistant/0.1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=AKSON_OCR_TIMEOUT_SECONDS) as response:
            raw_response = response.read()
    except urllib.error.HTTPError as exc:
        detail = _read_http_error(exc)
        raise _domain_error_for_status(exc.code, detail) from exc
    except urllib.error.URLError as exc:
        raise DomainError("AKSONOCR_NETWORK_ERROR", f"Unable to connect to AksonOCR: {exc.reason}") from exc

    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR returned a non-JSON response.") from exc
    if not isinstance(payload, dict):
        raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR response must be a JSON object.")
    return payload


def _multipart_body(
    *,
    boundary: str,
    fields: dict[str, str],
    file_field_name: str,
    file_path: Path,
) -> bytes:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="{_escape_multipart_value(name)}"\r\n\r\n'.encode("utf-8"))
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.append(f"--{boundary}\r\n".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="{_escape_multipart_value(file_field_name)}"; '
            f'filename="{_escape_multipart_value(file_path.name)}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_path.read_bytes())
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts)


def _escape_multipart_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read(4096)
    except OSError:
        return ""
    try:
        return raw.decode("utf-8", errors="replace")
    except AttributeError:
        return ""


def _domain_error_for_status(status_code: int, detail: str) -> DomainError:
    message = detail.strip() or f"AksonOCR upload failed with HTTP {status_code}."
    if status_code in {401, 403}:
        return DomainError("AKSONOCR_AUTH_FAILED", message)
    if status_code == 402:
        return DomainError("AKSONOCR_CREDITS_REQUIRED", message)
    if status_code == 413:
        return DomainError("AKSONOCR_FILE_TOO_LARGE", message)
    if status_code == 429:
        return DomainError("AKSONOCR_RATE_LIMITED", message)
    if 400 <= status_code < 500:
        return DomainError("AKSONOCR_UPLOAD_REJECTED", message)
    return DomainError("AKSONOCR_UPLOAD_FAILED", message)


def _extract_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR response did not include OCR pages.")

    pages: list[dict[str, Any]] = []
    for index, raw_page in enumerate(raw_pages):
        if not isinstance(raw_page, dict):
            raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR response page must be an object.")
        markdown = raw_page.get("markdown")
        if not isinstance(markdown, str):
            raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR response page did not include markdown.")
        page_index = raw_page.get("index", index)
        pages.append(
            {
                "index": page_index if isinstance(page_index, int) else index,
                "markdown": markdown.strip(),
                "confidence": _optional_float(raw_page.get("confidence")),
            }
        )

    if not any(str(page["markdown"]).strip() for page in pages):
        raise DomainError("AKSONOCR_RESPONSE_INVALID", "AksonOCR returned empty markdown.")
    return pages


def _pages_processed(payload: dict[str, Any], pages: list[dict[str, Any]]) -> int:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        pages_processed = usage.get("pages_processed")
        if isinstance(pages_processed, int) and pages_processed > 0:
            return pages_processed
    return len(pages)


def _average_confidence(payload: dict[str, Any], pages: list[dict[str, Any]]) -> float | None:
    top_level_confidence = _optional_float(payload.get("confidence"))
    if top_level_confidence is not None:
        return top_level_confidence
    page_confidences = [
        confidence
        for confidence in (_optional_float(page.get("confidence")) for page in pages)
        if confidence is not None
    ]
    if not page_confidences:
        return None
    return sum(page_confidences) / len(page_confidences)


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
    file_sha256: str,
    pages_processed: int,
    average_confidence: float | None,
    created_at: str,
) -> str:
    header = [
        "<!--",
        "Generated by DMC Assistant from AksonOCR.",
        f"Model: {model}",
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
        return "unknown"
    return f"{value:.2f}".rstrip("0").rstrip(".")
