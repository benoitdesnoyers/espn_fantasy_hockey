"""Data update coordinator for ESPN Fantasy Hockey."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EspnApiError, EspnAuthError, EspnFantasyHockeyApi, League, Team
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGO_PROXY_URL, PRIVATE_LOGO_HOST

_LOGGER = logging.getLogger(__name__)

type EspnFantasyHockeyConfigEntry = ConfigEntry[EspnFantasyHockeyCoordinator]


class EspnFantasyHockeyCoordinator(DataUpdateCoordinator[League]):
    """Polls ESPN for league data."""

    config_entry: EspnFantasyHockeyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EspnFantasyHockeyConfigEntry,
        api: EspnFantasyHockeyApi,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        # Proxied logo bytes keyed by ESPN URL; a new upload gets a new URL.
        self._image_cache: dict[str, tuple[bytes, str]] = {}

    async def _async_update_data(self) -> League:
        try:
            return await self.api.async_get_league()
        except EspnAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EspnApiError as err:
            raise UpdateFailed(str(err)) from err

    def logo_url(self, team: Team) -> str | None:
        """URL a browser can load: direct for public logos, via HA for private uploads."""
        if not team.logo:
            return None
        if urlparse(team.logo).hostname == PRIVATE_LOGO_HOST and self.api.has_cookies:
            path = LOGO_PROXY_URL.format(entry_id=self.config_entry.entry_id, team_id=team.id)
            # The query string changes when the logo does, so browsers re-fetch it.
            return f"{path}?v={urlparse(team.logo).path.rsplit('/', 1)[-1][:8]}"
        return team.logo

    async def async_get_logo(self, team: Team) -> tuple[bytes, str]:
        """Return a team's logo bytes, downloading once per logo URL."""
        if team.logo not in self._image_cache:
            self._image_cache[team.logo] = await self.api.async_get_image(team.logo)
        return self._image_cache[team.logo]
