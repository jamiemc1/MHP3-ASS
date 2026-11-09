"""A search's result list, its duplicate removal, and the lines it is saved as.

Ported from ``Form1::HashArmor``, ``SolutionExists``, ``AddSolution( String^,
Solution^ )`` and ``AddSolutions`` (``legacy/Form1.h:1691-1746``), as the
harness's ``ResultSet`` (``harness/src/SearchDump.cpp``) collects them, and
from the solution lines of ``Form1::SaveConfig`` (``legacy/Form1.h:495-538``)
with the harness's hashes over them.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import Armor, Charm, Skill
from mhp3ass.query import Query
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


def hash_armor(armors: Sequence[Armor | None]) -> int:
    """``HashArmor`` (Form1.h:1691-1699): each slot's armour index shifted by
    three bits per slot, summed.

    The shifts overlap (indices go up to 225), so different armour sets can
    share a hash (quirk 4). The original shifts a 32-bit ``unsigned``, which
    would only overflow for an index of 2**20 or more. It dereferences every
    slot, so an empty one throws.
    """
    total = 0
    for slot, armor in enumerate(armors):
        if armor is None:
            raise LegacyNullReferenceError(f"HashArmor dereferences the empty slot {slot}")
        total += armor.index << (slot * 3)
    return total


@dataclass
class ResultSet:
    """``Form1``'s ``all_solutions`` and ``existing_armor`` for one search.

    Charmed solutions are kept once per (charm name, armour hash), the first
    one to arrive (quirk 5: which one depends on arrival order); charm-free
    solutions are always kept. ``existing_armor`` persists across calls, as
    the original only clears it when a new search starts (Form1.h:1257).

    Loading saved results (``LoadConfig``, Form1.h:342-379, :430-433) reuses
    ``add_solution`` on the same keys: it empties the solution list but not
    ``existing_armor``, and files charm-free lines outside ``all_solutions``,
    so it calls ``add_solution`` itself rather than ``add_solutions``.
    """

    all_solutions: list[Solution] = field(default_factory=list)
    existing_armor: dict[str, set[int]] = field(default_factory=dict)

    def _solution_exists(self, name: str, solution: Solution) -> bool:
        """``SolutionExists`` (Form1.h:1701-1721): records the hash if it is new."""
        # The original adds the charm's entry before hashing, so it stays even
        # when HashArmor throws.
        hashes = self.existing_armor.setdefault(name, set())
        armor_hash = hash_armor(solution.armors)
        if armor_hash in hashes:
            return True
        hashes.add(armor_hash)
        return False

    def add_solution(self, name: str, solution: Solution) -> bool:
        """``AddSolution( String^, Solution^ )`` (Form1.h:1723-1730): keep
        ``solution`` under the charm name ``name`` unless the key is taken."""
        if self._solution_exists(name, solution):
            return False
        self.all_solutions.append(solution)
        return True

    def add_solutions(self, solutions: Iterable[Solution]) -> list[Solution]:
        """``AddSolutions`` (Form1.h:1732-1746): the solutions it kept, in order.

        The key is the charm's name after ``MatchesQuery`` reduced it, so
        different templates can meet on one name. A charm ``MatchesQuery``
        removed makes the solution charm-free. If ``hash_armor`` throws, the
        solutions added before it stay in ``all_solutions``.
        """
        added = []
        for solution in solutions:
            if solution.charm is None:
                self.all_solutions.append(solution)
                added.append(solution)
            elif self.add_solution(charm_name(solution.charm), solution):
                added.append(solution)
        return added


def solution_line(solution: Solution, skill_index: dict[Skill, int]) -> str:
    """One solution line as ``SearchDump``'s ``SolutionLine`` writes it (the
    ``settings.cfg`` format, Form1.h:495-538, without the newline).

    Every field ends in a space: the armour indices (-1 for an empty slot),
    total and per-size spare slots, the decorations, the extra skills, then
    the charm's slots and pairs when it has one. ``skill_index`` maps each
    skill to its position in the game's skill list.
    """
    fields = [str(armor.index if armor is not None else -1) for armor in solution.armors]
    slots_spare = solution.slots_spare
    if slots_spare is None:
        raise ValueError("a solution line needs the slots MatchesQuery counted")
    fields.append(str(solution.total_slots_spare))
    fields += [str(slots_spare[size]) for size in (1, 2, 3)]
    fields.append(str(len(solution.decorations)))
    fields += [str(decoration.index) for decoration in solution.decorations]
    fields.append(str(len(solution.extra_skills)))
    fields += [str(skill_index[skill]) for skill in solution.extra_skills]
    charm = solution.charm
    if charm is not None:
        fields += [str(charm.num_slots), str(len(charm.abilities))]
        for pair in charm.abilities:
            fields += [str(pair.amount), str(pair.ability.static_index)]
    line = "".join(f"{field} " for field in fields)
    return line


def lines_sha256(lines: Iterable[str]) -> str:
    """The harness's ``LinesSha256`` (``SearchDump.cpp``): SHA-256 of the lines'
    UTF-8 text, each ending in a newline."""
    text = "".join(f"{line}\n" for line in lines)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest


@dataclass(frozen=True)
class SearchException:
    """A worker that threw, recorded as the harness's ``--record-exceptions``
    does: the worker's number and the .NET exception the original raises.
    ``template`` is the worker's charm template, for messages; manifests
    don't record it."""

    worker: int
    type: str
    message: str
    template: Charm | None = None


