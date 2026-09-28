"""The ESPN Fantasy Hockey integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import EspnFantasyHockeyApi
from .const import CARDS_URL, CONF_ESPN_S2, CONF_LEAGUE_ID, CONF_SEASON, CONF_SWID, DOMAIN
from .coordinator import EspnFantasyHockeyConfigEntry, EspnFantasyHockeyCoordinator
from .logo_view import EspnLogoView

PLATFORMS: list[Platform] = [Platform.SENSOR]
CARDS_FILE = Path(__file__).parent / "frontend" / "espn-fantasy-cards.js"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register what's shared by every league: the logo proxy and the dashboard cards."""
    hass.http.register_view(EspnLogoView())

    # Serve the cards and load them on every dashboard, so users don't have to add a
    # Lovelace resource. The mtime query string busts browser caches after an update.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARDS_URL, str(CARDS_FILE), cache_headers=True)]
    )
    mtime = await hass.async_add_executor_job(lambda: int(CARDS_FILE.stat().st_mtime))
    add_extra_js_url(hass, f"{CARDS_URL}?v={mtime}")
    return True


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
