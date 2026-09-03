from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dmc_sidecar.ai.base import OcrDocumentRequest, SecretStore
from dmc_sidecar.ai.gemini import GeminiProvider
from dmc_sidecar.errors import DomainError


class FieldTestError(Exception):
    pass


class EphemeralSecretStore:
    """Keeps a CLI or environment key in process memory for one field test."""

    def __init__(self, provider: str, secret: str) -> None:
        self._secrets = {provider: secret}

    def get(self, provider: str) -> str | None:
        return self._secrets.get(provider)

    def set(self, provider: str, secret: str) -> None:
        self._secrets[provider] = secret

    def delete(self, provider: str) -> bool:
        return self._secrets.pop(provider, None) is not None


def build_gemini_provider(api_key: str) -> GeminiProvider:
    """Build an in-memory provider without reading or writing the OS keyring."""
    store: SecretStore = EphemeralSecretStore("gemini", api_key)
    return GeminiProvider(store)


def discover_pdfs(pdf_dir: Path, *, max_files: int | None) -> list[Path]:
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        raise FieldTestError(f"PDF directory not found: {pdf_dir}")
    pdfs = sorted(path for path in pdf_dir.glob("*.pdf") if path.is_file())
    if max_files is not None:
        pdfs = pdfs[:max_files]
    if not pdfs:
        raise FieldTestError(f"No PDF files found in {pdf_dir}")
    return pdfs


def _field_rows(response: Any, file_name: str) -> list[dict[str, object]]:
    output_path = Path(response.structured_json_path or response.markdown_path)
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FieldTestError("OCR output could not be read from the local cache.") from exc
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return []

    rows: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        fields = record.get("fields")
        if not isinstance(fields, dict):
            continue
        needs_review = record.get("needs_review")
        review_text = " | ".join(str(item) for item in needs_review) if isinstance(needs_review, list) else ""
        for field_name, value in fields.items():
            rows.append(
                {
                    "file_name": file_name,
                    "record_type": record.get("record_type", ""),
                    "page_start": record.get("page_start", ""),
                    "page_end": record.get("page_end", ""),
                    "field_name": field_name,
                    "value": value if value is not None else "",
                    "needs_review": review_text,
                }
            )
    return rows


def run_pdf(provider: GeminiProvider, pdf_path: Path, *, model: str, processing_mode: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        response = provider.ocr_document(
            OcrDocumentRequest(
                provider="gemini",
                source_path=str(pdf_path),
                model=model,
                processing_mode=processing_mode,
            )
        )
    except DomainError as exc:
        raise FieldTestError(f"Gemini OCR failed: {exc.code}") from None
    except Exception:
        raise FieldTestError("Gemini OCR failed unexpectedly. Review local diagnostics without sharing the API key.") from None

    usage_totals = response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata is not None else {}
    summary: dict[str, object] = {
        "file_name": pdf_path.name,
        "output_path": response.structured_json_path or response.markdown_path,
        "page_count": response.pages_processed,
        "model": response.model,
        "processing_mode": response.processing_mode,
        "usage_totals": usage_totals,
    }
    return summary, _field_rows(response, pdf_path.name)


def write_outputs(output_dir: Path, summaries: list[dict[str, object]], field_rows: list[dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "quality-summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file_name", "output_path", "page_count", "model", "processing_mode", "usage_totals"],
        )
        writer.writeheader()
        for summary in summaries:
            row = dict(summary)
            row["usage_totals"] = json.dumps(row["usage_totals"], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)
    with (output_dir / "field-results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file_name", "record_type", "page_start", "page_end", "field_name", "value", "needs_review"],
        )
        writer.writeheader()
        writer.writerows(field_rows)


def console_summary(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: summary[key]
        for key in ("output_path", "page_count", "model", "processing_mode", "usage_totals")
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an opt-in local Gemini OCR field test against scanned PDFs.")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing scanned PDF files.")
    parser.add_argument("--gemini-api-key", default=os.getenv("GEMINI_API_KEY", ""), help="Gemini API key for this process only.")
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--processing-mode", choices=("standard", "batch"), default="batch")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default=str(Path(".dmc-field-tests") / "form-converter" / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = str(args.gemini_api_key).strip()
    if not api_key:
        raise SystemExit("--gemini-api-key or GEMINI_API_KEY is required.")
    provider = build_gemini_provider(api_key)
    summaries: list[dict[str, object]] = []
    field_rows: list[dict[str, object]] = []
    for pdf_path in discover_pdfs(Path(args.pdf_dir), max_files=args.max_files):
        summary, rows = run_pdf(provider, pdf_path, model=str(args.model), processing_mode=str(args.processing_mode))
        summaries.append(summary)
        field_rows.extend(rows)
        print(json.dumps(console_summary(summary), ensure_ascii=False))
    write_outputs(Path(args.output_dir), summaries, field_rows)


if __name__ == "__main__":
    main()
