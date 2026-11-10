#!/usr/bin/env python3
"""Build the fictional demo for static hosting. Never accepts a personal archive."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from archive import ROOT, asset_bytes, load_source, organization, project_for, report, safe_name
from examples.make_demo import make_demo
from server import search_text

DEMO_CSP = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"


def build_demo_site(output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be a new or empty directory")
    # There is deliberately no input/data option. The only source is make_demo.
    with tempfile.TemporaryDirectory(prefix="claude-fictional-demo-") as temporary:
        source = Path(temporary)
        make_demo(source)
        data, files = load_source(source)
        org = organization(source, data)
        index = {"conversations": [{k: v for k, v in c.items() if k != "chat_messages"} |
                                   {"count": len(c["chat_messages"]), "search": search_text(c)} for c in data["conversations"]],
                 "projects": data["projects"], "frames": data["frames"], "organization": org,
                 "project_matches": {c["uuid"]: {"project": project_for(c, org, data)} for c in data["conversations"]},
                 "report": report(data, org)}
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "web", output, dirs_exist_ok=True)
        html = (output / "index.html").read_text(encoding="utf-8")
        html = html.replace('href="/', 'href="./').replace('src="/', 'src="./')
        html = html.replace('<script src="./data.js">', '<script src="./demo-data.js"></script><script src="./data.js">')
        html = html.replace('<title>Claude · Архив</title>', '<title>Claude Archive · Интерактивное демо</title>')
        (output / "index.html").write_text(html, encoding="utf-8")
        payload = json.dumps({"fictional": True, "index": index, "conversations": data["conversations"]}, ensure_ascii=False).replace("<", "\\u003c")
        (output / "demo-data.js").write_text("window.CLAUDE_ARCHIVE_DEMO=" + payload + ";\n", encoding="utf-8")
        for name, entry in files.items():
            target = output / "assets" / safe_name(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = asset_bytes(entry)
            if name.endswith(".html"):
                text = content.decode("utf-8")
                text = text.replace("<head>", '<head><meta http-equiv="Content-Security-Policy" content="' + DEMO_CSP + '">', 1)
                content = text.encode("utf-8")
            target.write_bytes(content)
        (output / ".nojekyll").touch()
        shutil.copy2(ROOT / "LICENSE", output / "LICENSE.txt")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(build_demo_site(args.output))
    except (OSError, ValueError) as e:
        parser.exit(1, "Error: " + str(e) + "\n")
