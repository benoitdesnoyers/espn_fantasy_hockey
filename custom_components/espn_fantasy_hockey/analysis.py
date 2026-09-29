"""Derived information: lineup problems, projected scores and polling cadence.

Pure functions over parsed ESPN data, so they're easy to test without Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .api import League, MatchupTeam, Player, ProGame, ProSchedule, Team
from .const import (
    BENCH_SLOTS,
    IDLE_INTERVAL,
    LINEUP_SLOTS,
    LIVE_GAME_LENGTH,
    LIVE_LEAD_TIME,
    MATCHUP_LAST_WEEKDAY,
    NHL_GAMES_PER_SEASON,
    UNAVAILABLE_STATUSES,
)

# NHL game days (and ESPN scoring periods) follow Eastern time.
NHL_TIME_ZONE = ZoneInfo("America/New_York")
BENCH = 7  # lineup slot id


@dataclass(frozen=True)
class LineupIssue:
    """Something in a lineup that costs points today."""

    kind: str  # injured_starter, idle_starter or empty_slot
    slot: str
    player: str | None  # the starter concerned; None for an empty slot
    replacement: str | None  # a benched player who could fill the slot today

    @property
    def message(self) -> str:
        """An English description, handy in notifications."""
        swap = (
            f"; {self.replacement} is on the bench and plays today"
            if self.replacement
            else ""
        )
        if self.kind == "injured_starter":
            return f"{self.player} is injured but in your {self.slot} slot{swap}"
        if self.kind == "idle_starter":
            return f"{self.player} has no game today{swap}"
        return f"A {self.slot} slot is empty{swap}"


def _is_available(player: Player) -> bool:
    return player.injury_status not in UNAVAILABLE_STATUSES


def lineup_issues(
    team: Team, league: League, schedule: ProSchedule, now: datetime
) -> list[LineupIssue]:
    """Find starters who won't score today and bench players who could.

    A benched player only counts as a replacement if they're healthy, eligible for
    the slot, and their game hasn't started yet (lineups lock at puck drop).
    """
    today = league.scoring_period

    def game_today(player: Player) -> ProGame | None:
        return schedule.game_for(player.pro_team_id, today)

    def movable_replacement(slot_id: int, taken: set[int]) -> Player | None:
        for player in team.roster:
            game = game_today(player)
            if (
                player.lineup_slot_id == BENCH
                and player.id not in taken
                and slot_id in player.eligible_slot_ids
                and _is_available(player)
                and game is not None
                and game.start > now
            ):
                return player
        return None

    issues: list[LineupIssue] = []
    taken: set[int] = set()  # each bench player is suggested at most once

    def add(kind: str, slot_id: int, starter: Player | None) -> None:
        replacement = movable_replacement(slot_id, taken)
        if replacement:
            taken.add(replacement.id)
        issues.append(
            LineupIssue(
                kind=kind,
                slot=LINEUP_SLOTS.get(slot_id, str(slot_id)),
                player=starter.name if starter else None,
                replacement=replacement.name if replacement else None,
            )
        )

    starters = [p for p in team.roster if p.lineup_slot_id not in BENCH_SLOTS]
    for player in starters:
        if not _is_available(player):
            add("injured_starter", player.lineup_slot_id, player)
        # An idle starter is only worth flagging when the bench has someone better.
        elif (
            schedule.games
            and game_today(player) is None
            and movable_replacement(player.lineup_slot_id, taken)
        ):
            add("idle_starter", player.lineup_slot_id, player)

    for slot_id, capacity in league.lineup_slot_counts.items():
        if slot_id in BENCH_SLOTS:
            continue
        filled = sum(1 for p in starters if p.lineup_slot_id == slot_id)
        for _ in range(capacity - filled):
            add("empty_slot", slot_id, None)

    return issues


def game_day(game: ProGame) -> date:
    """The NHL calendar day a game belongs to."""
    return game.start.astimezone(NHL_TIME_ZONE).date()


def remaining_matchup_games(
    league: League, schedule: ProSchedule, now: datetime
) -> list[ProGame]:
    """Games from now until the matchup ends (the Sunday of the current week).

    ESPN doesn't expose matchup boundaries for hockey, so this assumes its usual
    Monday-to-Sunday weeks; a longer opening or playoff week is under-counted.
    """
    today_games = schedule.games_in(league.scoring_period)
    today = (
        game_day(today_games[0])
        if today_games
        else now.astimezone(NHL_TIME_ZONE).date()
    )
    last_day = today + timedelta(days=(MATCHUP_LAST_WEEKDAY - today.weekday()) % 7)
    return [
        g for g in schedule.games if g.start > now and today <= game_day(g) <= last_day
    ]


def projected_score(
    side: MatchupTeam,
    team: Team,
    remaining_games: list[ProGame],
) -> float | None:
    """Current score plus each healthy starter's expected points in remaining games.

    Expected points per game are the player's projected season total spread over
    an 82-game NHL season, which also discounts goalies who don't start every game.
    """
    if not isinstance(side.score, int | float):
        return None  # category leagues have no point total to project
    expected = 0.0
    for player in team.roster:
        if player.lineup_slot_id in BENCH_SLOTS or not _is_available(player):
            continue
        games = sum(1 for g in remaining_games if player.pro_team_id in g.team_ids)
        expected += games * player.points.get("projected", 0.0) / NHL_GAMES_PER_SEASON
    return round(side.score + expected, 1)


def update_interval(
    schedule: ProSchedule,
    now: datetime,
    live_interval: timedelta,
    normal_interval: timedelta,
) -> timedelta:
    """Poll quickly during games, normally on game days, rarely otherwise."""
    if not schedule.games:
        return normal_interval  # schedule unavailable: stay on the safe default
    for game in schedule.games:
        if game.start - LIVE_LEAD_TIME <= now <= game.start + LIVE_GAME_LENGTH:
            return live_interval
    soon = now + timedelta(days=1)
    if any(now < game.start <= soon for game in schedule.games):
        return normal_interval
    return IDLE_INTERVAL
