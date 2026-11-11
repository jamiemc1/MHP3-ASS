from __future__ import annotations

from dataclasses import replace

import pytest

from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm
from mhp3ass.skill_picker import SkillRow, SkillRowsByHunter, starting_rows


@pytest.fixture
def form_with_gunner_rows_filtered() -> QueryForm:
    """The starting form, with every Gunner row's filter set to the first tag."""
    gunner = tuple(SkillRow(filter_index=2, skill=None) for _ in range(6))
    form = replace(
        QueryForm.starting(),
        skill_rows=SkillRowsByHunter(blademaster=starting_rows(), gunner=gunner),
    )
    return form


def test_the_starting_form_has_the_originals_defaults():
    form = QueryForm.starting()

    assert form.hunter_type is HunterType.BLADEMASTER
    assert form.gender is Gender.MALE
    assert (form.hr, form.elder_star, form.weapon_slots) == (6, 6, 0)
    assert form.charm_mode is CharmMode.SLOTTED
    assert (form.allow_bad, form.allow_piercings, form.allow_event, form.allow_low_rank) == (
        False,
        True,
        True,
        True,
    )
    assert form.skill_rows == SkillRowsByHunter(blademaster=starting_rows(), gunner=starting_rows())


def test_blademaster_shows_the_blademaster_rows(form_with_gunner_rows_filtered):
    rows = form_with_gunner_rows_filtered.current_rows()

    assert rows == starting_rows()


def test_switching_to_gunner_shows_the_gunner_rows_and_keeps_both(form_with_gunner_rows_filtered):
    gunner_form = replace(form_with_gunner_rows_filtered, hunter_type=HunterType.GUNNER)

    assert gunner_form.current_rows() == form_with_gunner_rows_filtered.skill_rows.gunner
    assert gunner_form.skill_rows == form_with_gunner_rows_filtered.skill_rows


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("hunter_type", HunterType.BOTH_TYPES, "Blademaster or Gunner, not BOTH_TYPES"),
        ("gender", Gender.BOTH_GENDERS, "male or female, not BOTH_GENDERS"),
        ("hr", 0, "HR must be 1 to 6, not 0"),
        ("hr", 7, "HR must be 1 to 6, not 7"),
        ("elder_star", 0, "village must be 1 to 6, not 0"),
        ("elder_star", 7, "village must be 1 to 6, not 7"),
        ("weapon_slots", -1, "weapon slots must be 0 to 3, not -1"),
        ("weapon_slots", 4, "weapon slots must be 0 to 3, not 4"),
    ],
)
def test_values_the_controls_cant_hold_raise(field, value, message):
    with pytest.raises(ValueError, match=message):
        replace(QueryForm.starting(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [("hr", 1), ("elder_star", 1), ("weapon_slots", 3)],
)
def test_the_range_ends_are_allowed(field, value):
    form = replace(QueryForm.starting(), **{field: value})

    assert getattr(form, field) == value
