import { BaseCard } from "../lib/base-card.js";
import { INJURY, SLOT_GROUPS, WINDOWS } from "../lib/const.js";
import { AUTO, dropdown, makeEditor } from "../lib/editor.js";
import { esc, gameText, playerPoints, pts, statLine } from "../lib/format.js";
import { language } from "../lib/i18n.js";
import { lineupIssuesHtml, logoHtml, meterHtml, playerRowHtml } from "../lib/templates.js";

const KNOWN_SLOTS = new Set(SLOT_GROUPS.flatMap(([, slots]) => slots));

/** Players grouped into roster sections; slots we don't know go under "Other". */
function groupBySlot(players) {
  return [...SLOT_GROUPS, ["group_other", null]]
    .map(([label, slots]) => [
      label,
      players.filter((p) => (slots ? slots.includes(p.slot) : !KNOWN_SLOTS.has(p.slot))),
    ])
    .filter(([, members]) => members.length);
}

const sum = (players, window) =>
  players.reduce((total, p) => total + (Number(playerPoints(p, window)) || 0), 0);

export class RosterCard extends BaseCard {
  static Editor = makeEditor({
    extraSchema: (t) => [
      dropdown("window", [
        { value: AUTO, label: t("automatic_window") },
        ...WINDOWS.map((w) => ({ value: w, label: t(`window_${w}`) })),
      ]),
    ],
  });

  getCardSize() {
    return 12;
  }

  render({ league, team }) {
    const { t } = this;
    const lang = language(this._hass);
    const { players } = team;
    // Category leagues don't score fantasy points, so show stats only.
    const showPoints = !league.isCategoryLeague;
    // Before any games every actual total is 0, so projections are more useful.
    const hasActual = players.some((p) => Number(p.points_season) > 0);
    const window = this._ui.window ?? this._config.window ?? (hasActual ? "season" : "projected");
    const max = Math.max(1, ...players.map((p) => Math.abs(Number(playerPoints(p, window)) || 0)));
    const injured = players.filter((p) => INJURY[p.injury]).length;
    const issues = team.id === league.myTeamId ? league.lineupIssues?.attributes.issues : undefined;

    let index = 0;
    const sections = groupBySlot(players)
      .map(([label, members]) => {
        const rows = members
          .map((player) => {
            const game = gameText(player, lang);
            const stats = statLine(player);
            const meta = [
              esc(player.nhl_team),
              game && `<span class="game">${esc(game)}</span>`,
              stats,
            ].filter(Boolean);
            const value = Number(playerPoints(player, window)) || 0;
            return playerRowHtml({
              player,
              entity: team.entities.roster,
              index: index++,
              meta: meta.join('<span class="dot">·</span>'),
              value: showPoints
                ? `<strong>${pts(playerPoints(player, window))}</strong>${meterHtml(Math.abs(value) / max)}`
                : "",
            });
          })
          .join("");
        const subtotal = showPoints ? `<span>${pts(sum(members, window))}</span>` : "";
        return `<div class="group">
            <span>${esc(t(label))} · ${members.length}</span>${subtotal}
          </div>${rows}`;
      })
      .join("");

    const rankChip = team.rank
      ? `<span class="chip ${team.rank === 1 ? "gold" : ""}">#${team.rank}</span>`
      : "";
    const windowButtons = WINDOWS.map(
      (w) =>
        `<button data-window="${w}" aria-pressed="${w === window}">${esc(t(`short_${w}`))}</button>`,
    ).join("");
    const total = showPoints
      ? `<div class="total">
          <div class="big">${pts(sum(players, window))}</div>
          <div class="eyebrow">${esc(t(`window_${window}`))}</div>
        </div>`
      : "";

    return `
      <div class="hero">
        <div class="head">
          <div class="ringed">${logoHtml(team, "lg")}</div>
          <div class="cell grow">
            <div class="eyebrow">${esc(t("roster"))}</div>
            <div class="title">${esc(team.name)}</div>
            <div class="chips">
              ${rankChip}
              <span class="chip">${esc(team.record)}</span>
              <span class="chip">${esc(t("players", { n: players.length }))}</span>
              ${injured ? `<span class="chip">${esc(t("injured", { n: injured }))}</span>` : ""}
            </div>
          </div>
          ${total}
        </div>
        ${showPoints ? `<div class="seg" role="group" aria-label="${esc(t("points_window"))}">${windowButtons}</div>` : ""}
      </div>
      ${lineupIssuesHtml(issues, t)}
      ${sections || `<div class="empty">${esc(t("no_players"))}</div>`}`;
  }

  static styles = `
    .head {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 14px;
    }
    .grow {
      flex: 1;
    }
    .total {
      text-align: right;
    }
    .big {
      font-size: 2rem;
      font-weight: 800;
      line-height: 1;
      font-variant-numeric: tabular-nums;
      background: linear-gradient(180deg, #fff, var(--efh-ice));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .seg {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 2px;
      padding: 3px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.1);
    }
    .seg button {
      all: unset;
      cursor: pointer;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 600;
      color: rgba(255, 255, 255, 0.8);
      transition: background 0.2s, color 0.2s;
    }
    .seg button:hover {
      color: #fff;
    }
    .seg button[aria-pressed="true"] {
      background: #fff;
      color: #0c2750;
    }
    .seg button:focus-visible {
      outline: 2px solid var(--efh-ice);
    }
    @container (max-width: 400px) {
      .head {
        flex-wrap: wrap;
      }
      .total {
        display: flex;
        align-items: baseline;
        gap: 8px;
        width: 100%;
        text-align: left;
      }
    }
  `;
}
