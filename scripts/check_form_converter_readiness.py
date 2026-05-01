from __future__ import annotations

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_DOC = REPO_ROOT / "docs" / "form-converter-ocr-policy.md"
READINESS_DOC = REPO_ROOT / "docs" / "form-converter-production-readiness.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    provider = os.getenv("DMC_OCR_PROVIDER", "mock").strip().lower() or "mock"
    max_pdf_bytes = int(os.getenv("DMC_OCR_MAX_PDF_BYTES", str(20 * 1024 * 1024)))
    max_pages = int(os.getenv("DMC_OCR_MAX_PAGES_PER_JOB", "100"))

    require(provider in {"mock", "openai", "gemini"}, "DMC_OCR_PROVIDER must be mock, openai, or gemini.")
    require(max_pdf_bytes > 0, "DMC_OCR_MAX_PDF_BYTES must be positive.")
    require(max_pages > 0, "DMC_OCR_MAX_PAGES_PER_JOB must be positive.")
    require(POLICY_DOC.exists(), "Form converter OCR policy doc is missing.")
    require(READINESS_DOC.exists(), "Form converter readiness doc is missing.")

    openai_configured = bool(os.getenv("DMC_OCR_OPENAI_API_KEY", "").strip())
    if provider == "openai":
        require(openai_configured, "OpenAI OCR provider requires DMC_OCR_OPENAI_API_KEY.")
    gemini_configured = bool(os.getenv("DMC_OCR_GEMINI_API_KEY", "").strip())
    if provider == "gemini":
        require(gemini_configured, "Gemini OCR provider requires DMC_OCR_GEMINI_API_KEY.")

    print(
        json.dumps(
            {
                "status": "ok",
                "provider": provider,
                "openai_configured": openai_configured,
                "gemini_configured": gemini_configured,
                "max_pdf_bytes": max_pdf_bytes,
                "max_pages_per_job": max_pages,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
