"""Charm table generation against the harness's CharmDatabase dump (DataDump.cpp:230-309)."""

from __future__ import annotations

from typing import Any

from golden_shapes import charm_shape
from mhp3ass.charms.generation import CharmTables, rank_point, rnd, rnd_table, slot_lookup


def _charm_table_section(tables: CharmTables) -> list[dict[str, Any]]:
    section = [
        {
            "charm_type": charm_type,
            "slots": slots,
            "max_points": [
                {"ability": ability.static_index, "points": points}
                for ability, points in tables.max_points[charm_type][slots].items()
            ],
        }
        for charm_type in range(3)
        for slots in range(4)
    ]
    return section


def _two_skill_section(tables: CharmTables, abilities) -> list[dict[str, Any]]:
    section = []
    for i in range(1, len(abilities)):
        for j in range(i):
            charms = tables.two_skill[abilities[i]][abilities[j]]
            if charms:
                charm_entries = [charm_shape(charm) for charm in charms]
                section.append({"ability_a": i, "ability_b": j, "charms": charm_entries})
    return section


def _table_hashes_section(tables: CharmTables) -> list[dict[str, Any]]:
    section = [
        {
            "table": table_number,
            "charm_type": charm_type,
            "slots": slots,
            "hashes": tables.table_hashes[table_number][charm_type][slots],
        }
        for table_number in range(12)
        for charm_type in range(3)
        for slots in range(4)
    ]
    return section


def _first_difference(ours: list[Any], golden: list[Any]) -> Any:
    """The first differing entry (or the length mismatch), so failures stay readable."""
    for index, (our_entry, golden_entry) in enumerate(zip(ours, golden, strict=False)):
        if our_entry != golden_entry:
            return {"index": index, "ours": our_entry, "golden": golden_entry}
    if len(ours) != len(golden):
        return {"lengths": [len(ours), len(golden)]}
    return None


def test_rnd_maps_zero_to_176_and_stays_16_bit():
    outputs = [rnd(n) for n in range(65536)]

    assert [outputs[0], max(outputs) <= 0xFFFF, min(outputs) >= 0] == [176, True, True]


def test_rnd_table_walks_each_table_seed_round_a_5400_state_cycle():
    step = rnd_table()
    seeds = [2, 5, 9, 26, 6, 4, 13, 18, 15, 1, 12, 3]
    cycles = []
    for seed in seeds:
        cycle = [seed]
        while (n := step[cycle[-1]]) != seed:
            cycle.append(n)
        cycles.append(cycle)
    states = {n for cycle in cycles for n in cycle}

    assert [len(step), [len(cycle) for cycle in cycles], len(states)] == [
        65536,
        [5400] * 12,
        64800,
    ]


def test_slot_lookup_gives_the_first_threshold_the_roll_does_not_exceed():
    # Timeworn rank 1 thresholds are (21, 71, 91, 99); mystery rank 0 is (99,).
    timeworn_rank1 = slot_lookup(0)[1]
    mystery_rank0 = slot_lookup(2)[0]

    assert [
        [timeworn_rank1[roll] for roll in (0, 21, 22, 71, 72, 91, 92, 99)],
        set(mystery_rank0),
        [len(slot_lookup(kind)) for kind in range(3)],
    ] == [[0, 0, 1, 1, 2, 2, 3, 3], {0}, [21, 21, 11]]


def test_rank_point_truncates_in_single_precision():
    # 1 / 1.2f + 11 / 1.2f falls just below 10 in float32; in double it reaches 10.
    # No generated charm reaches these inputs, so the charm golden can't check this.
    double = int(1 / (12 / 10.0) + 11 / (12 / 10.0))

    assert [rank_point(max1=12, point1=1, max2=12, point2=11), double] == [9, 10]


def test_max_points_match_golden(charm_tables, charm_database_golden):
    ours = _charm_table_section(charm_tables)

    assert _first_difference(ours, charm_database_golden["charm_table"]) is None


def test_two_skill_charms_match_golden(charm_tables, charm_database_golden, teamhgg_game):
    ours = _two_skill_section(charm_tables, teamhgg_game.abilities)

    assert _first_difference(ours, charm_database_golden["two_skill_charms"]) is None


def test_table_hashes_match_golden(charm_tables, charm_database_golden):
    ours = _table_hashes_section(charm_tables)

    assert _first_difference(ours, charm_database_golden["table_hashes"]) is None


def test_charm_hashes_match_golden(charm_tables, charm_database_golden):
    golden = charm_database_golden["charm_hashes"]

    assert _first_difference(charm_tables.charm_hashes, golden) is None


def test_two_skill_lists_stay_shared_between_orders(charm_tables, teamhgg_game):
    abilities = teamhgg_game.abilities
    pairs = [(abilities[i], abilities[j]) for i in range(1, len(abilities)) for j in range(i)]
    unshared = [
        (a.name, b.name)
        for a, b in pairs
        if charm_tables.two_skill[a][b] is not charm_tables.two_skill[b][a]
    ]
    filled = sum(1 for a, b in pairs if charm_tables.two_skill[a][b])

    assert [unshared, filled > 0] == [[], True]
