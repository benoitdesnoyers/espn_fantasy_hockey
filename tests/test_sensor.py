"""Tests for the sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import CONF_MY_TEAM, DOMAIN

from .conftest import MY_TEAM_ID, mock_espn_responses, setup_integration

PREFIX = "sensor.test_league_2026"


async def test_entities_are_created(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, config_entry.entry_id)

    # League: period, latest transaction, lineup issues, transactions event;
    # then standing, matchup and roster for each of the 4 teams.
    assert len(entries) == 16
    # The cards find entities by role, so every one needs a translation key.
    assert {e.translation_key for e in entries} == {
        "matchup_period",
        "latest_transaction",
        "lineup_issues",
        "transactions",
        "team_matchup",
        "team_roster",
        "team_standing",
    }


async def test_league_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    state = hass.states.get(f"{PREFIX}_matchup_period")

    assert state.state == "1"
    assert state.attributes["league_name"] == "Test League"
    assert state.attributes["my_team_id"] == MY_TEAM_ID
    assert state.attributes["is_category_league"] is False
    # Noon on a game day, games tonight: the normal (not live) cadence.
    assert state.attributes["update_interval_seconds"] == 15 * 60


async def test_standing_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    state = hass.states.get(f"{PREFIX}_blue_liners_standing")

    assert state.name == "Test League (2026) Blue Liners standing"
    assert state.state == "2"
    assert state.attributes["team_id"] == MY_TEAM_ID
    assert state.attributes["record"] == "8-4-0"
    assert state.attributes["owners"] == ["Owner 4"]


async def test_matchup_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    mine = hass.states.get(f"{PREFIX}_blue_liners_matchup")
    attrs = mine.attributes
    opponent = next(
        s
        for s in hass.states.async_all("sensor")
        if s.entity_id.endswith("_matchup")
        and s.attributes.get("team_id") == attrs["opponent_id"]
    )

    assert float(mine.state) == attrs["score"]
    assert attrs["opponent_score"] == opponent.attributes["score"]
    assert opponent.attributes["opponent_id"] == MY_TEAM_ID
    # Games remain this week, so projections exceed the current scores.
    assert attrs["projected_score"] > attrs["score"]
    assert attrs["opponent_projected_score"] > attrs["opponent_score"]
    assert "categories" not in attrs  # points league

    players = {p["name"]: p for p in attrs["players"]}
    assert players["Auston Matthews"]["opponent_today"] == "vs MTL"
    assert players["Auston Matthews"]["game_today"].startswith("2026-09-29T23:00")
    assert players["Alex Tuch"]["game_today"] is None
    assert sum(p["points_today"] or 0 for p in players.values()) == 12.6


async def test_category_matchup_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    league_json["settings"]["scoringSettings"]["scoringType"] = "H2H_CATEGORY"
    mock_espn_responses(aioclient_mock, league_json)
    await setup_integration(hass, config_entry)

    attrs = hass.states.get(f"{PREFIX}_blue_liners_matchup").attributes
    goals = next(c for c in attrs["categories"] if c["name"] == "goals")

    assert goals["abbreviation"] == "G"
    assert goals["lower_is_better"] is False
    assert {"score", "opponent_score", "result"} <= set(goals)


async def test_roster_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    state = hass.states.get(f"{PREFIX}_blue_liners_roster")
    players = state.attributes["players"]

    assert state.attributes["player_count"] == len(players) == 23
    assert float(state.state) == round(sum(p["points_season"] or 0 for p in players), 1)
    assert {
        "name",
        "slot",
        "headshot",
        "game_today",
        "opponent_today",
        "points_today",
        "points_matchup",
        "stats",
    } <= set(players[0])


async def test_lineup_issues(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    """On the fixture's game day, Tolvanen is the only benched player who plays."""
    await setup_integration(hass, config_entry)
    state = hass.states.get(f"{PREFIX}_lineup_issues")

    assert state.state == "1"
    assert state.attributes["team_name"] == "Blue Liners"
    [issue] = state.attributes["issues"]
    assert issue["type"] == "idle_starter"
    assert issue["player"] == "Alex Tuch"
    assert issue["replacement"] == "Eeli Tolvanen"


async def test_lineup_issues_follow_the_chosen_team(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_MY_TEAM: "1"})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{PREFIX}_lineup_issues")
    assert state.attributes["team_id"] == 1


async def test_lineup_issues_unavailable_without_a_team(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    """A public league without cookies can't know which team is the user's."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test League (2026)",
        data={"league_id": 12345, "season": 2026},
    )
    mock_espn_responses(aioclient_mock, league_json)
    await setup_integration(hass, entry)

    assert hass.states.get(f"{PREFIX}_lineup_issues").state == STATE_UNAVAILABLE


async def test_latest_transaction(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    state = hass.states.get(f"{PREFIX}_latest_transaction")

    assert state.state == "Ice Wolves added Gabe Perreault"
    assert [t["description"] for t in state.attributes["recent"]] == [
        "Ice Wolves added Gabe Perreault",
        "Five Hole Heroes added Jacob Markstrom",
    ]


async def test_private_logo_is_proxied(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    private = hass.states.get(f"{PREFIX}_blue_liners_standing")
    public = hass.states.get(f"{PREFIX}_ice_wolves_standing")

    assert private.attributes["entity_picture"].startswith(
        f"/api/espn_fantasy_hockey/logo/{config_entry.entry_id}/{MY_TEAM_ID}?v="
    )
    assert public.attributes["entity_picture"].startswith("https://g.espncdn.com/")
