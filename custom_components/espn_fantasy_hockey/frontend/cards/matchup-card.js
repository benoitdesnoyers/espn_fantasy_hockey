import { BaseCard } from "../lib/base-card.js";
import { BENCH_SLOTS } from "../lib/const.js";
import { makeEditor } from "../lib/editor.js";
import { esc, gameText, isNum, playerPoints, pts, scoreText, scoreValue } from "../lib/format.js";
import { language } from "../lib/i18n.js";
import { lineupIssuesHtml, logoHtml, playerRowHtml } from "../lib/templates.js";

/**
 * Which players to feature under the score: this matchup's points once games
 * have been played, else the last 7 days, the season, then projections.
 */
const FEATURE_WINDOWS = [
  ["matchup", "this_week"],
  ["last_7", "hot_last_7"],
  ["season", "top_season"],
  ["projected", "top_projected"],
];
const FEATURED_PLAYERS = 4;

function pickFeatureWindow(players) {
  const found = FEATURE_WINDOWS.find(([w]) => players.some((p) => Number(playerPoints(p, w)) > 0));
  return found ?? FEATURE_WINDOWS.at(-1);
}

function statusText({ leader, a, b, winner, isPoints, t }) {
  if (winner && winner !== "UNDECIDED") {
    return leader ? t("won", { team: leader.name }) : t("tied");
  }
  if (leader) {
    return isPoints
      ? t("leads_by", { team: leader.name, diff: pts(Math.abs(a - b)) })
      : t("leads", { team: leader.name });
  }
  return a + b > 0 ? t("all_tied") : t("puck_drop");
}

/**
 * A team's players for this card: the matchup sensor's list (with today's and
 * this matchup's points) merged into the roster's (with season stats and points).
 */
function playersOf(team) {
  const live = new Map(team.matchupPlayers.map((p) => [p.name, p]));
  return team.players.map((p) => ({ ...p, ...live.get(p.name) }));
}

export class MatchupCard extends BaseCard {
  static Editor = makeEditor();

  render({ league, team, teams }) {
    const { t } = this;
    const lang = language(this._hass);
    const m = team.matchup?.attributes ?? {};
    const opp = teams.find((other) => other.id === m.opponent_id);
    const week = m.matchup_period ?? league.week;
    const header = `<div class="top">
        <span class="eyebrow">${esc(league.name)}</span>
        <span class="chip">${esc(t("week", { week }))}</span>
      </div>`;
    const issues = team.id === league.myTeamId ? league.lineupIssues?.attributes.issues : undefined;

    if (!opp) {
      return `<div class="hero centerline">
        ${header}
        <div class="bye">
          <div class="ringed">${logoHtml(team, "lg")}</div>
          <div class="title">${esc(team.name)}</div>
          <div class="sub">${esc(t("bye"))}</div>
        </div>
      </div>
      ${lineupIssuesHtml(issues, t)}`;
    }

    const a = scoreValue(m.score);
    const b = scoreValue(m.opponent_score);
    const share = a + b > 0 ? (a / (a + b)) * 100 : 50;
    const leader = a === b ? null : a > b ? team : opp;
    const status = statusText({ leader, a, b, winner: m.winner, isPoints: isNum(m.score), t });

    const score = (value, lead) =>
      `<div class="score ${lead ? "lead" : ""}">${scoreText(value)}</div>`;
    const projection = (value) =>
      isNum(value)
        ? `<div class="proj">${esc(t("projected", { score: pts(value) }))}</div>`
        : "<span></span>";
    const record = (side) =>
      `<div class="trec">${esc(side.record)}${side.rank ? ` · #${side.rank}` : ""}</div>`;
    const hasProjection = isNum(m.projected_score) || isNum(m.opponent_projected_score);

    const mine = playersOf(team);
    const theirs = playersOf(opp);
    const details = league.isCategoryLeague
      ? this._categories(m.categories ?? [])
      : this._featured(team, mine, opp, theirs, lang);

    // Cells fill the 3-column grid row by row, so both sides line up whatever the name lengths.
    return `
      <div class="hero centerline">
        ${header}
        <div class="versus">
          ${logoHtml(team, `lg ${leader === team ? "glow" : ""}`)}
          <div class="vs ringed">VS</div>
          ${logoHtml(opp, `lg ${leader === opp ? "glow" : ""}`)}
          <div class="tname">${esc(team.name)}</div><span></span><div class="tname">${esc(opp.name)}</div>
          ${record(team)}<span></span>${record(opp)}
          ${score(m.score, leader === team)}<span class="dash">–</span>${score(m.opponent_score, leader === opp)}
          ${hasProjection ? `${projection(m.projected_score)}<span></span>${projection(m.opponent_projected_score)}` : ""}
        </div>
        <div class="bar" role="img" aria-label="${esc(status)}">
          <i style="width:${share.toFixed(1)}%"></i><i style="width:${(100 - share).toFixed(1)}%"></i>
        </div>
        <div class="status">${esc(status)}</div>
      </div>
      ${lineupIssuesHtml(issues, t)}
      ${details}`;
  }

