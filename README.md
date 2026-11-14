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
uv run pytest -m fuzz      # the full fuzz and L3 gates (minutes)
uv run pytest -m results   # every settings.cfg save/load golden
```

## Running the terminal UI

```bash
uv run mhp3-ass
```

Opens the search screen. It's being built: so far it shows
the query editor (hunter, gender, HR, village, weapon slots and charm mode,
starting from the saved `settings.cfg`, else the original's defaults), the
skill picker (type to filter, ▲▼ and ⏎ to add, up to six;
backspace in the empty box or ⏎ on a chip removes one), Search (`^S`, the
button, or ⏎ in the empty skill box; cancelling keeps the previous
results), and the results: a charm sidebar with
counts (⏎ filters), the sort (`s` picks it from a list; `S` reverses the key, or the search
order under None; ties go to the highest defence, then fewest jewels, then
search order), a table of every set, titled with how many it shows and
the sort, with short names (`Barroth S` for Barroth Tasset S, `+4 Att +3
Sharpn (1)` for the charm; the pieces are cut with `…` where they don't
fit, and the spare slots and charm scroll into view: `#` and Def stay at
the left, ←/→ scroll a whole column and Shift+←/→ to the first or last,
and `<` or `>` in the header shows there are more that way), and the inspector
beside it showing the selected set's full pieces, jewels, spare slots,
extra skills and stats. Find
(`/`, then `n`/`N`) moves to the sets naming a piece, jewel, charm or skill.
After a search the editor collapses to a one-line summary (the options
show only where they differ from the defaults): `e` (or `1`) reopens it.
The open editor takes at most about 40 % of the screen and scrolls past
that. In it, ←/→ move between the fields on a row and ↑/↓ between rows;
⏎ or space opens a drop-down, which then takes ↑/↓ itself. The skill box
keeps its own arrows (▲▼ browse the offered skills; ▲ at the top of the
list goes up a row). The screen has three regions, numbered in their
titles: ¹ the query, ² the charm sidebar and ³ the sets. Tab and Shift+Tab
move between them (inside the open editor, between its fields first), and
`1`, `2` and `3` jump to one (in the skill box the digits type: Esc or Tab
out first). Esc backs out one level at a time: it closes an open
drop-down, the skill list or the keys panel, then clears and closes the
find box, then closes a modal or collapses the editor (before the first
search, leaves it), then cancels a running search. It never quits. The
footer shows the keys that work where the focus is: the sort
and find keys (`s`, `S`, `/`, `n`, `N`) are the sets table's. `q` quits,
`?` shows the keys panel, and `^P` opens the command palette, which lists
every action by name, the fields included ("Set hunter…", "Set HR…", "Add
skill…"). `o` opens the options: the four armour options (space toggles),
the language (skill, armour and charm names and the labels switch at once,
and `mycharms.txt` is rewritten in it, as the original does), the colour
theme (`dracula` to start with; moving through the list shows each theme,
⏎ or leaving the list keeps it, esc goes back) and the number
of search processes; each change is saved straight away. Outside a terminal it prints the help instead; `mhp3-ass --help`
lists the `search` and `import-save` commands below.

## Importing charms from your save

```bash
uv run mhp3-ass import-save <path to MHP3RD.BIN>
```

Does what the original's import dialog does with its defaults: the first
character with charms, the charms "Select Best" ticks, hacked charms
skipped. It writes the saved-data folder's `mycharms.txt`, the one the TUI
reads (`--out <file>` writes elsewhere), and replaces it, as the original
replaces its list.

## Saved data

The TUI keeps the original's `settings.cfg` and `mycharms.txt`, in the
original's formats, in its saved-data folder: `~/.config/mhp3-ass/`
(`$XDG_CONFIG_HOME/mhp3-ass/` when set, `%APPDATA%\mhp3-ass\` on Windows).
`MHP3ASS_HOME` points it elsewhere, as does `data_dir` in that folder's
`tui.toml`; a first run copies the original's shipped charm list there.
`mhp3-ass info` prints the folders in use. In the options (`o`), the saved
data box changes the folder (type a path and ⏎, or Browse…): for an empty or
new folder you can move both files there or start fresh; a folder that
already holds either file, such as a Windows install's `Run` folder, is used
as it is. "clear…" resets the saved search (keeping the language), deletes
my charms (the next start copies the shipped list again) or deletes both,
saying which files first. Either restarts the TUI from the folder. With `MHP3ASS_HOME` set, the folder can't be
changed there.

`settings.cfg` holds the language, the form (both hunter types' skills), the
four armour options, the sort and the last search's results. The TUI starts
from it and saves it when it starts, when a search finishes, when the sort
changes and when it quits, as the original does. On macOS and Linux, closing
the terminal window (or a shutdown) quits the same way, saving first. A
cancelled search leaves
the previous results in it. Every skill row is written with the All filter.
As in the original, a load keeps charm-free sets only under None, so the
next save leaves them out (a notice says how many). A file that can't be
loaded is renamed to `settings.cfg.unreadable` and the TUI starts from the
defaults. `tui.toml` keeps what `settings.cfg` has no line for: whether the
sort is reversed (`S`), the search's processes (`jobs`), the colour `theme`
(also set by the palette's theme command) and `data_dir`.

`--lang <language folder>` names skills in another language (default
`English (TeamHGG)`).

## Searching

```bash
uv run mhp3-ass search <query.json>                    # solution lines on stdout
uv run mhp3-ass search <query.json> --out out/<name>   # the harness's output files
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
