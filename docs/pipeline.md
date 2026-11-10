# Pipeline and archive format

## Inspect → organize → build → review → optionally migrate

`archive.py inspect` reads ZIPs directly and emits an inventory. It accepts `conversations.json`, `projects/**/*.json` records containing `uuid`, and `artifacts/<id>/artifact.json` plus artifact files. A loose `conversations.json` is used only when no ZIP supplies conversations. Keep related export ZIPs in one input directory. Archives are processed in filename order; duplicate record IDs and asset paths use the last archive. This is deterministic precedence, not a merge of message histories.

Native conversation `project_uuid` or `project_id` values are used only when they identify a known project. Other project membership must be assigned explicitly. The program does not infer it from conversation titles. An agent may inspect relevant content and propose assignments, but must distinguish those proposals from recovered metadata.

Use `organization.json` in the input directory, or supply `--organization /path/to/file` to inspect/build:

```json
{
  "projects": {
    "chats/CONVERSATION_ID": "PROJECT_ID",
    "chats/ANOTHER_CONVERSATION_ID": ""
  },
  "frames": {
    "ARTIFACT_ID": ["CONVERSATION_ID"],
    "ANOTHER_ARTIFACT_ID": []
  }
}
```

All IDs must exist in the input. An explicit empty project overrides a native project assignment. An artifact entry replaces automatic conversation links; an empty list rejects all automatic links for that artifact. Omit the entry to retain automatic links. The current viewer edits project assignments; artifact overrides are edited in this JSON file before starting/restarting the server.

### Screenshots, copied sidebar text and notes

When project relationships are missing, the archive skill first uses user-provided screenshots, copied sidebar/project lists or notes saved before losing access. It matches visible project headings and chat titles against exported records. Duplicate/cropped/renamed titles or conflicts with native/previously confirmed links require clarification. Content similarity is a separate inference source. Missing chats in a partial or collapsed sidebar do not prove non-membership.

`organization.json` optionally includes `project_evidence`, keyed by `chats/<conversation-id>`. Each record has `project`, `source`, `status`, `reference` and `reason`. Supported sources are `export`, `screenshot`, `copied_sidebar`, `user_note`, `user_confirmation`, `content_inference` and `manual`. References/reasons are nonempty strings up to 4000 characters. Old files containing only `projects` and `frames` remain valid.

```json
{
  "projects": {"chats/CHAT_ID": "PROJECT_ID"},
  "frames": {},
  "project_evidence": {
    "chats/CHAT_ID": {
      "project": "PROJECT_ID",
      "source": "screenshot",
      "status": "confirmed",
      "reference": "sidebar-01.png, expanded project heading and third chat",
      "reason": "The full title uniquely matches this exported conversation."
    }
  }
}
```

`confirmed` records must match an explicit assignment in `projects`. To retain an unresolved match, use `status: proposed` and omit that target from the active `projects` map; the proposal alone never assigns or migrates a chat. A restricted build filters evidence to included chats/projects, while a full archive retains unresolved proposals too. Review proposals that could affect project selection before a restricted build or migration. Referenced evidence files are not copied automatically; keep them privately alongside your original export.

The report includes this evidence. The viewer shows its reference and reasoning below the Project dropdown. A manual project change replaces the current evidence with `manual`/`confirmed` and rolls back both fields if saving fails. Current evidence is not a full edit-history log. Codex workspace context retains evidence for included source conversations.

Artifact IDs found in conversation records create direct links. Exact artifact title or long description matches in Artifact tool calls create suggested links. Review the suggestions in the report; they are not guaranteed relationships. If selecting projects before build, establish assignments first; otherwise build a full archive and use the viewer to organize it.

`archive.py build` refuses a nonempty output folder. It never edits source ZIPs. `--project` includes only conversations assigned to the selected projects and their linked artifacts/project files. It excludes unassigned conversations and unrelated project metadata. A full build without `--project` includes every conversation, including unassigned ones, and all recognized project/artifact assets.

