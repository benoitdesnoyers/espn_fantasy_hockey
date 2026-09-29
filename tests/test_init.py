"""Tests for setting up and unloading the integration."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import CARDS_ENTRYPOINT, CARDS_URL

from .conftest import LEAGUE_URL


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_espn: AiohttpClientMocker
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_espn_is_down(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    aioclient_mock.get(LEAGUE_URL, status=HTTPStatus.SERVICE_UNAVAILABLE)
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_rejected_cookies_start_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    aioclient_mock.get(LEAGUE_URL, status=HTTPStatus.UNAUTHORIZED)
    await _setup(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_cards_are_served_and_loaded(
    hass: HomeAssistant,
    hass_client,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    await async_setup_component(hass, "http", {})
    await _setup(hass, config_entry)

    [entrypoint] = [
        url
        for url in hass.data[DATA_EXTRA_MODULE_URL].urls
        if url.startswith(CARDS_URL)
    ]
    assert entrypoint.endswith(f"/{CARDS_ENTRYPOINT}")

    client = await hass_client()
    for path in (entrypoint, entrypoint.replace(CARDS_ENTRYPOINT, "lib/data.js")):
        resp = await client.get(path)
        assert resp.status == HTTPStatus.OK, path
        assert "javascript" in resp.headers["Content-Type"]
