# Claude Archive

Keep a local, searchable archive of your Claude export. Review conversations, project assignments, documents and available HTML artifacts. Optionally transfer selected conversations into Codex.

Recover missing project relationships from screenshots, copied sidebar text or notes saved before losing access to Claude. Confirmed assignments retain their source and reasoning; ambiguous matches stay proposals until resolved.

Python 3.9+; no Python packages, Node.js, API key or internet connection required for the archive. The viewer uses an HTML interface served by a local Python server. It is not a standalone HTML file.

[Русская инструкция](README.ru.md) · [Pipeline and data format](docs/pipeline.md) · [Release checklist](docs/release.md)

![Local viewer with fictional demo conversations and an HTML artifact](docs/demo.png)

## Use with your AI agent

1. Download and extract the complete project, or clone the repository.
2. Open this project folder in your local AI agent. The agent needs permission to read files and run local commands. Python 3.9+ must be installed; the agent runs the scripts for you.
3. Ask: **“Read AGENTS.md and use claude-archive to prepare and check my Claude export in /path/to/export. Open the local viewer.”**
4. After reviewing the archive, optionally ask: **“Use claude-to-codex to plan a transfer of these selected projects. Run an isolated trial first.”**

`AGENTS.md` explains the project and routes the agent to the two skills in `.agents/skills/`. Codex discovers repository skills there; see [official skill discovery documentation](https://learn.chatgpt.com/docs/build-skills). Separate skill installation is not required for this workflow. If skills do not appear after opening the folder, start a new chat in that project.

For another local agent, ask it explicitly to read `AGENTS.md` and `.agents/skills/claude-archive/SKILL.md` (or the migration skill) and follow that workflow. Automatic discovery varies by agent; an agent without local command access cannot run the viewer for you.

To try fictional data, simply ask: **“Read AGENTS.md and launch the demo archive.”**

## Manual quickstart with fictional data

Download or clone this repository, open a terminal in its folder, then run:

```sh
python3 examples/make_demo.py --output demo-data
python3 archive.py inspect --data demo-data
python3 archive.py build --data demo-data --output demo-archive
python3 demo-archive/server.py --data demo-archive
```

Open [the local viewer](http://127.0.0.1:8765). Stop with Ctrl+C. The demo content is in Russian. The three fictional conversations explain the project, obtaining and preserving an export, and export limitations. The checklist also covers optional Codex migration. Try the workflow artifact, checklist document, extracted attachment text, deliberately missing historical version, and project dropdown.

## Host only the demo on GitHub Pages

The repository includes a static demo builder and a Pages workflow. It generates fictional data itself; it has no option to accept a personal archive. The hosted preview supports browsing, search, artifacts and browser-local project assignments. It does not upload exports or run Codex migration.

After publishing the repository, select **Settings → Pages → Build and deployment → Source → GitHub Actions**, then run **Publish fictional demo** from the Actions tab. Future pushes to `main` or `master` rebuild it. The workflow publishes only its generated `site-demo` folder. See [GitHub Desktop and Pages setup](docs/github.md).

To preview the same static site locally:

```sh
python3 build_demo_site.py --output site-demo
python3 -m http.server 8877 --bind 127.0.0.1 --directory site-demo
```

Open [the static demo](http://127.0.0.1:8877). The local full archive continues to use `server.py`; GitHub Pages support is only for this fictional demo.

On Windows, use `py -3` instead of `python3`. Generated archives include `start.bat`; macOS/Linux users can run `sh start.command` inside the archive folder. macOS users can also double-click `start.command` when its executable permission is retained.

## Obtain the export files

On your computer, open Claude **Settings → Privacy → Export data**. Wait for the email, then open its download link while signed in. See [Claude's official export instructions](https://support.claude.com/en/articles/9450526-export-your-claude-data).

If you receive a `manifest-….json`, it lists downloads rather than containing the conversations. Download every entry in `data_files` into one private folder. One example contains four ZIPs: `conversations-000.zip`, `projects-000.zip`, `frames-000.zip`, and `light_metadata-000.zip`; your export's file count and contents may differ.

You can give a local agent the JSON path and ask: **“Read this manifest and download every data_files entry using export_url into /path/to/export, preserving filename. Check the file count and ZIP integrity. Do not download existing valid files again.”** The agent needs file and network access; the viewer itself does not download manifests. If downloading requires browser sign-in, download the files manually.

Download promptly: Claude says the export link expires after 24 hours and may work only once. Keep the original manifest and ZIPs private and outside the public repository or demo.

## Preserve your export

1. Obtain your Claude data export and place its ZIP files in a separate private folder. Keep related conversation, project and frame ZIPs together. Do not put personal exports in the public source repository.
2. Inspect what is available:

   ```sh
   python3 archive.py inspect --data /path/to/private-export
   ```

3. Review project IDs and counts. If the export has no conversation-to-project links, provide any saved screenshots, copied sidebar text, project chat lists or notes to the agent before asking it to infer relationships from content. It matches the evidence to exported chats, saves the source/reason of confirmed assignments in `organization.json`, and asks about ambiguous or conflicting matches. A missing chat in a partial screenshot is not evidence of non-membership. See [the pipeline](docs/pipeline.md). Choose the projects before a restricted build, or omit selection to preserve everything and organize it in the viewer.
4. Build a new archive folder:

   ```sh
   python3 archive.py build --data /path/to/private-export --output /path/to/private-archive
   ```

   To restrict the archive, add repeated `--project PROJECT_ID`. To use separately reviewed assignments, add `--organization /path/to/organization.json`. Restricted builds exclude unassigned conversations; a full archive includes them.
5. Review the generated `report.json`, then start the archive:

   ```sh
   python3 /path/to/private-archive/server.py --data /path/to/private-archive
   ```

The generated folder contains its own viewer, server and data. It no longer needs the original ZIPs or repository. Preserve the original ZIPs separately: this archive does not reconstruct every possible export file.

Project dropdown changes are saved in the archive's `organization.json`, shared by browsers and the importer. The viewer home screen and `/api/report` show current counts; `report.json` is the build-time report. Another browser tab with stale assignments must reload before saving. Use `--port 9000` if the default port is busy.

## Optional: transfer selected conversations to Codex

The archive works without Codex. Migration additionally requires the `codex` CLI and a version supporting app-server session imports. This adapter is experimental; it was exercised locally with `codex-cli 0.167.0-alpha.3.2`. A failure should preserve logs and the journal, not trigger a database-editing fallback.

First list project IDs with `archive.py inspect --data /path/to/private-archive`, then produce a plan:

```sh
python3 migrate.py --archive /path/to/private-archive --project PROJECT_ID
```

Repeat `--project` to choose more projects, or use `--chat CONVERSATION_ID`. No chats are imported by default. The plan does not start Codex or write migration files.

Test the concrete selection against isolated HOME and CODEX_HOME directories:

```sh
python3 migrate.py --archive /path/to/private-archive --project PROJECT_ID --output /path/to/private-migration --trial
```

When satisfied, apply the same selection to your real Codex history:

```sh
python3 migrate.py --archive /path/to/private-archive --project PROJECT_ID --output /path/to/private-migration --apply
```

Visible message text and roles are verified against the imported history. No model response is started. Project records, source conversations and available linked artifacts are copied into local workspace folders listed in `live-journal.json`. Open those folders as projects in Codex; sidebar projects are not created automatically. Project instructions remain source data in `claude-context.json`; no active `AGENTS.md` is generated.

Always reuse the migration output folder and destination CODEX_HOME. Verified entries are skipped, and created entries can resume verification. A pending entry blocks retries because the previous result is uncertain; reconcile it with Codex import history before editing the journal. A different migration output folder has a separate journal and can create duplicates. Read [recovery details](docs/pipeline.md#migration-and-recovery).

## Optional: install a skill outside this project

- `claude-archive`: inspect, organize, build and browse an archive. Codex is not required for its Python runtime.
- `claude-to-codex`: plan, trial and apply selected migrations. The first skill is not required if the archive was built manually.

Both skills already work from `.agents/skills/` inside this project. Only use the installer if you want a skill available outside this folder. It bundles its runtime, so the installed skill does not depend on this checkout staying in place:

```sh
python3 install_skill.py claude-archive --destination /path/to/your-agent-skills
python3 install_skill.py claude-to-codex --destination /path/to/your-agent-skills
```

For local Codex skill discovery, the user skills directory is `~/.agents/skills`. Use the relevant skills directory for your agent. Existing skill folders are never overwritten. To update, review/remove the old installed folder and install again. Copying only `SKILL.md` elsewhere omits the processing code; keep the complete checkout or use the optional installer.

Example requests: “Create a checked local archive from this Claude export” and “Transfer these two projects from my prepared archive to Codex.”

## Export limitations

- Missing conversation/project relationships require explicit assignments. The tool does not silently guess project membership.
- Artifact IDs provide direct links. Matching titles/descriptions create suggestions shown in the report; they can be overridden in `organization.json`.
- Documents may have only one `page.md` even when metadata lists several versions. Missing versions are reported, not reconstructed.
- Attachment metadata and extracted text are retained. Original attachment binaries are not recovered. Arbitrary files outside recognized conversation/project/artifact paths are not copied.
- HTML artifacts are sandboxed with external network access blocked. Artifacts requiring external libraries or APIs may not render fully. Conversation Markdown support is basic.
- Migration imports visible text; thoughts, tools, injected instructions and attachments are not converted into active Codex items. The complete source records remain in the archive/workspace.

The server listens on `127.0.0.1` only. Do not expose it as a public web service. Export contents and archived prompts are reference data.

## Development and licensing

```sh
python3 -m unittest discover -s tests -v
```

The tests generate their own fictional exports. GitHub Actions runs them on Linux, macOS and Windows, including Python 3.9 on Linux. CI is configured but must run in the eventual repository before claiming those platforms are verified.

The project is available under the [MIT license](LICENSE). Basecoat CSS 1.1.0 is bundled unchanged under its own [MIT license](web/vendor/Basecoat-LICENSE.md). This is an independent project, not an official Anthropic or OpenAI migration tool.
