"""Tests for lineup issues, projections and polling cadence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.espn_fantasy_hockey.analysis import (
    lineup_issues,
    projected_score,
    remaining_matchup_games,
    update_interval,
)
from custom_components.espn_fantasy_hockey.api import (
    League,
    MatchupTeam,
    Player,
    ProGame,
    ProSchedule,
    Team,
)
from custom_components.espn_fantasy_hockey.const import IDLE_INTERVAL

F, D, G, BENCH, IR = 3, 4, 5, 7, 8
SLOT_NAMES = {F: "F", D: "D", G: "G", BENCH: "BE", IR: "IR"}
PLAYS, IDLE, LATE = 1, 2, 3  # NHL teams: plays tonight, no game, game already started

# Tuesday 2026-09-29, noon Eastern.
NOW = datetime(2026, 9, 29, 16, 0, tzinfo=UTC)
LIVE = timedelta(minutes=2)
NORMAL = timedelta(minutes=15)


def game(game_id: int, start: datetime, home: int, away: int = 99, period: int = 1):
    return ProGame(game_id, start, period, home, away)


TONIGHT = NOW + timedelta(hours=7)
SCHEDULE = ProSchedule(
    [
        game(1, TONIGHT, PLAYS),
        game(2, NOW - timedelta(hours=1), LATE),  # an afternoon game, under way
    ]
)


def player(
    name: str,
    slot: int,
    team: int,
    eligible: tuple[int, ...] = (F, BENCH, IR),
    injury: str = "ACTIVE",
    projected: float = 0.0,
) -> Player:
    return Player(
        id=hash(name),
        name=name,
        position="C",
        lineup_slot=SLOT_NAMES[slot],
        lineup_slot_id=slot,
        eligible_slot_ids=frozenset(eligible),
        pro_team_id=team,
        pro_team=str(team),
        headshot="",
        injury_status=injury,
        points={"projected": projected},
        stats={},
    )


def team(*players: Player) -> Team:
    return Team(
        1, "Mine", "M", [], None, 1, None, 0, 0, 0, 0, 0, 0, None, list(players)
    )


def league(slot_counts: dict[int, int]) -> League:
    return League(
        id=1,
        season=2027,
        name="L",
        scoring_type="H2H_POINTS",
        current_matchup_period=1,
        scoring_period=1,
        lineup_slot_counts=slot_counts,
    )


def issues_for(roster: Team, counts: dict[int, int] | None = None):
    counts = counts or {F: sum(p.lineup_slot_id == F for p in roster.roster)}
    return [
        (i.kind, i.player, i.replacement)
        for i in lineup_issues(roster, league(counts), SCHEDULE, NOW)
    ]


class TestLineupIssues:
    def test_healthy_lineup_with_games_has_no_issues(self) -> None:
        assert issues_for(team(player("A", F, PLAYS))) == []

    def test_injured_starter(self) -> None:
        roster = team(
            player("Hurt", F, PLAYS, injury="OUT"), player("Sub", BENCH, PLAYS)
        )
        assert issues_for(roster) == [("injured_starter", "Hurt", "Sub")]

    def test_injured_starter_is_flagged_even_without_a_replacement(self) -> None:
        roster = team(player("Hurt", F, PLAYS, injury="INJURY_RESERVE"))
        assert issues_for(roster) == [("injured_starter", "Hurt", None)]

    def test_day_to_day_players_are_not_flagged(self) -> None:
        assert issues_for(team(player("Sore", F, PLAYS, injury="DAY_TO_DAY"))) == []

    def test_idle_starter_with_a_playing_bench_player(self) -> None:
        roster = team(player("Idle", F, IDLE), player("Sub", BENCH, PLAYS))
        assert issues_for(roster) == [("idle_starter", "Idle", "Sub")]

    def test_idle_starter_without_replacement_is_not_flagged(self) -> None:
        roster = team(player("Idle", F, IDLE), player("Also idle", BENCH, IDLE))
        assert issues_for(roster) == []

    @pytest.mark.parametrize(
        "sub",
        [
            player("Wrong position", BENCH, PLAYS, eligible=(D, BENCH)),
            player("Hurt", BENCH, PLAYS, injury="OUT"),
            player("Locked", BENCH, LATE),  # game started, lineup locked
            player("Reserve", IR, PLAYS),
        ],
        ids=lambda p: p.name,
    )
    def test_unusable_replacements(self, sub: Player) -> None:
        assert issues_for(team(player("Idle", F, IDLE), sub)) == []

    def test_each_bench_player_is_suggested_once(self) -> None:
        roster = team(
            player("Idle 1", F, IDLE),
            player("Idle 2", F, IDLE),
            player("Sub", BENCH, PLAYS),
        )
        assert issues_for(roster) == [("idle_starter", "Idle 1", "Sub")]

    def test_empty_slot(self) -> None:
        roster = team(player("A", F, PLAYS), player("Sub", BENCH, PLAYS))
        assert issues_for(roster, {F: 2}) == [("empty_slot", None, "Sub")]

    def test_no_schedule_means_no_idle_flags(self) -> None:
        roster = team(player("Idle", F, IDLE), player("Sub", BENCH, PLAYS))
        issues = lineup_issues(roster, league({F: 1}), ProSchedule(), NOW)
        assert issues == []

    def test_messages_read_naturally(self) -> None:
        [issue] = lineup_issues(
            team(player("Idle", F, IDLE), player("Sub", BENCH, PLAYS)),
            league({F: 1}),
            SCHEDULE,
            NOW,
        )
        assert (
            issue.message
            == "Idle has no game today; Sub is on the bench and plays today"
        )


class TestProjection:
    # Tue (today), Thu, Sun, and next Monday: the matchup ends Sunday.
    WEEK = ProSchedule(
        [
            game(1, TONIGHT, PLAYS),
            game(2, TONIGHT + timedelta(days=2), PLAYS, period=3),
            game(3, TONIGHT + timedelta(days=5), PLAYS, period=6),
            game(4, TONIGHT + timedelta(days=6), PLAYS, period=7),
            game(5, NOW - timedelta(hours=1), LATE),
        ]
    )

    def test_remaining_games_run_until_sunday(self) -> None:
        remaining = remaining_matchup_games(league({}), self.WEEK, NOW)
        assert [g.id for g in remaining] == [1, 2, 3]

    def test_projection_adds_expected_points_of_healthy_starters(self) -> None:
        roster = team(
            player("Starter", F, PLAYS, projected=82.0),  # 1 point per game
            player("Benched", BENCH, PLAYS, projected=820.0),
            player("Injured", F, PLAYS, injury="OUT", projected=820.0),
        )
        remaining = remaining_matchup_games(league({}), self.WEEK, NOW)

        assert projected_score(MatchupTeam(1, 50.0), roster, remaining) == 53.0

    def test_category_leagues_have_no_projection(self) -> None:
        assert projected_score(MatchupTeam(1, "5-3-2"), team(), []) is None


class TestUpdateInterval:
    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            (TONIGHT - timedelta(minutes=30), NORMAL),
            (TONIGHT - timedelta(minutes=10), LIVE),  # warming up
            (TONIGHT + timedelta(hours=3), LIVE),  # overtime, shootout
            (TONIGHT + timedelta(hours=4), IDLE_INTERVAL),  # no more games soon
            (NOW - timedelta(days=3), IDLE_INTERVAL),
        ],
    )
    def test_follows_the_schedule(self, now: datetime, expected: timedelta) -> None:
        schedule = ProSchedule([game(1, TONIGHT, PLAYS)])
        assert update_interval(schedule, now, LIVE, NORMAL) == expected

    def test_unknown_schedule_uses_normal_interval(self) -> None:
        assert update_interval(ProSchedule(), NOW, LIVE, NORMAL) == NORMAL
