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
| `data/models.json.gz` | `dump-models` output in the GUI's default language (inputs in `tests/models/`) |
| `data/best-decorations.json.gz` | `best-decorations` output: `best[hr - 1][village - 1][max slots]` per ability, a decoration index, `-1` for none, or `-2` where the call threw (the entry's `exception`) |
| `data/solution-probes.json.gz` | `solution-probes` output: `point_score_in_bounds` (`Solution.cpp:326`), `point_score_rank` (dense rank of `point_score[k]` for k = 0-22; only the order is stable, see `harness/README.md`), `private_methods` |
| `data/charm-location.json.gz` | `charm-location` output (only with `generate-goldens.ps1 -CharmLocation`): `find_charm2`, one record per direct `FindCharm2` call (arguments, `table[ table ][ mystery, shining, timeworn ]` counts, example charm or null); `parse_and_find`, one record per charm name parsed by the tooltip (language, name, then the exception type, or the cached counts, example and menu header) |
| `relevance/<query>.json.gz` | `relevance` output for each query in `tests/corpus/`, `tests/relevance/` and `tests/traces/queries/`: armour and decorations as list indices in list order, charms as in `data/models.json.gz` |
| `search/<query>.manifest.json` | Per-worker charm, solutions found and kept after duplicate removal, total |
| `search/<query>.solutions.txt.gz` | Every solution, in `settings.cfg` line format (see `tests/corpus/README.md`) |
| `search/<query>.candidates.txt.gz` | `gui_order_dependent` queries only: every solution found before duplicate removal, as `<worker>\t<charm name>\t<solution line>` |
| `traces/<spec>.jsonl.gz` | `traces` output for each spec in `tests/traces/`: a header with the per-worker census, then `MatchesQuery` stage by stage for each sampled combination (format in `tests/traces/README.md`) |

Fixtures derived from a personal save file live in the gitignored
`tests/savefile/golden/` instead.
