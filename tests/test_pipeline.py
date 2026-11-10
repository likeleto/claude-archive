import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import archive
import install_skill
import migrate
from examples.make_demo import ident, make_demo
from server import ArchiveServer


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "export"
        self.zip = make_demo(self.source)
        self.output = self.root / "archive"

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return archive.build(self.source, self.output)

    def test_portable_archive_preserves_source_and_reports_gaps(self):
        original = self.zip.read_bytes()
        report = self.build()
        self.assertEqual(self.zip.read_bytes(), original)
        self.assertEqual(report["counts"]["conversations"], 3)
        self.assertEqual(report["counts"]["messages"], 6)
        self.assertEqual(report["unassigned_conversations"], [ident("unassigned")])
        self.assertEqual(len(report["missing_artifact_versions"]), 1)
        self.assertTrue(report["warnings"])
        self.zip.unlink()
        data, files = archive.load_source(self.output)
        self.assertIn(b"Claude Archive", archive.asset_bytes(files["artifacts/" + ident("diagram") + "/versions/" + ident("diagram-v2") + ".html"]))
        self.assertTrue((self.output / "web/index.html").exists())
        self.assertEqual(len(data["projects"]), 2)

    def test_selection_uses_manual_overrides_and_never_guesses(self):
        data, _ = archive.load_source(self.source)
        org = {"projects": {"chats/" + ident("unassigned"): ident("garden"), "chats/" + ident("layout"): ""}, "frames": {}}
        archive.write_json(self.source / "organization.json", org)
        report = archive.build(self.source, self.output, [ident("garden")])
        self.assertEqual(report["counts"]["conversations"], 2)
        result, _ = archive.load_source(self.output)
        self.assertEqual({c["uuid"] for c in result["conversations"]}, {ident("watering"), ident("unassigned")})
        self.assertNotIn(ident("diagram"), {f["id"] for f in result["frames"]})
        self.assertNotIn("projects/" + ident("recipes") + ".json", result["assets"])
        with self.assertRaises(ValueError):
            archive.build(self.source, self.root / "other", ["unknown"])

    def test_unsafe_zip_paths_and_ids_are_rejected(self):
        with zipfile.ZipFile(self.zip, "a") as z:
            z.writestr("artifacts/../../escape.txt", "bad")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse((self.root / "escape.txt").exists())

    def test_injected_id_is_rejected(self):
        self.zip.unlink()
        archive.write_json(self.source / "conversations.json", [{"uuid": '\"><script>', "chat_messages": []}])
        with self.assertRaises(ValueError):
            archive.load_source(self.source)

    def test_artifact_override_can_reject_automatic_link(self):
        org = {"projects": {}, "frames": {ident("diagram"): []}}
        archive.write_json(self.source / "organization.json", org)
        archive.build(self.source, self.output, [ident("garden")])
        data, _ = archive.load_source(self.output)
        self.assertEqual({f["id"] for f in data["frames"]}, {ident("page")})
        self.assertFalse(any(n.startswith("artifacts/" + ident("diagram")) for n in data["assets"]))

    def test_prepared_archive_reports_missing_asset_instead_of_silent_loss(self):
        self.build()
        asset = self.output / "assets/artifacts" / ident("page") / "page.md"
        asset.unlink()
        with self.assertRaisesRegex(ValueError, "missing asset"):
            archive.load_source(self.output)

    def test_nonempty_output_is_not_overwritten(self):
        self.build()
        with self.assertRaises(ValueError):
            self.build()

    def test_project_evidence_survives_build_and_proposals_do_not_assign(self):
        key = "chats/" + ident("layout")
        proposed = "chats/" + ident("unassigned")
        evidence = {"project": ident("recipes"), "source": "screenshot", "status": "confirmed",
                    "reference": "sidebar.png, expanded heading", "reason": "Unique full title under the heading."}
        proposal = {"project": ident("garden"), "source": "copied_sidebar", "status": "proposed",
                    "reference": "sidebar.txt, line 8", "reason": "Cropped title; needs clarification."}
        org = {"projects": {key: ident("recipes")}, "frames": {}, "project_evidence": {key: evidence, proposed: proposal}}
        archive.write_json(self.source / "organization.json", org)
        self.build()
        data, _ = archive.load_source(self.output)
        saved = archive.organization(self.output, data)
        self.assertEqual(saved, org)
        chat = next(c for c in data["conversations"] if c["uuid"] == ident("unassigned"))
        self.assertEqual(archive.project_for(chat, saved, data), "")
        self.assertEqual(archive.report(data, saved)["project_evidence"][proposed], proposal)
        _, filtered = archive.selected_data(data, saved, [ident("recipes")])
        self.assertEqual(filtered["project_evidence"], {key: evidence})
        preview, source, files, org, chats = migrate.plan(self.output, [ident("recipes")], [])
        workspace = self.root / "workspace"
        migrate.prepare_workspace(workspace, source, files, org, ident("recipes"), chats)
        context = archive.read_json(workspace / "claude-context.json")
        self.assertEqual(context["organization"]["project_evidence"], {key: evidence})

    def test_invalid_or_unconfirmed_active_evidence_is_rejected(self):
        data, _ = archive.load_source(self.source)
        key = "chats/" + ident("layout")
        valid = {"project": ident("garden"), "source": "screenshot", "status": "confirmed",
                 "reference": "sidebar.png", "reason": "Unique visible title."}
        for changes in ({"source": "invented"}, {"source": []}, {"reference": ""}, {"project": "unknown"},
                        {"project": ident("recipes")}, {"status": "proposed"}):
            with self.subTest(changes=changes):
                org = {"projects": {key: ident("garden")}, "frames": {}, "project_evidence": {key: dict(valid, **changes)}}
                with self.assertRaises(ValueError):
                    archive.validate_organization(org, data)

    def test_server_persists_links_checks_revision_and_isolates_html(self):
        self.build()
        server = ArchiveServer(self.output, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with urlopen(base + "/api/index") as response:
                index = json.load(response)
            self.assertEqual(index["report"]["counts"]["conversations"], 3)
            key = "chats/" + ident("unassigned")
            org = {"projects": {key: ident("recipes")}, "frames": {}, "project_evidence": {key: {
                "project": ident("recipes"), "source": "user_note", "status": "confirmed",
                "reference": "User's saved note", "reason": "User confirmed this project's membership."}}}
            body = json.dumps({"organization": org, "revision": index["organization_revision"]}).encode()
            request = Request(base + "/api/organization", data=body, method="PUT", headers={"X-Archive-Token": index["write_token"]})
            with urlopen(request) as response:
                self.assertEqual(json.load(response)["revision"], 1)
            self.assertEqual(archive.organization(self.output, server.data), org)
            with self.assertRaises(HTTPError) as conflict:
                urlopen(request)
            self.assertEqual(conflict.exception.code, 409)
            conflict.exception.close()
            with self.assertRaises(HTTPError) as forbidden:
                urlopen(Request(base + "/api/organization", data=body, method="PUT"))
            self.assertEqual(forbidden.exception.code, 403)
            forbidden.exception.close()
            url = base + "/export/artifacts/" + ident("diagram") + "/versions/" + ident("diagram-v2") + ".html"
            with urlopen(url) as response:
                self.assertIn("sandbox allow-scripts", response.headers["Content-Security-Policy"])
                self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
            with self.assertRaises(HTTPError) as missing:
                urlopen(base + "/archive-data.json")
            self.assertEqual(missing.exception.code, 404)
            missing.exception.close()
            with self.assertRaises(HTTPError) as host:
                urlopen(Request(base + "/api/index", headers={"Host": "example.com"}))
            self.assertEqual(host.exception.code, 403)
            host.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_plan_has_no_side_effects_and_requires_selection(self):
        self.build()
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*") if "__pycache__" not in str(p))
        preview, *_ = migrate.plan(self.output, [ident("garden")], [])
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*") if "__pycache__" not in str(p))
        self.assertEqual(before, after)
        self.assertEqual(len(preview["conversations"]), 2)
        with self.assertRaises(ValueError):
            migrate.plan(self.output, [ident("recipes")], [])
        with self.assertRaises(ValueError):
            migrate.plan(self.source, [ident("garden")], [])

    def test_cli_json_preserves_unicode_with_legacy_stdout_encoding(self):
        self.build()
        env = dict(os.environ, PYTHONIOENCODING="cp1252:strict")
        commands = [
            ("archive.py", ["inspect", "--data", str(self.output)]),
            ("migrate.py", ["--archive", str(self.output), "--project", ident("garden")]),
        ]
        for script, args in commands:
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, str(archive.ROOT / script), *args],
                                        capture_output=True, env=env)
                self.assertEqual(result.returncode, 0, result.stderr.decode("cp1252"))
                report = json.loads(result.stdout.decode("cp1252"))
                if script == "archive.py":
                    self.assertEqual(report["projects"][0]["name"], "Claude Archive · Начните здесь")
                else:
                    self.assertEqual(report["conversations"][0]["title"], "01 · Что такое Claude Archive?")

    def test_installed_skills_run_without_original_repository(self):
        self.build()
        for name in ("claude-archive", "claude-to-codex"):
            installed = install_skill.install(name, self.root / "skills")
            args = ["inspect", "--data", str(self.output)] if name == "claude-archive" else ["--archive", str(self.output), "--project", ident("garden")]
            result = subprocess.run([sys.executable, str(installed / "scripts/run.py"), *args], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("conversations", json.loads(result.stdout)) if name == "claude-to-codex" else self.assertIn("counts", json.loads(result.stdout))
        with self.assertRaises(ValueError):
            install_skill.install("claude-archive", self.root / "skills")

    def test_checkout_skills_run_without_installation_from_another_directory(self):
        self.build()
        checkout = self.root / "Downloaded project with spaces"
        checkout.mkdir()
        import shutil
        shutil.copytree(archive.ROOT / ".agents", checkout / ".agents")
        for name in ("archive.py", "server.py", "migrate.py", "start.command", "start.bat", "LICENSE"):
            shutil.copy2(archive.ROOT / name, checkout / name)
        shutil.copytree(archive.ROOT / "web", checkout / "web")
        entry = checkout / ".agents/skills/claude-archive/scripts/run.py"
        built = self.root / "Built via skill"
        result = subprocess.run([sys.executable, str(entry), "build", "--data", str(self.source), "--output", str(built)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["counts"]["conversations"], 3)
        self.assertTrue((built / "web/index.html").is_file())
        entry = checkout / ".agents/skills/claude-to-codex/scripts/run.py"
        result = subprocess.run([sys.executable, str(entry), "--archive", str(built), "--project", ident("garden")],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["conversations"]), 2)

    def test_import_resume_and_unknown_outcome_do_not_duplicate(self):
        self.build()
        args = migrate.plan(self.output, [ident("garden")], [])
        dest = self.root / "migration"
        class FakeRPC:
            calls, imported, instances = [], {}, 0
            def __init__(self, executable, env, log):
                type(self).instances += 1
                self.env = env
            def send(self, value):
                pass
            def call(self, method, params):
                self.calls.append(method)
                if method == "externalAgentConfig/import":
                    session = params["migrationItems"][0]["details"]["sessions"][0]
                    path = Path(session["path"])
                    assert path.is_relative_to(Path(self.env["HOME"]))
                    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                    tid = str(uuid_for_test(len(self.imported)))
                    self.imported[tid] = records
                    self.last_tid = tid
                    return {"importId": tid}
                if method == "thread/read":
                    records = self.imported[params["threadId"]]
                    items = [{"type": "userMessage", "content": r["message"]["content"]} if r["type"] == "user" else
                             {"type": "agentMessage", "text": r["message"]["content"][0]["text"]} for r in records if r["type"] != "summary"]
                    return {"thread": {"turns": [{"items": items}]}}
                return {}
            def completed(self, import_id):
                return {"importId": import_id, "itemTypeResults": [{"successes": [{"target": self.last_tid}], "failures": []}]}
            def close(self):
                pass
        with patch.object(migrate, "RPC", FakeRPC), contextlib.redirect_stdout(io.StringIO()):
            first = migrate.execute(*args, dest, trial=True, executable="fake")
            self.assertEqual(len(FakeRPC.imported), 2)
            self.assertTrue(all(e["status"] == "verified" for e in first["conversations"].values()))
            migrate.execute(*args, dest, trial=True, executable="fake")
            self.assertEqual(len(FakeRPC.imported), 2)
            self.assertNotIn("turn/start", FakeRPC.calls)
            self.assertFalse(list((dest / "trial-runtime/home").rglob("*.jsonl")))
            journal = archive.read_json(dest / "trial-journal.json")
            journal["conversations"][ident("layout")]["status"] = "pending"
            archive.write_json(dest / "trial-journal.json", journal)
            with self.assertRaises(ValueError):
                migrate.execute(*args, dest, trial=True, executable="fake")
            self.assertEqual(len(FakeRPC.imported), 2)
        self.assertFalse((dest / ".migration.lock").exists())


def uuid_for_test(index):
    return ident("test-thread-" + str(index))


if __name__ == "__main__":
    unittest.main()
