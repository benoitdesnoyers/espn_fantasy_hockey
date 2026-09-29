/**
 * Dashboard cards for the ESPN Fantasy Hockey integration.
 *
 * The integration serves this folder and loads this module on every dashboard
 * (see __init__.py), so no Lovelace resource is needed.
 *
 *   type: custom:espn-fantasy-roster-card   (team, league, window)
 *   type: custom:espn-fantasy-matchup-card  (team, league)
 *   type: custom:espn-fantasy-league-card   (team, league, show_matchups)
 */

import { LeagueCard } from "./cards/league-card.js";
import { MatchupCard } from "./cards/matchup-card.js";
import { RosterCard } from "./cards/roster-card.js";
import { VERSION } from "./lib/const.js";

const CARDS = [
  {
    tag: "espn-fantasy-roster-card",
    card: RosterCard,
    name: "ESPN Fantasy Roster",
    description: "A fantasy hockey roster with headshots, fantasy points and stats.",
  },
  {
    tag: "espn-fantasy-matchup-card",
    card: MatchupCard,
    name: "ESPN Fantasy Matchup",
    description: "This week's head-to-head matchup with live scores and hot players.",
  },
  {
    tag: "espn-fantasy-league-card",
    card: LeagueCard,
    name: "ESPN Fantasy League",
    description: "League standings and this week's matchups.",
  },
];

window.customCards ??= [];
for (const { tag, card, name, description } of CARDS) {
  card.getConfigElement = () => document.createElement(`${tag}-editor`);
  if (!customElements.get(tag)) customElements.define(tag, card);
  if (!customElements.get(`${tag}-editor`)) customElements.define(`${tag}-editor`, card.Editor);
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name, description, preview: true });
  }
}

console.info(
  `%c ESPN FANTASY HOCKEY %c cards ${VERSION} `,
  "background:#0c2750;color:#7dd3fc;font-weight:700",
  "background:#7dd3fc;color:#0c2750",
);
