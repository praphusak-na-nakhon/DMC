from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str = "dmc-cloud"
    version: str = "0.1.0"
    api_bearer_token: str = os.getenv("DMC_CLOUD_API_BEARER_TOKEN", "").strip()
    config_signing_key_id: str = os.getenv("DMC_CLOUD_CONFIG_SIGNING_KEY_ID", "dev-2026-01")
    config_signing_private_key_hex: str = os.getenv(
        "DMC_CLOUD_CONFIG_SIGNING_PRIVATE_KEY_HEX",
        "",
    ).strip()
    updater_latest_version: str = os.getenv("DMC_CLOUD_UPDATER_LATEST_VERSION", "0.1.0")
    updater_pub_date: str = os.getenv("DMC_CLOUD_UPDATER_PUB_DATE", "2026-04-22T00:00:00Z")
    updater_notes: str = os.getenv("DMC_CLOUD_UPDATER_NOTES", "No update available.")
    updater_windows_x86_64_url: str = os.getenv("DMC_CLOUD_UPDATER_WINDOWS_X86_64_URL", "")
    updater_windows_x86_64_signature: str = os.getenv(
        "DMC_CLOUD_UPDATER_WINDOWS_X86_64_SIGNATURE",
        "",
    )
    sqlite_path: str = os.getenv(
        "DMC_CLOUD_SQLITE_PATH",
        str(Path(__file__).resolve().parents[3] / ".dmc-assistant-data" / "cloud" / "state.sqlite3"),
    )
    session_duration_hours: int = int(os.getenv("DMC_CLOUD_SESSION_DURATION_HOURS", "168"))
    ocr_provider: str = os.getenv("DMC_OCR_PROVIDER", "mock").strip().lower() or "mock"
    ocr_openai_api_key: str = os.getenv("DMC_OCR_OPENAI_API_KEY", "").strip()
    ocr_openai_model: str = os.getenv("DMC_OCR_OPENAI_MODEL", "gpt-5.5").strip()
    ocr_openai_base_url: str = os.getenv("DMC_OCR_OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    ocr_gemini_api_key: str = os.getenv("DMC_OCR_GEMINI_API_KEY", "").strip()
    ocr_gemini_model: str = os.getenv("DMC_OCR_GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
    ocr_gemini_base_url: str = os.getenv(
        "DMC_OCR_GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com",
    ).strip().rstrip("/")
    ocr_max_pdf_bytes: int = int(os.getenv("DMC_OCR_MAX_PDF_BYTES", str(20 * 1024 * 1024)))
    ocr_max_pages_per_job: int = int(os.getenv("DMC_OCR_MAX_PAGES_PER_JOB", "100"))
    form_converter_ocr_credits_per_page: int = int(os.getenv("DMC_FORM_CONVERTER_OCR_CREDITS_PER_PAGE", "3"))
    trusted_proxy_hosts: str = os.getenv("DMC_CLOUD_TRUSTED_PROXY_HOSTS", "").strip()
    rate_limit_sqlite_path: str = os.getenv("DMC_CLOUD_RATE_LIMIT_SQLITE_PATH", "").strip()


settings = Settings()
