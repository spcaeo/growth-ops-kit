#!/usr/bin/env python3
"""growth unlock <lock> --agent <name> [--force]: give a lock back (see lock.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lock  # noqa: E402

if __name__ == "__main__":
    sys.exit(lock.main(mode="unlock"))