@dataclass(frozen=True)
class WorkerResult:
    """One worker's run: its charm template (``None`` for charm-free), every
    solution it found in loop order, and the ones duplicate removal kept."""

    template: Charm | None
    found: list[Solution]
    added: list[Solution]


@dataclass(frozen=True)
class SearchResult:
    """Everything one search produced, in the harness's terms.

    ``workers`` holds the workers that finished: with a recorded exception,
    the throwing worker and those after it are missing, while
    ``worker_count`` still counts every worker the search started.
    """

    query: Query
    my_charms_loaded: int
    my_charms_illegal: int
    worker_count: int
    workers: list[WorkerResult]
    results: ResultSet
    exceptions_recorded: bool
    exception: SearchException | None


def skill_indices(game: GameData) -> dict[Skill, int]:
    """Each skill's position in the game's skill list, as solution lines number them."""
    indices = {skill: index for index, skill in enumerate(game.skills)}
    return indices


def solution_lines(result: SearchResult, game: GameData) -> list[str]:
    """The kept solutions' lines, in the order they were kept."""
    skill_index = skill_indices(game)
    lines = [solution_line(solution, skill_index) for solution in result.results.all_solutions]
    return lines


@dataclass(frozen=True)
class CandidateLine:
    """A solution one worker found, before duplicate removal (``--candidates``)."""

    worker: int
    # The solution's charm name after MatchesQuery, "" when it has no charm.
    charm_name: str
    solution_line: str


def candidate_lines(result: SearchResult, game: GameData) -> list[CandidateLine]:
    """Every solution each finished worker found, in worker and loop order."""
    skill_index = skill_indices(game)
    candidates = [
        CandidateLine(
            worker=number,
            charm_name="" if solution.charm is None else charm_name(solution.charm),
            solution_line=solution_line(solution, skill_index),
        )
        for number, worker in enumerate(result.workers)
        for solution in worker.found
    ]
    return candidates


def search_manifest(
    spec_json: dict[str, Any], result: SearchResult, game: GameData, max_solution_lines: int = -1
) -> dict[str, Any]:
    """The harness's ``<prefix>.manifest.json`` for ``result`` (``SearchDump::Run``),
    fields in its order.

    ``query_json`` is a compact re-serialisation of ``spec_json``, not the
    harness's byte for byte, so compare it parsed. ``max_solution_lines``
    below 0 means no limit; above it ``solutions_file`` is false. The kept
    solutions are the workers' added ones in worker order, so their lines
    are those of ``solution_lines``.
    """
    skill_index = skill_indices(game)
    workers = []
    lines: list[str] = []
    for number, worker in enumerate(result.workers):
        added_lines = [solution_line(solution, skill_index) for solution in worker.added]
        lines += added_lines
        workers.append(
            {
                "worker": number,
                "charm": None if worker.template is None else charm_name(worker.template),
                "found": len(worker.found),
                "added": len(worker.added),
                "added_sha256": lines_sha256(added_lines),
            }
        )
    manifest: dict[str, Any] = {
        "id": spec_json["id"],
        "query_json": json.dumps(spec_json, ensure_ascii=False, separators=(",", ":")),
        "my_charms_loaded": result.my_charms_loaded,
        "my_charms_illegal": result.my_charms_illegal,
        "relevant_armor_counts": [len(slot) for slot in result.query.rel_armor],
        "relevant_decoration_count": len(result.query.rel_decorations),
        "worker_count": result.worker_count,
        "workers": workers,
        "solution_count": len(lines),
        "solutions_sha256": lines_sha256(lines),
        # The harness sorts ordinally (UTF-16 code units); the lines are ASCII.
        "solution_set_sha256": lines_sha256(sorted(lines)),
        "solutions_file": max_solution_lines < 0 or len(lines) <= max_solution_lines,
    }
    if result.exceptions_recorded:
        exception = result.exception
        manifest["exception"] = (
            None
            if exception is None
            else {"worker": exception.worker, "type": exception.type, "message": exception.message}
        )
    return manifest


