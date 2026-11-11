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

from dataclasses import dataclass

from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.skill_picker import SkillRow, SkillRowsByHunter, starting_rows


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
