"""Data update coordinator for ESPN Fantasy Hockey."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EspnApiError, EspnAuthError, EspnFantasyHockeyApi, League
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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

    async def _async_update_data(self) -> League:
        try:
            return await self.api.async_get_league()
        except EspnAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EspnApiError as err:
            raise UpdateFailed(str(err)) from err
