from __future__ import annotations

import pytest

from mhp3ass.model import Material, MaterialComponent
from mhp3ass.results.difficulty import hard_materials
from mhp3ass.solution.state import Solution
from solution_builders import make_jewel


def test_the_hard_materials_add_up_to_every_found_sets_difficulty(one_skill_search):
    """g13: HR 3, Attack Up + Health, one-skill charms."""
    mismatched = [
        solution
        for solution in one_skill_search.result.results.all_solutions
        if sum(part.count * part.material.difficulty for part in hard_materials(solution))
        != solution.difficulty
    ]

    assert mismatched == []


@pytest.fixture
def hard_parts_solution(make_armor, attack):
    """Head: 3 Ruby (2) and 1 Bone (0); legs: 1 Plate (5) and 2 Ruby;
    two jewels each needing 4 Ruby and an event Ticket (0)."""
    ruby = Material(name="Ruby", difficulty=2)
    plate = Material(name="Plate", difficulty=5)
    bone = Material(name="Bone")
    ticket = Material(name="Ticket", event_only=True)
    head = make_armor(
        "Head",
        components=[
            MaterialComponent(material=ruby, amount=3),
            MaterialComponent(material=bone, amount=1),
        ],
    )
    legs = make_armor(
        "Legs",
        components=[
            MaterialComponent(material=plate, amount=1),
            MaterialComponent(material=ruby, amount=2),
        ],
    )
    jewel = make_jewel("Jewel", first=attack, amount=1)
    jewel.components = [
        MaterialComponent(material=ruby, amount=4),
        MaterialComponent(material=ticket, amount=1),
    ]
    solution = Solution(
        armors=[head, None, None, None, legs], charm=None, decorations=[jewel, jewel]
    )
    return solution


def test_pieces_count_each_unit_and_jewels_each_material_once(hard_parts_solution):
    parts = hard_materials(hard_parts_solution)

    assert [(part.material.name, part.count) for part in parts] == [("Ruby", 7), ("Plate", 1)]


def test_a_set_without_hard_materials_lists_none(make_armor):
    solution = Solution(armors=[make_armor(), None, None, None, None], charm=None)

    assert hard_materials(solution) == []