def _json_string(text: str) -> str:
    """``JsonWriter::Escape`` (``harness/src/Json.h``): quotes, backslashes and
    \\n \\r \\t escaped by name, anything else outside printable ASCII as a
    lower-case ``\\u`` escape of its UTF-16 code unit."""
    escaped = ['"']
    named = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for character in text:
        code = ord(character)
        if character in named:
            escaped.append(named[character])
        elif 0x20 <= code <= 0x7E:
            escaped.append(character)
        elif code > 0xFFFF:
            surrogates = character.encode("utf-16-be")
            high = int.from_bytes(surrogates[:2], "big")
            low = int.from_bytes(surrogates[2:], "big")
            escaped.append(f"\\u{high:04x}\\u{low:04x}")
        else:
            escaped.append(f"\\u{code:04x}")
    escaped.append('"')
    text_literal = "".join(escaped)
    return text_literal


def _json_value(value: Any, depth: int) -> str:
    """One value in ``JsonWriter``'s layout: two-space indent, ``"key": value``,
    empty containers as ``{}`` and ``[]``."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _json_string(value)
    inner = "\n" + "  " * (depth + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        members = [
            f"{_json_string(key)}: {_json_value(item, depth + 1)}" for key, item in value.items()
        ]
        text = "{" + inner + ("," + inner).join(members) + "\n" + "  " * depth + "}"
        return text
    if isinstance(value, list):
        if not value:
            return "[]"
        elements = [_json_value(item, depth + 1) for item in value]
        text = "[" + inner + ("," + inner).join(elements) + "\n" + "  " * depth + "]"
        return text
    raise TypeError(f"no JSON form for {value!r}")


def manifest_text(manifest: dict[str, Any]) -> str:
    """A manifest as the harness's ``JsonWriter`` writes it, ending in a newline."""
    text = _json_value(manifest, depth=0) + "\n"
    return text


def gzip_lines(lines: Iterable[str]) -> bytes:
    """A lines file as ``FixtureFiles::WriteText`` writes it: UTF-8, each line
    ending in ``\\n``, gzip-compressed; no lines gives RFC 1952's empty member
    (which the harness writes by hand, since .NET's ``GZipStream`` writes nothing)."""
    text = "".join(f"{line}\n" for line in lines)
    if text == "":
        empty_member = bytes(
            [0x1F, 0x8B, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF] + [0x03, 0x00] + [0x00] * 8
        )
        return empty_member
    # mtime=0 keeps the output the same from run to run.
    compressed = gzip.compress(text.encode("utf-8"), mtime=0)
    return compressed


def write_search_outputs(
    prefix: Path,
    manifest: dict[str, Any],
    lines: list[str],
    candidates: list[CandidateLine] | None,
) -> None:
    """The harness's ``search`` outputs for ``prefix``: ``.solutions.txt.gz``
    (removed instead when the manifest says no solutions file), when given
    ``.candidates.txt.gz``, then ``.manifest.json``. The manifest goes last,
    so a new manifest means the files it describes were written."""
    solutions_path = Path(f"{prefix}.solutions.txt.gz")
    if manifest["solutions_file"]:
        solutions_path.write_bytes(gzip_lines(lines))
    else:
        solutions_path.unlink(missing_ok=True)
    if candidates is not None:
        rows = [
            f"{candidate.worker}\t{candidate.charm_name}\t{candidate.solution_line}"
            for candidate in candidates
        ]
        Path(f"{prefix}.candidates.txt.gz").write_bytes(gzip_lines(rows))
    Path(f"{prefix}.manifest.json").write_bytes(manifest_text(manifest).encode("utf-8"))
