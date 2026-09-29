"""Minimal async client for the ESPN Fantasy Hockey API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
import json
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_PLAYERS_URL,
    API_SEASON_URL,
    API_VIEWS,
    CATEGORY_SCORING_TYPES,
    HEADSHOT_URL,
    LINEUP_SLOTS,
    POSITIONS,
    PRO_TEAMS,
    STAT_NAMES,
    STAT_SOURCE_ACTUAL,
    STAT_SOURCE_PROJECTED,
    STAT_SPLIT_SEASON,
    STAT_SPLITS,
    TRANSACTION_TYPES,
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

type Score = float | str | None


class EspnApiError(Exception):
    """Generic error talking to ESPN."""


class EspnAuthError(EspnApiError):
    """The league is private and the cookies are missing or invalid."""


class EspnLeagueNotFound(EspnApiError):
    """The league/season combination does not exist."""


@dataclass
class Player:
    """A rostered player and their performance."""

    id: int
    name: str
    position: str
    lineup_slot: str
    lineup_slot_id: int
    eligible_slot_ids: frozenset[int]
    pro_team_id: int | None
    pro_team: str
    headshot: str
    injury_status: str | None
    # Fantasy points keyed by split: season, last_7, last_15, last_30, projected.
    points: dict[str, float]
    # Current-season raw stats keyed by STAT_NAMES value.
    stats: dict[str, float]


@dataclass
class Team:
    """A fantasy team and its standing."""

    id: int
    name: str
    abbrev: str
    owners: list[str]
    logo: str | None
    seed: int | None
    final_rank: int | None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    games_back: float
    streak: str | None
    roster: list[Player] = field(default_factory=list)


@dataclass
class CategoryResult:
    """One side's score in one category of a category-league matchup."""

    score: float
    result: str | None  # WIN, LOSS, TIE, or None while undecided


@dataclass
class MatchupTeam:
    """One side of a matchup."""

    team_id: int | None
    score: Score
    # Fantasy points per player id, for today and for the whole matchup period.
    points_today: dict[int, float] = field(default_factory=dict)
    points_matchup: dict[int, float] = field(default_factory=dict)
    # Category leagues only: results by ESPN stat id.
    categories: dict[str, CategoryResult] = field(default_factory=dict)


@dataclass
class Matchup:
    """A head-to-head matchup in a given matchup period."""

    matchup_period: int
    home: MatchupTeam
    away: MatchupTeam
    winner: str

    def sides(self, team_id: int) -> tuple[MatchupTeam, MatchupTeam]:
        """Return (team's side, opponent's side)."""
        if team_id == self.home.team_id:
            return self.home, self.away
        return self.away, self.home


@dataclass(frozen=True)
class Category:
    """A scored category in a category league."""

    stat_id: str
    name: str
    lower_is_better: bool


@dataclass
class League:
    """Parsed league snapshot."""

    id: int
    season: int
    name: str
    scoring_type: str | None
    current_matchup_period: int | None
    scoring_period: int | None
    first_scoring_period: int | None = None
    final_scoring_period: int | None = None
    is_active: bool = True
    my_team_id: int | None = None
    # Starting slots and how many of each a lineup has, by lineup slot id.
    lineup_slot_counts: dict[int, int] = field(default_factory=dict)
    categories: list[Category] = field(default_factory=list)
    teams: dict[int, Team] = field(default_factory=dict)
    current_matchups: list[Matchup] = field(default_factory=list)

    @property
    def is_category_league(self) -> bool:
        """Whether matchups are decided by categories instead of points."""
        return self.scoring_type in CATEGORY_SCORING_TYPES

    def matchup_for(self, team_id: int) -> Matchup | None:
        """Return the current matchup a team is in, if any."""
        for matchup in self.current_matchups:
            if team_id in (matchup.home.team_id, matchup.away.team_id):
                return matchup
        return None


@dataclass(frozen=True)
class ProGame:
    """An NHL game."""

    id: int
    start: datetime
    scoring_period: int
    home_team_id: int
    away_team_id: int

    @property
    def team_ids(self) -> tuple[int, int]:
        return self.home_team_id, self.away_team_id


@dataclass
class ProSchedule:
    """The NHL schedule for a season, indexed by fantasy scoring period (day)."""

    games: list[ProGame] = field(default_factory=list)

    def games_in(self, scoring_period: int | None) -> list[ProGame]:
        """Return the games of one scoring period."""
        return [g for g in self.games if g.scoring_period == scoring_period]

    def game_for(
        self, pro_team_id: int | None, scoring_period: int | None
    ) -> ProGame | None:
        """Return the game an NHL team plays in a scoring period, if any."""
        for game in self.games_in(scoring_period):
            if pro_team_id in game.team_ids:
                return game
        return None


@dataclass(frozen=True)
class TransactionItem:
    """One player movement within a transaction."""

    kind: str  # ADD, DROP or TRADE
    player_id: int
    from_team_id: int | None
    to_team_id: int | None


@dataclass(frozen=True)
class Transaction:
    """A roster-changing league transaction."""

    id: str
    kind: str  # a TRANSACTION_TYPES value
    date: datetime
    team_id: int
    items: tuple[TransactionItem, ...]


class EspnFantasyHockeyApi:
    """Fetch league data from ESPN."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        league_id: int,
        season: int,
        espn_s2: str | None = None,
        swid: str | None = None,
    ) -> None:
        self._session = session
        self._league_id = league_id
        self._season = season
        self._cookies: dict[str, str] = {}
        if espn_s2 and swid:
            self._cookies = {"espn_s2": espn_s2, "SWID": swid}

    @property
    def has_cookies(self) -> bool:
        """Whether this client is logged in to ESPN."""
        return bool(self._cookies)

    async def async_get_league(self) -> League:
        """Fetch and parse the league."""
        data = await self._async_get_json(self._league_url(), self._views(*API_VIEWS))
        # Past seasons are served as a one-element list.
        if isinstance(data, list):
            if not data:
                raise EspnLeagueNotFound("Empty response from ESPN")
            data = data[0]
        return parse_league(data, self._cookies.get("SWID"))

    async def async_get_pro_schedule(self) -> ProSchedule:
        """Fetch the NHL schedule for the season."""
        data = await self._async_get_json(
            API_SEASON_URL.format(season=self._season),
            self._views("proTeamSchedules_wl"),
        )
        return parse_pro_schedule(data)

    async def async_get_transactions(self) -> list[Transaction]:
        """Fetch the league's roster-changing transactions, newest first."""
        data = await self._async_get_json(
            self._league_url(),
            self._views("mTransactions2"),
            fantasy_filter={
                "transactions": {"filterType": {"value": list(TRANSACTION_TYPES)}}
            },
        )
        return parse_transactions(data)

    async def async_get_player_names(self, player_ids: Iterable[int]) -> dict[int, str]:
        """Look up player names by id, for players who aren't on a roster."""
        ids = sorted(set(player_ids))
        if not ids:
            return {}
        data = await self._async_get_json(
            API_PLAYERS_URL.format(season=self._season),
            self._views("players_wl"),
            fantasy_filter={"filterIds": {"value": ids}},
        )
        return {p["id"]: p.get("fullName", str(p["id"])) for p in data}

    async def async_season_exists(self, season: int) -> bool:
        """Whether the league has been renewed for `season`."""
        url = API_BASE_URL.format(season=season, league_id=self._league_id)
        try:
            await self._async_get_json(url, self._views("mStatus"))
        except EspnLeagueNotFound:
            return False
        return True

    async def async_get_image(self, url: str) -> tuple[bytes, str]:
        """Download an image that ESPN only serves to logged-in users."""
        try:
            async with self._session.get(
                url,
                # ESPN answers 406 to "Accept: image/*"; the type is checked below.
                headers=self._headers("*/*"),
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                if not resp.content_type.startswith("image/"):
                    raise EspnApiError(f"Not an image: {resp.content_type}")
                return await resp.read(), resp.content_type
        except aiohttp.ClientError as err:
            raise EspnApiError(f"Error downloading {url}: {err}") from err

    def _league_url(self) -> str:
        return API_BASE_URL.format(season=self._season, league_id=self._league_id)

    @staticmethod
    def _views(*views: str) -> list[tuple[str, str]]:
        return [("view", view) for view in views]

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        if self._cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        return headers

    async def _async_get_json(
        self,
        url: str,
        params: list[tuple[str, str]],
        fantasy_filter: dict[str, Any] | None = None,
    ) -> Any:
        headers = self._headers("application/json")
        if fantasy_filter is not None:
            headers["X-Fantasy-Filter"] = json.dumps(fantasy_filter)
        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    raise EspnAuthError("League is private or cookies are invalid")
                if resp.status == HTTPStatus.NOT_FOUND:
                    raise EspnLeagueNotFound(f"Not found: {url}")
                resp.raise_for_status()
                # ESPN sometimes serves JSON with a text/plain content type.
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise EspnApiError(f"Error communicating with ESPN: {err}") from err
        except ValueError as err:
            raise EspnApiError("ESPN returned an invalid response") from err


def parse_league(data: dict[str, Any], swid: str | None = None) -> League:
    """Build a League from an ESPN league response."""
    settings = data.get("settings", {})
    status = data.get("status", {})
    current_period = status.get("currentMatchupPeriod")
    season = data.get("seasonId")
    scoring = settings.get("scoringSettings", {})

    # displayName is often an auto-generated handle like "ESPNfan9422471749".
    members = {
        m["id"]: f"{m.get('firstName', '')} {m.get('lastName', '')}".strip()
        or m.get("displayName")
        for m in data.get("members", [])
    }
    slot_counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {})

    league = League(
        id=data.get("id"),
        season=season,
        name=settings.get("name", f"League {data.get('id')}"),
        scoring_type=scoring.get("scoringType"),
        current_matchup_period=current_period,
        scoring_period=data.get("scoringPeriodId"),
        first_scoring_period=status.get("firstScoringPeriod"),
        final_scoring_period=status.get("finalScoringPeriod"),
        is_active=status.get("isActive", True),
        my_team_id=_find_my_team(data.get("teams", []), swid),
        lineup_slot_counts={
            int(slot): count
            for slot, count in slot_counts.items()
            if count and int(slot) in LINEUP_SLOTS
        },
        teams={t["id"]: _parse_team(t, members, season) for t in data.get("teams", [])},
        current_matchups=[
            _parse_matchup(m)
            for m in data.get("schedule", [])
            if m.get("matchupPeriodId") == current_period
        ],
    )
    if league.is_category_league:
        league.categories = [
            Category(
                stat_id=str(item["statId"]),
                name=STAT_NAMES.get(str(item["statId"]), f"stat_{item['statId']}"),
                lower_is_better=bool(item.get("isReverseItem")),
            )
            for item in scoring.get("scoringItems", [])
        ]
    return league


