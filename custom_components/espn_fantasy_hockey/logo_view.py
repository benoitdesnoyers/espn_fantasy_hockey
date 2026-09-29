"""Serve custom team logos that ESPN only returns to logged-in users."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState

from .api import EspnApiError
from .const import DOMAIN, LOGO_PROXY_URL

_LOGGER = logging.getLogger(__name__)


class EspnLogoView(HomeAssistantView):
    """Proxy a team logo using the config entry's ESPN cookies.

    Unauthenticated because <img> tags can't send HA's auth header. It only serves
    the logo URL ESPN reported for a team in a loaded entry, never arbitrary URLs,
    and the cookies themselves never leave Home Assistant.
    """

    url = LOGO_PROXY_URL
    name = f"api:{DOMAIN}:logo"
    requires_auth = False

    async def get(
        self, request: web.Request, entry_id: str, team_id: str
    ) -> web.Response:
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            raise web.HTTPNotFound

        coordinator = entry.runtime_data
        try:
            team = coordinator.data.league.teams.get(int(team_id))
        except ValueError:
            raise web.HTTPNotFound from None
        if team is None or not team.logo:
            raise web.HTTPNotFound

        try:
            body, content_type = await coordinator.async_get_logo(team)
        except EspnApiError as err:
            _LOGGER.debug("Could not fetch logo for team %s: %s", team.name, err)
            raise web.HTTPBadGateway from err

        return web.Response(
            body=body,
            content_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
