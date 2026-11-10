# Harness

A C++/CLI console program that compiles the original sources in `legacy/`
unchanged, without the WinForms UI, and records their behaviour as golden
fixtures for the Python port.

## Layout

| Path | What |
|---|---|
| `Harness.vcxproj` | Release/Win32 project. Compiles the legacy core (`Armor`, `CharmDatabase`, `Common`, `Decoration`, `LoadedData`, `PSPCryptoEngine`, `SaveDataEncryption`, `Skill`, `Solution`, `StringManipulation`) plus `src/` |
| `src/Main.cpp` | Command-line entry point. Loads data in the GUI's startup order (`Form1.h:309-322`) |
| `src/DataDump.cpp` | L1 dumps of game data, charm tables and per-language names |
| `src/SaveDump.cpp` | L1 dump of save decryption and charm import |
| `src/ModelDump.cpp` | L1 record behaviour that needs no query (skills, decorations, charm validity, my-charms file, charm comparisons) |
| `src/QueryFile.cpp` | Corpus query files and `FormulateQuery`, shared by `search` and `relevance` |
| `src/RelevanceDump.cpp` | L2 query set-up: `GetRelevantData`, `CharmDatabase::GetCharms`, the query-based `GetBestDecoration` |
| `src/SearchDump.cpp` | L3 Quick Search: charm dispatch, search loop and duplicate removal |
| `src/Workers.cpp` | The workers `StartSearch` starts and the loop each runs, shared by `search` and `results` |
| `src/Results.cpp` | Form1's result lists and duplicate removal, and the `settings.cfg` solution line |
| `src/ResultsDump.cpp` | The solution part of `SaveConfig` and `LoadConfig` (`settings.cfg` and File > Save/Load `.ass`) |
| `src/Fixtures.h` | Serialisation shared by every fixture (charms, ability pairs, hex) |
| `src/Json.h` | Deterministic JSON writer (gzip when the output ends in `.gz`) |

Logic that lives inside the original's forms is copied into the harness with
the UI controls swapped for plain data, and each copy cites the original
`file:line`. Keep these copies minimal and line-for-line.

The harness builds **Release only**. The shipped application is a Release
build, where the legacy `Assert` macro (`Common.h:3-7`) compiles to nothing,
so Release is what reproduces its behaviour.

`Charm` defines a member `operator==`, so `charm == nullptr` calls it and
crashes on a null argument. Test charm handles directly (`if( charm )`), as
the legacy code does.