def _parse_team(t: dict[str, Any], members: dict[str, str], season: int) -> Team:
    overall = t.get("record", {}).get("overall", {})
    streak_type = overall.get("streakType")
    streak_len = overall.get("streakLength")
    return Team(
        id=t["id"],
        name=(
            t.get("name")
            or f"{t.get('location', '')} {t.get('nickname', '')}".strip()
            or t.get("abbrev")
            or f"Team {t['id']}"
        ),
        abbrev=t.get("abbrev", ""),
        owners=[members.get(o, o) for o in t.get("owners", [])],
        logo=t.get("logo"),
        seed=t.get("playoffSeed"),
        final_rank=t.get("rankCalculatedFinal") or None,
        wins=overall.get("wins", 0),
        losses=overall.get("losses", 0),
        ties=overall.get("ties", 0),
        points_for=overall.get("pointsFor", 0.0),
        points_against=overall.get("pointsAgainst", 0.0),
        games_back=overall.get("gamesBack", 0.0),
        streak=f"{streak_type[0]}{streak_len}" if streak_type and streak_len else None,
        roster=_parse_roster(t.get("roster", {}), season),
    )


def _find_my_team(teams: list[dict[str, Any]], swid: str | None) -> int | None:
    """The SWID cookie is the ESPN user ID that appears in a team's owners list."""
    if not swid:
        return None
    swid = swid.strip().upper()
    for t in teams:
        if swid in (o.upper() for o in t.get("owners", [])):
            return t["id"]
    return None


def _parse_matchup(m: dict[str, Any]) -> Matchup:
    return Matchup(
        matchup_period=m.get("matchupPeriodId"),
        home=_parse_matchup_team(m.get("home", {})),
        away=_parse_matchup_team(m.get("away", {})),
        winner=m.get("winner", "UNDECIDED"),
    )


def _parse_matchup_team(side: dict[str, Any]) -> MatchupTeam:
    record = side.get("cumulativeScoreLive") or side.get("cumulativeScore") or {}
    return MatchupTeam(
        team_id=side.get("teamId"),
        score=_side_score(side),
        points_today=_player_points(side.get("rosterForCurrentScoringPeriod")),
        points_matchup=_player_points(side.get("rosterForMatchupPeriod")),
        categories={
            stat_id: CategoryResult(
                score=value.get("score", 0.0), result=value.get("result")
            )
            for stat_id, value in (record.get("scoreByStat") or {}).items()
        },
    )


def _player_points(roster: dict[str, Any] | None) -> dict[int, float]:
    """Points per player from a scoreboard roster (for a day or a matchup period)."""
    return {
        entry["playerId"]: round(
            entry["playerPoolEntry"].get("appliedStatTotal", 0.0), 1
        )
        for entry in (roster or {}).get("entries", [])
        if "playerPoolEntry" in entry
    }


