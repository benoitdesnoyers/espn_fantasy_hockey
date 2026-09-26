"""The ESPN Fantasy Hockey integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EspnFantasyHockeyApi
from .const import CONF_ESPN_S2, CONF_LEAGUE_ID, CONF_SEASON, CONF_SWID
from .coordinator import EspnFantasyHockeyConfigEntry, EspnFantasyHockeyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry) -> bool:
    """Set up ESPN Fantasy Hockey from a config entry."""
    api = EspnFantasyHockeyApi(
        async_get_clientsession(hass),
        league_id=entry.data[CONF_LEAGUE_ID],
        season=entry.data[CONF_SEASON],
        espn_s2=entry.data.get(CONF_ESPN_S2),
        swid=entry.data.get(CONF_SWID),
    )
    coordinator = EspnFantasyHockeyCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
