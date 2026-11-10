# Manual commands

The main workflow is to open the project in a local AI agent and ask it to follow `AGENTS.md`. These commands are for development, troubleshooting, or running without an agent.

Run from the project folder with Python 3.9+. On Windows, use `py -3` instead of `python3`. No additional Python packages are required. Keep personal exports and generated archives outside the public source folder.

## Build and browse an archive

Keep all related export ZIPs in one private folder. Inspect, then build into a new directory:

```sh
python3 archive.py inspect --data /path/to/export
python3 archive.py build --data /path/to/export --output /path/to/archive
python3 /path/to/archive/server.py --data /path/to/archive
```

Open the printed loopback URL. Stop with Ctrl+C. Use `--port 9000` if the default is busy. A generated archive also includes `start.bat` and `start.command`; macOS/Linux users can run `sh start.command` from its folder.

Without selection, all conversations are included. Repeat `--project PROJECT_ID` to restrict a build; unassigned conversations are excluded from restricted builds. Use `--organization /path/to/organization.json` for separately reviewed assignments. Read [the pipeline](pipeline.md) before resolving ambiguous links or editing the data format.

The generated folder contains its own viewer and server. Preserve the original ZIPs separately. The viewer needs the server; opening its HTML directly is not supported.

## Try fictional data

Use new output directories; existing exports and nonempty build folders are not overwritten.

```sh
python3 examples/make_demo.py --output /path/to/demo-data
python3 archive.py build --data /path/to/demo-data --output /path/to/demo-archive
python3 /path/to/demo-archive/server.py --data /path/to/demo-archive
```

For the static demo and GitHub Pages, see [publishing instructions](github.md).

## Optional Codex migration

Requires a compatible Codex CLI with app-server session imports. The experimental adapter was tested locally with `codex-cli 0.167.0-alpha.3.2`.

First inspect the archive for project IDs, then plan, trial, and apply the same selection:

```sh
python3 archive.py inspect --data /path/to/archive
python3 migrate.py --archive /path/to/archive --project PROJECT_ID
python3 migrate.py --archive /path/to/archive --project PROJECT_ID --output /path/to/migration --trial
python3 migrate.py --archive /path/to/archive --project PROJECT_ID --output /path/to/migration --apply
```

Repeat `--project`, or use `--chat CONVERSATION_ID` to select individual chats. The plan imports nothing; the trial uses isolated HOME and CODEX_HOME directories. `--apply` writes to real Codex history. Open the generated workspace folders as projects yourself; sidebar projects are not created automatically.

Reuse the same output folder and destination CODEX_HOME on retries. Do not delete a journal to bypass a pending result. See [migration and recovery](pipeline.md#migration-and-recovery).

## Optional skill installation outside this project

The complete project already includes both skills. To use one from other folders:

```sh
python3 install_skill.py claude-archive --destination /path/to/agent-skills
python3 install_skill.py claude-to-codex --destination /path/to/agent-skills
```

Use your agent's skills directory. The installer bundles the runtime and refuses to overwrite existing skill folders.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests use fictional exports. See [the release checklist](release.md) before publishing.
