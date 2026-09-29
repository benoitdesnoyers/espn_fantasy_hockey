"""Tests for parsing ESPN responses."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.espn_fantasy_hockey.api import (
    parse_league,
    parse_pro_schedule,
    parse_transactions,
)
from custom_components.espn_fantasy_hockey.const import STAT_NAMES

from .conftest import MY_SWID, MY_TEAM_ID, load_fixture


def test_parse_league(league_json: dict[str, Any]) -> None:
    league = parse_league(league_json, MY_SWID)

    assert league.name == "Test League"
    assert league.season == 2026
    assert league.scoring_type == "H2H_POINTS"
    assert sorted(league.teams) == [1, 2, 3, 4]
    assert league.my_team_id == MY_TEAM_ID


@pytest.mark.parametrize("swid", [None, "", "{11111111-0000-4000-8000-000000000000}"])
def test_my_team_unknown(league_json: dict[str, Any], swid: str | None) -> None:
    assert parse_league(league_json, swid).my_team_id is None


def test_my_team_matches_case_insensitively(league_json: dict[str, Any]) -> None:
    assert parse_league(league_json, MY_SWID.lower()).my_team_id == MY_TEAM_ID


def test_team(league_json: dict[str, Any]) -> None:
    team = parse_league(league_json).teams[2]

    assert team.name == "Blue Liners"
    assert team.abbrev == "T2"
    assert team.owners == ["Owner 4"]  # real names beat "ESPNfan…" handles
    assert (team.wins, team.losses, team.ties) == (8, 4, 0)
    assert team.seed == 2
    assert team.final_rank is None  # ESPN reports 0 until the season ends
    assert team.streak == "L2"


def test_team_name_fallbacks(league_json: dict[str, Any]) -> None:
    raw = league_json["teams"][0]
    del raw["name"]
    raw |= {"location": "Old", "nickname": "Style"}
    assert parse_league(league_json).teams[raw["id"]].name == "Old Style"

    del raw["location"], raw["nickname"]
    assert parse_league(league_json).teams[raw["id"]].name == raw["abbrev"]


def test_league_settings(league_json: dict[str, Any]) -> None:
    league = parse_league(league_json)

    assert league.scoring_period == 1
    assert league.lineup_slot_counts == {3: 9, 4: 5, 5: 2, 6: 1, 7: 6, 8: 1}
    assert not league.is_category_league
    assert league.categories == []


def test_matchups(league_json: dict[str, Any]) -> None:
    league = parse_league(league_json)
    matchup = league.matchup_for(MY_TEAM_ID)

    assert matchup is not None
    mine, theirs = matchup.sides(MY_TEAM_ID)
    assert mine.team_id == MY_TEAM_ID
    assert {mine.score, theirs.score} == {88.4, 71.2}
    assert matchup.sides(theirs.team_id) == (theirs, mine)
    assert league.matchup_for(99) is None


def test_matchup_player_points(league_json: dict[str, Any]) -> None:
    league = parse_league(league_json)
    mine, _ = league.matchup_for(MY_TEAM_ID).sides(MY_TEAM_ID)
    roster_ids = {p.id for p in league.teams[MY_TEAM_ID].roster}

    assert sorted(mine.points_today.values()) == [0.0, 2.0, 4.5, 6.1]
    assert sum(mine.points_matchup.values()) == pytest.approx(91.1)  # 12.25 -> 12.2
    assert set(mine.points_matchup) <= roster_ids


def test_category_league(league_json: dict[str, Any]) -> None:
    league_json["settings"]["scoringSettings"]["scoringType"] = "H2H_CATEGORY"
    matchup = league_json["schedule"][0]
    matchup["home"]["cumulativeScore"] |= {"wins": 5, "losses": 3, "ties": 2}
    matchup["away"]["cumulativeScore"] |= {"wins": 3, "losses": 5, "ties": 2}
    matchup["home"]["cumulativeScore"]["scoreByStat"]["13"] = {
        "score": 7.0,
        "result": "WIN",
    }

    league = parse_league(league_json)
    parsed = league.current_matchups[0]

    assert league.is_category_league
    goals = next(c for c in league.categories if c.name == "goals")
    assert not goals.lower_is_better
    assert (parsed.home.score, parsed.away.score) == ("5-3-2", "3-5-2")
    assert parsed.home.categories["13"].score == 7.0
    assert parsed.home.categories["13"].result == "WIN"


def test_pro_schedule() -> None:
    schedule = parse_pro_schedule(load_fixture("pro_schedule.json"))
    first_day = schedule.games_in(1)

    assert len(first_day) == 5
    assert all(g.start.tzinfo is not None for g in schedule.games)
    assert schedule.games == sorted(schedule.games, key=lambda g: g.start)
    montreal, toronto = 10, 21
    game = schedule.game_for(montreal, 1)
    assert game is not None
    assert set(game.team_ids) == {montreal, toronto}
    assert schedule.game_for(montreal, 2) is None


def test_transactions_keep_executed_roster_moves_only() -> None:
    data = load_fixture("transactions.json")
    data["transactions"] += [
        {**data["transactions"][0], "id": "lineup", "type": "ROSTER"},
        {**data["transactions"][0], "id": "canceled", "status": "CANCELED"},
    ]

    transactions = parse_transactions(data)

    assert [t.id for t in transactions] == ["tx-1", "tx-2"]  # newest first
    assert transactions[0].kind == "free_agent"
    assert transactions[0].items[0].kind == "ADD"
    assert transactions[0].items[0].from_team_id is None  # 0 means free agency


def test_roster_is_ordered_by_lineup_slot(league_json: dict[str, Any]) -> None:
    roster = parse_league(league_json).teams[MY_TEAM_ID].roster
    order = ["F", "D", "G", "UTIL", "BE", "IR"]
    slots = [p.lineup_slot for p in roster]

    assert slots == sorted(slots, key=order.index)


def test_player(league_json: dict[str, Any]) -> None:
    roster = parse_league(league_json).teams[MY_TEAM_ID].roster
    skater = next(p for p in roster if p.position != "G" and p.stats.get("goals"))
    goalie = next(p for p in roster if p.position == "G" and p.stats)

    assert skater.pro_team.isalpha()
    assert skater.eligible_slot_ids
    assert f"/full/{skater.id}.png" in skater.headshot
    assert set(skater.points) >= {"season", "projected"}
    assert skater.stats["points"] == skater.stats["goals"] + skater.stats["assists"]
    assert isinstance(skater.stats["toi_per_game_seconds"], float)
    assert (
        goalie.stats["saves"]
        == goalie.stats["shots_against"] - goalie.stats["goals_against"]
    )


def test_stat_names_reproduce_espn_points(league_json: dict[str, Any]) -> None:
    """Recomputing fantasy points from the named stats must match ESPN's totals.

    Guards the stat ID -> name table: a wrong ID would break the sum. The fixture
    league scores goals, assists, wins, shutouts, saves, shots, hits, blocks, etc.
    """
    weights = {  # the fixture league's scoring settings, by stat name
        "wins": 4.0,
        "shutouts": 3.0,
        "goals": 2.0,
        "assists": 1.0,
        "ot_losses": 1.0,
        "ppp": 0.5,
        "shp": 0.5,
        "blocks": 0.5,
        "saves": 0.2,
        "shots": 0.1,
        "hits": 0.1,
        "goals_against": -2.0,
    }
    assert set(weights) <= set(STAT_NAMES.values())

    players = [p for t in parse_league(league_json).teams.values() for p in t.roster]
    checked = 0
    for player in players:
        if not player.stats:
            continue
        computed = sum(player.stats.get(name, 0) * w for name, w in weights.items())
        assert computed == pytest.approx(player.points["season"], abs=0.11), player.name
        checked += 1
    assert checked > 50
