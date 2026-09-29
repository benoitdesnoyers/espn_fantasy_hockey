"""Tests for polling, transactions and the extras the coordinator fetches."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import EVENT_TRANSACTION

from .conftest import (
    MY_TEAM_ID,
    load_fixture,
    mock_espn_responses,
    setup_integration,
)

PREFIX = "test_league_2026"


async def _refresh_later(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int
) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_new_transactions_fire_events(
    hass: HomeAssistant,
    game_day: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    events = async_capture_events(hass, EVENT_TRANSACTION)
    mock_espn_responses(aioclient_mock, league_json)
    await setup_integration(hass, config_entry)
    assert events == [], "existing transactions are not announced"

    my_team = next(t for t in league_json["teams"] if t["id"] == MY_TEAM_ID)
    my_bench_player = my_team["roster"]["entries"][-1]["playerId"]  # Eeli Tolvanen
    transactions = load_fixture("transactions.json")
    transactions["transactions"].insert(
        0,
        {
            "id": "tx-3",
            "type": "WAIVER",
            "status": "EXECUTED",
            "proposedDate": 1790700000000,
            "teamId": MY_TEAM_ID,
            "items": [
                {
                    "type": "ADD",
                    "playerId": my_bench_player,
                    "fromTeamId": 0,
                    "toTeamId": 2,
                },
                {"type": "DROP", "playerId": 5452, "fromTeamId": 2, "toTeamId": 0},
            ],
        },
    )
    aioclient_mock.clear_requests()
    mock_espn_responses(aioclient_mock, league_json, transactions=transactions)
    await _refresh_later(hass, game_day, minutes=16)

    [event] = events
    assert event.data["type"] == "waiver"
    assert event.data["description"] == (
        "Blue Liners added Eeli Tolvanen and dropped Jacob Markstrom"
    )
    assert event.data["config_entry_id"] == config_entry.entry_id

    entity = hass.states.get(f"event.{PREFIX}_transactions")
    assert entity.attributes["event_type"] == "waiver"
    assert entity.attributes["dropped"] == ["Jacob Markstrom"]
    latest = hass.states.get(f"sensor.{PREFIX}_latest_transaction")
    assert latest.state == event.data["description"]


async def test_transactions_are_fetched_every_15_minutes(
    hass: HomeAssistant,
    game_day: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    # Live cadence (every 2 minutes) during tonight's first game.
    game_day.move_to("2026-09-29T21:30:00+00:00")
    mock_espn_responses(aioclient_mock, league_json)
    await setup_integration(hass, config_entry)

    def transaction_calls() -> int:
        return sum(
            "view=mTransactions2" in str(c[1]) for c in aioclient_mock.mock_calls
        )

    assert transaction_calls() == 1
    await _refresh_later(hass, game_day, minutes=2)
    assert transaction_calls() == 1
    await _refresh_later(hass, game_day, minutes=14)
    assert transaction_calls() == 2


async def test_live_polling_during_games(
    hass: HomeAssistant,
    game_day: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    game_day.move_to("2026-09-29T21:30:00+00:00")  # first game started at 21:00
    await setup_integration(hass, config_entry)

    state = hass.states.get(f"sensor.{PREFIX}_matchup_period")
    assert state.attributes["update_interval_seconds"] == 2 * 60


async def test_extras_failing_does_not_break_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    mock_espn_responses(
        aioclient_mock,
        league_json,
        schedule_status=HTTPStatus.INTERNAL_SERVER_ERROR,
        next_season_status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    # Without a schedule, no one can be called idle, and polling stays normal.
    assert hass.states.get(f"sensor.{PREFIX}_lineup_issues").state == "0"
    period = hass.states.get(f"sensor.{PREFIX}_matchup_period")
    assert period.attributes["update_interval_seconds"] == 15 * 60
