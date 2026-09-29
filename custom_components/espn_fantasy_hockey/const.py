"""Constants for the ESPN Fantasy Hockey integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "espn_fantasy_hockey"

CONF_LEAGUE_ID: Final = "league_id"
CONF_SEASON: Final = "season"
CONF_ESPN_S2: Final = "espn_s2"
CONF_SWID: Final = "swid"

# Options
CONF_MY_TEAM: Final = "my_team"
CONF_LIVE_INTERVAL: Final = "live_interval"
CONF_NORMAL_INTERVAL: Final = "normal_interval"
MY_TEAM_AUTO: Final = "auto"
DEFAULT_LIVE_INTERVAL: Final = 2  # minutes, while NHL games are being played
DEFAULT_NORMAL_INTERVAL: Final = 15  # minutes, on game days outside games

# "fhl" is ESPN's game code for fantasy hockey.
API_SEASON_URL: Final = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{season}"
)
API_BASE_URL: Final = API_SEASON_URL + "/segments/0/leagues/{league_id}"
API_PLAYERS_URL: Final = API_SEASON_URL + "/players"
API_VIEWS: Final = (
    "mTeam",
    "mMatchup",
    "mMatchupScore",
    "mRoster",
    "mSettings",
    "mStandings",
    "mStatus",
)

# Polling. Live: from shortly before a game starts until it has surely ended.
IDLE_INTERVAL: Final = timedelta(hours=1)  # no NHL games in the next day
LIVE_LEAD_TIME: Final = timedelta(minutes=15)
LIVE_GAME_LENGTH: Final = timedelta(hours=3, minutes=30)
TRANSACTIONS_INTERVAL: Final = timedelta(minutes=15)
SEASON_CHECK_INTERVAL: Final = timedelta(days=1)
SCHEDULE_REFRESH_INTERVAL: Final = timedelta(days=1)

# Transaction types that change a roster; lineup moves ("ROSTER") are left out.
TRANSACTION_TYPES: Final = {
    "FREEAGENT": "free_agent",
    "WAIVER": "waiver",
    "TRADE_ACCEPT": "trade",
    "TRADE_UPHOLD": "trade",
}
EVENT_TRANSACTION: Final = f"{DOMAIN}_transaction"
RECENT_TRANSACTIONS: Final = 10

# Fantasy points per NHL team game are estimated from season projections.
NHL_GAMES_PER_SEASON: Final = 82
# ESPN hockey matchups run Monday to Sunday.
MATCHUP_LAST_WEEKDAY: Final = 6  # Sunday
CATEGORY_SCORING_TYPES: Final = frozenset({"H2H_CATEGORY", "H2H_MOST_CATEGORIES"})

# ESPN's resizing proxy; the raw headshots are ~1040x760 and ~250 KB each.
HEADSHOT_URL: Final = (
    "https://a.espncdn.com/combiner/i?img=/i/headshots/nhl/players/full/{player_id}.png"
    "&w=208&h=152"
)

# Custom-uploaded team logos live here and require the espn_s2/SWID cookies, which
# browsers won't send from a Home Assistant page, so they're proxied through HA.
PRIVATE_LOGO_HOST: Final = "mystique-api.fantasy.espn.com"
LOGO_PROXY_URL: Final = "/api/espn_fantasy_hockey/logo/{entry_id}/{team_id}"

# Dashboard cards shipped with the integration, served from frontend/ under
# CARDS_URL/<build id>/ and loaded through CARDS_ENTRYPOINT.
CARDS_URL: Final = "/espn_fantasy_hockey/cards"
CARDS_ENTRYPOINT: Final = "espn-fantasy-cards.js"

# player.defaultPositionId
POSITIONS: Final = {1: "C", 2: "LW", 3: "RW", 4: "D", 5: "G"}

# roster entry lineupSlotId; the order here is the order players are listed in.
LINEUP_SLOTS: Final = {
    0: "C",
    1: "LW",
    2: "RW",
    3: "F",
    4: "D",
    5: "G",
    6: "UTIL",
    7: "BE",
    8: "IR",
}
BENCH_SLOTS: Final = frozenset({7, 8})  # lineup slot ids that don't score
# Injury statuses that keep a player out of a game.
UNAVAILABLE_STATUSES: Final = frozenset({"OUT", "INJURY_RESERVE", "SUSPENSION"})

# player.proTeamId -> abbreviation.
# Source: .../games/fhl/seasons/<year>?view=proTeamSchedules_wl
PRO_TEAMS: Final = {
    0: "FA",
    1: "BOS",
    2: "BUF",
    3: "CGY",
    4: "CHI",
    5: "DET",
    6: "EDM",
    7: "CAR",
    8: "LA",
    9: "DAL",
    10: "MTL",
    11: "NJ",
    12: "NYI",
    13: "NYR",
    14: "OTT",
    15: "PHI",
    16: "PIT",
    17: "COL",
    18: "SJ",
    19: "STL",
    20: "TB",
    21: "TOR",
    22: "VAN",
    23: "WSH",
    25: "ANA",
    26: "FLA",
    27: "NSH",
    28: "WPG",
    29: "CBJ",
    30: "MIN",
    37: "VGK",
    124292: "SEA",
    129764: "UTA",
}

# ESPN stat ID -> attribute name. Verified by recomputing every rostered player's
# fantasy points from these stats against ESPN's own totals. IDs whose meaning
# couldn't be confirmed (8, 12, 25, 26, 30, 33, 35-37) are deliberately omitted.
STAT_NAMES: Final = {
    # Skaters
    "13": "goals",
    "14": "assists",
    "16": "points",
    "15": "plus_minus",
    "17": "pim",
    "18": "ppg",
    "19": "ppa",
    "38": "ppp",
    "20": "shg",
    "21": "sha",
    "39": "shp",
    "22": "gwg",
    "28": "hat_tricks",
    "29": "shots",
    "31": "hits",
    "32": "blocks",
    "23": "faceoffs_won",
    "24": "faceoffs_lost",
    "34": "games_played",
    "27": "toi_per_game_seconds",
    # Goalies
    "0": "games_started",
    "1": "wins",
    "2": "losses",
    "9": "ot_losses",
    "3": "shots_against",
    "4": "goals_against",
    "6": "saves",
    "7": "shutouts",
    "10": "gaa",
    "11": "save_pct",
}

# Short labels for category leagues, keyed by STAT_NAMES value.
STAT_ABBREVIATIONS: Final = {
    "goals": "G",
    "assists": "A",
    "points": "PTS",
    "plus_minus": "+/-",
    "pim": "PIM",
    "ppg": "PPG",
    "ppa": "PPA",
    "ppp": "PPP",
    "shg": "SHG",
    "sha": "SHA",
    "shp": "SHP",
    "gwg": "GWG",
    "hat_tricks": "HAT",
    "shots": "SOG",
    "hits": "HIT",
    "blocks": "BLK",
    "faceoffs_won": "FOW",
    "faceoffs_lost": "FOL",
    "games_played": "GP",
    "games_started": "GS",
    "wins": "W",
    "losses": "L",
    "ot_losses": "OTL",
    "shots_against": "SA",
    "goals_against": "GA",
    "saves": "SV",
    "shutouts": "SO",
    "gaa": "GAA",
    "save_pct": "SV%",
}

# stats[] entries: statSourceId 0 = actual, 1 = projected;
# statSplitTypeId 0 = season, 1 = last 7 days, 2 = last 15, 3 = last 30.
STAT_SOURCE_ACTUAL: Final = 0
STAT_SOURCE_PROJECTED: Final = 1
STAT_SPLIT_SEASON: Final = 0
STAT_SPLITS: Final = {
    STAT_SPLIT_SEASON: "season",
    1: "last_7",
    2: "last_15",
    3: "last_30",
}
