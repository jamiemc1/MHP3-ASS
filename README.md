# MHP3-ASS

Armor set search for Monster Hunter Portable 3rd. This fork is porting
[Athena's Armor Set Search](https://github.com/AthenaADP/MHP3-ASS) from
C++/CLI (Windows-only) to Python with a Textual terminal UI, so it runs on
macOS and Linux.

The port preserves behaviour exactly: the original program is the
specification, and golden fixtures recorded from it gate every change.

## Repository layout

| Path | What | Who changes it |
|---|---|---|
| `legacy/` | The original Visual Studio solution, sources and runtime data (`legacy/Run/Data/`), unchanged apart from moving into this folder | Nobody. Frozen reference |
| `harness/` | C++/CLI console program that compiles the `legacy/` sources and records their behaviour as JSON | Edited on any machine, built on Windows |
| `src/mhp3ass/` | The Python port | Python only |
| `tests/corpus/` | Query inputs for the harness | Python side, authored or generated |
| `tests/golden/` | Harness output: the contract the port must match | **Only** by re-running the harness |
| `tests/` (rest) | Python tests | Python side |
| `docs/` | Roadmap, quirks log, Windows setup | — |

The game data in `legacy/Run/Data/` is the single source of truth for both
implementations.

## Development (Python)

```bash
uv sync
uv run pre-commit install
uv run pytest
uv run pre-commit run --all-files   # ruff format, ruff check, ty, pytest
```

## Regenerating golden fixtures (Windows)

See [`docs/windows-setup.md`](docs/windows-setup.md) to set up the toolchain and
[`harness/README.md`](harness/README.md) to run it.

## Licence

MIT. The original code is © 2017 AthenaADP; see [`LICENSE`](LICENSE).
