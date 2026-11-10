#!/usr/bin/env python3
"""Install one self-contained skill with the runtime it needs."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def install(name, destination):
    source = ROOT / ".agents" / "skills" / name
    target = Path(destination).expanduser().resolve() / name
    if target.exists():
        raise ValueError("Skill already exists; choose another destination or remove it explicitly: " + str(target))
    shutil.copytree(source, target)
    runtime = target / "scripts" / "runtime"
    runtime.mkdir()
    names = ["archive.py", "migrate.py", "LICENSE"] if name == "claude-to-codex" else ["archive.py", "server.py", "start.command", "start.bat", "LICENSE"]
    for filename in names:
        shutil.copy2(ROOT / filename, runtime / filename)
    if name == "claude-archive":
        shutil.copytree(ROOT / "web", runtime / "web")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=("claude-archive", "claude-to-codex"))
    parser.add_argument("--destination", type=Path, required=True, help="Your agent's skills directory")
    args = parser.parse_args()
    try:
        print(install(args.name, args.destination))
    except (ValueError, OSError) as e:
        parser.exit(1, "Error: " + str(e) + "\n")
