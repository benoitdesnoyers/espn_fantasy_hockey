"""Constants for the ESPN Fantasy Hockey integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "espn_fantasy_hockey"

CONF_LEAGUE_ID: Final = "league_id"
CONF_SEASON: Final = "season"
CONF_ESPN_S2: Final = "espn_s2"
CONF_SWID: Final = "swid"

# "fhl" is ESPN's game code for fantasy hockey.
API_BASE_URL: Final = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{season}"
    "/segments/0/leagues/{league_id}"
)
API_VIEWS: Final = (
    "mTeam",
    "mMatchup",
    "mMatchupScore",
    "mSettings",
    "mStandings",
    "mStatus",
)

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)
