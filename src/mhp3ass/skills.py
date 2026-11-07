"""Which skill an ability's points give.

Ported from ``Ability::GetSkill`` (``legacy/Skill.cpp:9-29``).
"""

from __future__ import annotations

from mhp3ass.model import Ability, Skill


def get_skill(ability: Ability, amount: int) -> Skill | None:
    """The skill with the highest threshold ``amount`` reaches, in its sign's direction.

    Positive points take the largest positive threshold at or below them;
    negative points the most negative threshold at or above them. Zero, or
    points short of every threshold, give no skill.
    """
    if amount == 0:
        return None
    best = 0
    for threshold in ability.skills:
        better_positive = amount > 0 and best < threshold <= amount
        better_negative = amount < 0 and amount <= threshold < best
        if better_positive or better_negative:
            best = threshold
    if best == 0:
        return None
    skill = ability.skills[best]
    return skill
