from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dmc_sidecar.backup import create_backup_archive  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a backup archive of sidecar state.")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    path = create_backup_archive(output)
    print(path)


if __name__ == "__main__":
    main()
