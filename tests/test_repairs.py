"""Tests for switching a league to its new season."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import CONF_SEASON, DOMAIN
from custom_components.espn_fantasy_hockey.repairs import async_create_fix_flow

from .conftest import SEASON, mock_espn_responses, setup_integration


def _issue(hass: HomeAssistant, entry: MockConfigEntry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"new_season_{entry.entry_id}")


async def test_no_issue_while_the_league_is_not_renewed(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await setup_integration(hass, config_entry)
    assert _issue(hass, config_entry) is None


async def test_switch_to_the_new_season(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    mock_espn_responses(aioclient_mock, league_json, next_season_status=200)
    mock_espn_responses(aioclient_mock, league_json, season=SEASON + 1)
    await setup_integration(hass, config_entry)
    entities_before = {
        e.entity_id
        for e in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
    }

    issue = _issue(hass, config_entry)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {"league": "Test League", "season": "2027"}

    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_init()
    assert result["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert config_entry.data[CONF_SEASON] == SEASON + 1
    assert config_entry.unique_id == f"12345_{SEASON + 1}"
    assert config_entry.title == "Test League (2027)"
    # Same entities (and so dashboards) after the switch.
    entities_after = {
        e.entity_id
        for e in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
    }
    assert entities_after == entities_before


async def test_switch_aborts_when_new_season_is_already_set_up(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    league_json: dict[str, Any],
) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=f"12345_{SEASON + 1}").add_to_hass(hass)
    mock_espn_responses(aioclient_mock, league_json, next_season_status=200)
    await setup_integration(hass, config_entry)

    issue = _issue(hass, config_entry)
    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    result = await flow.async_step_confirm({})

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_SEASON] == SEASON
