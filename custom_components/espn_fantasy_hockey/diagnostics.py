"""Diagnostics download, with credentials and personal details removed."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ESPN_S2, CONF_SWID
from .coordinator import EspnFantasyHockeyConfigEntry

# Cookies are credentials; owner names identify people.
TO_REDACT = {CONF_ESPN_S2, CONF_SWID, "owners"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EspnFantasyHockeyConfigEntry
) -> dict[str, Any]:
    """Return the entry's configuration and the latest parsed league data."""
    coordinator = entry.runtime_data
    data = coordinator.data
    interval = coordinator.update_interval
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": interval.total_seconds() if interval else None,
            "my_team_id": data.my_team_id,
            "schedule_games": len(data.schedule.games),
            "games_today": len(data.schedule.games_in(data.league.scoring_period)),
            "transactions": [asdict(t) for t in data.transactions],
        },
        "league": async_redact_data(asdict(data.league), TO_REDACT),
    }
