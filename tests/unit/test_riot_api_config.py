"""Unit tests for Riot API config mappings."""

import pytest

from app.internal.riot_api.config import (
    REGION_TO_PLATFORM,
    PLATFORM_TO_REGION,
    RiotPlatform,
    RiotRegion,
)


@pytest.mark.parametrize(
    "region,expected_platform",
    [
        ("na", RiotPlatform.NA1),
        ("na1", RiotPlatform.NA1),
        ("euw", RiotPlatform.EUW1),
        ("euw1", RiotPlatform.EUW1),
        ("kr", RiotPlatform.KR),
        ("br", RiotPlatform.BR1),
        ("lan", RiotPlatform.LA1),
        ("las", RiotPlatform.LA2),
        ("oce", RiotPlatform.OC1),
        ("jp", RiotPlatform.JP1),
    ],
)
def test_region_to_platform(region, expected_platform):
    assert REGION_TO_PLATFORM[region] == expected_platform


@pytest.mark.parametrize(
    "platform,expected_region",
    [
        (RiotPlatform.NA1, RiotRegion.AMERICAS),
        (RiotPlatform.EUW1, RiotRegion.EUROPE),
        (RiotPlatform.KR, RiotRegion.ASIA),
        (RiotPlatform.BR1, RiotRegion.AMERICAS),
        (RiotPlatform.OC1, RiotRegion.SEA),
    ],
)
def test_platform_to_region(platform, expected_region):
    assert PLATFORM_TO_REGION[platform] == expected_region
