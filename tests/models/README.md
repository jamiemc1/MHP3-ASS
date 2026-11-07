# Model fixture inputs

Synthetic inputs for the harness's `dump-models` command
(`harness/src/ModelDump.cpp`), whose output is
`tests/golden/data/models.json.gz`.

`mycharms/*.txt` are my-charms files in `mycharms.txt` format
(`NumSlots,Skill1,Points1,Skill2,Points2`), with skill names in
`English (TeamHGG)`. The harness loads each, in name order, as
`CharmDatabase::LoadCustom` loads `Data/mycharms.txt`:

| File | Covers |
|---|---|
| `01-valid.txt` | One-skill, two-skill, slot-only and second-column-only charms; a charm the game can't produce; a negative first skill; blank lines, comments and surrounding white space |
| `02-errors.txt` | Wrong field counts, unknown skills (including a leading space, which fields keep), unreadable and overflowing points, a skill with no points |
| `03-bad-slots.txt` | An unreadable slot count, which the original doesn't catch: loading stops there |
| `04-four-slots.txt` | Four slots, which the original's validity check can't index: loading stops there |
| `05-bad-quotes.txt` | A field of only white space, which `Utility::RemoveQuotes` can't index: loading stops there |

These are made up; none comes from a real save.
