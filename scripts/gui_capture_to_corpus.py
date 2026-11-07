"""Turn a captured GUI search into a harness corpus query.

A capture is a folder holding the original GUI's ``settings.cfg`` (written
after every search: options, chosen skills and all solutions) and the
``mycharms.txt`` in use at the time, as archived by
``scripts/windows/capture-gui-searches.ps1``.

Queries whose results depend on the charm list (``my_charms`` mode, or an
Auto-Guard skill in the slotted/one-skill/two-skill modes, which looks up a
charm in the list; ``Form1.h:1273-1291``) are personal and belong in the
gitignored ``tests/savefile/corpus/``. Others don't read the charm list, so
it is left empty and the query can be committed to ``tests/corpus/``.

Usage:
    uv run python scripts/gui_capture_to_corpus.py <capture-dir> --id 03 \
        --description "..." --out tests/corpus/03-....json
"""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapturedSearch:
    query: dict[str, Any]
    depends_on_my_charms: bool


def language_folders(languages_dir: Path) -> list[str]:
    """Language folders in the order the GUI lists them (NTFS name order).

    ``Directory::GetDirectories`` returns NTFS order, which compares names
    case-insensitively, so "English (TeamHGG)" sorts before "English (TMO)".
    """
    folders = sorted(
        (path.name for path in languages_dir.iterdir() if path.is_dir()), key=str.upper
    )
    return folders


def read_bool(line: str) -> bool:
    if line not in ("True", "False"):
        raise ValueError(f"expected True or False, got {line!r}")
    return line == "True"


def parse_capture(capture_dir: Path, repo_root: Path) -> CapturedSearch:
    """Read a capture's settings.cfg (version 2, Form1.h:464-493).

    Lines 1-14 are options. Lines 15-38 hold, for each of the 6 skill
    drop-downs: blademaster filter, blademaster skill, gunner filter, gunner
    skill, where skills are indices into Skill::static_skills (-1 if empty).
    Every later line is a solution.
    """
    lines = (capture_dir / "settings.cfg").read_text(encoding="utf-8").splitlines()
    if lines[0] != "2":
        raise ValueError(f"unsupported settings.cfg version {lines[0]!r}")

    language = language_folders(repo_root / "legacy" / "Run" / "Data" / "Languages")[int(lines[1])]
    # Line 3 records which tab the last search ran on; line 4 is merely the tab now showing.
    gunner = read_bool(lines[2])
    # The Charms drop-down, in its item order (Form1.h:1293-1373).
    charm_mode = ["none", "my_charms", "slotted", "one_skill", "two_skill"][int(lines[10])]

    skill_lines = lines[14:38]
    skill_column = 3 if gunner else 1
    skills = [int(skill_lines[i * 4 + skill_column]) for i in range(6)]
    skills = [index for index in skills if index >= 0]

    golden_data = repo_root / "tests" / "golden" / "data"
    with gzip.open(golden_data / "names" / f"{language}.json.gz", "rt", encoding="utf-8") as handle:
        names = json.load(handle)
    with gzip.open(golden_data / "game-data.json.gz", "rt", encoding="utf-8") as handle:
        game_data = json.load(handle)

    auto_guard_abilities = {
        ability["static_index"] for ability in game_data["abilities"] if ability["auto_guard"]
    }
    has_auto_guard = any(
        game_data["skills"][index]["ability"] in auto_guard_abilities for index in skills
    )
    depends_on_my_charms = charm_mode == "my_charms" or (charm_mode != "none" and has_auto_guard)

    my_charms: list[str] = []
    if depends_on_my_charms:
        my_charms_text = (capture_dir / "mycharms.txt").read_text(encoding="utf-8")
        my_charms = [line for line in my_charms_text.splitlines() if line]

    solution_count = sum(1 for line in lines[38:] if line)
    query = {
        "language": language,
        "hunter_type": "gunner" if gunner else "blademaster",
        "gender": "male" if read_bool(lines[4]) else "female",
        "hr": int(lines[11]),
        "elder_star": int(lines[12]),
        "weapon_slots": int(lines[13]),
        "allow_bad": read_bool(lines[5]),
        "include_piercings": read_bool(lines[6]),
        "allow_event": read_bool(lines[7]),
        "allow_low_rank": read_bool(lines[8]),
        "charm_mode": charm_mode,
        "skills": skills,
        "skill_names": [names["skills"][index] for index in skills],
        "my_charms": my_charms,
        "gui_solution_count": solution_count,
        "gui_capture": capture_dir.name,
    }
    captured = CapturedSearch(query=query, depends_on_my_charms=depends_on_my_charms)
    return captured


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    captured = parse_capture(args.capture_dir.resolve(), repo_root)
    personal_dir = (repo_root / "tests" / "savefile").resolve()
    if captured.depends_on_my_charms and personal_dir not in args.out.resolve().parents:
        raise SystemExit(f"this query uses the personal charm list: write it under {personal_dir}")

    query = {"id": args.id, "description": args.description, **captured.query}
    args.out.write_text(json.dumps(query, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    personal = " (personal)" if captured.depends_on_my_charms else ""
    summary = (
        f"{query['charm_mode']}, {len(query['skills'])} skills, "
        f"{query['gui_solution_count']} GUI solutions{personal}"
    )
    print(f"wrote {args.out}: {summary}")


if __name__ == "__main__":
    main()
