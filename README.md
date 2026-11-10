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

## Importing charms from your save

```bash
uv run mhp3ass import-save <path to MHP3RD.BIN> --out mycharms.txt
```

Does what the original's import dialog does with its defaults: the first
character with charms, the charms "Select Best" ticks, hacked charms
skipped. The output file is replaced, as the original replaces its list.
`--lang <language folder>` names skills in another language (default
`English (TeamHGG)`).

## Searching

```bash
uv run mhp3ass search <query.json>                    # solution lines on stdout
uv run mhp3ass search <query.json> --out out/<name>   # the harness's output files
```

Runs a query file in the corpus format (`tests/corpus/README.md`) as the
original's search does, and writes what the harness's `search` writes:
`<name>.manifest.json` and `<name>.solutions.txt.gz`, plus
`<name>.candidates.txt.gz` with `--candidates`. `--max-solution-lines N`
leaves out the solutions file above N lines, and `--progress` reports each
finished worker. The workers run in a pool of `--jobs N` processes (default:
one per CPU, at most 8); `--jobs 1` runs them in turn in one process, the
reference path. The results are the same either way; in a pool, `--progress`
reports the workers once the pool has finished. Where the original would throw, the command exits with
code 3 naming the worker; with `--record-exceptions` it records the
exception in the manifest instead and exits 0, as the harness does. To
compare with a golden:

```bash
gzcat tests/golden/search/<name>.solutions.txt.gz | diff - <(gzcat out/<name>.solutions.txt.gz)
```

## Regenerating golden fixtures (Windows)

See [`docs/windows-setup.md`](docs/windows-setup.md) to set up the toolchain and
[`harness/README.md`](harness/README.md) to run it.

## Licence

MIT. The original code is © 2017 AthenaADP; see [`LICENSE`](LICENSE).
