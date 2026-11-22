"""Skill thresholds against the harness's GetSkill dump (ModelDump.cpp)."""

from __future__ import annotations

from mhp3ass.model import Skill
from mhp3ass.skills import get_skill


def test_get_skill_matches_golden_for_every_ability_and_points(models_golden, teamhgg_game):
    dump = models_golden["get_skill"]
    points_range = range(dump["min_points"], dump["max_points"] + 1)
    ours = []
    for ability in teamhgg_game.abilities:
        skills = [get_skill(ability, points) for points in points_range]
        ours.append([skill.static_index if skill is not None else -1 for skill in skills])

    mismatched = [
        teamhgg_game.abilities[index].name
        for index, (row, golden_row) in enumerate(zip(ours, dump["skills"], strict=True))
        if row != golden_row
    ]

    assert mismatched == []


def test_get_skill_walks_thresholds_by_sign(make_ability):
    ability = make_ability("Attack", 0)
    for points in (15, -10, 10, 20, -20):
        ability.skills[points] = Skill(
            name=f"Attack {points}", points_required=points, ability=ability, static_index=0
        )

    names = [get_skill(ability, amount) for amount in (0, 9, 14, 25, -9, -19, -25)]

    assert [skill.name if skill is not None else None for skill in names] == [
        None,
        None,
        "Attack 10",
        "Attack 20",
        None,
        "Attack -10",
        "Attack -20",
    ]
