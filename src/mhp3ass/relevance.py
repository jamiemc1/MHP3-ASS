"""What a query needs from the game data before the search starts.

Ported from ``LoadedData::GetRelevantData``, ``GetRelevantArmors``,
``GetRelevantDecorations`` and both ``AddToList`` overloads
(``legacy/LoadedData.cpp:44-167``), and the end of ``Form1::FormulateQuery``
(``legacy/Form1.h:1215``).

Like the original, this writes per-query state onto the shared game
records: every ability's ``relevant`` flag, and ``no_skills`` and ``danger``
on each matched armour piece. Run one query per freshly loaded game when
comparing with the harness, which runs each query in a new process.
"""

from __future__ import annotations

from mhp3ass.armor import armor_is_better_than, armor_matches_query
from mhp3ass.data import GameData
from mhp3ass.decorations import decoration_is_better_than, decoration_matches_query
from mhp3ass.model import Ability, Armor, ArmorType, Decoration
from mhp3ass.query import Query, QuerySpec, build_query


def _remove_first[T](items: list[T], item: T) -> None:
    """.NET ``List.Remove``: drops the first occurrence (by identity here), if any."""
    index = next((position for position, entry in enumerate(items) if entry is item), None)
    if index is not None:
        del items[index]


def _add_decoration(
    decorations: list[Decoration], decoration: Decoration, inferior: list[Decoration]
) -> None:
    """``AddToList`` for decorations (LoadedData.cpp:44-58).

    The new decoration removes listed ones it beats that don't also beat it,
    and is dropped if a listed one beats it. Once listed it stays on
    ``inferior`` even if later removed.
    """
    index = 0
    while index < len(decorations):
        listed = decorations[index]
        if decoration_is_better_than(decoration, listed):
            if not decoration_is_better_than(listed, decoration):
                del decorations[index]
                continue
        elif decoration_is_better_than(listed, decoration):
            return
        index += 1
    decorations.append(decoration)
    inferior.append(decoration)


def _add_armor(
    armors: list[Armor], armor: Armor, rel_abilities: list[Ability], inferior: list[Armor]
) -> None:
    """``AddToList`` for armour (LoadedData.cpp:60-82).

    As for decorations, but ``inferior`` keeps every piece with skills that
    was listed or beaten, while a skill-less piece is on it only while
    listed. A piece with a danger skill only displaces or is displaced by a
    piece with the same one.
    """
    index = 0
    while index < len(armors):
        listed = armors[index]
        if armor_is_better_than(armor, listed, rel_abilities):
            same_danger = armor.danger is None or armor.danger is listed.danger
            if same_danger and not armor_is_better_than(listed, armor, rel_abilities):
                if listed.no_skills:
                    _remove_first(inferior, listed)
                del armors[index]
                continue
        elif (listed.danger is None or listed.danger is armor.danger) and armor_is_better_than(
            listed, armor, rel_abilities
        ):
            if not armor.no_skills:
                inferior.append(armor)
            return
        index += 1
    armors.append(armor)
    inferior.append(armor)


def _get_relevant_armors(
    query: Query,
    relevant: list[Armor],
    armors: list[Armor],
    inferior: list[Armor],
    danger_skills: list[Ability],
) -> None:
    """``GetRelevantArmors`` (LoadedData.cpp:84-95).

    ``max_slots`` is a running maximum over matched pieces in load order, so
    whether a skill-less piece is kept depends on the pieces before it.
    """
    max_slots = 0
    for armor in armors:
        if armor_matches_query(armor, query, danger_skills=danger_skills, max_slots=max_slots):
            max_slots = max(max_slots, armor.num_slots)
            _add_armor(relevant, armor, rel_abilities=query.rel_abilities, inferior=inferior)


def _get_relevant_decorations(game: GameData, query: Query) -> None:
    """``GetRelevantDecorations`` (LoadedData.cpp:97-111): per query skill, its
    decorations in load order."""
    for skill in query.skills:
        if skill.ability not in game.decorations_by_ability:
            continue
        for decoration in game.decorations_by_ability[skill.ability]:
            if decoration_matches_query(decoration, query):
                _add_decoration(query.rel_decorations, decoration, inferior=query.inf_decorations)


def get_relevant_data(game: GameData, query: Query) -> None:
    """``LoadedData::GetRelevantData`` (LoadedData.cpp:121-167).

    Fills the query's relevant abilities, decorations and armour and sets
    the abilities' ``relevant`` flags. The danger-skill list stays empty: the
    code that filled it is commented out in the original (:141-158).
    """
    for ability in game.abilities:
        ability.relevant = False
    danger_skills: list[Ability] = []
    for skill in query.skills:
        query.rel_abilities.append(skill.ability)
        skill.ability.relevant = True
    _get_relevant_decorations(game, query)
    for armor_type in ArmorType:
        _get_relevant_armors(
            query,
            relevant=query.rel_armor[armor_type.value],
            armors=game.armors[armor_type],
            inferior=query.inf_armor[armor_type.value],
            danger_skills=danger_skills,
        )


def formulate_query(game: GameData, spec: QuerySpec) -> Query:
    """``Form1::FormulateQuery`` (Form1.h:1184-1216): build the query, then
    ``GetRelevantData``."""
    query = build_query(game, spec)
    get_relevant_data(game, query)
    return query
