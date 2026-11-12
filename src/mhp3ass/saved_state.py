"""The TUI's form, sort and results as ``settings.cfg`` holds them.

Ported from ``Form1::SaveConfig`` and ``Form1::LoadConfig``
(``legacy/Form1.h:380-541``): what the form's controls write, and how a load
puts them back. The TUI shows skills as chips (``skill_chips``), so every row
is written with the All filter (0), and the rows a load restores are closed
up into chips in the same order.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from mhp3ass.data import GameData
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode, Query
from mhp3ass.query_form import QueryForm
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import ResultSet
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.view import ResultsView
from mhp3ass.settings_cfg import (
    SettingsCfg,
    SettingsCfgError,
    check_header,
    load_results,
    with_solutions,
)
from mhp3ass.skill_chips import chip_rows
from mhp3ass.skill_picker import (
    SkillRowsByHunter,
    SkillSelection,
    query_skills,
    restore_skill_rows,
    saved_skill_index,
    starting_rows,
)
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class LoadedResults:
    """Results read back from ``settings.cfg``: their view, the query they
    belong to (``FormulateQuery( false, last_search_gunner )``,
    ``Form1.h:428``), the form as that search read it, and how many
    charm-free sets the load kept only under None (quirk 45)."""

    view: ResultsView
    query: Query
    form: QueryForm
    charm_free_only_under_none: int


@dataclass(frozen=True)
class SavedSearch:
    """What a load restores: the form, the sort, whether the results came
    from a Gunner search, and the results when the file has any lines."""

    form: QueryForm
    sort_key: SortKey
    last_search_gunner: bool
    results: LoadedResults | None

    @classmethod
    def starting(cls) -> SavedSearch:
        """The state with no ``settings.cfg`` (``Form1.h:289-305``)."""
        search = cls(
            form=QueryForm.starting(),
            sort_key=SortKey.NONE,
            last_search_gunner=False,
            results=None,
        )
        return search


def settings_for(
    form: QueryForm,
    game: GameData,
    language_index: int,
    last_search_gunner: bool,
    sort_key: SortKey,
    solutions: Sequence[Solution],
) -> SettingsCfg:
    """``SaveConfig``'s values for ``form`` (``Form1.h:464-541``): both
    tabs' rows with the All filter, and ``solutions`` (the view's
    ``all_solutions``) as the result lines."""
    selections = tuple(
        SkillSelection(
            blademaster_filter=0,
            blademaster_skill=saved_skill_index(game, blademaster),
            gunner_filter=0,
            gunner_skill=saved_skill_index(game, gunner),
        )
        for blademaster, gunner in zip(
            form.skill_rows.blademaster, form.skill_rows.gunner, strict=True
        )
    )
    header = SettingsCfg(
        version="2",
        language_index=language_index,
        last_search_gunner=last_search_gunner,
        hunter_tab=1 if form.hunter_type is HunterType.GUNNER else 0,
        male=form.gender is Gender.MALE,
        allow_bad=form.allow_bad,
        allow_piercings=form.allow_piercings,
        allow_event=form.allow_event,
        allow_low_rank=form.allow_low_rank,
        sort_index=int(sort_key),
        charm_select_index=int(form.charm_mode),
        hr=form.hr,
        elder_star=form.elder_star,
        weapon_slots=form.weapon_slots,
        skill_selections=selections,
        solution_lines=(),
    )
    settings = with_solutions(header, solutions, game)
    return settings


def form_from_settings(settings: SettingsCfg, game: GameData) -> QueryForm:
    """The form ``LoadConfig`` restores (``Form1.h:399-427``) from start-up's
    empty rows, each tab's rows closed up into chips. Raises
    ``SettingsCfgError`` for a value the TUI's controls can't hold: a hunter
    tab other than 0 or 1, no charm mode selected (-1), or a filter index
    the drop-down hasn't got."""
    if settings.hunter_tab not in (0, 1):
        raise SettingsCfgError(f"hunter tab {settings.hunter_tab} is neither 0 nor 1")
    if settings.charm_select_index == -1:
        raise SettingsCfgError("no charm mode is selected (-1)")
    try:
        restored = restore_skill_rows(
            game,
            current=SkillRowsByHunter(blademaster=starting_rows(), gunner=starting_rows()),
            selections=settings.skill_selections,
        )
    except ValueError as error:
        raise SettingsCfgError(f"can't restore the skill rows: {error}") from error
    form = QueryForm(
        hunter_type=HunterType.GUNNER if settings.hunter_tab == 1 else HunterType.BLADEMASTER,
        gender=Gender.MALE if settings.male else Gender.FEMALE,
        hr=settings.hr,
        elder_star=settings.elder_star,
        weapon_slots=settings.weapon_slots,
        charm_mode=CharmMode(settings.charm_select_index),
        allow_bad=settings.allow_bad,
        allow_piercings=settings.allow_piercings,
        allow_event=settings.allow_event,
        allow_low_rank=settings.allow_low_rank,
        skill_rows=SkillRowsByHunter(
            blademaster=chip_rows(query_skills(restored.blademaster)),
            gunner=chip_rows(query_skills(restored.gunner)),
        ),
    )
    return form


def restore_search(
    settings: SettingsCfg, game: GameData, language: str, language_count: int
) -> SavedSearch:
    """``LoadConfig`` after its version line (``Form1.h:395-438``), for
    ``game`` in ``language``: the form, the sort, then the results under the
    query of the last search's hunter type. Raises ``SettingsCfgError`` on
    the first value it can't restore (``check_header``, ``form_from_settings``,
    then each result line).

    Formulating the query sets the game's abilities' ``relevant`` flags, as
    the original's load does before reading the lines."""
    check_header(settings, language_count=language_count)
    form = form_from_settings(settings, game)
    sort_key = SortKey(max(settings.sort_index, 0))
    results = None
    if settings.solution_lines:
        results_form = dataclasses.replace(
            form,
            hunter_type=(
                HunterType.GUNNER if settings.last_search_gunner else HunterType.BLADEMASTER
            ),
        )
        spec = results_form.search_spec(game, language=language, my_charms=())
        query = formulate_query(game, spec.query)
        view = load_results(settings, game=game, results=ResultSet(), language_count=language_count)
        results = LoadedResults(
            view=view,
            query=query,
            form=results_form,
            charm_free_only_under_none=len(view.no_charm_solutions),
        )
    search = SavedSearch(
        form=form,
        sort_key=sort_key,
        last_search_gunner=settings.last_search_gunner,
        results=results,
    )
    return search
