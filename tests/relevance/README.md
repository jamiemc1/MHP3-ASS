# Relevance queries

Inputs for the harness's `relevance` command, alongside every query in
`tests/corpus/`. Each `*.json` file uses the corpus schema
(`tests/corpus/README.md`) without the charm fields (`charm_mode`,
`my_charms`): `LoadedData::GetRelevantData` and `CharmDatabase::GetCharms`
never read the my-charms list. `scripts/windows/generate-goldens.ps1` writes
each result to `tests/golden/relevance/<name>.json.gz`.

They cover what the search corpus doesn't: every HR and village level (charm
types unlock by HR; armour is available when either rank suffices), Gunner
and female hunters, each armour toggle off on its own, Auto-Guard (the only
ability with no decorations), skills with and without negative second skills
on their decorations, and two-skill charm pairs with no or many charms. Some
repeat the query fields of personal-charm queries in `tests/savefile/corpus/`
so the public tests cover them too.

File names must not clash with `tests/corpus/`: both write to the same
golden folder.
