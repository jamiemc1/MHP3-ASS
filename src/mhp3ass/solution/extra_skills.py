"""The skills a combination gives beyond the query's.

Ported from ``Solution::CalculateExtraSkills`` (``legacy/Solution.cpp:726-740``).
"""

from __future__ import annotations

from mhp3ass.skills import get_skill
from mhp3ass.solution.state import CalculationData


def calculate_extra_skills(data: CalculationData) -> None:
    """``CalculateExtraSkills`` (Solution.cpp:726-740).

    Walks ``abilities`` in enumeration order, which is insertion order (query
    skills, then armour head to body, the charm, then decorations as they
    were added). A skill the query didn't ask for is a bad skill when its
    points are negative and bad skills aren't allowed, otherwise an extra
    skill. With bad skills allowed, negative skills are extras.
    """
    solution = data.solution
    solution.extra_skills.clear()
    solution.bad_skills.clear()
    for ability, points in solution.abilities.items():
        skill = get_skill(ability, points)
        if skill is None or skill in data.relevant:
            continue
        if points < 0 and not data.query.allow_bad:
            solution.bad_skills.append(skill)
        else:
            solution.extra_skills.append(skill)
