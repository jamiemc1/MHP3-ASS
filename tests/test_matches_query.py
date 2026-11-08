"""``matches_query`` against the harness traces, stage by stage and as one call."""

from __future__ import annotations

from solution_trace import matches_query_mismatches, matches_query_stages, stage_mismatches


def test_every_stage_matches_every_trace(trace_goldens, scratch_game):
    stages = matches_query_stages(scratch_game)

    assert stage_mismatches(trace_goldens, scratch_game, stages) == []


def test_personal_every_stage_matches_every_trace(personal_trace_goldens, scratch_game):
    stages = matches_query_stages(scratch_game)

    assert stage_mismatches(personal_trace_goldens, scratch_game, stages) == []


def test_matches_query_ends_where_every_trace_ends(trace_goldens, scratch_game):
    assert matches_query_mismatches(trace_goldens, scratch_game) == []


def test_personal_matches_query_ends_where_every_trace_ends(personal_trace_goldens, scratch_game):
    assert matches_query_mismatches(personal_trace_goldens, scratch_game) == []
