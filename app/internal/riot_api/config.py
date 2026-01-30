"""
Configuration for Riot API clients.

Provides immutable configuration, region/platform enums, and routing mappings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class RiotRegion(str, Enum):
    """Regional routing values for Riot API."""
    AMERICAS = "americas"
    EUROPE = "europe"
    ASIA = "asia"
    SEA = "sea"


class RiotPlatform(str, Enum):
    """Platform routing values for Riot API."""
    BR1 = "br1"
    EUN1 = "eun1"
    EUW1 = "euw1"
    JP1 = "jp1"
    KR = "kr"
    LA1 = "la1"
    LA2 = "la2"
    NA1 = "na1"
    OC1 = "oc1"
    PH2 = "ph2"
    RU = "ru"
    SG2 = "sg2"
    TH2 = "th2"
    TR1 = "tr1"
    TW2 = "tw2"
    VN2 = "vn2"


# Map region codes returned by Riot API to platform routing values
REGION_TO_PLATFORM: dict[str, RiotPlatform] = {
    "br": RiotPlatform.BR1,
    "br1": RiotPlatform.BR1,
    "eun": RiotPlatform.EUN1,
    "eun1": RiotPlatform.EUN1,
    "eune": RiotPlatform.EUN1,
    "euw": RiotPlatform.EUW1,
    "euw1": RiotPlatform.EUW1,
    "jp": RiotPlatform.JP1,
    "jp1": RiotPlatform.JP1,
    "kr": RiotPlatform.KR,
    "la1": RiotPlatform.LA1,
    "la2": RiotPlatform.LA2,
    "lan": RiotPlatform.LA1,
    "las": RiotPlatform.LA2,
    "na": RiotPlatform.NA1,
    "na1": RiotPlatform.NA1,
    "oc": RiotPlatform.OC1,
    "oc1": RiotPlatform.OC1,
    "oce": RiotPlatform.OC1,
    "ph": RiotPlatform.PH2,
    "ph2": RiotPlatform.PH2,
    "ru": RiotPlatform.RU,
    "sg": RiotPlatform.SG2,
    "sg2": RiotPlatform.SG2,
    "th": RiotPlatform.TH2,
    "th2": RiotPlatform.TH2,
    "tr": RiotPlatform.TR1,
    "tr1": RiotPlatform.TR1,
    "tw": RiotPlatform.TW2,
    "tw2": RiotPlatform.TW2,
    "vn": RiotPlatform.VN2,
    "vn2": RiotPlatform.VN2,
}

# Map platform to regional routing for match API
PLATFORM_TO_REGION: dict[RiotPlatform, RiotRegion] = {
    RiotPlatform.NA1: RiotRegion.AMERICAS,
    RiotPlatform.BR1: RiotRegion.AMERICAS,
    RiotPlatform.LA1: RiotRegion.AMERICAS,
    RiotPlatform.LA2: RiotRegion.AMERICAS,
    RiotPlatform.OC1: RiotRegion.SEA,
    RiotPlatform.PH2: RiotRegion.SEA,
    RiotPlatform.SG2: RiotRegion.SEA,
    RiotPlatform.TH2: RiotRegion.SEA,
    RiotPlatform.TW2: RiotRegion.SEA,
    RiotPlatform.VN2: RiotRegion.SEA,
    RiotPlatform.JP1: RiotRegion.ASIA,
    RiotPlatform.KR: RiotRegion.ASIA,
    RiotPlatform.EUN1: RiotRegion.EUROPE,
    RiotPlatform.EUW1: RiotRegion.EUROPE,
    RiotPlatform.TR1: RiotRegion.EUROPE,
    RiotPlatform.RU: RiotRegion.EUROPE,
}


@dataclass(frozen=True)
class RiotAPIConfig:
    """
    Immutable configuration for Riot API clients.

    Attributes:
        api_key: Riot API authentication key.
        base_url_template: URL template with {routing} placeholder.
        default_account_region: Default region for account endpoints.
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        retry_backoff_factor: Backoff multiplier for retries.
        retry_status_codes: HTTP status codes that trigger a retry.
    """
    api_key: str
    base_url_template: str = "https://{routing}.api.riotgames.com"
    default_account_region: RiotRegion = RiotRegion.EUROPE
    timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_backoff_factor: float = 1.0
    retry_status_codes: FrozenSet[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )
