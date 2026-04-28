from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from write_release_config import build_config


REPO_ROOT = Path(__file__).resolve().parents[1]
TAURI_CONFIG_PATH = REPO_ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
PACKAGE_JSON_PATH = REPO_ROOT / "package.json"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def check_tauri_config() -> None:
    config = load_json(TAURI_CONFIG_PATH)
    bundle = config.get("bundle")
    plugins = config.get("plugins")
    require(isinstance(bundle, dict), "Tauri bundle config is missing.")
    resources = bundle.get("resources")
    require(isinstance(resources, list), "Tauri bundle resources must be a list.")
    require("bundled-sidecar" in resources, "Tauri bundle must include bundled-sidecar resources.")
    require("release-config" in resources, "Tauri bundle must include release-config resources.")
    require(isinstance(plugins, dict), "Tauri plugins config is missing.")
    require(isinstance(plugins.get("updater"), dict), "Tauri updater config must be an object.")


def check_package_scripts() -> None:
    package_json = load_json(PACKAGE_JSON_PATH)
    scripts = package_json.get("scripts")
    require(isinstance(scripts, dict), "package.json scripts are missing.")
    for script_name in ("ci:verify", "sidecar:bundle", "desktop:package", "release:manifest"):
        require(script_name in scripts, f"package.json is missing {script_name}.")


def check_gitignore() -> None:
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    require(
        "apps/desktop/src-tauri/bundled-sidecar/*" in content,
        "bundled sidecar artifacts must stay ignored.",
    )
    require(
        "!apps/desktop/src-tauri/bundled-sidecar/.gitkeep" in content,
        "bundled-sidecar .gitkeep must remain trackable.",
    )
    require(
        "apps/desktop/src-tauri/release-config/*.json" in content,
        "generated release config JSON must stay ignored.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate release build prerequisites that do not require signing.")
    parser.add_argument(
        "--environment",
        choices=["development", "staging", "production"],
        default=os.getenv("DMC_RELEASE_ENVIRONMENT", "development"),
    )
    parser.add_argument("--cloud-base-url", default="")
    parser.add_argument("--updater-endpoint", default="")
    parser.add_argument("--updater-public-key", default="")
    args = parser.parse_args()

    release_config = build_config(args)
    check_tauri_config()
    check_package_scripts()
    check_gitignore()
    cloud_configured = bool(release_config["cloud_base_url"])
    updater_configured = bool(
        release_config["updater_endpoint"] and release_config["updater_public_key"]
    )
    if release_config["environment"] == "production":
        require(cloud_configured, "Production release requires --cloud-base-url.")
        require(updater_configured, "Production release requires updater endpoint and public key.")

    print(
        json.dumps(
            {
                "status": "ok",
                "environment": release_config["environment"],
                "cloud_configured": cloud_configured,
                "updater_configured": updater_configured,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
