from __future__ import annotations

from dataclasses import replace

import pytest

from mhp3ass.data.strings import StringIndex
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm, charm_mode_label
from mhp3ass.skill_chips import chip_rows
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


@pytest.fixture
def misc_rows() -> tuple[SkillRow, ...]:
    """Six empty rows filtered by Misc, unlike either tab of the fixture form."""
    rows = tuple(SkillRow(filter_index=1, skill=None) for _ in range(6))
    return rows


def test_new_blademaster_rows_keep_the_gunner_tab(form_with_gunner_rows_filtered, misc_rows):
    updated = form_with_gunner_rows_filtered.with_rows(HunterType.BLADEMASTER, rows=misc_rows)

    assert updated.skill_rows == SkillRowsByHunter(
        blademaster=misc_rows, gunner=form_with_gunner_rows_filtered.skill_rows.gunner
    )


def test_new_gunner_rows_go_to_the_gunner_tab_while_blademaster_is_shown(
    form_with_gunner_rows_filtered, misc_rows
):
    updated = form_with_gunner_rows_filtered.with_rows(HunterType.GUNNER, rows=misc_rows)

    assert updated.skill_rows == SkillRowsByHunter(
        blademaster=form_with_gunner_rows_filtered.skill_rows.blademaster, gunner=misc_rows
    )
    assert updated.hunter_type is HunterType.BLADEMASTER


def test_new_rows_without_six_rows_raise():
    with pytest.raises(ValueError, match="the Blademaster tab has six skill rows, not 0"):
        QueryForm.starting().with_rows(HunterType.BLADEMASTER, rows=())


@pytest.fixture
def g19_form(teamhgg_game) -> QueryForm:
    """g19's controls (Gunner, Load Up + Accuracy+1, slotted charms), with
    Attack Up [Med] left on the Blademaster tab."""
    skill_map = teamhgg_game.skill_map
    form = QueryForm(
        hunter_type=HunterType.GUNNER,
        gender=Gender.MALE,
        hr=6,
        elder_star=6,
        weapon_slots=0,
        charm_mode=CharmMode.SLOTTED,
        allow_bad=False,
        allow_piercings=True,
        allow_event=True,
        allow_low_rank=True,
        skill_rows=SkillRowsByHunter(
            blademaster=chip_rows([skill_map["Attack Up [Med]"]]),
            gunner=chip_rows([skill_map["Load Up"], skill_map["Accuracy+1"]]),
        ),
    )
    return form


@pytest.fixture
def form_1a(teamhgg_game) -> QueryForm:
    """1a's controls: Blademaster, Attack Up [Med] + Sharp Sword, my charms."""
    skill_map = teamhgg_game.skill_map
    form = replace(
        QueryForm.starting(),
        charm_mode=CharmMode.MY_CHARMS,
        skill_rows=SkillRowsByHunter(
            blademaster=chip_rows([skill_map["Attack Up [Med]"], skill_map["Sharp Sword"]]),
            gunner=starting_rows(),
        ),
    )
    return form


def test_the_shown_tabs_search_is_the_query_files(teamhgg_game, corpus_spec, g19_form):
    expected = corpus_spec("corpus/g19-gunner-load-up-piercings-event.json")

    spec = g19_form.search_spec(
        teamhgg_game, language="English (TeamHGG)", my_charms=(), query_id="g19"
    )

    assert spec == expected


def test_the_my_charms_lines_go_into_the_search(teamhgg_game, corpus_spec, form_1a):
    expected = corpus_spec("corpus/1a-attack-sharp-default-charms.json")

    spec = form_1a.search_spec(
        teamhgg_game,
        language="English (TeamHGG)",
        my_charms=expected.my_charms,
        query_id="1a",
    )

    assert spec == expected


def test_no_skills_give_a_search_with_no_skills(teamhgg_game):
    spec = QueryForm.starting().search_spec(
        teamhgg_game, language="English (TeamHGG)", my_charms=()
    )

    assert (spec.query.skills, spec.query.skill_names) == ((), ())


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


