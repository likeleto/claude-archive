# Before publishing

The source tree is prepared separately from the author's private export. No personal ZIPs, source conversation JSON, project assignment files or migration logs belong in the public repository.

Selected release defaults:

- Repository name: `claude-archive`; the owner chooses their GitHub account or organization when publishing.
- Original code: MIT, included in `LICENSE`. Vendored Basecoat retains its own license.

Release procedure:

1. Run `python3 -m unittest discover -s tests -v` from a clean checkout. Confirm `AGENTS.md` and both `.agents/skills/*/SKILL.md` files are included. Run both skill entrypoints directly from the checkout without installation, including from a different working directory and a path containing spaces. Also check optional installation into a temporary skills directory.
2. Generate the fictional demo, build its archive, and follow the quickstart. Check HTML and document previews and persistent project assignments. Do not take release screenshots using a private export.
3. Run an isolated demo migration and repeat it with the same output directory; verify both chats remain the same IDs with `verified` status. A live history import is not necessary for a release check.
4. Initialize Git in this source folder (or use the GitHub Desktop flow in `github.md`), then review the exact staged file list and diff. Include `LICENSE`. `.gitignore` is an aid, not a proof that staged files contain no personal data.
5. Create/push the GitHub repository only when the owner has approved publication. Check CI results on supported platforms before claiming cross-platform validation.
6. Capture demo screenshots, describe experimental migration limits, tag the first release, and link the English and Russian quickstarts.
7. For the optional hosted demo, enable Pages with GitHub Actions as the source and run `Publish fictional demo`. Verify the published URL. Its builder generates fictional records only; never replace it with an upload of a personal archive.

Configured CI exercises Python 3.9 and 3.13 on Linux and Python 3.13 on Windows/macOS. Those remote jobs have not run until the repository is published. A local trial was performed with `codex-cli 0.167.0-alpha.3.2`; integration trials are not part of CI and do not require an API key.
