"""Make the underscore-named scripts in scripts/ importable as top-level modules.

Mirrors how selfcheck.py wires the path: the scripts import each other by bare
name (e.g. `from scan_agent import scan`), so tests need scripts/ on sys.path.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
