"""Minimal async client for the ESPN Fantasy Hockey API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_VIEWS


class EspnApiError(Exception):
    """Generic error talking to ESPN."""


class EspnAuthError(EspnApiError):
    """The league is private and the cookies are missing or invalid."""


class EspnLeagueNotFound(EspnApiError):
    """The league/season combination does not exist."""


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


@dataclass
class Matchup:
    """A head-to-head matchup in a given matchup period."""

    matchup_period: int
    home_team_id: int | None
    away_team_id: int | None
    home_score: float | str | None
    away_score: float | str | None
    winner: str

    def opponent_of(self, team_id: int) -> tuple[int | None, float | str | None, float | str | None]:
        """Return (opponent_id, own_score, opponent_score) for a team."""
        if team_id == self.home_team_id:
            return self.away_team_id, self.home_score, self.away_score
        return self.home_team_id, self.away_score, self.home_score


@dataclass
class League:
    """Parsed league snapshot."""

    id: int
    season: int
    name: str
    scoring_type: str | None
    current_matchup_period: int | None
    scoring_period: int | None
    teams: dict[int, Team] = field(default_factory=dict)
    current_matchups: list[Matchup] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def matchup_for(self, team_id: int) -> Matchup | None:
        """Return the current matchup a team is in, if any."""
        for matchup in self.current_matchups:
            if team_id in (matchup.home_team_id, matchup.away_team_id):
                return matchup
        return None


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

    async def async_get_league(self) -> League:
        """Fetch and parse the league."""
        return _parse_league(await self._async_get_raw())

    async def _async_get_raw(self) -> dict[str, Any]:
        url = API_BASE_URL.format(season=self._season, league_id=self._league_id)
        params = [("view", view) for view in API_VIEWS]
        headers = {"Accept": "application/json"}
        if self._cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self._cookies.items())

        try:
            async with self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise EspnAuthError("League is private or cookies are invalid")
                if resp.status == 404:
                    raise EspnLeagueNotFound(
                        f"League {self._league_id} not found for season {self._season}"
                    )
                resp.raise_for_status()
                # ESPN sometimes serves JSON with a text/plain content type.
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise EspnApiError(f"Error communicating with ESPN: {err}") from err
        except ValueError as err:
            raise EspnApiError("ESPN returned an invalid response") from err

        # Past seasons are served as a one-element list.
        if isinstance(data, list):
            if not data:
                raise EspnLeagueNotFound("Empty response from ESPN")
            data = data[0]
        return data


def _parse_league(data: dict[str, Any]) -> League:
    settings = data.get("settings", {})
    status = data.get("status", {})

    members = {
        m["id"]: (
            m.get("displayName")
            or f"{m.get('firstName', '')} {m.get('lastName', '')}".strip()
        )
        for m in data.get("members", [])
    }

    teams: dict[int, Team] = {}
    for t in data.get("teams", []):
        overall = t.get("record", {}).get("overall", {})
        streak_len = overall.get("streakLength")
        streak_type = overall.get("streakType")
        name = (
            t.get("name")
            or f"{t.get('location', '')} {t.get('nickname', '')}".strip()
            or t.get("abbrev")
            or f"Team {t['id']}"
        )
        teams[t["id"]] = Team(
            id=t["id"],
            name=name,
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
        )

    current_period = status.get("currentMatchupPeriod")
    matchups = [
        _parse_matchup(m)
        for m in data.get("schedule", [])
        if m.get("matchupPeriodId") == current_period
    ]

    return League(
        id=data.get("id"),
        season=data.get("seasonId"),
        name=settings.get("name", f"League {data.get('id')}"),
        scoring_type=settings.get("scoringSettings", {}).get("scoringType"),
        current_matchup_period=current_period,
        scoring_period=data.get("scoringPeriodId"),
        teams=teams,
        current_matchups=matchups,
        raw=data,
    )


def _parse_matchup(m: dict[str, Any]) -> Matchup:
    home = m.get("home", {})
    away = m.get("away", {})
    return Matchup(
        matchup_period=m.get("matchupPeriodId"),
        home_team_id=home.get("teamId"),
        away_team_id=away.get("teamId"),
        home_score=_side_score(home),
        away_score=_side_score(away),
        winner=m.get("winner", "UNDECIDED"),
    )


def _side_score(side: dict[str, Any]) -> float | str | None:
    """Points leagues return a number; category leagues a 'W-L-T' string."""
    if not side:
        return None
    cumulative = side.get("cumulativeScore")
    if cumulative and (cumulative.get("wins") or cumulative.get("losses") or cumulative.get("ties")):
        return f"{cumulative.get('wins', 0)}-{cumulative.get('losses', 0)}-{cumulative.get('ties', 0)}"
    live = side.get("totalPointsLive")
    return live if live is not None else side.get("totalPoints")
