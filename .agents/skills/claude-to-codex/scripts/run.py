#!/usr/bin/env python3
"""Run from the source checkout or the self-contained installed skill."""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
runtime = HERE.parent / "runtime"
if not runtime.is_dir():
    runtime = HERE.parents[4]
entry = runtime / "migrate.py"
if not entry.is_file():
    raise SystemExit("Runtime missing. Open the complete project folder, or install the skill with install_skill.py.")
sys.path.insert(0, str(runtime))
runpy.run_path(str(entry), run_name="__main__")
