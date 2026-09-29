"""Tests for the config flow."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import (
    CONF_ESPN_S2,
    CONF_LIVE_INTERVAL,
    CONF_MY_TEAM,
    CONF_NORMAL_INTERVAL,
    CONF_SWID,
    DOMAIN,
)

from .conftest import ENTRY_DATA, LEAGUE_URL, setup_integration

SETUP = "custom_components.espn_fantasy_hockey.async_setup_entry"


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, mock_espn: AiohttpClientMocker) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test League (2026)"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == "12345_2026"


async def test_user_flow_public_league_without_cookies(
    hass: HomeAssistant, mock_espn: AiohttpClientMocker
) -> None:
    result = await _start(hass)
    blank_cookies = {**ENTRY_DATA, CONF_ESPN_S2: "", CONF_SWID: ""}

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], blank_cookies
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_ESPN_S2 not in result["data"]
    assert CONF_SWID not in result["data"]
    assert "Cookie" not in (mock_espn.mock_calls[-1][3] or {})


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"status": HTTPStatus.UNAUTHORIZED}, "invalid_auth"),
        ({"status": HTTPStatus.FORBIDDEN}, "invalid_auth"),
        ({"status": HTTPStatus.NOT_FOUND}, "league_not_found"),
        ({"json": []}, "league_not_found"),
        ({"status": HTTPStatus.INTERNAL_SERVER_ERROR}, "cannot_connect"),
        ({"exc": aiohttp.ClientConnectionError()}, "cannot_connect"),
        ({"text": "<html>not json</html>"}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
    response: dict[str, Any],
    error: str,
) -> None:
    aioclient_mock.get(LEAGUE_URL, **response)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # The form keeps working once the problem is fixed.
    aioclient_mock.clear_requests()
    aioclient_mock.get(LEAGUE_URL, json=league_json)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unexpected_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(
        "custom_components.espn_fantasy_hockey.config_flow.EspnFantasyHockeyApi.async_get_league",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ENTRY_DATA
        )

    assert result["errors"] == {"base": "unknown"}


async def test_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(LEAGUE_URL, status=HTTPStatus.UNAUTHORIZED)
    new_cookies = {CONF_ESPN_S2: "new-s2", CONF_SWID: "{new-swid}"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_cookies
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(LEAGUE_URL, json=league_json)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_cookies
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {**ENTRY_DATA, **new_cookies}


async def test_options_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    coordinator = config_entry.runtime_data

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    team_field = next(k for k in result["data_schema"].schema if k == CONF_MY_TEAM)
    options = result["data_schema"].schema[team_field].config["options"]
    assert options[0] == {"value": "auto", "label": "Automatic (Blue Liners)"}
    assert [o["label"] for o in options[1:]] == [
        "Blue Liners",
        "Five Hole Heroes",
        "Ice Wolves",
        "Top Shelf",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MY_TEAM: "1", CONF_LIVE_INTERVAL: 5.0, CONF_NORMAL_INTERVAL: 30.0},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_MY_TEAM: "1",
        CONF_LIVE_INTERVAL: 5,
        CONF_NORMAL_INTERVAL: 30,
    }
    # New options take effect through a reload.
    assert config_entry.runtime_data is not coordinator
    assert config_entry.runtime_data.data.my_team_id == 1
