"""The user's charm list, ``Data/mycharms.txt``.

Ported from ``CharmDatabase::LoadCustom`` and ``CharmDatabase::SaveCustom``
(``legacy/CharmDatabase.cpp:90-168``), plus the harness's stricter reading of
a query file's charm lines (``harness/src/Workers.cpp``). Each of the original's message boxes
becomes a per-line outcome. Where the original lets an exception escape
``LoadCustom`` (an unreadable slot count, a field ``RemoveQuotes`` can't
handle, a charm with four or more slots), the GUI fails to start; this
raises ``MyCharmsFileError`` instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData
from mhp3ass.data.text import read_lines, split_fields, to_int32, to_uint32
from mhp3ass.model import AbilityPair, Charm


class LineOutcome(Enum):
    """What ``LoadCustom`` did with a line; all but ``ACCEPTED`` show a message box."""

    ACCEPTED = "accepted"
    # The charm isn't one the game can produce; one "cheater" message follows the file.
    REJECTED = "rejected"
    WRONG_FIELD_COUNT = "wrong_field_count"
    NO_SUCH_SKILL = "no_such_skill"
    BAD_POINTS = "bad_points"


@dataclass(frozen=True)
class LoadedLine:
    line: str
    outcome: LineOutcome


@dataclass
class LoadedMyCharms:
    lines: list[LoadedLine] = field(default_factory=list)
    charms: list[Charm] = field(default_factory=list)
    # The original shows its "cheater" message once, after the whole file.
    cheater_message: bool = False


class MyCharmsFileError(Exception):
    """Loading stopped where the original's ``LoadCustom`` throws."""

    def __init__(self, line: str, cause: Exception):
        super().__init__(f"can't load my-charms line {line!r}: {cause}")
        self.line = line
        self.cause = cause


class _SkillColumnsFailed(Exception):
    """A skill column the original answers with a message box, then skips the line."""

    def __init__(self, outcome: LineOutcome, message: str):
        super().__init__(message)
        self.outcome = outcome
        self.message = message


def _read_points(fields: list[str], game: GameData) -> list[AbilityPair]:
    """The skill columns (CharmDatabase.cpp:129-156); raises ``_SkillColumnsFailed``."""
    pairs = []
    for name_field, points_field in ((1, 2), (3, 4)):
        if fields[name_field] == "":
            continue
        ability = game.ability_map.get(fields[name_field])
        if ability is None:
            raise _SkillColumnsFailed(
                LineOutcome.NO_SUCH_SKILL, message=f'"{fields[name_field]}": No such skill'
            )
        try:
            amount = to_int32(fields[points_field])
        except ValueError, OverflowError:
            raise _SkillColumnsFailed(
                LineOutcome.BAD_POINTS, message="Could not read skill points"
            ) from None
        pairs.append(AbilityPair(ability=ability, amount=amount))
    return pairs


def load_my_charms(path: Path, game: GameData, validity: CharmValidity) -> LoadedMyCharms:
    """``LoadCustom`` over the file at ``path``; see ``load_my_charm_lines``."""
    loaded = load_my_charm_lines(read_lines(path), game=game, validity=validity)
    return loaded


def load_query_my_charms(
    lines: Sequence[str], game: GameData, validity: CharmValidity
) -> LoadedMyCharms:
    """A query file's ``my_charms``, as the harness's ``LoadMyCharms``
    (``harness/src/Workers.cpp``) reads them: ``LoadCustom``, except that a
    line ``LoadCustom`` answers with a message box (wrong field count, unknown
    skill, unreadable points) raises ``MyCharmsFileError``. Rejected charms
    are still skipped; ``my_charms_illegal`` counts them."""
    loaded = load_my_charm_lines(lines, game=game, validity=validity, stop_at_message=True)
    return loaded


def my_charms_illegal(loaded: LoadedMyCharms) -> int:
    """How many charms were rejected as ones the game can't produce."""
    count = sum(1 for line in loaded.lines if line.outcome is LineOutcome.REJECTED)
    return count


def _message_box(
    loaded: LoadedMyCharms, line: str, outcome: LineOutcome, message: str, stop_at_message: bool
) -> None:
    """A line ``LoadCustom`` answers with a message box and skips; with
    ``stop_at_message`` it raises instead, as the harness's ``LoadMyCharms``."""
    if stop_at_message:
        raise MyCharmsFileError(line, ValueError(message))
    loaded.lines.append(LoadedLine(line=line, outcome=outcome))


def load_my_charm_lines(
    lines: Sequence[str], game: GameData, validity: CharmValidity, stop_at_message: bool = False
) -> LoadedMyCharms:
    """``LoadCustom``: every line's outcome and the charms kept, in line order.

    Skill names are looked up in ``game``'s current language. A blank first
    skill with a filled second makes the second the charm's only skill. With
    ``stop_at_message``, a line that would show a message box raises
    ``MyCharmsFileError`` instead of being skipped.
    """
    loaded = LoadedMyCharms()
    for line in lines:
        if line == "" or line[0] == "#":
            continue
        try:
            fields = split_fields(line)
        except ValueError as error:
            raise MyCharmsFileError(line, error) from error
        if len(fields) != 5:
            _message_box(
                loaded,
                line=line,
                outcome=LineOutcome.WRONG_FIELD_COUNT,
                message="Incorrect number of commas",
                stop_at_message=stop_at_message,
            )
            continue
        try:
            num_slots = to_uint32(fields[0])
        except (ValueError, OverflowError) as error:
            raise MyCharmsFileError(line, error) from error
        try:
            pairs = _read_points(fields, game)
        except _SkillColumnsFailed as failure:
            _message_box(
                loaded,
                line=line,
                outcome=failure.outcome,
                message=failure.message,
                stop_at_message=stop_at_message,
            )
            continue
        charm = Charm(num_slots=num_slots, abilities=pairs)
        try:
            # CharmIsIllegal only runs when the hash isn't known, as the original's ||.
            valid = validity.exists(charm) or not validity.is_illegal(charm)
        except IndexError as error:
            raise MyCharmsFileError(line, error) from error
        if valid:
            charm.custom = True
            loaded.charms.append(charm)
            loaded.lines.append(LoadedLine(line=line, outcome=LineOutcome.ACCEPTED))
        else:
            loaded.cheater_message = True
            loaded.lines.append(LoadedLine(line=line, outcome=LineOutcome.REJECTED))
    return loaded


def my_charms_text(charms: list[Charm]) -> str:
    """``SaveCustom``'s file contents: a format comment, then one line per charm, CRLF.

    Only the first two skills are written; a missing one is ``,,``.
    """
    lines = ["#Format: NumSlots,Skill1,Points1,Skill2,Points2"]
    for charm in charms:
        columns = [str(charm.num_slots)]
        for index in range(2):
            if index < len(charm.abilities):
                pair = charm.abilities[index]
                columns.append(f"{pair.ability.name},{pair.amount}")
            else:
                columns.append(",")
        lines.append(",".join(columns))
    text = "".join(f"{line}\r\n" for line in lines)
    return text


def save_my_charms(path: Path, charms: list[Charm]) -> None:
    """``SaveCustom``: UTF-8 without a byte order mark, as ``StreamWriter( path )`` writes."""
    path.write_bytes(my_charms_text(charms).encode("utf-8"))
