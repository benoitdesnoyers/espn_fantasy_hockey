/**
 * Finding the integration's data in `hass`.
 *
 * Sensors are located through the entity registry rather than by entity ID
 * (which users can rename): each one has a translation_key naming its role and,
 * for team sensors, a `team_id` attribute. One device represents one league.
 */

import { DOMAIN } from "./const.js";

/** Team sensors, by translation key. */
const TEAM_ROLES = {
  team_standing: "standing",
  team_matchup: "matchup",
  team_roster: "roster",
};

/** League-level sensors, by translation key. */
const LEAGUE_ROLES = {
  matchup_period: "period",
  lineup_issues: "lineupIssues",
  latest_transaction: "activity",
};

/** Every configured league, with its teams' sensor states grouped by team id. */
export function getLeagues(hass) {
  const leagues = new Map();
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform !== DOMAIN) continue;
    const state = hass.states[entry.entity_id];
    if (!state) continue;

    if (!leagues.has(entry.device_id)) {
      leagues.set(entry.device_id, { id: entry.device_id, period: null, teams: new Map() });
    }
    const league = leagues.get(entry.device_id);

    const leagueRole = LEAGUE_ROLES[entry.translation_key];
    if (leagueRole) {
      league[leagueRole] = state;
      continue;
    }
    const role = TEAM_ROLES[entry.translation_key];
    const teamId = state.attributes.team_id;
    if (!role || teamId == null) continue;
    if (!league.teams.has(teamId)) league.teams.set(teamId, { id: teamId });
    league.teams.get(teamId)[role] = state;
  }

  return [...leagues.values()]
    .filter((league) => league.period)
    .map((league) => ({
      ...league,
      name: (league.period.attributes.league_name || "Fantasy league").trim(),
      season: league.period.attributes.season,
      week: league.period.state,
      myTeamId: league.period.attributes.my_team_id ?? null,
      isCategoryLeague: Boolean(league.period.attributes.is_category_league),
    }));
}

/**
 * Pick the league and team a card should show.
 *
 * `config.team` defaults to the user's own team (known when ESPN cookies were
 * entered), then to the first team; `config.league` defaults to the first league.
 */
export function resolve(hass, config) {
  const leagues = getLeagues(hass);
  const league = leagues.find((l) => l.id === config.league) ?? leagues[0];
  if (!league) return { error: "no_league" };
  const wanted =
    config.team != null && config.team !== "auto" ? Number(config.team) : league.myTeamId;
  const team = league.teams.get(wanted) ?? [...league.teams.values()][0];
  if (!team) return { error: "no_teams" };

  return {
    leagues,
    league,
    team: teamInfo(team),
    teams: [...league.teams.values()].map(teamInfo),
  };
}

/** Flatten a team's three sensor states into what the cards render. */
export function teamInfo(t) {
  const s = t.standing?.attributes ?? {};
  const rank = Number(t.standing?.state);
  return {
    id: t.id,
    name: s.team_name || t.roster?.attributes.team_name || `Team ${t.id}`,
    abbrev: s.abbrev || "",
    owners: s.owners ?? [],
    logo: s.entity_picture,
    record: s.record || "0-0-0",
    pf: s.points_for,
    pa: s.points_against,
    streak: s.streak,
    rank: Number.isFinite(rank) && rank > 0 ? rank : null,
    matchup: t.matchup,
    players: t.roster?.attributes.players ?? [],
    // The matchup sensor's players carry points for today and this matchup.
    matchupPlayers: t.matchup?.attributes.players ?? [],
    entities: {
      standing: t.standing?.entity_id,
      matchup: t.matchup?.entity_id,
      roster: t.roster?.entity_id,
    },
  };
}

/** Changes whenever any of the integration's states changes; used to skip re-renders. */
export function signature(hass) {
  let sig = "";
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform === DOMAIN) sig += hass.states[entry.entity_id]?.last_updated ?? "";
  }
  return sig;
}