  /** Each side's best active players, with today's points and tonight's game. */
  _featured(team, mine, opp, theirs, lang) {
    const { t } = this;
    const [window, label] = pickFeatureWindow([...mine, ...theirs]);
    const column = (side, players) => {
      const top = players
        .filter((p) => !BENCH_SLOTS.includes(p.slot))
        .sort(
          (x, y) => (Number(playerPoints(y, window)) || 0) - (Number(playerPoints(x, window)) || 0),
        )
        .slice(0, FEATURED_PLAYERS);
      if (!top.length) return "";
      return top
        .map((player, index) => {
          const game = gameText(player, lang);
          const today =
            Number(player.points_today) > 0
              ? `<div class="today">${esc(t("today_points", { points: pts(player.points_today) }))}</div>`
              : "";
          return playerRowHtml({
            player,
            entity: side.entities.matchup,
            index,
            meta: [esc(player.nhl_team), game && `<span class="game">${esc(game)}</span>`]
              .filter(Boolean)
              .join('<span class="dot">·</span>'),
            value: `<strong>${pts(playerPoints(player, window))}</strong>${today}`,
          });
        })
        .join("");
    };
    return `<div class="hotlabel">${esc(t(label))}</div>
      <div class="hotgrid">
        <div><div class="group"><span>${esc(team.name)}</span></div>${column(team, mine)}</div>
        <div><div class="group"><span>${esc(opp.name)}</span></div>${column(opp, theirs)}</div>
      </div>`;
  }

  /** Category leagues: each category's score for both sides, winners highlighted. */
  _categories(categories) {
    if (!categories.length) return "";
    const lang = language(this._hass);
    const cell = (value, won) =>
      `<span class="${won ? "won" : ""}">${isNum(value) ? Number(value).toLocaleString(lang) : "–"}</span>`;
    const rows = categories
      .map(
        (c) => `<div class="cat">
          ${cell(c.score, c.result === "WIN")}
          <span class="cat-name">${esc(c.abbreviation)}</span>
          ${cell(c.opponent_score, c.result === "LOSS")}
        </div>`,
      )
      .join("");
    return `<div class="hotlabel">${esc(this.t("categories"))}</div><div class="cats">${rows}</div>`;
  }

  static styles = `
    .top {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      margin-bottom: 16px;
      text-align: center;
    }
    /* Equal side columns keep the middle one (VS) exactly on the center line. */
    .versus {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 64px minmax(0, 1fr);
      justify-items: center;
      align-items: start;
      row-gap: 4px;
      text-align: center;
    }
    .versus > .logo {
      align-self: center;
      margin-bottom: 8px;
    }
    .tname {
      max-width: 100%;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .trec {
      font-size: 0.78rem;
      opacity: 0.75;
    }
    .dash {
      align-self: center;
      font-size: 1.4rem;
      font-weight: 700;
      opacity: 0.35;
    }
    .score {
      font-size: 2.1rem;
      font-weight: 800;
      line-height: 1.1;
      font-variant-numeric: tabular-nums;
      opacity: 0.8;
    }
    .score.lead {
      opacity: 1;
      background: linear-gradient(180deg, #fff, var(--efh-ice));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .vs {
      --ring-size: 118px;
      align-self: center;
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      margin-bottom: 8px;
      border-radius: 50%;
      font-size: 0.8rem;
      font-weight: 900;
      letter-spacing: 0.1em;
      background: rgba(255, 255, 255, 0.12);
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.25);
    }
    .bar {
      display: flex;
      gap: 3px;
      height: 8px;
      margin-top: 14px;
    }
    .bar i {
      display: block;
      height: 100%;
      border-radius: 8px;
      transition: width 0.8s var(--efh-ease);
    }
    .bar i:first-child {
      background: linear-gradient(90deg, var(--efh-blue), var(--efh-ice));
      transform-origin: left;
    }
    .bar i:last-child {
      background: linear-gradient(90deg, var(--efh-orange), var(--efh-red));
      transform-origin: right;
    }
    .proj {
      font-size: 0.75rem;
      opacity: 0.7;
      font-variant-numeric: tabular-nums;
    }
    .today {
      font-size: 0.7rem;
      color: var(--efh-muted);
      white-space: nowrap;
    }
    .cats {
      display: grid;
      gap: 2px;
      padding: 6px 16px 0;
    }
    .cat {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 12px;
      padding: 4px 8px;
      border-radius: 8px;
      font-variant-numeric: tabular-nums;
    }
    .cat:nth-child(odd) {
      background: var(--efh-hover);
    }
    .cat > span:first-child {
      text-align: right;
    }
    .cat-name {
      min-width: 44px;
      text-align: center;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--efh-muted);
    }
    .cat .won {
      font-weight: 800;
      color: var(--primary-color);
    }
    .status {
      margin-top: 8px;
      text-align: center;
      font-size: 0.85rem;
      font-weight: 600;
      opacity: 0.9;
    }
    .bye {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      text-align: center;
    }
    .bye .ringed {
      margin-bottom: 8px;
    }
    .hotlabel {
      padding: 14px 16px 0;
      text-align: center;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--efh-muted);
    }
    .hotgrid {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }
    .hotgrid > div + div {
      border-left: 1px solid var(--efh-line);
    }
    .hotgrid .row {
      gap: 10px;
      padding: 6px 12px;
    }
    .hotgrid .num {
      min-width: 0;
    }
    .hotgrid .group {
      justify-content: center;
      padding: 8px 12px 4px;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      text-transform: none;
      color: var(--primary-text-color);
    }
    .hotgrid .group span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    @container (max-width: 460px) {
      .hotgrid {
        grid-template-columns: 1fr;
      }
      .hotgrid > div + div {
        border-left: 0;
        border-top: 1px solid var(--efh-line);
      }
      .logo.lg {
        width: 60px;
        height: 60px;
      }
      .vs {
        --ring-size: 96px;
      }
      .versus {
        grid-template-columns: minmax(0, 1fr) 48px minmax(0, 1fr);
      }
      .score {
        font-size: 1.6rem;
      }
    }
  `;
}
