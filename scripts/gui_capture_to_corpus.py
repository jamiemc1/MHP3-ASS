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

from mhp3ass.settings_cfg import read_settings_cfg


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


def parse_capture(capture_dir: Path, repo_root: Path) -> CapturedSearch:
    """Build a corpus query from a capture's settings.cfg."""
    settings = read_settings_cfg(capture_dir / "settings.cfg")
    languages_dir = repo_root / "legacy" / "Run" / "Data" / "Languages"
    language = language_folders(languages_dir)[settings.language_index]
    # The tab the last search ran on, not the one showing when the file was saved.
    gunner = settings.last_search_gunner
    # The Charms drop-down, in its item order (Form1.h:1293-1373).
    charm_modes = ["none", "my_charms", "slotted", "one_skill", "two_skill"]
    charm_mode = charm_modes[settings.charm_select_index]

    selected = [
        selection.gunner_skill if gunner else selection.blademaster_skill
        for selection in settings.skill_selections
    ]
    skills = [index for index in selected if index >= 0]

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
    # One- and two-skill modes run many workers whose duplicates collide across threads (quirk 5);
    # Auto-Guard replaces them with a single worker.
    order_dependent = charm_mode in ("one_skill", "two_skill") and not has_auto_guard

    my_charms: list[str] = []
    if depends_on_my_charms:
        my_charms_text = (capture_dir / "mycharms.txt").read_text(encoding="utf-8")
        my_charms = [line for line in my_charms_text.splitlines() if line]

    query = {
        "language": language,
        "hunter_type": "gunner" if gunner else "blademaster",
        "gender": "male" if settings.male else "female",
        "hr": settings.hr,
        "elder_star": settings.elder_star,
        "weapon_slots": settings.weapon_slots,
        "allow_bad": settings.allow_bad,
        "include_piercings": settings.allow_piercings,
        "allow_event": settings.allow_event,
        "allow_low_rank": settings.allow_low_rank,
        "charm_mode": charm_mode,
        "skills": skills,
        "skill_names": [names["skills"][index] for index in skills],
        "my_charms": my_charms,
        "gui_solution_count": len(settings.solution_lines),
        "gui_capture": capture_dir.name,
    }
    if order_dependent:
        query["gui_order_dependent"] = True
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
