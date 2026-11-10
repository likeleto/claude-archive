#!/usr/bin/env python3
"""Serve a Claude export or a prepared archive on loopback only."""
import argparse
import json
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from archive import ROOT, asset_bytes, load_source, organization, project_for, report, validate_organization, write_json


def search_text(chat):
    parts = [chat.get("name", "")]
    for message in chat.get("chat_messages", []):
        parts.append(message.get("text", ""))
        parts.extend(b.get("text", "") for b in message.get("content", []) if b.get("type") == "text")
        for attachment in message.get("attachments", []):
            parts.extend([attachment.get("file_name", ""), attachment.get("extracted_content", "")])
    return "\n".join(parts)


class ArchiveServer(ThreadingHTTPServer):
    def __init__(self, folder, port=8765):
        self.folder = Path(folder).resolve()
        self.data, self.files = load_source(self.folder)
        self.organization = organization(self.folder, self.data)
        self.organization_revision = 0
        self.organization_lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self):
        if not self.local_request():
            self.send_error(403)
            return
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/index":
                with self.server.organization_lock:
                    data, org = self.server.data, self.server.organization
                    chats = [{k: v for k, v in c.items() if k != "chat_messages"} |
                             {"count": len(c.get("chat_messages", [])), "search": search_text(c)} for c in data["conversations"]]
                    self.send_json({"conversations": chats, "frames": data["frames"], "projects": data["projects"],
                                    "project_matches": {c["uuid"]: {"project": project_for(c, org, data)} for c in data["conversations"]},
                                    "organization": org, "organization_revision": self.server.organization_revision,
                                    "write_token": self.server.token, "report": report(data, org)})
            elif path == "/api/report":
                self.send_json(report(self.server.data, self.server.organization))
            elif path.startswith("/api/conversation/"):
                chat = next((c for c in self.server.data["conversations"] if c["uuid"] == path.rsplit("/", 1)[-1]), None)
                self.send_json(chat) if chat else self.send_error(404)
            elif path.startswith("/export/"):
                entry = self.server.files.get(path[len("/export/"):])
                if entry is None:
                    self.send_error(404)
                    return
                self.respond(asset_bytes(entry), mimetypes.guess_type(path)[0] or "application/octet-stream", sandbox=True)
            elif path in ("/", "/data.js", "/app.js", "/connections.js", "/layout.js", "/style.css", "/vendor/basecoat-1.1.0.min.css"):
                file = ROOT / "web" / ("index.html" if path == "/" else path[1:])
                self.respond(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "text/plain")
            else:
                self.send_error(404)
        except (OSError, ValueError) as e:
            self.send_json({"error": str(e)}, 500)

    def do_PUT(self):
        if not self.local_request() or not secrets.compare_digest(self.headers.get("X-Archive-Token", ""), self.server.token):
            self.send_error(403)
            return
        if urlparse(self.path).path != "/api/organization":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("Invalid organization size")
            body = json.loads(self.rfile.read(length))
            with self.server.organization_lock:
                if body.get("revision") != self.server.organization_revision:
                    self.send_json({"error": "Archive was edited in another tab. Reload before saving."}, 409)
                    return
                org = validate_organization(body["organization"], self.server.data)
                write_json(self.server.folder / "organization.json", org)
                self.server.organization = org
                self.server.organization_revision += 1
                self.send_json({"revision": self.server.organization_revision})
        except (ValueError, KeyError, TypeError) as e:
            self.send_json({"error": str(e)}, 400)
        except OSError as e:
            self.send_json({"error": str(e)}, 500)

    def send_json(self, value, status=200):
        self.respond(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json", status=status)

    def respond(self, data, kind, sandbox=False, status=200):
        self.send_response(status)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") or kind == "application/json" else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        if sandbox:
            self.send_header("Content-Security-Policy", "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'")
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        server = ArchiveServer(args.data, args.port)
    except (ValueError, OSError, KeyError) as e:
        parser.exit(1, "Error: " + str(e) + "\n")
    print(f"Claude Archive: http://127.0.0.1:{server.server_port} — {len(server.data['conversations'])} chats", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
