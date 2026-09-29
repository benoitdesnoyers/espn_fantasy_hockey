"""Tests for the diagnostics download."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import MY_SWID, MY_TEAM_ID, setup_integration


async def test_diagnostics_hide_credentials_and_owners(
    hass: HomeAssistant,
    hass_client,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    assert await async_setup_component(hass, "diagnostics", {})
    await setup_integration(hass, config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    dumped = json.dumps(result)

    assert result["entry"]["data"]["espn_s2"] == "**REDACTED**"
    assert result["entry"]["data"]["swid"] == "**REDACTED**"
    assert "fake-espn-s2" not in dumped
    assert MY_SWID not in dumped
    assert "Owner 4" not in dumped
    assert result["coordinator"]["my_team_id"] == MY_TEAM_ID
    assert result["coordinator"]["games_today"] == 5
    assert len(result["league"]["teams"]) == 4