## Generated folder

```text
archive-data.json       Schema version, source conversations/projects/frames,
                        asset index, source filenames and SHA-256 fingerprints
organization.json       Reviewed assignments and artifact overrides
report.json             Counts and limitations at build time
assets/                 Available project/artifact entries from the ZIPs
server.py, archive.py    Portable local runtime
web/                    HTML/CSS/JavaScript viewer and vendored CSS
start.command, start.bat
```

The archive retains source conversation records, including tool blocks and extracted attachment text. It does not copy arbitrary unrecognized export entries or reconstruct unavailable attachment binaries. Original ZIPs should remain the archival source of truth. Unknown/malformed input can fail with an error rather than being silently discarded.

`schema_version` is currently `1`. The viewer reads archive data into memory and writes only `organization.json`. Restart it after external edits. Project changes use revision checks to reject stale browser tabs. Only one viewer server should edit a given archive at a time. The build-time report is immutable; `/api/report` computes a report using current in-memory assignments.

The UI requires the included Python server and does not work by opening `index.html` via `file://`. It stays local to loopback. HTML artifacts are returned with a sandbox CSP, while the preview iframe also has a sandbox. Scripts may run inside the isolated artifact, with network access disabled; this is not a hosted multiuser application.

## Migration and recovery

Migration input must be a prepared archive. `migrate.py --archive ... --project ...` or `--chat ...` creates a read-only plan. It imports only selected visible message text and roles. Missing `text` fields fall back to text content blocks. Empty/unrecognized conversations are rejected rather than silently skipped.

`--trial --output ...` uses an isolated HOME and CODEX_HOME under the migration output. `--apply` uses the current CODEX_HOME or the user's default `~/.codex`. Workspaces are grouped by project; unassigned explicitly selected conversations get separate workspaces. Stable UUID-based workspace directories avoid interpreting exported names as paths. Context files retain source metadata and available selected assets. Imported chats point at these workspace paths; open the folders as projects in the Codex app yourself.

The adapter converts text into temporary Claude Code session JSONL, imports it through `externalAgentConfig/import`, waits for the matching `importId` completion, records the new thread ID, then verifies the result using `thread/read`. Temporary session files are removed in a `finally` block. No turn-start or command-execution RPC is permitted. See [official app-server documentation](https://learn.chatgpt.com/docs/app-server) for the protocol; the Claude web-export conversion itself is this project's adapter, not an official web-export import endpoint.

`trial-journal.json` and `live-journal.json` are separate. Each source conversation records its visible-text hash, destination thread, workspace and state:

| State | Meaning | Retry behavior |
| --- | --- | --- |
| `pending` | Import may have been dispatched; outcome not safely recorded | Stops the batch before further imports |
| `created` | Destination thread ID is recorded, verification incomplete | Resumes naming/verification without creating a new chat |
| `verified` | Imported visible transcript matched the source | Skips this conversation |

Reusing the same output directory is required for duplicate protection. Journals do not coordinate across different output directories. A changed visible-text hash or different destination CODEX_HOME blocks reuse.

For a pending entry, inspect the recorded `import_id`, completion if present, server log and Codex import history. Recover a confirmed destination thread ID into the entry with state `created`, then rerun to verify. Remove a pending entry only after establishing that no destination chat was created and no import remains in progress. Do not delete the whole journal to force retries. Failed verification preserves the `created` entry and can be resumed after diagnosing the discrepancy.

A `.migration.lock` prevents simultaneous runs sharing an output directory. If a process was killed, check that no importer is still running before removing a stale lock. Journals, logs and copied workspace data can contain private information and belong outside the source repository.

The adapter was tested against one installed CLI version, not every Codex release. Version differences should stop with a diagnosable error. There is no direct Codex database manipulation and no automated sidebar-project registration. The trial validates the actual app-server importer, but does not prove how every desktop app version will present imported chats.
