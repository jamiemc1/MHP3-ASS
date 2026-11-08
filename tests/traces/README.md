# Trace specs

Inputs for the harness's `traces` command, which records
`Solution::MatchesQuery` (`legacy/Solution.cpp:660-724`) stage by stage for
sampled armour combinations. `scripts/windows/generate-goldens.ps1` writes
each spec's result to `tests/golden/traces/<name>.jsonl.gz`. Specs for
personal-charm queries live in the gitignored `tests/savefile/traces/` and
write to `tests/savefile/golden/traces/`.

## Spec schema

```json
{ "query": "../corpus/g03-attack-sharp-one-skill.json", "stride": 200, "include": [[0, 1, 2, 0, 3, 4]] }
```

| Field | Meaning |
|---|---|
| `query` | A query file (corpus schema, `tests/corpus/README.md`), relative to the spec |
| `stride` | Optional. For workers with more than 500 combinations, sample every `stride`-th in loop order. Default: combinations / 150. Workers with up to 500 combinations are sampled completely |
| `include` | Optional. Extra combinations to sample, as `[worker, head, body, arms, waist, legs]` positions in the relevant-armour lists (after an empty slot gets its one `nullptr` piece). The harness fails if one never runs |

The first two combinations of each census category (below) are always
sampled too.

`queries/` holds synthetic queries written for traces: paths the corpus
doesn't reach (bad skills allowed, weapon slots, every armour slot empty
with a custom charm, the Auto-Guard worker, custom charms with irrelevant
or negative skills, two-skill charms at HR 1, many 1-slot gems with a
negative second skill). Their relevance goldens are generated too.

## Golden format

JSON lines. The first line is a header:

| Field | Meaning |
|---|---|
| `id` | The spec's file name |
| `query_json`, `spec_json` | The query and spec as parsed, for staleness checks |
| `my_charms_illegal` | My-charms lines skipped as illegal |
| `rel_decoration_map` | Relevant decoration indices by slot size 0-3, as `MatchesQuery` builds them |
| `point_score_rank` | `point_score` ranks after the run (see `tests/golden/README.md`, `solution-probes`) |
| `workers` | Per worker: `charm` name and `template`, `combinations`, `stride`, `census` and `exception_types` over every combination |

Census categories: `accepted`, `rejected_points` (`Solution.cpp:679`),
`rejected_bad_skills` (`:684`), `exception`; among accepted ones
`via_fix_bad`, `via_reorder`, `with_bad_skills`, `charm_changed`,
`charm_nulled`; and `decorations_fell` (`SwapOut` removed gems) and `wrapped`
(an unsigned counter at or above 2^31 after some stage).

Every other line is one sampled combination: `worker`, `combination`
(positions), `index` (in loop order), `armor` (armour indices, -1 for
empty), `sampled_by`, `outcome`, `exception` (type name or null) and
`stages`. A stage has its `stage` name, any result (`points`: `accepted`;
`fix_bad`: `called`, `result`; `reorder`: `result`) and the fields that
changed since the previous stage. `initial` and `final` list every field.
Stage order: `initial`, `decorated`, `points`, `extra`, then `fix_bad` and
`reorder` when bad skills need fixing; for a charm, `rearranged` (custom
charms) or `slots_reduced`, `skills_reduced`, `rearranged`, `charm_reduced`,
`extra_final` (generated charms); then `final`. A rejection or exception ends
the list early.

Fields: `decorations`, `body_decorations`, `non_body_decorations`
(decoration indices, in order); `abilities` and `need` (`[ability, points]`
in enumeration order); `extra_skills`, `bad_skills` (skill indices); `charm`
(`num_slots` and `abilities`, or null); `torso_slots_spare`,
`torso_multiplier`, `total_slots_spare`, `slots_spare` (all four sizes); and
the armour stats.
