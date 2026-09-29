"""Sensors for ESPN Fantasy Hockey."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .analysis import lineup_issues, projected_score, remaining_matchup_games
from .api import League, MatchupTeam, Player, ProSchedule, Team
from .const import PRO_TEAMS, STAT_ABBREVIATIONS
from .coordinator import (
    EspnFantasyHockeyConfigEntry,
    EspnFantasyHockeyCoordinator,
    describe_transaction,
)
from .entity import EspnFantasyHockeyEntity

HEALTHY_STATUSES = frozenset({"ACTIVE", "NORMAL"})
MAX_STATE_LENGTH = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EspnFantasyHockeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create league sensors, then standing, matchup and roster sensors per team."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        LeagueMatchupPeriodSensor(coordinator),
        LatestTransactionSensor(coordinator),
        LineupIssuesSensor(coordinator),
    ]
    for team_id in coordinator.data.league.teams:
        entities += [
            TeamStandingSensor(coordinator, team_id),
            TeamMatchupSensor(coordinator, team_id),
            TeamRosterSensor(coordinator, team_id),
        ]
    async_add_entities(entities)


def game_today(player: Player, league: League, schedule: ProSchedule) -> dict[str, Any]:
    """When a player's NHL team plays today, and against whom."""
    game = schedule.game_for(player.pro_team_id, league.scoring_period)
    if game is None:
        return {"game_today": None, "opponent_today": None}
    home = game.home_team_id == player.pro_team_id
    opponent_id = game.away_team_id if home else game.home_team_id
    opponent = PRO_TEAMS.get(opponent_id, str(opponent_id))
    return {
        "game_today": game.start.isoformat(),
        "opponent_today": f"vs {opponent}" if home else f"@ {opponent}",
    }


class LeagueMatchupPeriodSensor(EspnFantasyHockeyEntity, SensorEntity):
    """Current matchup period of the league."""

    _attr_translation_key = "matchup_period"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator) -> None:
        super().__init__(coordinator, "matchup_period")

    @property
    def native_value(self) -> int | None:
        return self.data.league.current_matchup_period

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        league = self.data.league
        return {
            "league_id": league.id,
            "league_name": league.name,
            "season": league.season,
            "scoring_type": league.scoring_type,
            "is_category_league": league.is_category_league,
            "scoring_period": league.scoring_period,
            # The team treated as the user's: chosen in the options, else detected.
            "my_team_id": self.data.my_team_id,
            "update_interval_seconds": int(
                self.coordinator.update_interval.total_seconds()
            )
            if self.coordinator.update_interval
            else None,
        }


class LatestTransactionSensor(EspnFantasyHockeyEntity, SensorEntity):
    """The league's latest add, drop, waiver claim or trade."""

    _attr_translation_key = "latest_transaction"
    _attr_icon = "mdi:swap-horizontal"
    _unrecorded_attributes = frozenset({"recent"})

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator) -> None:
        super().__init__(coordinator, "latest_transaction")

    def _recent(self) -> list[dict[str, Any]]:
        return [
            describe_transaction(t, self.data.league, self.data.player_names)
            for t in self.data.transactions
        ]

    @property
    def native_value(self) -> str | None:
        recent = self._recent()
        return str(recent[0]["description"])[:MAX_STATE_LENGTH] if recent else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"recent": self._recent()}


class TeamEntity(EspnFantasyHockeyEntity):
    """A sensor about one team, named "<team> <translation>".

    The translation key also tells the dashboard cards which role a sensor plays.
    """

    def __init__(
        self, coordinator: EspnFantasyHockeyCoordinator, team_id: int, key: str
    ) -> None:
        super().__init__(coordinator, f"team_{team_id}_{key}")
        self._team_id = team_id
        self._attr_translation_key = f"team_{key}"
        self._attr_translation_placeholders = {
            "team": coordinator.data.league.teams[team_id].name
        }

    @property
    def team(self) -> Team | None:
        return self.data.league.teams.get(self._team_id)

    @property
    def available(self) -> bool:
        return super().available and self.team is not None

    @property
    def entity_picture(self) -> str | None:
        return self.coordinator.logo_url(self.team) if self.team else None

    def _team_attributes(self) -> dict[str, Any]:
        return {
            "team_id": self._team_id,
            "team_name": self.team.name if self.team else None,
        }


