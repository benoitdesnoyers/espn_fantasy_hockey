"""Shared fixtures.

tests/fixtures/ holds real ESPN responses with every personal detail replaced:

- league.json: "Test League" (id 12345, season 2026), four teams, two matchups.
  Team 2 "Blue Liners" belongs to MY_SWID and has a private logo. Records, matchup
  scores and daily/weekly player points are synthetic; players and stats are real.
- pro_schedule.json: the first two weeks of the NHL schedule. Scoring period 1,
  the league's current one, is Tuesday 2026-09-29 (games 17:00-22:30 Eastern).
- transactions.json / players.json: two free-agent adds and the players' names.

Tests run at NOON_ON_GAME_DAY unless they move the clock.
"""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.espn_fantasy_hockey.const import (
    CONF_ESPN_S2,
    CONF_LEAGUE_ID,
    CONF_SEASON,
    CONF_SWID,
    DOMAIN,
)

LEAGUE_ID = 12345
SEASON = 2026
MY_SWID = "{00000004-0000-4000-8000-000000000004}"
MY_TEAM_ID = 2
NOON_ON_GAME_DAY = "2026-09-29T16:00:00+00:00"

SEASON_URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fhl/seasons/{SEASON}"
LEAGUE_URL = f"{SEASON_URL}/segments/0/leagues/{LEAGUE_ID}"

ENTRY_DATA = {
    CONF_LEAGUE_ID: LEAGUE_ID,
    CONF_SEASON: SEASON,
    CONF_ESPN_S2: "fake-espn-s2",
    CONF_SWID: MY_SWID,
}
FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """A fresh copy of a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Allow Home Assistant to load the integration from custom_components/."""
    yield


@pytest.fixture(autouse=True)
def game_day(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Run every test at noon Eastern on the fixture's first game day."""
    freezer.move_to(NOON_ON_GAME_DAY)
    return freezer


@pytest.fixture
def league_json() -> dict[str, Any]:
    """A fresh copy of the ESPN league response."""
    return load_fixture("league.json")


def espn_urls(season: int = SEASON) -> dict[str, str]:
    """The ESPN endpoints for a season of the fixture league."""
    season_url = SEASON_URL.replace(f"/seasons/{SEASON}", f"/seasons/{season}")
    league_url = f"{season_url}/segments/0/leagues/{LEAGUE_ID}"
    return {
        "season": season_url,
        "league": league_url,
        "transactions": f"{league_url}?view=mTransactions2",
        "players": f"{season_url}/players",
        "next_season": league_url.replace(
            f"/seasons/{season}/", f"/seasons/{season + 1}/"
        ),
    }


def mock_espn_responses(
    aioclient_mock: AiohttpClientMocker,
    league: dict[str, Any],
    *,
    season: int = SEASON,
    transactions: dict[str, Any] | None = None,
    next_season_status: int = 404,
    schedule_status: int = 200,
) -> None:
    """Register every ESPN endpoint the integration calls for a season.

    More specific URLs go first: a matcher without a query string matches any query.
    """
    urls = espn_urls(season)
    aioclient_mock.get(
        urls["transactions"], json=transactions or load_fixture("transactions.json")
    )
    aioclient_mock.get(urls["next_season"], status=next_season_status, json={})
    aioclient_mock.get(urls["players"], json=load_fixture("players.json"))
    aioclient_mock.get(urls["league"], json=league)
    aioclient_mock.get(
        urls["season"], status=schedule_status, json=load_fixture("pro_schedule.json")
    )


@pytest.fixture
def mock_espn(
    aioclient_mock: AiohttpClientMocker, league_json: dict[str, Any]
) -> AiohttpClientMocker:
    """Answer every ESPN request with the fixtures."""
    mock_espn_responses(aioclient_mock, league_json)
    return aioclient_mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry for the fixture league, logged in as the owner of team 2."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Test League ({SEASON})",
        unique_id=f"{LEAGUE_ID}_{SEASON}",
        data=ENTRY_DATA,
    )


async def setup_integration(hass, entry: MockConfigEntry) -> None:
    """Add the entry and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
