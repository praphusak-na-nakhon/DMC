from __future__ import annotations

import sys

from .rpc import run_stdio_server


if __name__ == "__main__":
    sys.exit(run_stdio_server())
