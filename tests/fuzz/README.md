# Differential-fuzz corpus

500 seeded random queries, `f001.json` to `f500.json`, for the final
port-vs-harness gate (phase 9). The schema is the hand-picked corpus's
(`tests/corpus/README.md`), without the `gui_*` fields. Every query carries
an explicit `my_charms` list of generated charms, even outside my-charms
mode, because Auto-Guard reads the list in the slotted, one-skill and
two-skill modes.

Don't edit these files by hand. They are written by:

```bash
uv run python scripts/generate_fuzz_corpus.py --seed 9 --count 500
```

`tests/test_fuzz_corpus.py` runs the same command with `--check` and fails
if the committed files differ. The generator uses the data loaders, the
relevance port and the charm tables to choose queries, so a deliberate
change to any of them may change the corpus: regenerate it, then the fuzz
goldens.

## How queries are drawn

- Language: 85 % `English (TeamHGG)`, the rest spread over the other six;
  skill and charm names are in the query's language
- Hunter type, gender: 50/50. HR and village stars: 1-6. Weapon slots: 0-3
- `allow_bad` 30 % on; piercings, event and low-rank armour 80 % on each
- Charm mode: 20 % each of none, my charms, slotted, one-skill and two-skill
- 1-6 skills, from one of two samplers (50/50):
  - *uniform*: distinct abilities from the 146 skills the GUI offers.
    Skills whose (unused) `skills.txt` type column names the other hunter
    type weigh 0.3
  - *armour-seeded*: a skill for each positive ability of a random piece
    the hunter can wear (torso-up pieces weigh 3), topped up from
    decoration abilities
- `my_charms`: 0-12 generated charms holding a query ability plus 0-20
  others; 20 % of them weakened (first skill lowered); sometimes slot-only
  charms and duplicates; the Auto-Guard charm in half the Auto-Guard
  queries. Ten queries also carry 1-3 illegal lines (a first skill of 14 or
  15 points), which the original skips
- Each query's `description` names its sampler, charm mode, the port's
  estimate of workers and evaluations, and the quota features it has

## Selection

The generator draws 5,000 candidates and drops those with more than
2,000,000 evaluations (armour combinations times workers). It then fills
these quotas in draw order, and tops up to 500 in draw order:

| Quota | Minimum |
|---|---|
| Auto-Guard with its charm in `my_charms` | 13 |
| Auto-Guard without it | 12 |
| A torso-up piece among the relevant armour | 50 |
| A slot with no relevant armour | 25 |
| A skill of the other hunter type | 25 |
| Two-skill charms below HR 5 | 50 |
| One-skill charms at HR 3 or below | 25 |
| Illegal my-charms lines | exactly 10 |
