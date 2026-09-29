import { BaseCard } from "../lib/base-card.js";
import { makeEditor } from "../lib/editor.js";
import { esc, isNum, pts, scoreText, scoreValue, transactionText } from "../lib/format.js";
import { language } from "../lib/i18n.js";
import { logoHtml, meterHtml } from "../lib/templates.js";

const MEDALS = ["gold", "silver", "bronze"];
const ACTIVITY_ITEMS = 5;

/** Standings order: rank, then points for, then name. Unranked teams go last. */
const byStanding = (x, y) =>
  (x.rank ?? Infinity) - (y.rank ?? Infinity) ||
  (Number(y.pf) || 0) - (Number(x.pf) || 0) ||
  x.name.localeCompare(y.name);

/** Each matchup once, from the matchup sensors of both teams in it. */
function matchupPairs(teams) {
  const seen = new Set();
  const pairs = [];
  for (const team of teams) {
    const m = team.matchup?.attributes;
    if (!m || m.opponent_id == null) continue;
    const key = [team.id, m.opponent_id].sort((a, b) => a - b).join("-");
    if (seen.has(key)) continue;
    seen.add(key);
    pairs.push({
      team,
      score: m.score,
      opp: teams.find((t) => t.id === m.opponent_id),
      oppScore: m.opponent_score,
    });
  }
  return pairs;
}

/** "2027" -> "2026–27": ESPN names a hockey season after the year it ends. */
const seasonLabel = (season) => (isNum(season) ? `${season - 1}–${String(season).slice(-2)}` : "");

export class LeagueCard extends BaseCard {
  static Editor = makeEditor({
    extraSchema: () => [
      { name: "show_matchups", default: true, selector: { boolean: {} } },
      { name: "show_activity", default: true, selector: { boolean: {} } },
    ],
    teamLabel: "highlighted_team",
  });

  getCardSize() {
    return 10;
  }

