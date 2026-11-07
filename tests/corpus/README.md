# Query corpus

Inputs for the harness's `search` command. Each `*.json` file is one Quick
Search; `scripts/windows/generate-goldens.ps1` writes its result to
`tests/golden/search/<name>.manifest.json` and `<name>.solutions.txt.gz`
(plus `<name>.candidates.txt.gz` for `gui_order_dependent` queries).

Queries whose charm list comes from a personal save go in the gitignored
`tests/savefile/corpus/` instead; their results go to
`tests/savefile/golden/search/`.

## Schema

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Short identifier, used in test output |
| `description` | string | What the query covers |
| `language` | string | Folder under `legacy/Run/Data/Languages`. Charm names, and so duplicate removal, depend on it |
| `hunter_type` | `blademaster` \| `gunner` | |
| `gender` | `male` \| `female` | |
| `hr`, `elder_star`, `weapon_slots` | int | HR, village quest stars, max weapon slots |
| `allow_bad`, `include_piercings`, `allow_event`, `allow_low_rank` | bool | The Options menu toggles |
| `charm_mode` | `none` \| `my_charms` \| `slotted` \| `one_skill` \| `two_skill` | The Charms drop-down |
| `skills` | int[] | Indices into the skill list (`Skill::static_skills`), as the GUI saves them. At most 6, each with positive points and a distinct ability, as the GUI's drop-downs allow; the harness rejects anything else |
| `skill_names` | string[] | The same skills by name in `language`; the harness fails if they disagree |
| `my_charms` | string[] | Lines in `mycharms.txt` format (`NumSlots,Skill1,Points1,Skill2,Points2`) |
| `gui_solution_count` | int, optional | Count the original GUI reported for this query; tests check the harness matches it |
| `gui_capture` | string, optional | Folder under the gitignored `tests/savefile/gui-captures/` holding the GUI's own `settings.cfg` for this query. Tests compare its solution lines with the harness's as a set. Without a `gui-captures/` folder the comparison is skipped; with one, a missing capture fails |
| `gui_order_dependent` | bool, optional | The GUI's result depends on thread timing (quirk 5 in `docs/quirks.md`), so it may keep different duplicates from the harness. The golden then also includes `<name>.candidates.txt.gz`, and tests check the GUI kept one candidate per duplicate key instead of comparing sets |

Queries with a `gui_capture` are written from the capture by
`scripts/gui_capture_to_corpus.py`.

## Solution line format

One line per solution, exactly as the GUI writes them to `settings.cfg`
(`Form1.h:495-538`). Order: each worker's solutions in loop order, workers in
the order `StartSearch` starts them. The GUI interleaves its parallel
workers' progress batches, so its own order differs; the set is the same.

```
<head> <body> <arms> <waist> <legs> <total spare> <spare1> <spare2> <spare3> <n decorations> <decoration>... <n extra skills> <skill>... [<charm slots> <n charm skills> (<points> <ability>)...]
```

Armour and decoration numbers are list indices (`-1` for an empty slot);
skill and ability numbers are indices into the base data.
