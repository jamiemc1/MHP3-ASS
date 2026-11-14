from __future__ import annotations

from mhp3ass.regions import Region, region_hint


def test_the_regions_are_numbered_in_screen_order():
    assert [(region.name, int(region)) for region in Region] == [
        ("QUERY", 1),
        ("CHARMS", 2),
        ("SETS", 3),
    ]


def test_each_hint_is_its_regions_number_as_a_superscript():
    assert [region_hint(region) for region in Region] == ["¹", "²", "³"]
