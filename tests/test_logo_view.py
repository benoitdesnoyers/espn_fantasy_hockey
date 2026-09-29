"""Tests for the private logo proxy."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import MY_TEAM_ID

PRIVATE_LOGO = (
    "https://mystique-api.fantasy.espn.com/apis/v1/domains/lm/images/"
    "00000002-aaaa-bbbb-cccc-000000000000"
)
PNG = b"\x89PNG fake image"


async def _client(hass: HomeAssistant, entry: MockConfigEntry, hass_client_no_auth):
    await async_setup_component(hass, "http", {})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await hass_client_no_auth()


def _logo_path(entry: MockConfigEntry, team_id: int | str) -> str:
    return f"/api/espn_fantasy_hockey/logo/{entry.entry_id}/{team_id}"


async def test_serves_logo_with_cookies_once(
    hass: HomeAssistant,
    hass_client_no_auth,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    mock_espn.get(PRIVATE_LOGO, content=PNG, headers={"Content-Type": "image/png"})
    client = await _client(hass, config_entry, hass_client_no_auth)

    for _ in range(2):
        resp = await client.get(_logo_path(config_entry, MY_TEAM_ID))
        assert resp.status == HTTPStatus.OK
        assert resp.content_type == "image/png"
        assert await resp.read() == PNG

    logo_calls = [c for c in mock_espn.mock_calls if str(c[1]) == PRIVATE_LOGO]
    assert len(logo_calls) == 1, "the logo should be downloaded once, then cached"
    assert "espn_s2=fake-espn-s2" in logo_calls[0][3]["Cookie"]


async def test_upstream_errors_become_bad_gateway(
    hass: HomeAssistant,
    hass_client_no_auth,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    mock_espn.get(
        PRIVATE_LOGO, text="<html>login</html>", headers={"Content-Type": "text/html"}
    )
    client = await _client(hass, config_entry, hass_client_no_auth)

    resp = await client.get(_logo_path(config_entry, MY_TEAM_ID))

    assert resp.status == HTTPStatus.BAD_GATEWAY


async def test_unknown_targets_are_not_found(
    hass: HomeAssistant,
    hass_client_no_auth,
    config_entry: MockConfigEntry,
    mock_espn: AiohttpClientMocker,
) -> None:
    client = await _client(hass, config_entry, hass_client_no_auth)

    for path in (
        _logo_path(config_entry, 99),
        _logo_path(config_entry, "not-a-number"),
        "/api/espn_fantasy_hockey/logo/unknown-entry/2",
    ):
        resp = await client.get(path)
        assert resp.status == HTTPStatus.NOT_FOUND, path
