from __future__ import annotations

import argparse
import json
from pathlib import Path


def find_updater_archive(bundle_dir: Path) -> Path:
    candidates = sorted(
        path
        for path in bundle_dir.rglob("*.zip")
        if not path.name.endswith(".sig")
    )
    if not candidates:
        raise SystemExit("No updater archive (.zip) was found under the bundle directory.")

    preferred = [path for path in candidates if ".msi." in path.name.lower() or path.name.lower().endswith(".msi.zip")]
    selected = preferred[0] if preferred else candidates[0]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate updater manifest from Tauri bundle output.")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--pub-date", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir)
    archive_path = find_updater_archive(bundle_dir)
    signature_path = archive_path.with_suffix(archive_path.suffix + ".sig")
    if not signature_path.exists():
        raise SystemExit(f"Signature file was not found for updater archive: {signature_path}")

    manifest = {
        "version": args.version,
        "pub_date": args.pub_date,
        "url": f"{args.base_url.rstrip('/')}/{archive_path.name}",
        "signature": signature_path.read_text(encoding="utf-8").strip(),
        "notes": args.notes,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