  render({ league, team: mine, teams }) {
    const { t } = this;
    const standings = [...teams].sort(byStanding);
    const maxPf = Math.max(1, ...standings.map((t) => Number(t.pf) || 0));
    const season = seasonLabel(league.season);

    const rows = standings
      .map((team, i) => {
        const rank = team.rank ?? i + 1;
        const streakClass = { W: "w", L: "l" }[team.streak?.[0]] ?? "";
        const streak = team.streak
          ? `<span class="streak ${streakClass}">${esc(team.streak)}</span>`
          : "";
        return `<div class="row ${team.id === mine.id ? "mine" : ""}" style="--i:${i}" data-entity="${esc(team.entities.standing)}">
          <div class="lead-cell"><span class="rank ${MEDALS[rank - 1] ?? ""}">${rank}</span>${logoHtml(team, "sm")}</div>
          <div class="cell">
            <div class="name">${esc(team.name)}</div>
            <div class="meta">${esc(team.owners.join(", ") || team.abbrev)}</div>
          </div>
          <div class="num">
            <div class="rec"><strong>${esc(team.record)}</strong>${streak}</div>
            <div class="meta">${pts(team.pf)} ${esc(t("points_for"))}</div>
            ${meterHtml((Number(team.pf) || 0) / maxPf)}
          </div>
        </div>`;
      })
      .join("");

    return `
      <div class="hero centerline centered">
        <div class="eyebrow">${esc(t("standings"))}${season ? ` · ${esc(season)}` : ""}</div>
        <div class="ringed"><div class="title">${esc(league.name)}</div></div>
        <div class="chips">
          <span class="chip">${esc(t("week", { week: league.week }))}</span>
          <span class="chip">${esc(t("teams", { n: teams.length }))}</span>
          ${mine.rank ? `<span class="chip ${mine.rank === 1 ? "gold" : ""}">${esc(mine.name)} · #${mine.rank}</span>` : ""}
        </div>
      </div>
      ${rows}
      ${this._config.show_matchups === false ? "" : this._matchups(league, teams, mine)}
      ${this._config.show_activity === false ? "" : this._activity(league)}`;
  }

  /** The league's latest adds, drops and trades. */
  _activity(league) {
    const recent = league.activity?.attributes.recent ?? [];
    if (!recent.length) return "";
    const lang = language(this._hass);
    const items = recent
      .slice(0, ACTIVITY_ITEMS)
      .map((item) => {
        const when = new Date(item.date).toLocaleDateString(lang, {
          month: "short",
          day: "numeric",
        });
        return `<li><span>${esc(transactionText(item, this.t))}</span><time>${esc(when)}</time></li>`;
      })
      .join("");
    return `<div class="group"><span>${esc(this.t("recent_activity"))}</span></div>
      <ul class="activity" data-entity="${esc(league.activity.entity_id)}">${items}</ul>`;
  }

  _matchups(league, teams, mine) {
    const pairs = matchupPairs(teams);
    if (!pairs.length) return "";
    const line = (t, score, other) => `
      <div class="mline ${scoreValue(score) > scoreValue(other) ? "ahead" : ""} ${t?.id === mine.id ? "me" : ""}">
        ${logoHtml(t, "sm")}<span class="mname">${esc(t?.name ?? "—")}</span><span class="mscore">${scoreText(score)}</span>
      </div>`;
    const cards = pairs
      .map(
        ({ team, score, opp, oppScore }) =>
          `<div class="mcard" data-entity="${esc(team.entities.matchup)}">
            ${line(team, score, oppScore)}${line(opp, oppScore, score)}
          </div>`,
      )
      .join("");
    return `<div class="group"><span>${esc(this.t("week_matchups", { week: league.week }))}</span></div>
      <div class="mgrid">${cards}</div>`;
  }

  static styles = `
    .centered {
      text-align: center;
    }
    .activity {
      margin: 0;
      padding: 0 16px;
      list-style: none;
      cursor: pointer;
    }
    .activity li {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 6px 0;
      font-size: 0.85rem;
      border-bottom: 1px solid var(--efh-line);
    }
    .activity li:last-child {
      border-bottom: 0;
    }
    .activity time {
      flex: none;
      color: var(--efh-muted);
    }
    .centered .ringed {
      --ring-size: 96px;
      margin: 10px 0;
    }
    .centered .chips {
      justify-content: center;
      margin-top: 8px;
    }
    .lead-cell {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .rank {
      display: grid;
      place-items: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      font-size: 0.75rem;
      font-weight: 800;
      background: var(--efh-hover);
      color: var(--primary-text-color);
    }
    .rank.gold {
      background: linear-gradient(135deg, #fde68a, #f59e0b);
      color: #3b2300;
    }
    .rank.silver {
      background: linear-gradient(135deg, #f1f5f9, #94a3b8);
      color: #1e293b;
    }
    .rank.bronze {
      background: linear-gradient(135deg, #fed7aa, #c2410c);
      color: #fff;
    }
    .row.mine {
      background: linear-gradient(90deg, rgba(125, 211, 252, 0.18), transparent 70%);
      box-shadow: inset 3px 0 0 var(--efh-ice);
    }
    .rec {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
    }
    .rec strong {
      font-size: 0.95rem;
    }
    .streak {
      padding: 1px 5px;
      border-radius: 5px;
      font-size: 0.65rem;
      font-weight: 800;
      background: var(--efh-hover);
    }
    .streak.w {
      background: rgba(52, 211, 153, 0.18);
      color: #059669;
    }
    .streak.l {
      background: rgba(251, 113, 133, 0.18);
      color: #e11d48;
    }
    .num .meter {
      width: 72px;
      margin-left: auto;
    }
    .mgrid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 8px;
      padding: 6px 16px 0;
    }
    .mcard {
      display: grid;
      gap: 6px;
      padding: 8px 10px;
      border-radius: 12px;
      cursor: pointer;
      background: linear-gradient(135deg, var(--efh-hover), transparent);
      box-shadow: inset 0 0 0 1px var(--efh-line);
      transition: transform 0.2s;
    }
    .mcard:hover {
      transform: translateY(-2px);
    }
    .mline {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      color: var(--efh-muted);
    }
    .mline.ahead {
      color: var(--primary-text-color);
      font-weight: 700;
    }
    .mline.me .mname {
      color: var(--primary-color);
    }
    .mline .logo.sm {
      width: 24px;
      height: 24px;
    }
    .mname {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .mscore {
      font-variant-numeric: tabular-nums;
    }
  `;
}