def _side_score(side: dict[str, Any]) -> Score:
    """Points leagues return a number; category leagues a 'W-L-T' string."""
    if not side:
        return None
    record = side.get("cumulativeScore") or {}
    wins, losses, ties = (record.get(k, 0) for k in ("wins", "losses", "ties"))
    if wins or losses or ties:
        return f"{wins}-{losses}-{ties}"
    live = side.get("totalPointsLive")
    return live if live is not None else side.get("totalPoints")


def _parse_roster(roster: dict[str, Any], season: int) -> list[Player]:
    slot_rank = {slot_id: rank for rank, slot_id in enumerate(LINEUP_SLOTS)}
    players = [_parse_player(e, season) for e in roster.get("entries", [])]
    players.sort(
        key=lambda p: (slot_rank.get(p.lineup_slot_id, len(slot_rank)), p.name)
    )
    return players


def _parse_player(entry: dict[str, Any], season: int) -> Player:
    player = entry.get("playerPoolEntry", {}).get("player", {})
    player_id = player.get("id", entry.get("playerId"))
    slot_id = entry.get("lineupSlotId", -1)
    pro_team_id = player.get("proTeamId")

    points: dict[str, float] = {}
    stats: dict[str, float] = {}
    for s in player.get("stats", []):
        if s.get("seasonId") != season or s.get("scoringPeriodId", 0) != 0:
            continue
        source, split = s.get("statSourceId"), s.get("statSplitTypeId")
        total = round(s.get("appliedTotal", 0.0), 1)
        if source == STAT_SOURCE_ACTUAL and split in STAT_SPLITS:
            points[STAT_SPLITS[split]] = total
            if split == STAT_SPLIT_SEASON:
                stats = _named_stats(s.get("stats", {}))
        elif source == STAT_SOURCE_PROJECTED and split == STAT_SPLIT_SEASON:
            points["projected"] = total

    return Player(
        id=player_id,
        name=player.get("fullName", "Unknown"),
        position=POSITIONS.get(player.get("defaultPositionId"), "?"),
        lineup_slot=LINEUP_SLOTS.get(slot_id, str(slot_id)),
        lineup_slot_id=slot_id,
        eligible_slot_ids=frozenset(player.get("eligibleSlots", [])),
        pro_team_id=pro_team_id,
        pro_team=PRO_TEAMS.get(pro_team_id, str(pro_team_id)),
        headshot=HEADSHOT_URL.format(player_id=player_id),
        injury_status=player.get("injuryStatus") or entry.get("injuryStatus"),
        points=points,
        stats=stats,
    )


def _named_stats(raw: dict[str, float]) -> dict[str, float]:
    """Rename ESPN stat IDs, keeping whole numbers as ints and rates to 3 decimals."""
    stats: dict[str, float] = {}
    for stat_id, name in STAT_NAMES.items():
        if (value := raw.get(stat_id)) is None:
            continue
        stats[name] = int(value) if float(value).is_integer() else round(value, 3)
    return stats


def _from_millis(millis: int) -> datetime:
    return datetime.fromtimestamp(millis / 1000, tz=UTC)


def parse_pro_schedule(data: dict[str, Any]) -> ProSchedule:
    """Build the NHL schedule; each game appears under both of its teams."""
    games: dict[int, ProGame] = {}
    for team in data.get("settings", {}).get("proTeams", []):
        for period, period_games in team.get("proGamesByScoringPeriod", {}).items():
            for g in period_games:
                games[g["id"]] = ProGame(
                    id=g["id"],
                    start=_from_millis(g["date"]),
                    scoring_period=int(period),
                    home_team_id=g["homeProTeamId"],
                    away_team_id=g["awayProTeamId"],
                )
    return ProSchedule(sorted(games.values(), key=lambda g: g.start))


def parse_transactions(data: dict[str, Any]) -> list[Transaction]:
    """Roster-changing, executed transactions, newest first."""
    transactions = [
        Transaction(
            id=t["id"],
            kind=TRANSACTION_TYPES[t["type"]],
            date=_from_millis(t.get("processDate") or t["proposedDate"]),
            team_id=t.get("teamId"),
            items=tuple(
                TransactionItem(
                    kind=i["type"],
                    player_id=i["playerId"],
                    from_team_id=i.get("fromTeamId") or None,
                    to_team_id=i.get("toTeamId") or None,
                )
                for i in t.get("items", [])
                if i.get("type") in ("ADD", "DROP", "TRADE")
            ),
        )
        for t in data.get("transactions", [])
        if t.get("type") in TRANSACTION_TYPES and t.get("status") == "EXECUTED"
    ]
    return sorted(transactions, key=lambda t: t.date, reverse=True)
