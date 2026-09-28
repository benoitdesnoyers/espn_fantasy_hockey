"""Sensors for ESPN Fantasy Hockey."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Team
from .const import DOMAIN
from .coordinator import EspnFantasyHockeyConfigEntry, EspnFantasyHockeyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EspnFantasyHockeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create standing, matchup and roster sensors per team, plus a league sensor."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [LeagueMatchupPeriodSensor(coordinator)]
    for team_id in coordinator.data.teams:
        entities.append(TeamStandingSensor(coordinator, team_id))
        entities.append(TeamMatchupSensor(coordinator, team_id))
        entities.append(TeamRosterSensor(coordinator, team_id))
    async_add_entities(entities)


class EspnFantasyHockeyEntity(CoordinatorEntity[EspnFantasyHockeyCoordinator]):
    """Base entity: all sensors hang off a single device per league."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="ESPN",
            model="Fantasy Hockey League",
            entry_type=DeviceEntryType.SERVICE,
        )


class LeagueMatchupPeriodSensor(EspnFantasyHockeyEntity, SensorEntity):
    """Current matchup period of the league."""

    _attr_translation_key = "matchup_period"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator) -> None:
        super().__init__(coordinator, "matchup_period")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.current_matchup_period

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        league = self.coordinator.data
        return {
            "league_id": league.id,
            "league_name": league.name,
            "season": league.season,
            "scoring_type": league.scoring_type,
            "scoring_period": league.scoring_period,
            # The team owned by the account whose cookies were entered; cards default to it.
            "my_team_id": league.my_team_id,
        }


class _TeamEntity(EspnFantasyHockeyEntity):
    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int, key: str) -> None:
        super().__init__(coordinator, f"team_{team_id}_{key}")
        self._team_id = team_id

    @property
    def team(self) -> Team | None:
        return self.coordinator.data.teams.get(self._team_id)

    @property
    def available(self) -> bool:
        return super().available and self.team is not None

    @property
    def entity_picture(self) -> str | None:
        return self.coordinator.logo_url(self.team) if self.team else None


class TeamStandingSensor(_TeamEntity, SensorEntity):
    """A team's position in the standings; record details as attributes."""

    _attr_icon = "mdi:podium"
    # Names stay dynamic (see `name`); the key only tags the entity's role for the cards.
    _attr_translation_key = "team_standing"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "standing")

    @property
    def name(self) -> str | None:
        return f"{self.team.name} standing" if self.team else None

    @property
    def native_value(self) -> int | None:
        team = self.team
        if team is None:
            return None
        return team.final_rank or team.seed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        team = self.team
        if team is None:
            return {}
        return {
            "team_id": team.id,
            "team_name": team.name,
            "abbrev": team.abbrev,
            "owners": team.owners,
            "record": f"{team.wins}-{team.losses}-{team.ties}",
            "wins": team.wins,
            "losses": team.losses,
            "ties": team.ties,
            "points_for": team.points_for,
            "points_against": team.points_against,
            "games_back": team.games_back,
            "streak": team.streak,
        }


class TeamMatchupSensor(_TeamEntity, SensorEntity):
    """A team's score in the current matchup (points, or W-L-T for categories)."""

    _attr_icon = "mdi:hockey-sticks"
    _attr_translation_key = "team_matchup"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "matchup")

    @property
    def name(self) -> str | None:
        return f"{self.team.name} matchup" if self.team else None

    @property
    def native_value(self) -> float | str | None:
        matchup = self.coordinator.data.matchup_for(self._team_id)
        if matchup is None:
            return None
        _, own_score, _ = matchup.opponent_of(self._team_id)
        return own_score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        league = self.coordinator.data
        matchup = league.matchup_for(self._team_id)
        if matchup is None:
            return {
                "team_id": self._team_id,
                "team_name": self.team.name if self.team else None,
                "matchup_period": league.current_matchup_period,
                "opponent": None,
            }
        opponent_id, own_score, opponent_score = matchup.opponent_of(self._team_id)
        opponent = league.teams.get(opponent_id) if opponent_id is not None else None
        return {
            "team_id": self._team_id,
            "team_name": self.team.name if self.team else None,
            "matchup_period": matchup.matchup_period,
            "opponent": opponent.name if opponent else None,  # None means a bye
            "opponent_id": opponent_id,
            "opponent_logo": self.coordinator.logo_url(opponent) if opponent else None,
            "score": own_score,
            "opponent_score": opponent_score,
            "winner": matchup.winner,
        }


class TeamRosterSensor(_TeamEntity, SensorEntity):
    """A team's roster; state is the season fantasy points of its current players."""

    _attr_icon = "mdi:account-group"
    _attr_translation_key = "team_roster"
    # The player list is large and changes every refresh; keep it out of history.
    _unrecorded_attributes = frozenset({"players"})

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "roster")

    @property
    def name(self) -> str | None:
        return f"{self.team.name} roster" if self.team else None

    @property
    def native_value(self) -> float | None:
        team = self.team
        if team is None:
            return None
        return round(sum(p.points.get("season", 0.0) for p in team.roster), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        team = self.team
        if team is None:
            return {}
        return {
            "team_id": team.id,
            "team_name": team.name,
            "player_count": len(team.roster),
            "injured": [p.name for p in team.roster if p.injury_status not in (None, "ACTIVE", "NORMAL")],
            "players": [
                {
                    "name": p.name,
                    "position": p.position,
                    "slot": p.lineup_slot,
                    "nhl_team": p.pro_team,
                    "headshot": p.headshot,
                    "injury": p.injury_status,
                    "points_season": p.points.get("season"),
                    "points_last_7": p.points.get("last_7"),
                    "points_last_15": p.points.get("last_15"),
                    "points_last_30": p.points.get("last_30"),
                    "points_projected": p.points.get("projected"),
                    "stats": p.stats,
                }
                for p in team.roster
            ],
        }
