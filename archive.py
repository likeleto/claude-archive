#!/usr/bin/env python3
"""Inspect Claude exports and build a portable local archive. Python 3.9+."""
import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
SCHEMA = 1
EVIDENCE_SOURCES = {"export", "screenshot", "copied_sidebar", "user_note", "user_confirmation", "content_inference", "manual"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe_name(name):
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or "\\" in name or any(p in ("..", ".") or ":" in p for p in parts):
        raise ValueError("Unsafe archive entry: " + name)
    return name


def validate_data(data):
    # IDs become HTML attributes and URL components in the existing viewer.
    for collection, key in (("conversations", "uuid"), ("projects", "uuid"), ("frames", "id")):
        seen = set()
        for item in data[collection]:
            value = item[key]
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value) or value in seen:
                raise ValueError("Invalid or duplicate " + collection + " identifier")
            seen.add(value)
    for frame in data["frames"]:
        for version in frame.get("versions", []):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", version["id"]):
                raise ValueError("Invalid artifact version identifier")
    return data


def load_source(folder):
    folder = Path(folder).resolve()
    if (folder / "archive-data.json").exists():
        data = read_json(folder / "archive-data.json")
        if data.get("schema_version") != SCHEMA:
            raise ValueError("Unsupported archive schema")
        files = {}
        for name in data["assets"]:
            safe_name(name)
            target = (folder / "assets" / name).resolve()
            if not target.is_relative_to((folder / "assets").resolve()):
                raise ValueError("Asset escapes archive directory")
            if not target.is_file():
                raise ValueError("Prepared archive is missing asset: " + name)
            files[name] = (target, None)
        return validate_data(data), files
    chats, frames, projects, files, sources, warnings = {}, {}, {}, {}, [], []
    archives = sorted(folder.glob("*.zip"))
    if not archives and not (folder / "conversations.json").exists():
        raise ValueError("No export found. Put Claude ZIP files or conversations.json in --data.")
    def records(name, value):
        if name == "conversations.json":
            for chat in value:
                chats[chat["uuid"]] = chat
        elif name.startswith("artifacts/") and name.endswith("/artifact.json"):
            frames[value["id"]] = value
        elif name.startswith("projects/") and name.endswith(".json") and isinstance(value, dict) and "uuid" in value:
            projects[value["uuid"]] = value
    for archive in archives:
        sources.append({"name": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.endswith("/"):
                    continue
                safe_name(name)
                if name == "conversations.json" or name.startswith(("artifacts/", "projects/")):
                    if name.endswith(".json"):
                        records(name, json.loads(z.read(name)))
                    if name != "conversations.json":
                        files[name] = (archive, name)
    # A loose conversations.json is a fallback, never a silent override of ZIPs.
    loose = folder / "conversations.json"
    if not chats and loose.exists():
        records("conversations.json", read_json(loose))
        sources.append({"name": loose.name, "sha256": hashlib.sha256(loose.read_bytes()).hexdigest()})
    if not chats:
        warnings.append("No conversations found in the export.")
    for frame in frames.values():
        prefix = "artifacts/" + frame["id"] + "/"
        frame["files"] = [n[len(prefix):] for n in files if n.startswith(prefix)]
        frame["conversations"], frame["link_reasons"] = [], {}
        for chat in chats.values():
            raw = json.dumps(chat, ensure_ascii=False)
            reason = "artifact ID in exported conversation" if frame["id"] in raw else ""
            if not reason:
                inputs = [b.get("input", {}) for m in chat.get("chat_messages", []) for b in m.get("content", [])
                          if b.get("type") == "tool_use" and "artifact" in b.get("name", "").lower() and isinstance(b.get("input"), dict)]
                if any((v.get("title") and v["title"] == b.get("title")) or
                       (len(v.get("description", "")) >= 30 and v["description"] == b.get("description"))
                       for v in frame.get("versions", []) for b in inputs):
                    reason = "suggested: matching artifact title or description"
            if reason:
                frame["conversations"].append(chat["uuid"])
                frame["link_reasons"][chat["uuid"]] = reason
    data = {"schema_version": SCHEMA, "conversations": list(chats.values()), "projects": list(projects.values()),
            "frames": list(frames.values()), "assets": sorted(files), "sources": sources, "warnings": warnings}
    return validate_data(data), files


def organization(folder, data):
    path = Path(folder) / "organization.json"
    value = read_json(path) if path.exists() else {"projects": {}, "frames": {}}
    return validate_organization(value, data)


def validate_organization(value, data):
    chats = {c["uuid"] for c in data["conversations"]}
    projects = {p["uuid"] for p in data["projects"]}
    frames = {f["id"] for f in data["frames"]}
    if not isinstance(value, dict) or not isinstance(value.get("projects", {}), dict) or not isinstance(value.get("frames", {}), dict):
        raise ValueError("Organization must contain projects and frames objects")
    for key, project in value.get("projects", {}).items():
        if key not in {"chats/" + c for c in chats} or project not in projects | {""}:
            raise ValueError("Unknown conversation or project in organization")
    for fid, ids in value.get("frames", {}).items():
        if fid not in frames or not isinstance(ids, list) or any(cid not in chats for cid in ids):
            raise ValueError("Unknown artifact or conversation in organization")
    result = {"projects": value.get("projects", {}), "frames": value.get("frames", {})}
    if "project_evidence" in value:
        evidence = value["project_evidence"]
        if not isinstance(evidence, dict):
            raise ValueError("project_evidence must be an object")
        for key, item in evidence.items():
            if key not in {"chats/" + c for c in chats} or not isinstance(item, dict):
                raise ValueError("Unknown conversation in project evidence")
            if not isinstance(item.get("project"), str) or item["project"] not in projects | {""}:
                raise ValueError("Unknown project in project evidence")
            if not isinstance(item.get("source"), str) or item["source"] not in EVIDENCE_SOURCES or not isinstance(item.get("status"), str) or item["status"] not in {"confirmed", "proposed"}:
                raise ValueError("Invalid project evidence source or status")
            for field in ("reference", "reason"):
                if not isinstance(item.get(field), str) or not item[field].strip() or len(item[field]) > 4000:
                    raise ValueError("Project evidence requires a reference and reason (1–4000 characters)")
            active = result["projects"].get(key)
            if item["status"] == "confirmed" and active != item["project"]:
                raise ValueError("Confirmed evidence must match an explicit project assignment")
            if item["status"] == "proposed" and active == item["project"]:
                raise ValueError("A proposed project assignment cannot also be active")
        result["project_evidence"] = copy.deepcopy(evidence)
    return result


def project_for(chat, org, data):
    key = "chats/" + chat["uuid"]
    if key in org["projects"]:
        return org["projects"][key]
    known = {p["uuid"] for p in data["projects"]}
    return next((chat.get(k) for k in ("project_uuid", "project_id") if chat.get(k) in known), "")


def frame_chats(frame, org):
    return org["frames"].get(frame["id"], frame.get("conversations", []))


def selected_data(data, org, project_ids):
    if not project_ids:
        return copy.deepcopy(data), copy.deepcopy(org)
    unknown = set(project_ids) - {p["uuid"] for p in data["projects"]}
    if unknown:
        raise ValueError("Unknown project IDs: " + ", ".join(sorted(unknown)))
    result = copy.deepcopy(data)
    result["projects"] = [p for p in data["projects"] if p["uuid"] in project_ids]
    result["conversations"] = [c for c in data["conversations"] if project_for(c, org, data) in project_ids]
    chats = {c["uuid"] for c in result["conversations"]}
    result["frames"] = [copy.deepcopy(f) for f in data["frames"] if chats.intersection(frame_chats(f, org))]
    for frame in result["frames"]:
        frame["conversations"] = [c for c in frame["conversations"] if c in chats]
        frame["link_reasons"] = {c: r for c, r in frame.get("link_reasons", {}).items() if c in chats}
    frame_ids = {f["id"] for f in result["frames"]}
    result["assets"] = [n for n in data["assets"] if
                        (n.startswith("artifacts/") and n.split("/")[1] in frame_ids) or
                        (n.startswith("projects/") and (n.split("/")[1] in project_ids or n.split("/")[1].removesuffix(".json") in project_ids))]
    kept = {"projects": {k: v for k, v in org["projects"].items() if k[6:] in chats},
            "frames": {k: [c for c in v if c in chats] for k, v in org["frames"].items() if k in frame_ids}}
    if "project_evidence" in org:
        kept["project_evidence"] = {k: copy.deepcopy(v) for k, v in org["project_evidence"].items()
                                    if k[6:] in chats and v["project"] in set(project_ids) | {""}}
    return result, kept


def report(data, org):
    unassigned = [c["uuid"] for c in data["conversations"] if not project_for(c, org, data)]
    missing_versions = []
    for f in data["frames"]:
        for v in f.get("versions", []):
            path = "page.md" if f.get("kind") == "page" else "versions/" + v["id"] + ".html"
            if path not in f.get("files", []) or (f.get("kind") == "page" and v["id"] != f.get("active_version")):
                missing_versions.append({"artifact": f["id"], "version": v["id"]})
    attachments = sum(len(m.get("attachments", [])) for c in data["conversations"] for m in c.get("chat_messages", []))
    return {"schema_version": SCHEMA, "counts": {"conversations": len(data["conversations"]), "projects": len(data["projects"]),
            "artifacts": len(data["frames"]), "messages": sum(len(c.get("chat_messages", [])) for c in data["conversations"]),
            "attachment_records": attachments, "asset_files": len(data["assets"])},
            "projects": [{"id": p["uuid"], "name": p.get("name", ""), "conversations": sum(project_for(c, org, data) == p["uuid"] for c in data["conversations"])} for p in data["projects"]],
            "unassigned_conversations": unassigned, "missing_artifact_versions": missing_versions,
            "project_evidence": org.get("project_evidence", {}),
            "suggested_artifact_links": [{"artifact": f["id"], "conversation": c, "reason": r} for f in data["frames"] for c, r in f.get("link_reasons", {}).items() if r.startswith("suggested:") and f["id"] not in org["frames"]],
            "warnings": data.get("warnings", []) + (["Attachment metadata/text is preserved; original attachment binaries are not reconstructed."] if attachments else [])}


def asset_bytes(entry):
    path, name = entry
    if name is None:
        return path.read_bytes()
    with zipfile.ZipFile(path) as z:
        return z.read(name)


def build(folder, output, project_ids=None, org_path=None):
    data, files = load_source(folder)
    org = validate_organization(read_json(org_path), data) if org_path else organization(folder, data)
    data, org = selected_data(data, org, project_ids)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be a new or empty directory")
    output.mkdir(parents=True, exist_ok=True)
    for name in data["assets"]:
        target = output / "assets" / safe_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(asset_bytes(files[name]))
    write_json(output / "archive-data.json", data)
    write_json(output / "organization.json", org)
    summary = report(data, org)
    write_json(output / "report.json", summary)
    # The result is portable and starts without the source repository or ZIPs.
    for name in ("archive.py", "server.py", "start.command", "start.bat", "LICENSE"):
        shutil.copy2(ROOT / name, output / name)
    shutil.copytree(ROOT / "web", output / "web", dirs_exist_ok=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "build"):
        p = sub.add_parser(command)
        p.add_argument("--data", type=Path, required=True)
        p.add_argument("--organization", type=Path)
        if command == "build":
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--project", action="append", help="Project ID; repeat to select multiple. Omit to archive everything.")
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build(args.data, args.output, args.project, args.organization)
        else:
            data, _ = load_source(args.data)
            org = validate_organization(read_json(args.organization), data) if args.organization else organization(args.data, data)
            result = report(data, org)
        # ASCII escapes keep CLI JSON portable across Windows pipe encodings.
        # File storage remains UTF-8; JSON readers recover the original text.
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as e:
        parser.exit(1, "Error: " + str(e) + "\n")


if __name__ == "__main__":
    main()
