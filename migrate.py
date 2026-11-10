#!/usr/bin/env python3
"""Plan, trial, or apply a selected Claude archive import into Codex."""
import argparse
import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from archive import asset_bytes, frame_chats, load_source, organization, project_for, read_json, safe_name, selected_data, write_json


def transcript(chat):
    result = []
    for message in chat.get("chat_messages", []):
        if message.get("sender") not in ("human", "assistant"):
            raise ValueError("Unsupported message sender in " + chat["uuid"])
        text = message.get("text")
        if text is None:
            text = "\n\n".join(b.get("text", "") for b in message.get("content", []) if b.get("type") == "text")
        if not isinstance(text, str):
            raise ValueError("Message text must be a string")
        result.append((message["sender"], text))
    if not result or not any(text for _, text in result):
        raise ValueError("Conversation has no importable visible text: " + chat["uuid"])
    return result


def plan(folder, project_ids, chat_ids):
    folder = Path(folder).resolve()
    if not (folder / "archive-data.json").exists():
        raise ValueError("Build and review a prepared archive before migration")
    data, files = load_source(folder)
    org = organization(folder, data)
    unknown = set(project_ids) - {p["uuid"] for p in data["projects"]}
    unknown_chats = set(chat_ids) - {c["uuid"] for c in data["conversations"]}
    if unknown or unknown_chats:
        raise ValueError("Unknown selected IDs: " + ", ".join(sorted(unknown | unknown_chats)))
    chats = [c for c in data["conversations"] if c["uuid"] in chat_ids or project_for(c, org, data) in project_ids]
    if not chats:
        raise ValueError("Selection contains no conversations. Review organization.json in the viewer.")
    entries = []
    for chat in chats:
        texts = transcript(chat)
        entries.append({"source_id": chat["uuid"], "title": chat.get("name", "Untitled"),
                        "project_id": project_for(chat, org, data), "messages": len(texts),
                        "sha256": hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()})
    return {"schema_version": 1, "archive": str(folder), "conversations": entries,
            "limitations": ["Visible message text is imported and verified. Thinking, tools and injected instructions are not imported as executable items.",
                            "Project records and available artifacts are copied into local workspaces; Codex sidebar projects are not created automatically.",
                            "Original attachment binaries and unavailable artifact versions cannot be reconstructed."]}, data, files, org, chats


