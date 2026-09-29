"""Config flow for ESPN Fantasy Hockey."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .api import (
    EspnApiError,
    EspnAuthError,
    EspnFantasyHockeyApi,
    EspnLeagueNotFound,
    League,
)
from .const import (
    CONF_ESPN_S2,
    CONF_LEAGUE_ID,
    CONF_LIVE_INTERVAL,
    CONF_MY_TEAM,
    CONF_NORMAL_INTERVAL,
    CONF_SEASON,
    CONF_SWID,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_NORMAL_INTERVAL,
    DOMAIN,
    MY_TEAM_AUTO,
)

_LOGGER = logging.getLogger(__name__)

# From August on, the upcoming NHL season is the one people are setting up.
SEASON_ROLLOVER_MONTH = 8


def _default_season() -> int:
    """ESPN names a hockey season after the year it ends (2026-27 -> 2027)."""
    today = date.today()
    return today.year + 1 if today.month >= SEASON_ROLLOVER_MONTH else today.year


class EspnFantasyHockeyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESPN Fantasy Hockey."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return EspnFantasyHockeyOptionsFlow()

    async def _async_validate(
        self, data: Mapping[str, Any]
    ) -> tuple[League | None, dict[str, str]]:
        api = EspnFantasyHockeyApi(
            async_get_clientsession(self.hass),
            league_id=data[CONF_LEAGUE_ID],
            season=data[CONF_SEASON],
            espn_s2=data.get(CONF_ESPN_S2),
            swid=data.get(CONF_SWID),
        )
        try:
            return await api.async_get_league(), {}
        except EspnAuthError:
            return None, {"base": "invalid_auth"}
        except EspnLeagueNotFound:
            return None, {"base": "league_not_found"}
        except EspnApiError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error validating ESPN league")
            return None, {"base": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for league details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {k: v for k, v in user_input.items() if v not in (None, "")}
            await self.async_set_unique_id(
                f"{user_input[CONF_LEAGUE_ID]}_{user_input[CONF_SEASON]}"
            )
            self._abort_if_unique_id_configured()

            league, errors = await self._async_validate(user_input)
            if league is not None:
                return self.async_create_entry(
                    title=f"{league.name} ({league.season})", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_LEAGUE_ID): vol.Coerce(int),
                vol.Required(CONF_SEASON, default=_default_season()): vol.Coerce(int),
                vol.Optional(CONF_ESPN_S2): str,
                vol.Optional(CONF_SWID): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Triggered when ESPN rejects the stored cookies."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for fresh espn_s2 / SWID cookies."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            league, errors = await self._async_validate(data)
            if league is not None:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_ESPN_S2): str, vol.Required(CONF_SWID): str}
            ),
            errors=errors,
        )


def _minutes(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            unit_of_measurement="min",
            mode=NumberSelectorMode.BOX,
        )
    )


class EspnFantasyHockeyOptionsFlow(OptionsFlow):
    """Choose "my team" and how often to poll ESPN."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_MY_TEAM: user_input[CONF_MY_TEAM],
                    CONF_LIVE_INTERVAL: int(user_input[CONF_LIVE_INTERVAL]),
                    CONF_NORMAL_INTERVAL: int(user_input[CONF_NORMAL_INTERVAL]),
                }
            )

        # Team names come from the running integration; without it, only "auto".
        teams: list[SelectOptionDict] = []
        detected = None
        if coordinator := getattr(self.config_entry, "runtime_data", None):
            league = coordinator.data.league
            detected = (
                league.teams.get(league.my_team_id) if league.my_team_id else None
            )
            teams = [
                SelectOptionDict(value=str(team.id), label=team.name)
                for team in sorted(league.teams.values(), key=lambda t: t.name.lower())
            ]
        auto_label = f"Automatic ({detected.name})" if detected else "Automatic"

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MY_TEAM, default=options.get(CONF_MY_TEAM, MY_TEAM_AUTO)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=MY_TEAM_AUTO, label=auto_label),
                            *teams,
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_LIVE_INTERVAL,
                    default=options.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL),
                ): _minutes(1, 15),
                vol.Required(
                    CONF_NORMAL_INTERVAL,
                    default=options.get(CONF_NORMAL_INTERVAL, DEFAULT_NORMAL_INTERVAL),
                ): _minutes(5, 120),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
