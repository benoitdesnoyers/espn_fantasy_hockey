"""Data update coordinator for ESPN Fantasy Hockey."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .analysis import update_interval
from .api import (
    EspnApiError,
    EspnAuthError,
    EspnFantasyHockeyApi,
    League,
    ProSchedule,
    Team,
    Transaction,
)
from .const import (
    CONF_LIVE_INTERVAL,
    CONF_MY_TEAM,
    CONF_NORMAL_INTERVAL,
    CONF_SEASON,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_NORMAL_INTERVAL,
    DOMAIN,
    EVENT_TRANSACTION,
    LOGO_PROXY_URL,
    MY_TEAM_AUTO,
    PRIVATE_LOGO_HOST,
    RECENT_TRANSACTIONS,
    SCHEDULE_REFRESH_INTERVAL,
    SEASON_CHECK_INTERVAL,
    TRANSACTIONS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type EspnFantasyHockeyConfigEntry = ConfigEntry[EspnFantasyHockeyCoordinator]


@dataclass
class LeagueData:
    """Everything the entities read, refreshed together."""

    league: League
    schedule: ProSchedule
    my_team_id: int | None
    now: datetime
    transactions: list[Transaction] = field(default_factory=list)
    # Transactions first seen in this update (empty on the first update).
    new_transactions: list[Transaction] = field(default_factory=list)
    player_names: dict[int, str] = field(default_factory=dict)

    @property
    def my_team(self) -> Team | None:
        if self.my_team_id is None:
            return None
        return self.league.teams.get(self.my_team_id)


def new_season_issue_id(entry: ConfigEntry) -> str:
    """Repairs issue id for "this league has a new season"."""
    return f"new_season_{entry.entry_id}"


class EspnFantasyHockeyCoordinator(DataUpdateCoordinator[LeagueData]):
    """Polls ESPN for league data, faster while NHL games are being played."""

    config_entry: EspnFantasyHockeyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EspnFantasyHockeyConfigEntry,
        api: EspnFantasyHockeyApi,
    ) -> None:
        self.options = dict(entry.options)  # as applied; see _async_options_updated
        options = entry.options
        self._live_interval = timedelta(
            minutes=options.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL)
        )
        self._normal_interval = timedelta(
            minutes=options.get(CONF_NORMAL_INTERVAL, DEFAULT_NORMAL_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )
        self.api = api
        self._schedule = ProSchedule()
        self._schedule_fetched: datetime | None = None
        self._transactions: list[Transaction] | None = None
        self._transactions_fetched: datetime | None = None
        self._player_names: dict[int, str] = {}
        self._season_checked: datetime | None = None
        # Proxied logos by team: (ESPN URL, bytes, content type). A new upload gets a
        # new URL, so keying on the team keeps one image per team at most.
        self._logos: dict[int, tuple[str, bytes, str]] = {}

    async def _async_update_data(self) -> LeagueData:
        try:
            league = await self.api.async_get_league()
        except EspnAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EspnApiError as err:
            raise UpdateFailed(str(err)) from err

        # The extras below are best effort: a failure keeps their previous values.
        now = dt_util.utcnow()
        await self._async_refresh_schedule(now)
        new_transactions = await self._async_refresh_transactions(league, now)
        await self._async_check_next_season(league, now)

        self.update_interval = update_interval(
            self._schedule, now, self._live_interval, self._normal_interval
        )
        return LeagueData(
            league=league,
            schedule=self._schedule,
            my_team_id=self._my_team_id(league),
            now=now,
            transactions=(self._transactions or [])[:RECENT_TRANSACTIONS],
            new_transactions=new_transactions,
            player_names=self._player_names,
        )

    def _my_team_id(self, league: League) -> int | None:
        """The team chosen in the options, else the one owned by the cookie's user."""
        chosen = self.config_entry.options.get(CONF_MY_TEAM, MY_TEAM_AUTO)
        if chosen != MY_TEAM_AUTO and int(chosen) in league.teams:
            return int(chosen)
        return league.my_team_id

    @staticmethod
    def _is_due(last: datetime | None, now: datetime, every: timedelta) -> bool:
        return last is None or now - last >= every

    async def _async_refresh_schedule(self, now: datetime) -> None:
        if not self._is_due(self._schedule_fetched, now, SCHEDULE_REFRESH_INTERVAL):
            return
        try:
            self._schedule = await self.api.async_get_pro_schedule()
        except EspnApiError as err:
            _LOGGER.debug("Keeping the previous NHL schedule: %s", err)
            return
        self._schedule_fetched = now

    async def _async_refresh_transactions(
        self, league: League, now: datetime
    ) -> list[Transaction]:
        """Fetch transactions when due; return and announce the ones not seen before."""
        if not self._is_due(self._transactions_fetched, now, TRANSACTIONS_INTERVAL):
            return []
        try:
            transactions = await self.api.async_get_transactions()
        except EspnApiError as err:
            _LOGGER.debug("Keeping the previous transactions: %s", err)
            return []
        self._transactions_fetched = now

        previous, self._transactions = self._transactions, transactions
        await self._async_resolve_player_names(league, transactions)
        if previous is None:
            return []  # first load: nothing counts as new
        seen = {t.id for t in previous}
        new = [t for t in transactions if t.id not in seen]
        for transaction in reversed(new):  # oldest first
            self.hass.bus.async_fire(
                EVENT_TRANSACTION,
                describe_transaction(transaction, league, self._player_names)
                | {"config_entry_id": self.config_entry.entry_id},
            )
        return new

    async def _async_resolve_player_names(
        self, league: League, transactions: list[Transaction]
    ) -> None:
        """Name every player in recent transactions; dropped ones need a lookup."""
        for team in league.teams.values():
            for player in team.roster:
                self._player_names[player.id] = player.name
        missing = {
            item.player_id
            for t in transactions[:RECENT_TRANSACTIONS]
            for item in t.items
            if item.player_id not in self._player_names
        }
        try:
            self._player_names |= await self.api.async_get_player_names(missing)
        except EspnApiError as err:
            _LOGGER.debug("Could not look up player names: %s", err)

    async def _async_check_next_season(self, league: League, now: datetime) -> None:
        """Offer a switch (through Repairs) once the league is renewed."""
        if not self._is_due(self._season_checked, now, SEASON_CHECK_INTERVAL):
            return
        next_season = self.config_entry.data[CONF_SEASON] + 1
        try:
            renewed = await self.api.async_season_exists(next_season)
        except EspnApiError as err:
            _LOGGER.debug("Could not check for next season: %s", err)
            return
        self._season_checked = now

        issue_id = new_season_issue_id(self.config_entry)
        if not renewed:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="new_season",
            translation_placeholders={
                "league": league.name.strip(),
                "season": str(next_season),
            },
            data={"entry_id": self.config_entry.entry_id, "season": next_season},
        )

    def logo_url(self, team: Team) -> str | None:
        """Return a URL browsers can load: direct, or via HA for private uploads."""
        if not team.logo:
            return None
        logo = urlparse(team.logo)
        if logo.hostname != PRIVATE_LOGO_HOST or not self.api.has_cookies:
            return team.logo
        path = LOGO_PROXY_URL.format(
            entry_id=self.config_entry.entry_id, team_id=team.id
        )
        # The query string changes with the logo, so browsers fetch the new one.
        return f"{path}?v={logo.path.rsplit('/', 1)[-1][:8]}"

    async def async_get_logo(self, team: Team) -> tuple[bytes, str]:
        """Return a team's logo bytes and content type, downloading on change."""
        cached = self._logos.get(team.id)
        if cached is None or cached[0] != team.logo:
            body, content_type = await self.api.async_get_image(team.logo)
            cached = self._logos[team.id] = (team.logo, body, content_type)
        return cached[1], cached[2]


def describe_transaction(
    transaction: Transaction, league: League, player_names: dict[int, str]
) -> dict[str, object]:
    """A transaction as plain data, for events and sensor attributes."""

    def team_name(team_id: int | None) -> str | None:
        team = league.teams.get(team_id) if team_id is not None else None
        return team.name if team else None

    def players(kind: str) -> list[str]:
        return [
            player_names.get(i.player_id, str(i.player_id))
            for i in transaction.items
            if i.kind == kind
        ]

    added, dropped, traded = players("ADD"), players("DROP"), players("TRADE")
    actions = [
        f"{verb} {', '.join(names)}"
        for verb, names in (("added", added), ("dropped", dropped), ("traded", traded))
        if names
    ]
    team = team_name(transaction.team_id)
    return {
        "id": transaction.id,
        "type": transaction.kind,
        "date": transaction.date.isoformat(),
        "team": team,
        "team_id": transaction.team_id,
        "added": added,
        "dropped": dropped,
        "traded": traded,
        "description": " ".join([team or "A team", " and ".join(actions)]).strip(),
    }
