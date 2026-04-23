from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "release" / "environments"
OUTPUT_PATH = REPO_ROOT / "apps" / "desktop" / "src-tauri" / "release-config" / "app-config.json"


def load_template(environment: str) -> dict[str, str]:
    template_path = TEMPLATES_DIR / f"{environment}.json"
    if not template_path.exists():
        raise SystemExit(f"Unknown release environment: {environment}")
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Release environment template must be a JSON object.")
    return {str(key): str(value) for key, value in payload.items()}


def normalize_url(value: str) -> str:
    return value.strip().rstrip("/")


def validate_url(name: str, value: str, *, allow_local_http: bool) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise SystemExit(f"{name} must be an absolute URL.")
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme == "https":
        return normalized
    if allow_local_http and parsed.scheme == "http" and hostname in {"localhost", "127.0.0.1"}:
        return normalized
    raise SystemExit(f"{name} must use HTTPS outside local development.")


def build_config(args: argparse.Namespace) -> dict[str, str]:
    config = load_template(args.environment)
    config["environment"] = args.environment

    cloud_base_url = args.cloud_base_url or os.getenv("DMC_CLOUD_BASE_URL", "")
    updater_endpoint = args.updater_endpoint or os.getenv("DMC_UPDATER_ENDPOINT", "")
    updater_public_key = args.updater_public_key or os.getenv("DMC_UPDATER_PUBLIC_KEY", "")

    allow_local_http = args.environment == "development"
    config["cloud_base_url"] = validate_url(
        "cloud_base_url",
        cloud_base_url or config.get("cloud_base_url", ""),
        allow_local_http=allow_local_http,
    )
    config["updater_endpoint"] = validate_url(
        "updater_endpoint",
        updater_endpoint or config.get("updater_endpoint", ""),
        allow_local_http=allow_local_http,
    )
    config["updater_public_key"] = (updater_public_key or config.get("updater_public_key", "")).strip()

    if args.environment != "development":
        if not config["cloud_base_url"]:
            raise SystemExit("cloud_base_url is required for staging/production builds.")
        if not config["updater_endpoint"]:
            raise SystemExit("updater_endpoint is required for staging/production builds.")
        if not config["updater_public_key"]:
            raise SystemExit("updater_public_key is required for staging/production builds.")
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Write packaged desktop release config.")
    parser.add_argument(
        "--environment",
        choices=["development", "staging", "production"],
        required=True,
    )
    parser.add_argument("--cloud-base-url", default="")
    parser.add_argument("--updater-endpoint", default="")
    parser.add_argument("--updater-public-key", default="")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    payload = build_config(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
