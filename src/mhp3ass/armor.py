"""Matching and comparing armour pieces for a query.

Ported from ``Armor::MatchesQuery``, ``Armor::IsBetterThan`` and
``Armor::GetSkillAt`` (``legacy/Armor.cpp:105-175``).
"""

from __future__ import annotations

from mhp3ass.model import Ability, Armor, Gender, HunterType
from mhp3ass.query import Query, rank_locked


def armor_skill_at(armor: Armor, ability: Ability) -> int:
    """``Armor::GetSkillAt``: the piece's points in ``ability``, or 0."""
    points = next((pair.amount for pair in armor.abilities if pair.ability is ability), 0)
    return points


def _meets_requirements(armor: Armor, query: Query) -> bool:
    """The availability checks at the top of ``MatchesQuery`` (Armor.cpp:108-114).

    A piece needs only one of HR and village stars to be high enough.
    """
    excluded = (
        (not query.include_piercings and armor.is_piercing)
        or (not query.allow_event and armor.is_event)
        or (not query.allow_low_rank and armor.hr < 4)
        or (
            armor.hunter_type is not HunterType.BOTH_TYPES
            and query.hunter_type is not armor.hunter_type
        )
        or (armor.gender is not Gender.BOTH_GENDERS and armor.gender is not query.gender)
        or rank_locked(armor.hr, armor.elder_star, query)
    )
    return not excluded


def armor_matches_query(
    armor: Armor, query: Query, danger_skills: list[Ability], max_slots: int
) -> bool:
    """``Armor::MatchesQuery`` (Armor.cpp:105-145).

    Sets ``armor.danger`` and ``armor.no_skills`` as the original does, except
    on torso-up pieces, which return before either is written. ``max_slots``
    is the most slots among pieces already matched in this slot.

    Quirk 6: ``bad_skills`` is only ever set to ``False`` (Armor.cpp:140), so
    a piece whose relevant points are all negative counts as skill-less.
    """
    if not _meets_requirements(armor, query):
        return False
    if armor.torso_inc:
        return True
    armor.danger = next(
        (
            pair.ability
            for pair in armor.abilities
            if pair.amount < 0 and pair.ability in danger_skills
        ),
        None,
    )
    armor.no_skills = True
    bad_skills = False
    for pair in armor.abilities:
        if pair.ability in query.rel_abilities:
            if pair.amount > 0:
                armor.no_skills = False
                return True
            bad_skills = False
    if armor.num_slots == max_slots:
        matches = armor.danger is None and not bad_skills
        return matches
    matches = armor.num_slots > max_slots and armor.danger is None
    return matches


def armor_is_better_than(armor: Armor, other: Armor, rel_abilities: list[Ability]) -> bool:
    """``Armor::IsBetterThan`` (Armor.cpp:147-167).

    Not a strict order: two pieces can each be better than the other (more
    points in different relevant abilities, or one torso-up piece against
    another piece), and full ties are better neither way.
    """
    if armor.num_slots > other.num_slots:
        return True
    if armor.no_skills and other.no_skills:
        if armor.defence == other.defence:
            return armor.rarity > other.rarity
        return armor.defence > other.defence
    if armor.torso_inc and other.torso_inc:
        if armor.rarity == other.rarity:
            return armor.defence > other.defence
        return armor.rarity > other.rarity
    if armor.torso_inc or other.torso_inc:
        return True
    better = any(
        armor_skill_at(armor, ability) > armor_skill_at(other, ability) for ability in rel_abilities
    )
    return better
