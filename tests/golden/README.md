# Golden fixtures

Output of `harness/` on Windows: the behaviour contract the Python port must
reproduce.

**Do not edit these files by hand.** To change them, change the harness or
the corpus and re-run `scripts/windows/generate-goldens.ps1` (see
`harness/README.md`). Large fixtures are gzip-compressed; read them with
`tests/goldens.py`.

| Path | Contents |
|---|---|
| `data/game-data.json.gz` | Every loaded table, before a language is applied |
| `data/charm-database.json.gz` | Charm tables built by `CharmDatabase::GenerateCharmTable()`, with names in the GUI's default language |
| `data/names/<language>.json.gz` | Display names per record for each language |
| `search/<query>.manifest.json` | Per-worker charm, solutions found and kept after duplicate removal, total |
| `search/<query>.solutions.txt.gz` | Every solution, in `settings.cfg` line format (see `tests/corpus/README.md`) |

Fixtures derived from a personal save file live in the gitignored
`tests/savefile/golden/` instead.