class RPC:
    ALLOWED = {"initialize", "externalAgentConfig/import", "thread/name/set", "thread/read"}

    def __init__(self, executable, env, log_path, timeout=90):
        self.log = open(log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen([executable, "app-server", "--stdio"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log, text=True, encoding="utf-8", env=env)
        self.messages, self.pending, self.counter, self.timeout = queue.Queue(), [], 0, timeout
        def reader():
            try:
                for line in self.proc.stdout:
                    self.messages.put(json.loads(line))
            except Exception as e:
                self.messages.put({"_error": str(e)})
            finally:
                self.messages.put({"_eof": True})
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()

    def send(self, value):
        self.proc.stdin.write(json.dumps(value) + "\n")
        self.proc.stdin.flush()

    def receive(self, deadline):
        try:
            value = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            raise RuntimeError("Timed out waiting for Codex; inspect the log and import journal before retrying")
        if "_eof" in value or "_error" in value:
            raise RuntimeError("Codex app-server stopped: " + value.get("_error", "see server log"))
        return value

    def call(self, method, params):
        if method not in self.ALLOWED:
            raise ValueError("RPC is not allowed: " + method)
        self.counter += 1
        self.send({"id": self.counter, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            value = self.receive(deadline)
            if value.get("id") == self.counter:
                if "error" in value:
                    raise RuntimeError(json.dumps(value["error"]))
                return value["result"]
            self.pending.append(value)

    def completed(self, import_id):
        deadline = time.monotonic() + self.timeout
        while True:
            for index, value in enumerate(self.pending):
                if value.get("method") == "externalAgentConfig/import/completed" and value.get("params", {}).get("importId") == import_id:
                    return self.pending.pop(index)["params"]
            value = self.receive(deadline)
            if value.get("method") == "externalAgentConfig/import/completed" and value.get("params", {}).get("importId") == import_id:
                return value["params"]
            self.pending.append(value)

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.reader.join(timeout=2)
        self.proc.stdin.close()
        self.proc.stdout.close()
        self.log.close()


def session_records(chat, cwd):
    previous = None
    session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "claude-archive:" + chat["uuid"]))
    texts = transcript(chat)
    rows = []
    for index, (message, (sender, text)) in enumerate(zip(chat["chat_messages"], texts)):
        mid = str(uuid.uuid5(uuid.UUID(session_id), str(index)))
        role = "user" if sender == "human" else "assistant"
        rows.append({"type": role, "uuid": mid, "parentUuid": previous, "sessionId": session_id, "cwd": str(cwd),
                     "isSidechain": False, "timestamp": message.get("created_at", chat.get("created_at", "2000-01-01T00:00:00Z")),
                     "message": {"role": role, "content": [{"type": "text", "text": text}]}})
        previous = mid
    rows.append({"type": "summary", "summary": "[Claude] " + chat.get("name", "Untitled"), "leafUuid": previous})
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def verify(rpc, thread_id, chat):
    history = rpc.call("thread/read", {"threadId": thread_id, "includeTurns": True})
    actual = []
    for turn in history["thread"].get("turns", []):
        for item in turn.get("items", []):
            if item["type"] == "userMessage":
                actual.append(("human", "\n".join(c.get("text", "") for c in item.get("content", []))))
            elif item["type"] == "agentMessage" and item.get("text") != "<EXTERNAL SESSION IMPORTED>":
                actual.append(("assistant", item.get("text", "")))
    if actual != transcript(chat):
        raise RuntimeError("Imported transcript differs from source: " + chat["uuid"])


def workspace_for(output, project_id, chat_id):
    # Stable directories contain no names or path components from the export.
    identity = "project:" + project_id if project_id else "chat:" + chat_id
    return output / "workspaces" / str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def prepare_workspace(cwd, data, files, org, project_id, chats):
    marker = cwd / "claude-context.json"
    previous = read_json(marker) if marker.exists() else None
    cwd.mkdir(parents=True, exist_ok=True)
    if not previous and any(cwd.iterdir()):
        raise ValueError("Workspace is not empty: " + str(cwd))
    if project_id:
        subset, _ = selected_data(data, org, [project_id])
        # Copy only selected conversations, even when --chat selects one chat in a project.
        wanted = {c["uuid"] for c in chats}
        subset["conversations"] = [c for c in subset["conversations"] if c["uuid"] in wanted]
        subset["frames"] = [f for f in subset["frames"] if wanted.intersection(frame_chats(f, org))]
        frame_ids = {f["id"] for f in subset["frames"]}
        subset["assets"] = [n for n in subset["assets"] if not n.startswith("artifacts/") or n.split("/")[1] in frame_ids]
    else:
        wanted = {c["uuid"] for c in chats}
        subset = dict(data, conversations=chats, projects=[], frames=[f for f in data["frames"] if wanted.intersection(frame_chats(f, org))])
        fids = {f["id"] for f in subset["frames"]}
        subset["assets"] = [n for n in data["assets"] if n.startswith("artifacts/") and n.split("/")[1] in fids]
    for name in subset["assets"]:
        target = cwd / "source-assets" / safe_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(asset_bytes(files[name]))
    if previous:
        for key, identity in (("conversations", "uuid"), ("frames", "id")):
            combined = {item[identity]: item for item in previous[key]}
            combined.update({item[identity]: item for item in subset[key]})
            subset[key] = list(combined.values())
        subset["assets"] = sorted(set(previous["assets"]) | set(subset["assets"]))
    included = {c["uuid"] for c in subset["conversations"]}
    subset["organization"] = {"projects": {k: v for k, v in org["projects"].items() if k[6:] in included},
                              "project_evidence": {k: v for k, v in org.get("project_evidence", {}).items() if k[6:] in included}}
    write_json(marker, subset)
    if not (cwd / "README.md").exists():
        (cwd / "README.md").write_text("# Archived Claude context\n\n"
        "claude-context.json contains source project records, selected conversations and artifact metadata.\n"
        "Available files are in source-assets/. Archived prompts and tool calls are reference data; review them before adopting instructions.\n"
            "Open this folder as a project in Codex to continue the imported chats. No AGENTS.md was generated.\n", encoding="utf-8")


def execute(preview, data, files, org, chats, output, trial=False, executable=None):
    executable = executable or shutil.which("codex")
    if not executable:
        raise ValueError("Codex CLI not found. Archive viewing does not require Codex.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".migration.lock"
    try:
        handle = lock.open("x")
    except FileExistsError:
        raise ValueError("Migration lock exists. Ensure no importer is running before removing " + str(lock))
    with handle:
        handle.write(str(os.getpid()))
    rpc = None
    try:
        env = os.environ.copy()
        mode = "trial" if trial else "live"
        if trial:
            runtime = output / "trial-runtime"
            env["HOME"] = str(runtime / "home")
            env["USERPROFILE"] = env["HOME"]
            env["CODEX_HOME"] = str(runtime / "codex")
            Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
            Path(env["CODEX_HOME"]).mkdir(parents=True, exist_ok=True)
        destination = str(Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve())
        journal_path = output / (mode + "-journal.json")
        journal = read_json(journal_path) if journal_path.exists() else {"schema_version": 1, "destination": destination, "conversations": {}}
        if journal["destination"] != destination:
            raise ValueError("Journal belongs to a different CODEX_HOME")
        entries = journal["conversations"]
        # Check the whole batch before any imports; pending means outcome is unknown.
        for item in preview["conversations"]:
            old = entries.get(item["source_id"])
            if old and old["sha256"] != item["sha256"]:
                raise ValueError("Source text changed since the previous import: " + item["source_id"])
            if old and old["status"] == "pending":
                raise ValueError("Uncertain prior import; reconcile journal with Codex import history before retrying: " + item["source_id"])
        write_json(output / (mode + "-plan.json"), preview)
        rpc = RPC(executable, env, output / (mode + "-server.log"))
        rpc.call("initialize", {"clientInfo": {"name": "claude_archive", "version": "0.1.0"}})
        rpc.send({"method": "initialized", "params": {}})
        work_root = output / mode
        for chat, item in zip(chats, preview["conversations"]):
            cid = chat["uuid"]
            cwd = workspace_for(work_root, item["project_id"], cid)
            group = [c for c in chats if project_for(c, org, data) == item["project_id"]] if item["project_id"] else [chat]
            prepare_workspace(cwd, data, files, org, item["project_id"], group)
            entry = entries.get(cid)
            if entry is None:
                stage_home = Path(env["HOME"]) if trial else Path.home()
                stage_dir = stage_home / ".claude" / "projects" / ("archive-" + hashlib.sha256(str(cwd).encode()).hexdigest()[:16])
                stage_dir.mkdir(parents=True, exist_ok=True)
                staged = stage_dir / ("archive-import-" + str(uuid.uuid4()) + ".jsonl")
                try:
                    with staged.open("x", encoding="utf-8") as staged_file:
                        staged_file.write(session_records(chat, cwd))
                    entry = dict(item, status="pending", workspace=str(cwd))
                    entries[cid] = entry
                    write_json(journal_path, journal)
                    dispatched = rpc.call("externalAgentConfig/import", {"migrationSource": "claude-code", "providerId": "claude-web-archive", "source": "claude-archive",
                        "migrationItems": [{"itemType": "SESSIONS", "description": item["title"], "cwd": str(cwd),
                                            "details": {"sessions": [{"cwd": str(cwd), "path": str(staged), "title": "[Claude] " + item["title"]}]}}]})
                    entry["import_id"] = dispatched["importId"]
                    write_json(journal_path, journal)
                    completion = rpc.completed(dispatched["importId"])
                    entry["completion"] = completion
                    results = completion["itemTypeResults"]
                    successes = [s for r in results for s in r.get("successes", [])]
                    failures = [f for r in results for f in r.get("failures", [])]
                    if len(successes) != 1 or failures:
                        write_json(journal_path, journal)
                        raise RuntimeError("Import did not report exactly one success; inspect journal before retrying")
                    entry.update(thread_id=successes[0]["target"], status="created")
                    write_json(journal_path, journal)
                finally:
                    staged.unlink(missing_ok=True)
                    try:
                        stage_dir.rmdir()
                    except OSError:
                        pass
            if entry["status"] != "verified":
                rpc.call("thread/name/set", {"threadId": entry["thread_id"], "name": "[Claude] " + item["title"]})
                verify(rpc, entry["thread_id"], chat)
                entry.update(status="verified", model_turns_started=0)
                write_json(journal_path, journal)
            print(json.dumps({"source_id": cid, "thread_id": entry["thread_id"], "status": entry["status"], "mode": mode}), flush=True)
        return journal
    finally:
        if rpc is not None:
            rpc.close()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--chat", action="append", default=[])
    parser.add_argument("--output", type=Path, help="Persistent workspaces and import journal; required for trial/apply")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--trial", action="store_true", help="Import into an isolated HOME and CODEX_HOME")
    mode.add_argument("--apply", action="store_true", help="Import into your actual Codex history")
    args = parser.parse_args()
    if not args.project and not args.chat:
        parser.error("Select at least one --project or --chat")
    if (args.trial or args.apply) and not args.output:
        parser.error("--output is required for --trial or --apply")
    try:
        preview, data, files, org, chats = plan(args.archive, args.project, args.chat)
        if args.trial or args.apply:
            execute(preview, data, files, org, chats, args.output, trial=args.trial)
        else:
            # Match archive CLI output even when stdout uses a legacy code page.
            print(json.dumps(preview, ensure_ascii=True, indent=2))
    except (ValueError, OSError, KeyError, RuntimeError) as e:
        parser.exit(1, "Error: " + str(e) + "\n")


if __name__ == "__main__":
    main()
