# CLAUDE.md

Guidance for agents working in this repository. Workspace-wide rules in
`~/Documents/Development/CLAUDE.md` also apply.

## What this is

A behaviour-preserving port of a C++/CLI WinForms application (`legacy/`) to
Python (`src/mhp3ass/`).

## Hard rules

- **Never modify anything under `legacy/`.** It is the reference implementation
- **Never hand-edit `tests/golden/`.** Golden files change only by re-running the harness on Windows
- **Never skip, xfail or loosen a golden-comparison test** to get green. A mismatch is either a porting bug (fix the port) or a quirk of the original (log it in `docs/quirks.md` and raise it)
- **Port faithfully before improving.** Reproduce the original's tie-breaking, iteration order, integer semantics and mutation behaviour. No algorithm changes until the differential-fuzz phase passes
- Each port module cites the original it came from (`legacy/Solution.cpp`) in its module docstring

## Never commit

This is a **public** repository. Files, commit messages, PR titles and PR
bodies must not contain:

- **Network and machine details:** IP addresses, hostnames or machine names, OS user names, SSH host aliases, key file names or paths, local config (`~/.ssh`, `~/.gitconfig`)
- **Personal identifiers:** email addresses (commits use the GitHub noreply address), real-world account names other than the public GitHub handle
- **Personal paths:** home directories (`/Users/...`, `C:\Users\<name>`), notes or plan locations outside the repo. Use `$HOME` or `<placeholders>` in docs
- **Game data the user owns:** save files, decrypted save contents, imported charm lists. They live in gitignored `tests/savefile/`; fixtures derived from a real save record hashes and charm lists only, never raw save bytes
- **How the game or saves were obtained:** no references to emulators, disc images, game serials, handheld devices or their file paths. Say "your MHP3rd save file"
- **Secrets:** tokens, credentials, private keys

The `no-private-details` pre-commit hook blocks the mechanical cases (private
IP ranges, default Windows machine names). It can't catch everything, so
re-read docs and PR text before pushing.

## Workflow on this fork

- The agent creates branches, commits green chunks and opens PRs. Jamie merges
- Before each commit: `uv run pre-commit run --all-files` (ruff format, ruff check, ty, pytest, private-details check)
- **Before opening or updating a PR, run `/review-pr`, then act on the findings without waiting to be asked.** Fix Important findings and in-scope Nits in the same PR, re-run the checks, and report what changed. Raise a finding with Jamie only when the fix is ambiguous, changes agreed scope or behaviour, or contradicts these rules. If a finding reveals a missing rule, propose adding it here
- **Every commit stands alone:** no references to files, commands or behaviour that only arrive in a later commit
- PR bodies follow the workspace template (Why / Testing / Risk / How to revert) and the "Never commit" rules above

## Commands

```bash
uv sync
uv run pytest
uv run ty check
uv run ruff format .
uv run ruff check --fix .
uv run pre-commit run --all-files
```

## Porting hazards (check every function)

- C++ `unsigned` arithmetic wraps on underflow; Python ints don't
- C++ `/` and `%` truncate towards zero; Python floors
- .NET `Dictionary` enumeration order: insertion order while nothing has been removed
- `>=` comparisons in "best candidate" loops pick the last tie
- Object copies (`gcnew Charm(other)`) may be shallow; mutation can leak
- Data files are UTF-8 with BOM (`encoding="utf-8-sig"`)
