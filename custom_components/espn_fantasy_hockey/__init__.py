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
from .const import (
    CARDS_ENTRYPOINT,
    CARDS_URL,
    CONF_ESPN_S2,
    CONF_LEAGUE_ID,
    CONF_SEASON,
    CONF_SWID,
    DOMAIN,
)
from .coordinator import EspnFantasyHockeyConfigEntry, EspnFantasyHockeyCoordinator
from .logo_view import EspnLogoView

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]
FRONTEND_DIR = Path(__file__).parent / "frontend"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register what every league shares: the logo proxy and the dashboard cards."""
    hass.http.register_view(EspnLogoView())

    # Serve the cards and load them on every dashboard, so users don't have to add a
    # Lovelace resource. The modules import each other by relative path, so the
    # build id goes in the path (not a query string) to bust caches for all of them.
    build_id = await hass.async_add_executor_job(_frontend_build_id)
    url = f"{CARDS_URL}/{build_id}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, str(FRONTEND_DIR), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{url}/{CARDS_ENTRYPOINT}")
    return True


def _frontend_build_id() -> str:
    """Identify the installed card files; changes whenever any of them does."""
    newest = max(path.stat().st_mtime_ns for path in FRONTEND_DIR.rglob("*.js"))
    return format(newest, "x")


async def async_setup_entry(
    hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry
) -> bool:
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
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry
) -> None:
    """Apply new options (team, polling intervals) by reloading.

    The listener also fires for data changes (new cookies, new season); those
    flows reload on their own, so only react when the options differ.
    """
    if entry.options != entry.runtime_data.options:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