class TeamStandingSensor(TeamEntity, SensorEntity):
    """A team's position in the standings; record details as attributes."""

    _attr_icon = "mdi:podium"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "standing")

    @property
    def native_value(self) -> int | None:
        if (team := self.team) is None:
            return None
        return team.final_rank or team.seed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (team := self.team) is None:
            return {}
        return {
            **self._team_attributes(),
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


class TeamMatchupSensor(TeamEntity, SensorEntity):
    """A team's score in the current matchup (points, or W-L-T for categories)."""

    _attr_icon = "mdi:hockey-sticks"
    _unrecorded_attributes = frozenset({"players", "categories"})

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "matchup")

    @property
    def native_value(self) -> float | str | None:
        matchup = self.data.league.matchup_for(self._team_id)
        return matchup.sides(self._team_id)[0].score if matchup else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        league = self.data.league
        matchup = league.matchup_for(self._team_id)
        if matchup is None or self.team is None:
            return {
                **self._team_attributes(),
                "matchup_period": league.current_matchup_period,
                "opponent": None,
            }
        mine, theirs = matchup.sides(self._team_id)
        opponent = league.teams.get(theirs.team_id)
        remaining = remaining_matchup_games(league, self.data.schedule, self.data.now)
        attributes = {
            **self._team_attributes(),
            "matchup_period": matchup.matchup_period,
            "opponent": opponent.name if opponent else None,  # None means a bye
            "opponent_id": theirs.team_id,
            "opponent_logo": self.coordinator.logo_url(opponent) if opponent else None,
            "score": mine.score,
            "opponent_score": theirs.score,
            "winner": matchup.winner,
            # Estimates; see analysis.projected_score.
            "projected_score": projected_score(mine, self.team, remaining),
            "opponent_projected_score": (
                projected_score(theirs, opponent, remaining) if opponent else None
            ),
            "players": self._players(mine),
        }
        if league.is_category_league:
            attributes["categories"] = self._categories(league, mine, theirs)
        return attributes

    def _players(self, side: MatchupTeam) -> list[dict[str, Any]]:
        """This team's players with their points today and this matchup."""
        league, schedule = self.data.league, self.data.schedule
        return [
            {
                "name": p.name,
                "position": p.position,
                "slot": p.lineup_slot,
                "headshot": p.headshot,
                "points_today": side.points_today.get(p.id),
                "points_matchup": side.points_matchup.get(p.id),
                **game_today(p, league, schedule),
            }
            for p in self.team.roster
        ]

    @staticmethod
    def _categories(
        league: League, mine: MatchupTeam, theirs: MatchupTeam
    ) -> list[dict[str, Any]]:
        results = []
        for category in league.categories:
            own = mine.categories.get(category.stat_id)
            other = theirs.categories.get(category.stat_id)
            results.append(
                {
                    "name": category.name,
                    "abbreviation": STAT_ABBREVIATIONS.get(
                        category.name, category.name
                    ),
                    "score": own.score if own else None,
                    "opponent_score": other.score if other else None,
                    "result": own.result if own else None,
                    "lower_is_better": category.lower_is_better,
                }
            )
        return results


class TeamRosterSensor(TeamEntity, SensorEntity):
    """A team's roster; state is the season fantasy points of its current players."""

    _attr_icon = "mdi:account-group"
    # The player list is large and changes every refresh; keep it out of history.
    _unrecorded_attributes = frozenset({"players"})

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator, team_id: int) -> None:
        super().__init__(coordinator, team_id, "roster")

    @property
    def native_value(self) -> float | None:
        if (team := self.team) is None:
            return None
        return round(sum(p.points.get("season", 0.0) for p in team.roster), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (team := self.team) is None:
            return {}
        league, schedule = self.data.league, self.data.schedule
        matchup = league.matchup_for(team.id)
        side = matchup.sides(team.id)[0] if matchup else MatchupTeam(team.id, None)
        return {
            **self._team_attributes(),
            "player_count": len(team.roster),
            "injured": [
                p.name
                for p in team.roster
                if p.injury_status and p.injury_status not in HEALTHY_STATUSES
            ],
            "players": [
                {
                    "name": p.name,
                    "position": p.position,
                    "slot": p.lineup_slot,
                    "nhl_team": p.pro_team,
                    "headshot": p.headshot,
                    "injury": p.injury_status,
                    **game_today(p, league, schedule),
                    "points_today": side.points_today.get(p.id),
                    "points_matchup": side.points_matchup.get(p.id),
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


class LineupIssuesSensor(EspnFantasyHockeyEntity, SensorEntity):
    """How many of the user's starters won't score today, with suggested swaps.

    Follows whichever team is the user's (options, else detected from the cookie)
    and is unavailable when that's unknown.
    """

    _attr_translation_key = "lineup_issues"
    _attr_icon = "mdi:clipboard-alert"

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator) -> None:
        super().__init__(coordinator, "lineup_issues")

    @property
    def available(self) -> bool:
        return super().available and self.data.my_team is not None

    def _issues(self) -> list[dict[str, Any]]:
        if (team := self.data.my_team) is None:
            return []
        issues = lineup_issues(
            team, self.data.league, self.data.schedule, self.data.now
        )
        return [
            {
                "type": issue.kind,
                "slot": issue.slot,
                "player": issue.player,
                "replacement": issue.replacement,
                "message": issue.message,
            }
            for issue in issues
        ]

    @property
    def native_value(self) -> int:
        return len(self._issues())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        team = self.data.my_team
        return {
            "team_id": team.id if team else None,
            "team_name": team.name if team else None,
            "issues": self._issues(),
        }
