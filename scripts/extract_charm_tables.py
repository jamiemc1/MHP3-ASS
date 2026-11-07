"""Write ``src/mhp3ass/charms/tables.py`` from ``OmaSkill`` in ``legacy/CharmDatabase.cpp``.

The tables are committed so the port never reads the C++ at runtime. The
output is already ruff-formatted; ``--check`` compares it with the committed
module instead of writing it (a test runs this).

Usage:
    uv run python scripts/extract_charm_tables.py [--check]
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Initialiser:
    values: list
    first_line: int
    last_line: int


def parse_initialiser(lines: list[str], name: str) -> Initialiser:
    """Parse ``static array<...> NAME = { ... };`` into nested lists, with its 1-based lines."""
    start = next(i for i, line in enumerate(lines) if re.search(rf"\b{name}\s*=", line))
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "};")
    body = "".join(re.sub(r"//.*", "", line) for line in lines[start : end + 1])
    braces = body[body.index("{") : body.rindex("}") + 1]
    as_json = re.sub(r",\s*]", "]", braces.replace("{", "[").replace("}", "]"))
    initialiser = Initialiser(values=json.loads(as_json), first_line=start + 1, last_line=end + 1)
    return initialiser


def tuple_literal(value: list, indent: int) -> str:
    pad = "    " * indent
    if value and isinstance(value[0], list):
        inner = ",\n".join(f"{pad}    {tuple_literal(item, indent + 1).lstrip()}" for item in value)
        return f"{pad}(\n{inner},\n{pad})"
    numbers = ", ".join(str(number) for number in value)
    trailing = "," if len(value) == 1 else ""
    return f"{pad}({numbers}{trailing})"


def render_module(slot_thresholds: Initialiser, skill_tables: Initialiser) -> str:
    slot_lines = f"{slot_thresholds.first_line}-{slot_thresholds.last_line}"
    skill_lines = f"{skill_tables.first_line}-{skill_tables.last_line}"
    table_type = "tuple[tuple[tuple[int, ...], ...], ...]"
    module = f'''"""The game's charm generation tables.

Extracted from ``OmaSkill`` in ``legacy/CharmDatabase.cpp`` by
``scripts/extract_charm_tables.py``; do not edit by hand. The charm-database
golden verifies them.
"""

from __future__ import annotations

# OmaSkill::FURUSLO (CharmDatabase.cpp:{slot_lines}): per charm kind (omakbn: 0 timeworn,
# 1 shining, 2 mystery), per rank point, the cumulative slot thresholds for rndChange(n).
SLOT_THRESHOLDS: {table_type} = {tuple_literal(slot_thresholds.values, 0)}

# OmaSkill::SKILL (CharmDatabase.cpp:{skill_lines}), indexed by FURU1, FURU2, HIKA1, HIKA2,
# NAZO1. Rows are (ordered ability index, min points, max points).
SKILL_TABLES: {table_type} = {tuple_literal(skill_tables.values, 0)}
'''
    return module


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="fail if the committed module differs")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source = (repo_root / "legacy" / "CharmDatabase.cpp").read_bytes().decode("utf-16")
    lines = source.splitlines()
    slot_thresholds = parse_initialiser(lines, "FURUSLO")
    skill_tables = parse_initialiser(lines, "SKILL")
    module = render_module(slot_thresholds, skill_tables)
    output = repo_root / "src" / "mhp3ass" / "charms" / "tables.py"
    if args.check:
        if output.read_text(encoding="utf-8") != module:
            raise SystemExit(
                f"{output.relative_to(repo_root)} differs from legacy/CharmDatabase.cpp"
            )
        print(f"{output.relative_to(repo_root)} matches legacy/CharmDatabase.cpp")
        return
    output.write_text(module, encoding="utf-8")
    print(f"wrote {output.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
