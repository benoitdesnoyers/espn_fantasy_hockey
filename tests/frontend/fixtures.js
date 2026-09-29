/**
 * A minimal `hass` object shaped like what the integration's sensors produce:
 * one league (device "league-1") with three teams, where team 1 is the user's.
 * Team 1 plays team 2 this week; team 3 has a bye.
 */

const DOMAIN = "espn_fantasy_hockey";

const player = (name, position, slot, points, extra = {}) => ({
  name,
  position,
  slot,
  nhl_team: "TOR",
  headshot: `https://example.invalid/${encodeURIComponent(name)}.png`,
  injury: "ACTIVE",
  points_season: points.season ?? 0,
  points_last_7: points.last_7 ?? 0,
  points_last_15: 0,
  points_last_30: 0,
  points_projected: points.projected ?? 0,
  stats: {},
  ...extra,
});

const TEAMS = [
  { id: 1, name: "Ice Wolves", rank: 2, record: "8-4-0", pf: 850.5, streak: "W2" },
  { id: 2, name: "Blue Liners", rank: 1, record: "9-3-0", pf: 901.2, streak: "L1" },
  { id: 3, name: "Top Shelf", rank: 3, record: "2-10-0", pf: 610.0, streak: null },
];

const ROSTERS = {
  1: [
    player(
      "Alex Forward",
      "C",
      "F",
      { season: 120.5, last_7: 12, projected: 180 },
      {
        stats: { goals: 20, assists: 25, points: 45, plus_minus: 7, shots: 150 },
      },
    ),
    player("Dee Fence", "D", "D", { season: 80, last_7: 4, projected: 120 }),
    player(
      "Gus Goalie",
      "G",
      "G",
      { season: 60, last_7: 9, projected: 150 },
      {
        stats: { wins: 12, gaa: 2.4567, save_pct: 0.9123, shutouts: 2 },
      },
    ),
    player("Benny Bench", "RW", "BE", { season: 30, last_7: 30, projected: 90 }),
    player("Ira Injured", "LW", "IR", { season: 5, projected: 60 }, { injury: "OUT" }),
  ],
  2: [player("Opp Onent", "C", "F", { season: 140, last_7: 15, projected: 200 })],
  3: [player("Third Guy", "D", "D", { season: 50, projected: 100 })],
};

const MATCHUPS = {
  1: {
    opponent_id: 2,
    score: 88.4,
    opponent_score: 71.2,
    projected_score: 120.5,
    opponent_projected_score: 101.3,
  },
  2: {
    opponent_id: 1,
    score: 71.2,
    opponent_score: 88.4,
    projected_score: 101.3,
    opponent_projected_score: 120.5,
  },
  3: { opponent_id: null, score: null, opponent_score: null },
};

// What the matchup sensor adds per player: today's and this week's points, tonight's game.
const LIVE = {
  "Alex Forward": {
    points_today: 3.5,
    points_matchup: 22.1,
    game_today: "2026-10-06T23:00:00+00:00",
    opponent_today: "vs MTL",
  },
  "Dee Fence": { points_today: 0, points_matchup: 30.4, game_today: null },
  "Opp Onent": { points_today: 0, points_matchup: 18.0, game_today: null },
};

const ISSUES = [
  { type: "idle_starter", slot: "F", player: "Alex Forward", replacement: "Benny Bench" },
];

const RECENT = [
  {
    date: "2026-10-05T14:00:00+00:00",
    team: "Blue Liners",
    added: ["New Guy"],
    dropped: ["Old Guy"],
    traded: [],
  },
];

export function makeHass({
  teams = TEAMS,
  myTeamId = 1,
  rosters = ROSTERS,
  language = "en",
  categoryLeague = false,
  categories = undefined,
  issues = ISSUES,
} = {}) {
  const states = {};
  const entities = {};
  const add = (entityId, translationKey, state, attributes) => {
    states[entityId] = {
      entity_id: entityId,
      state: String(state),
      attributes,
      last_updated: "t0",
    };
    entities[entityId] = {
      entity_id: entityId,
      platform: DOMAIN,
      device_id: "league-1",
      translation_key: translationKey,
    };
  };

  add("sensor.league_period", "matchup_period", 5, {
    league_name: "Test League",
    season: 2027,
    my_team_id: myTeamId,
    is_category_league: categoryLeague,
  });
  add("sensor.lineup_issues", "lineup_issues", issues.length, { team_id: myTeamId, issues });
  add("sensor.latest_transaction", "latest_transaction", "…", { recent: RECENT });
  for (const t of teams) {
    const base = { team_id: t.id, team_name: t.name };
    add(`sensor.t${t.id}_standing`, "team_standing", t.rank, {
      ...base,
      abbrev: `T${t.id}`,
      owners: [`Owner ${t.id}`],
      record: t.record,
      points_for: t.pf,
      streak: t.streak,
      entity_picture: `/logo/${t.id}.png`,
    });
    const m = MATCHUPS[t.id];
    add(`sensor.t${t.id}_matchup`, "team_matchup", m.score, {
      ...base,
      matchup_period: 5,
      winner: "UNDECIDED",
      ...m,
      players: (rosters[t.id] ?? []).map((p) => ({ name: p.name, ...LIVE[p.name] })),
      ...(categories ? { categories } : {}),
    });
    add(`sensor.t${t.id}_roster`, "team_roster", 0, {
      ...base,
      players: (rosters[t.id] ?? []).map((p) => ({ ...p, ...LIVE[p.name] })),
    });
  }
  // An unrelated integration's entity must be ignored.
  states["sensor.other"] = { entity_id: "sensor.other", state: "1", attributes: {} };
  entities["sensor.other"] = { entity_id: "sensor.other", platform: "demo", device_id: "x" };

  return { states, entities, locale: { language }, language };
}

export { TEAMS };
