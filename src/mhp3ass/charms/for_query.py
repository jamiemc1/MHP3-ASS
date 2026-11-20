"""The charms one- and two-skill charm modes search with.

Ported from ``CharmDatabase::GetCharms`` and the file-local ``::GetCharms``
(``legacy/CharmDatabase.cpp:11-86``).
"""

from __future__ import annotations

from mhp3ass.charms.generation import CharmTables
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.query import Query


def _one_skill_charms(query: Query, tables: CharmTables, max_slots: int) -> list[Charm]:
    """``::GetCharms`` (CharmDatabase.cpp:11-39).

    Per query skill, from ``max_slots`` slots down to none: the most points
    any charm type below ``max_slots`` reaches with that many slots (types in
    table order: mystery, shining, timeworn). The slot-less charm is skipped
    unless it beats the one-slot one. A slot count with no charm for the
    skill still adds a skill-less charm, so the list can repeat one.
    ``max_slots`` is at least 1, so the one-slot count is always seen
    before the slot-less one.
    """
    charms: list[Charm] = []
    for skill in query.skills:
        one_slot_max = 0
        for slots in range(max_slots, -1, -1):
            slot_max = 0
            for charm_type in range(max_slots):
                points_by_ability = tables.max_points[charm_type][slots]
                if skill.ability in points_by_ability:
                    slot_max = max(slot_max, points_by_ability[skill.ability])
            if slots == 1:
                one_slot_max = slot_max
            if slots == 0 and slot_max <= one_slot_max:
                continue
            charm = Charm(num_slots=slots)
            if slot_max:
                charm.abilities.append(AbilityPair(ability=skill.ability, amount=slot_max))
            charms.append(charm)
    return charms


def get_charms(query: Query, tables: CharmTables, use_two_skill_charms: bool) -> list[Charm]:
    """``CharmDatabase::GetCharms`` (CharmDatabase.cpp:41-86).

    Two-skill mode returns the table's own charm objects for every pair of
    query skills, at any HR. One-skill mode unlocks charm types by HR: one
    below HR 4, two at HR 4, three from HR 5. Either way a bare slotted
    charm for the HR (1, 2 or 3 slots) is added if no charm has that many.
    """
    tier_slots = 1 + (query.hr >= 5) + (query.hr >= 4)
    if use_two_skill_charms:
        charms: list[Charm] = []
        skills = query.skills
        for i in range(len(skills)):
            for j in range(i):
                charms.extend(tables.two_skill[skills[i].ability][skills[j].ability])
    else:
        charms = _one_skill_charms(query, tables=tables, max_slots=tier_slots)

    if not any(charm.num_slots == tier_slots for charm in charms):
        charms.append(Charm(num_slots=tier_slots))
    return charms