def test_a_charm_mode_that_isnt_a_charm_mode_raises():
    with pytest.raises(ValueError, match="charm mode must be a CharmMode, not 7"):
        replace(QueryForm.starting(), charm_mode=7)


@pytest.mark.parametrize(
    ("skill_rows", "message"),
    [
        (
            SkillRowsByHunter(blademaster=starting_rows()[:5], gunner=starting_rows()),
            "the Blademaster tab has six skill rows, not 5",
        ),
        (
            SkillRowsByHunter(
                blademaster=starting_rows(), gunner=(*starting_rows(), *starting_rows())
            ),
            "the Gunner tab has six skill rows, not 12",
        ),
    ],
)
def test_a_tab_without_six_skill_rows_raises(skill_rows, message):
    with pytest.raises(ValueError, match=message):
        replace(QueryForm.starting(), skill_rows=skill_rows)


@pytest.mark.parametrize(
    ("field", "value"),
    [("hr", 1), ("elder_star", 1), ("weapon_slots", 3)],
)
def test_the_range_ends_are_allowed(field, value):
    form = replace(QueryForm.starting(), **{field: value})

    assert getattr(form, field) == value


def test_the_summary_names_the_shown_tabs_query(english_strings, form_1a):
    assert form_1a.summary(english_strings) == (
        "Blademaster ♂ · HR 6 · Village Quests 6 · Max Weapon Slots 0"
        " · Attack Up [Med], Sharp Sword · Use only my charms"
        " · Allow Piercings · Allow Event Armor · Allow Low Rank Armor"
    )


def test_the_summary_follows_the_gunner_tab_and_a_female_hunter(english_strings, g19_form):
    female = replace(g19_form, gender=Gender.FEMALE, hr=4, weapon_slots=2)

    assert female.summary(english_strings) == (
        "Gunner ♀ · HR 4 · Village Quests 6 · Max Weapon Slots 2"
        " · Load Up, Accuracy+1 · Use only slotted charms"
        " · Allow Piercings · Allow Event Armor · Allow Low Rank Armor"
    )


def test_a_summary_without_skills_or_options_leaves_them_out(english_strings):
    form = replace(
        QueryForm.starting(), allow_piercings=False, allow_event=False, allow_low_rank=False
    )

    assert form.summary(english_strings) == (
        "Blademaster ♂ · HR 6 · Village Quests 6 · Max Weapon Slots 0 · Use only slotted charms"
    )


def test_the_armour_options_are_in_the_menus_order_with_their_fields():
    form = replace(QueryForm.starting(), allow_bad=True, allow_event=False)

    assert [(option.field, option.label, option.on) for option in form.armour_options()] == [
        ("allow_bad", StringIndex.ALLOW_BAD_SKILLS, True),
        ("allow_piercings", StringIndex.ALLOW_PIERCINGS, True),
        ("allow_event", StringIndex.ALLOW_EVENT_ARMOR, False),
        ("allow_low_rank", StringIndex.ALLOW_LOW_RANK_ARMOR, True),
    ]
    assert [getattr(form, option.field) for option in form.armour_options()] == [
        True,
        True,
        False,
        True,
    ]


def test_the_summary_names_bad_skills_first_as_the_menu_does(english_strings):
    form = replace(QueryForm.starting(), allow_bad=True, allow_event=False)

    assert form.summary(english_strings).endswith(
        " · Allow Bad Skills · Allow Piercings · Allow Low Rank Armor"
    )


@pytest.mark.parametrize(
    ("mode", "label"),
    [
        (CharmMode.NONE, StringIndex.USE_NO_CHARMS),
        (CharmMode.MY_CHARMS, StringIndex.USE_ONLY_MY_CHARMS),
        (CharmMode.SLOTTED, StringIndex.USE_ONLY_SLOTTED_CHARMS),
        (CharmMode.ONE_SKILL, StringIndex.USE_UP_TO_ONE_SKILL_CHARMS),
        (CharmMode.TWO_SKILL, StringIndex.USE_ONLY_TWO_SKILL_CHARMS),
    ],
)
def test_each_charm_mode_has_its_drop_down_label(mode, label):
    assert charm_mode_label(mode) is label
