"""Make ``zorbeck_app`` importable whether pytest runs from zorbeck/ or the repo
root (the root suite collects this directory too). Appended, not prepended, so
the repo-root ``app`` package is never shadowed by zorbeck/app.py."""

import sys
from pathlib import Path

ZORBECK_DIR = Path(__file__).resolve().parent.parent
if str(ZORBECK_DIR) not in sys.path:
    sys.path.append(str(ZORBECK_DIR))
