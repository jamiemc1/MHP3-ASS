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
| `src/SearchDump.cpp` | L3 Quick Search: query, charm dispatch, search loop and duplicate removal |
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

This writes `tests/golden/data/` and `tests/golden/search/` (committed) and,
for queries and saves from personal data, `tests/savefile/golden/`
(gitignored). Output is byte-identical across runs. Copy the files back to
the development machine and commit them there.
