"""The search form's values: hunter type, gender, ranks, weapon slots, charm
mode, the four options and both hunter types' skill rows.

Ported from ``Form1``'s controls (``legacy/Form1.h``): their designer defaults
(``InitializeComponent``: ``rdoMale`` ``:992``, the ``nudHR`` and ``nudElder``
values ``:660``, ``:713``, ``nudWeaponSlots`` left at 0, the option menu items
``:911-931``) and the constructor's charm mode (``:291``). These are the
values ``FormulateQuery`` reads (``:1184-1214``) and ``SaveConfig`` writes
(``:464-493``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mhp3ass.data import GameData
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode, QuerySpec, SearchSpec
from mhp3ass.skill_picker import (
    SkillRow,
    SkillRowsByHunter,
    query_skills,
    saved_skill_index,
    starting_rows,
)


@dataclass(frozen=True)
class QueryForm:
    """What the form's controls hold. The tab not shown keeps its skill rows."""

    hunter_type: HunterType
    gender: Gender
    hr: int
    elder_star: int
    weapon_slots: int
    charm_mode: CharmMode
    allow_bad: bool
    allow_piercings: bool
    allow_event: bool
    allow_low_rank: bool
    skill_rows: SkillRowsByHunter

    def __post_init__(self) -> None:
        if self.hunter_type not in (HunterType.BLADEMASTER, HunterType.GUNNER):
            raise ValueError(f"the form holds Blademaster or Gunner, not {self.hunter_type.name}")
        if self.gender not in (Gender.MALE, Gender.FEMALE):
            raise ValueError(f"the form holds male or female, not {self.gender.name}")
        if not 1 <= self.hr <= 6:
            raise ValueError(f"HR must be 1 to 6, not {self.hr}")
        if not 1 <= self.elder_star <= 6:
            raise ValueError(f"village must be 1 to 6, not {self.elder_star}")
        if not 0 <= self.weapon_slots <= 3:
            raise ValueError(f"weapon slots must be 0 to 3, not {self.weapon_slots}")
        if not isinstance(self.charm_mode, CharmMode):
            raise ValueError(f"charm mode must be a CharmMode, not {self.charm_mode!r}")
        for tab, rows in (
            ("Blademaster", self.skill_rows.blademaster),
            ("Gunner", self.skill_rows.gunner),
        ):
            if len(rows) != 6:
                raise ValueError(f"the {tab} tab has six skill rows, not {len(rows)}")

    @classmethod
    def starting(cls) -> QueryForm:
        """The form as the original opens with no ``settings.cfg``."""
        form = cls(
            hunter_type=HunterType.BLADEMASTER,
            gender=Gender.MALE,
            hr=6,
            elder_star=6,
            weapon_slots=0,
            charm_mode=CharmMode.SLOTTED,
            allow_bad=False,
            allow_piercings=True,
            allow_event=True,
            allow_low_rank=True,
            skill_rows=SkillRowsByHunter(blademaster=starting_rows(), gunner=starting_rows()),
        )
        return form

    def current_rows(self) -> tuple[SkillRow, ...]:
        """The skill rows of the hunter type the form shows."""
        if self.hunter_type is HunterType.GUNNER:
            return self.skill_rows.gunner
        return self.skill_rows.blademaster

    def search_spec(
        self, game: GameData, language: str, my_charms: tuple[str, ...], query_id: str = "tui"
    ) -> SearchSpec:
        """The search ``FormulateQuery`` builds from the form (``Form1.h:1184-1214``):
        the shown tab's skills in row order, with ``my_charms`` (``mycharms.txt``'s
        lines), which every charm mode reads (Auto-Guard looks its charm up there).
        ``game`` must be in ``language``."""
        chosen_rows = [row for row in self.current_rows() if row.skill is not None]
        skills = query_skills(chosen_rows)
        query = QuerySpec(
            id=query_id,
            language=language,
            hunter_type=self.hunter_type,
            gender=self.gender,
            hr=self.hr,
            elder_star=self.elder_star,
            weapon_slots=self.weapon_slots,
            allow_bad=self.allow_bad,
            include_piercings=self.allow_piercings,
            allow_event=self.allow_event,
            allow_low_rank=self.allow_low_rank,
            skills=tuple(saved_skill_index(game, row) for row in chosen_rows),
            skill_names=tuple(skill.name for skill in skills),
        )
        spec = SearchSpec(query=query, charm_mode=self.charm_mode, my_charms=my_charms)
        return spec

    def with_rows(self, hunter_type: HunterType, rows: tuple[SkillRow, ...]) -> QueryForm:
        """The form with ``hunter_type``'s tab's rows replaced; the other tab's are kept."""
        if hunter_type is HunterType.GUNNER:
            skill_rows = replace(self.skill_rows, gunner=rows)
        else:
            skill_rows = replace(self.skill_rows, blademaster=rows)
        updated = replace(self, skill_rows=skill_rows)
        return updated
