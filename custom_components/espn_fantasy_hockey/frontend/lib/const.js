export const DOMAIN = "espn_fantasy_hockey";

// Keep in sync with manifest.json; tests/test_manifest.py checks it.
export const VERSION = "1.0.1";

/** Points windows, as the suffixes of the roster's `points_*` fields, in display order. */
export const WINDOWS = ["today", "matchup", "season", "last_7", "last_15", "last_30", "projected"];

/** Roster sections, in display order: translation key and lineup slots. */
export const SLOT_GROUPS = [
  ["group_forwards", ["C", "LW", "RW", "F"]],
  ["group_defense", ["D"]],
  ["group_goalies", ["G"]],
  ["group_utility", ["UTIL"]],
  ["group_bench", ["BE"]],
  ["group_ir", ["IR"]],
];

/** Lineup slots that don't score. */
export const BENCH_SLOTS = ["BE", "IR"];

/** ESPN injury status -> [badge text, severity]. Healthy statuses are absent. */
export const INJURY = {
  OUT: ["OUT", "bad"],
  INJURY_RESERVE: ["IR", "bad"],
  SUSPENSION: ["SUSP", "bad"],
  DAY_TO_DAY: ["DTD", "warn"],
  QUESTIONABLE: ["Q", "warn"],
};
