"""Repairs: switch a league to its new season once ESPN has renewed it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import CONF_LEAGUE_ID, CONF_SEASON, DOMAIN


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the fix flow for a "new season" issue."""
    assert data is not None
    return NewSeasonRepairFlow(data["entry_id"], data["season"])


class NewSeasonRepairFlow(RepairsFlow):
    """Point the config entry at the new season, keeping its entities."""

    def __init__(self, entry_id: str, season: int) -> None:
        self._entry_id = entry_id
        self._season = season

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start with the confirmation step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for confirmation, then switch seasons."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")

        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"season": str(self._season)},
            )

        unique_id = f"{entry.data[CONF_LEAGUE_ID]}_{self._season}"
        if any(
            other.unique_id == unique_id
            for other in self.hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ):
            return self.async_abort(
                reason="already_configured",
                description_placeholders={"season": str(self._season)},
            )

        # Entity unique IDs don't include the season, so entities and dashboards
        # carry over. The title usually contains the season year; update it too.
        old_season = str(entry.data[CONF_SEASON])
        self.hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_SEASON: self._season},
            unique_id=unique_id,
            title=entry.title.replace(old_season, str(self._season)),
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_create_entry(data={})
