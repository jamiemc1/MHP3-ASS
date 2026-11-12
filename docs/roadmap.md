# Roadmap

Target: parity with every feature of the original, then a better UX on top.

## Parity phases

| # | Phase | Needs Windows | Status |
|---|---|---|---|
| 0 | Scaffold: layout, tooling, docs | No | Done |
| 1 | Harness + first query corpus → golden fixtures | Yes | Done (L2 traces deferred) |
| 2 | Data loaders (skills, armour, decorations, components, tags, languages) | No | Done |
| 3 | Domain models: abilities/skills, decorations, charms | Yes (3b fixtures) | Done |
| 4 | Relevance filtering (`GetRelevantData`) + charms for a query (`CharmDatabase::GetCharms`) | Yes (4a fixtures) | Done |
| 5 | `Solution.MatchesQuery` (decoration filling, charm reduction) | Yes (5a traces) | Done (5a traces, 5b decoration filling, 5c bad skills, 5d charm reduction and the search worker) |
| 6 | Search loop, charm modes, CLI | No | Done (6a worker dispatch, 6b duplicate removal, 6c `run_search` with L3 parity on all corpus queries, 6d `mhp3ass search`) |
| 7 | Save-file charm import (PSP decryption) | No | Done |
| 8 | Performance: per-charm multiprocessing, profiling, pruning if needed | No | Done (process pool `--jobs`, GC pause, faster start-up; no pruning). Budgets set from the gate run |
| 9 | Differential fuzz over ~500 random queries | Yes (one run) | Done (9a corpus and harness goldens; 9b the port matches all 500, `pytest -m fuzz`, with a 25-query smoke subset in the default run) |
| 10 | Textual TUI | No | Not started |

## Feature inventory (all in scope)

Features of the original, each mapped to the phase that delivers its core and
to the TUI.

| Feature | Original | Core phase |
|---|---|---|
| Skill search (Blademaster / Gunner) | `Form1.h` `FormulateQuery`, `StartSearch` | 4–6 |
| Skill rows: per-row filters, skills offered, restore from `settings.cfg` | `Form1.h:210-247`, `:1478-1556`, `:414-426` | 10 (`skill_picker.py`) |
| Query options: gender, HR, elder stars, weapon slots | `Form1.h:1192` | 4 |
| Toggles: piercings, bad skills, event armour, low-rank armour | `Form1.h:1198` | 4 |
| Charm modes: none, my charms, slotted, one-skill, two-skill | `Form1.h:1293` | 6 |
| Auto-guard special case | `Form1.h:1274` | 6 |
| Advanced search: per-piece armour/decoration include lists | `frmAdvanced.h`, `Form1.h:1420-1459` | 4, 10 (`advanced.py`) |
| Result sorting (the original's keys, sorted stably) | `Form1.h:20-80`, `:2149-2172` (`cmbSort`), `:1981-1996` | 10 (`results/sorting.py`, `results/view.py`) |
| Result filtering by charm (names listed case-insensitively) | `Form1.h:1723-1802`, `:2102-2130`, `:2226-2253` (`cmbCharms`) | 10 (`results/view.py`) |
| Result details (pieces and their notes, charm, jewels, slots spare, sort value, extra skills; layout is the TUI's) | `Form1.h:1569-1655` | 10 (`results/details.py`) |
| Find in results (case-insensitive, wrapping) | `frmFind.h:135-144`, `Form1.h:1938-1953` | 10 (`results/find.py`) |
| My-charms management (add, delete, persist to `mycharms.txt`) | `ManageCharms.h`, `CharmDatabase.cpp` | 3, 10 (editing: `charms/editing.py`) |
| Charm import from a PSP save | `ImportCharms.h`, `SaveDataEncryption.cpp`, `PSPCryptoEngine.cpp` | 7, 10 |
| Charm validity checking (possible/impossible charms) | `CharmDatabase.cpp` | 3 |
| Charm tooltip: which tables can produce a charm (`FindCharm2`) and its name parser | `CharmDatabase.cpp:1006-1099`, `Common.cpp:157-230` | Side stream (logic), 10 (menu) |
| Languages (7 data sets) | `Common.cpp:292`, `Form1.h:333` | 2 |
| Display strings (`strings.txt`), language list order and default language | `Common.cpp:290-311`, `Common.h:90-194`, `Form1.h:331-340`, `Form1.h:441-454` | 10 (`data/strings.py`, `data/languages.py`) |
| Persisted settings and results (`settings.cfg`, `.ass`) | `Form1.h:342-540` (`SaveConfig`, `LoadConfig`, `AddSolution`) | 10 (`settings_cfg.py`; the TUI's form, sort and results in `saved_state.py`) |
| About dialog | `frmAbout.h` | 10 |

## After parity

- Faster search through early pruning (only with L3 golden parity kept)
- TUI improvements: filter-as-you-type skill picker, chosen-skill chips, sortable results table with a detail pane
- Packaging: game data as package data, `uv tool install` / `pipx`
- Review the quirks log and decide which to fix
