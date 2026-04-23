from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backup import restore_backup_archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore cloud SQLite state from a backup archive.")
    parser.add_argument("--archive", required=True)
    args = parser.parse_args()

    result = restore_backup_archive(Path(args.archive))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