## Build and run (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\build-harness.ps1
harness\Release\Harness.exe                      # prints usage
```

| Command | Output |
|---|---|
| `dump-data --out <file>` | Abilities, skills, armour, decorations and materials, including list and dictionary enumeration order |
| `dump-data --names-only --lang <language> --out <file>` | Display names per record after loading a language |
| `dump-charms --lang <language> --out <file>` | `CharmDatabase::GenerateCharmTable()` output |
| `dump-models [<mycharms.txt>...] --lang <language> --out <file>` | Query-independent record behaviour: `Ability::GetSkill` thresholds, `Decoration::IsBetterThan` for every pair, `CharmExists`/`CharmIsIllegal` on a charm sample, `LoadCustom`/`SaveCustom` over each given file (inputs in `tests/models/`), and charm `==`, `StrictlyBetterThan`, `BasicallyTheSameAs` and `AddCharmToOptimalList` under several `relevant` ability flag sets |
| `decrypt-save <save.bin> --lang <language> --out <file>` | SHA-256 after each decryption layer, every charm per character, the "Select Best" choice, and the `mycharms.txt` an import would write |
| `search <query.json> --out <prefix>` | `<prefix>.manifest.json` and `<prefix>.solutions.txt.gz` for one corpus query (schema in `tests/corpus/README.md`) |
| `search <query.json> --out <prefix> --candidates` | Also `<prefix>.candidates.txt.gz`: every solution each worker found before duplicate removal, as `<worker>\t<charm name>\t<solution line>`. `generate-goldens.ps1` passes it for `gui_order_dependent` queries |
| `search <query.json> --out <prefix> --max-solution-lines <n>` | Writes `<prefix>.solutions.txt.gz` only when there are at most `<n>` solutions; the manifest's `solutions_file` says whether it did. Every manifest records `solutions_sha256` (the uncompressed lines in harness order), `solution_set_sha256` (sorted ordinally) and each worker's `added_sha256`, so a result is checkable without its file |
| `search <query.json> --out <prefix> --record-exceptions` | A worker that throws ends the query: the manifest's `exception` records the worker, type and message, instead of the harness failing. For the fuzz corpus; the hand-picked corpus fails loudly |
| `relevance <query.json> --out <file>` | `GetRelevantData` for one query (relevant abilities and flags; relevant and inferior armour per slot, with `no_skills` and `danger`; relevant and inferior decorations) and `GetCharms` for one- and two-skill charms. Charm fields in the query are ignored |
| `best-decorations --out <file>` | `GetBestDecoration( ability, max_slots, query )` for every ability, max slots 0-3, HR 1-6 and village 1-6 |
| `solution-probes --out <file>` | What `GetScore`'s `point_score` returns for indices 0-22 (in bounds verbatim; all of them as dense ranks, since past the 6-element array this build reads load-time method thunks that change per run), and the private `Solution` methods reachable by reflection |
| `charm-location --out <file>` | `FindCharm2` called directly (no ability, every ability at points 0-15, sampled two-skill pairs and their variations, wrapped negative points; each over slots 0-3), and charm names run through the tooltip's `UpdateContextMenu` in all 7 languages (English (TeamHGG) in full, about 200 per other language), recording what it caches and its header or the exception. Takes about 9 minutes; `generate-goldens.ps1` runs it only with `-CharmLocation` |
| `traces <spec.json> --out <file.jsonl.gz>` | `Solution::MatchesQuery` stage by stage for sampled armour combinations of the spec's query (spec schema in `tests/traces/README.md`). Every combination runs through the real `MatchesQuery` and a stepped copy of it; the command throws if they end in different states |
| `results <query.json> --out <file>` | Runs the query's search, then three steps: `save` (the result lists, and the SHA-256 of the solution lines `SaveConfig` writes), `load` (those lines read back by a fresh GUI, as at start-up) and `load_after_search` (read back by the GUI that ran the search, whose duplicate set `LoadConfig` keeps). Each load records where every line went (`placements`: `a` all solutions, `n` charm-free list only, `d` dropped as a duplicate), the list sizes and charm map, hashes of the stats `CalculateData` leaves, and the hash of the re-save `LoadConfig` ends with. The header lines (options, skill rows) aren't covered |
| `results-file <settings.cfg> --out <file>` | One `load` step for a saved file, in the language its header names |

`<language>` is a folder under `legacy/Run/Data/Languages`. The GUI defaults
to `English (TeamHGG)` on first run.

The search runs the GUI's workers one at a time in the order `StartSearch`
starts them: each worker's solutions in loop order, then the next worker's.
The GUI runs them in parallel and adds solutions in per-(head, body)
progress batches as each thread reaches them, so its order differs. The set
is the same: query 1b's 34,153 solution lines equal the GUI's `settings.cfg`
lines as a set.

The legacy loaders show a message box on some malformed input (a short
`strings.txt`, an unknown skill in a charm file). Over SSH that blocks
forever, so a hung run usually means bad input data.

## Regenerating golden fixtures

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\generate-goldens.ps1
```

This writes `tests/golden/data/`, `tests/golden/search/`, `tests/golden/results/`, `tests/golden/relevance/` and `tests/golden/traces/` (committed) and,
for queries, GUI captures and saves from personal data, `tests/savefile/golden/`
(gitignored). Output is byte-identical across runs. Copy the files back to
the development machine and commit them there.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\generate-goldens.ps1 -Fuzz
```

This writes only `tests/golden/fuzz/`: one search per query in `tests/fuzz/`,
with solution files for results of at most 5,000 lines and exceptions
recorded in the manifest. It takes 10-15 minutes, so the default run skips
it. Rerun it whenever `SearchDump.cpp`, `Workers.cpp`, `QueryFile.cpp`,
anything under `legacy/`, or the fuzz corpus changes.
