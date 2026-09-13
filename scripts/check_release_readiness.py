from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TAURI_CONFIG_PATH = REPO_ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
TAURI_PACKAGE_CONFIG_PATH = TAURI_CONFIG_PATH.with_name("tauri.package.conf.json")
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
    require(isinstance(bundle, dict), "Tauri bundle config is missing.")
    package = load_json(TAURI_PACKAGE_CONFIG_PATH)
    package_bundle = package.get("bundle")
    require(isinstance(package_bundle, dict), "Tauri package bundle config is missing.")
    effective_bundle = {**bundle, **package_bundle}
    require(effective_bundle.get("active") is True, "Tauri package bundle must be active.")
    targets = effective_bundle.get("targets")
    require(
        targets == "msi" or isinstance(targets, list) and "msi" in targets,
        "Tauri package must include an msi target.",
    )
    resources = effective_bundle.get("resources")
    require(isinstance(resources, list), "Tauri bundle resources must be a list.")
    for resource in ("bundled-sidecar", "templates"):
        require(resource in resources, f"Tauri bundle must include {resource} resources.")


def check_package_scripts() -> None:
    package_json = load_json(PACKAGE_JSON_PATH)
    scripts = package_json.get("scripts")
    require(isinstance(scripts, dict), "package.json scripts are missing.")
    for script_name in ("ci:verify", "sidecar:bundle", "desktop:package"):
        require(
            isinstance(scripts.get(script_name), str) and bool(scripts[script_name].strip()),
            f"package.json is missing {script_name}.",
        )
    require(
        scripts["desktop:package"] == (
            "corepack pnpm run sidecar:bundle && "
            "corepack pnpm --dir apps/desktop exec tauri build --config src-tauri/tauri.package.conf.json"
        ),
        "desktop:package must bundle the sidecar and build with tauri.package.conf.json.",
    )


def check_gitignore() -> None:
    lines = GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
    require(
        "apps/desktop/src-tauri/bundled-sidecar/*" in lines,
        "bundled sidecar artifacts must stay ignored.",
    )
    require(
        "!apps/desktop/src-tauri/bundled-sidecar/.gitkeep" in lines,
        "bundled-sidecar .gitkeep must remain trackable.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate manual Windows package prerequisites that do not require signing."
    )
    parser.parse_args()
    check_tauri_config()
    check_package_scripts()
    check_gitignore()
    print(json.dumps({"status": "ok"}, sort_keys=True))


if __name__ == "__main__":
    main()
