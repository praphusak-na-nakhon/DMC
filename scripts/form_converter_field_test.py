from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b")


class FieldTestError(Exception):
    pass


def json_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers=headers,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None,
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        detail = _http_error_detail(exc)
        raise FieldTestError(f"HTTP_{exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise FieldTestError(f"CLOUD_UNAVAILABLE: {exc.reason}") from exc
    if not body:
        return {}
    return dict(json.loads(body.decode("utf-8")))


def _http_error_detail(exc: HTTPError) -> str | None:
    try:
        body = exc.read()
    except OSError:
        return None
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    detail = payload.get("detail")
    return detail if isinstance(detail, str) else None


def inspect_pdf(path: Path) -> tuple[bytes, int]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise FieldTestError(f"{path.name}: not a PDF file")
    page_count = len(PDF_PAGE_PATTERN.findall(data)) or 1
    return data, page_count


def discover_pdfs(pdf_dir: Path, *, max_files: int | None) -> list[Path]:
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        raise FieldTestError(f"PDF directory not found: {pdf_dir}")
    pdfs = sorted(path for path in pdf_dir.glob("*.pdf") if path.is_file())
    if max_files is not None:
        pdfs = pdfs[:max_files]
    if not pdfs:
        raise FieldTestError(f"No PDF files found in {pdf_dir}")
    return pdfs


def login(base_url: str, *, email: str, password: str) -> str:
    response = json_request(
        base_url,
        "/v1/auth/login",
        method="POST",
        payload={
            "email": email,
            "password": password,
            "device_id": "form-converter-field-test",
            "device_name": "field-test-cli",
            "app_version": "0.1.0",
        },
    )
    token = response.get("token")
    if not isinstance(token, str) or not token:
        raise FieldTestError("Login response did not include token")
    return token


def run_pdf(base_url: str, token: str, pdf_path: Path, *, template_type: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document_bytes, page_count = inspect_pdf(pdf_path)
    job_id = f"field-test-{uuid.uuid4()}"
    reservation_id: str | None = None
    summary: dict[str, Any] = {
        "file_name": pdf_path.name,
        "job_id": job_id,
        "page_count": page_count,
        "status": "failed",
        "provider": "",
        "records": 0,
        "ready_fields": 0,
        "needs_review_fields": 0,
        "invalid_fields": 0,
        "avg_confidence": 0.0,
        "error": None,
    }
    field_rows: list[dict[str, Any]] = []
    try:
        reservation = json_request(
            base_url,
            "/v1/credits/reservations",
            method="POST",
            token=token,
            payload={
                "job_id": job_id,
                "module": "formConverter",
                "units": page_count,
                "idempotency_key": f"{job_id}:reserve",
            },
        )
        reservation_id = str(reservation["reservation_id"])
        ocr = json_request(
            base_url,
            "/v1/ocr/form-converter",
            method="POST",
            token=token,
            timeout=180,
            payload={
                "job_id": job_id,
                "module": "formConverter",
                "template_type": template_type,
                "page_count": page_count,
                "credit_reservation_id": reservation_id,
                "document_sha256": hashlib.sha256(document_bytes).hexdigest(),
                "document_base64": base64.b64encode(document_bytes).decode("ascii"),
            },
        )
        provider = ocr.get("provider")
        if isinstance(provider, str):
            summary["provider"] = provider
        confidence_values: list[float] = []
        for record in ocr.get("records", []):
            if not isinstance(record, dict):
                continue
            fields = record.get("fields", [])
            if not isinstance(fields, list):
                continue
            for field in fields:
                if not isinstance(field, dict):
                    continue
                confidence = float(field.get("confidence", 0))
                confidence_values.append(confidence)
                status = str(field.get("status", ""))
                if status == "ready":
                    summary["ready_fields"] += 1
                elif status == "invalid":
                    summary["invalid_fields"] += 1
                else:
                    summary["needs_review_fields"] += 1
                field_rows.append(
                    {
                        "file_name": pdf_path.name,
                        "job_id": job_id,
                        "provider": summary["provider"],
                        "record_id": record.get("record_id", ""),
                        "page_number": record.get("page_number", ""),
                        "record_status": record.get("status", ""),
                        "field_name": field.get("field_name", ""),
                        "label_th": field.get("label_th", ""),
                        "value": field.get("value", ""),
                        "confidence": f"{confidence:.4f}",
                        "field_status": status,
                        "alternatives": " | ".join(str(item) for item in field.get("alternatives", [])),
                    }
                )
        summary["status"] = "ok"
        summary["records"] = len(ocr.get("records", [])) if isinstance(ocr.get("records"), list) else 0
        summary["avg_confidence"] = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else 0.0
    except Exception as exc:
        summary["error"] = str(exc)
    finally:
        if reservation_id is not None:
            try:
                json_request(
                    base_url,
                    f"/v1/credits/reservations/{reservation_id}/release",
                    method="POST",
                    token=token,
                    payload={"units": page_count, "idempotency_key": f"{job_id}:release-after-field-test"},
                )
            except FieldTestError as exc:
                summary["release_error"] = str(exc)
    return summary, field_rows


def write_outputs(output_dir: Path, summaries: list[dict[str, Any]], field_rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "quality-summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_name",
                "job_id",
                "page_count",
                "status",
                "provider",
                "records",
                "ready_fields",
                "needs_review_fields",
                "invalid_fields",
                "avg_confidence",
                "error",
                "release_error",
            ],
        )
        writer.writeheader()
        writer.writerows(summaries)
    with (output_dir / "field-results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_name",
                "job_id",
                "provider",
                "record_id",
                "page_number",
                "record_status",
                "field_name",
                "label_th",
                "value",
                "confidence",
                "field_status",
                "alternatives",
            ],
        )
        writer.writeheader()
        writer.writerows(field_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local field test for formConverter OCR against cloud staging.")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing scanned PDF files.")
    parser.add_argument("--cloud-base-url", default=os.getenv("DMC_CLOUD_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--email", default=os.getenv("DMC_FIELD_TEST_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("DMC_FIELD_TEST_PASSWORD", ""))
    parser.add_argument("--template-type", default="student_history_v1")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default=str(Path(".dmc-field-tests") / "form-converter" / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.email or not args.password:
        raise SystemExit("--email/--password or DMC_FIELD_TEST_EMAIL/DMC_FIELD_TEST_PASSWORD are required.")
    pdfs = discover_pdfs(Path(args.pdf_dir), max_files=args.max_files)
    token = login(str(args.cloud_base_url), email=str(args.email), password=str(args.password))
    summaries: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    for pdf_path in pdfs:
        summary, rows = run_pdf(str(args.cloud_base_url), token, pdf_path, template_type=str(args.template_type))
        summaries.append(summary)
        field_rows.extend(rows)
        print(
            json.dumps(
                {
                    "file_name": summary["file_name"],
                    "status": summary["status"],
                    "provider": summary["provider"],
                    "page_count": summary["page_count"],
                    "records": summary["records"],
                    "avg_confidence": summary["avg_confidence"],
                    "error": summary.get("error"),
                },
                ensure_ascii=False,
            )
        )
    output_dir = Path(args.output_dir)
    write_outputs(output_dir, summaries, field_rows)
    failed = sum(1 for item in summaries if item["status"] != "ok")
    print(json.dumps({"output_dir": str(output_dir), "files": len(summaries), "failed": failed}, ensure_ascii=False))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
