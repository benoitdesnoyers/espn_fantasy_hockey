/**
 * Dashboard cards for the ESPN Fantasy Hockey integration.
 *
 * Served and auto-loaded by the integration (see __init__.py), so no Lovelace
 * resource is needed. Cards find their data through the entity registry: every
 * sensor of the integration carries a translation_key naming its role and a
 * team_id attribute, so nothing depends on entity IDs, which users can rename.
 *
 *   type: custom:espn-fantasy-roster-card   (team, league, window)
 *   type: custom:espn-fantasy-matchup-card  (team, league)
 *   type: custom:espn-fantasy-league-card   (team, league, show_matchups)
 *
 * `team` defaults to the team owned by the ESPN account whose cookies were
 * entered during setup; `league` defaults to the first configured league.
 */

const DOMAIN = "espn_fantasy_hockey";
const VERSION = "0.2.2";

const WINDOWS = {
  season: "Season",
  last_7: "Last 7 days",
  last_15: "Last 15 days",
  last_30: "Last 30 days",
  projected: "Projected",
};
const WINDOW_SHORT = { season: "Season", last_7: "7D", last_15: "15D", last_30: "30D", projected: "Proj" };

const SLOT_GROUPS = [
  ["Forwards", ["C", "LW", "RW", "F"]],
  ["Defense", ["D"]],
  ["Goalies", ["G"]],
  ["Utility", ["UTIL"]],
  ["Bench", ["BE"]],
  ["Injured reserve", ["IR"]],
];

const INJURY = {
  OUT: ["OUT", "bad"],
  INJURY_RESERVE: ["IR", "bad"],
  SUSPENSION: ["SUSP", "bad"],
  DAY_TO_DAY: ["DTD", "warn"],
  QUESTIONABLE: ["Q", "warn"],
};

// ---------------------------------------------------------------------------
// Data access
// ---------------------------------------------------------------------------

const ROLES = { team_standing: "standing", team_matchup: "matchup", team_roster: "roster" };

/** Every configured league, with its teams' sensors grouped by team id. */
function getLeagues(hass) {
  const leagues = new Map();
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform !== DOMAIN) continue;
    const state = hass.states[entry.entity_id];
    if (!state) continue;
    if (!leagues.has(entry.device_id)) {
      leagues.set(entry.device_id, { id: entry.device_id, period: null, teams: new Map() });
    }
    const league = leagues.get(entry.device_id);
    if (entry.translation_key === "matchup_period") {
      league.period = state;
      continue;
    }
    const role = ROLES[entry.translation_key];
    const teamId = state.attributes.team_id;
    if (!role || teamId == null) continue;
    if (!league.teams.has(teamId)) league.teams.set(teamId, { id: teamId });
    league.teams.get(teamId)[role] = state;
  }
  return [...leagues.values()]
    .filter((l) => l.period)
    .map((l) => ({
      ...l,
      name: (l.period.attributes.league_name || "Fantasy league").trim(),
      season: l.period.attributes.season,
      week: l.period.state,
      myTeamId: l.period.attributes.my_team_id ?? null,
    }));
}

function resolve(hass, config) {
  const leagues = getLeagues(hass);
  const league = leagues.find((l) => l.id === config.league) || leagues[0];
  if (!league) return { error: "No ESPN Fantasy Hockey league found. Add the integration first." };
  const wanted = config.team != null && config.team !== "auto" ? Number(config.team) : league.myTeamId;
  const team = league.teams.get(wanted) || [...league.teams.values()][0];
  if (!team) return { error: "This league has no teams yet." };
  return { leagues, league, team: teamInfo(team), teams: [...league.teams.values()].map(teamInfo) };
}

function teamInfo(t) {
  const s = t.standing?.attributes || {};
  const rank = Number(t.standing?.state);
  return {
    id: t.id,
    name: s.team_name || t.roster?.attributes.team_name || `Team ${t.id}`,
    abbrev: s.abbrev || "",
    owners: s.owners || [],
    logo: s.entity_picture,
    record: s.record || "0-0-0",
    wins: s.wins || 0,
    losses: s.losses || 0,
    ties: s.ties || 0,
    pf: s.points_for,
    pa: s.points_against,
    streak: s.streak,
    rank: Number.isFinite(rank) && rank > 0 ? rank : null,
    matchup: t.matchup,
    players: t.roster?.attributes.players || [],
    entities: { standing: t.standing?.entity_id, matchup: t.matchup?.entity_id, roster: t.roster?.entity_id },
  };
}

/** Change detection: re-render only when one of this integration's states changed. */
function signature(hass) {
  let sig = "";
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform === DOMAIN) sig += hass.states[entry.entity_id]?.last_updated || "";
  }
  return sig;
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const isNum = (v) => v !== null && v !== "" && !Number.isNaN(Number(v));
const pts = (v, d = 1) => (isNum(v) ? Number(v).toFixed(d) : "–");
const initials = (name) =>
  String(name || "?")
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

function playerPoints(p, window) {
  return p[`points_${window}`] ?? null;
}

function statLine(p) {
  const s = p.stats || {};
  const parts =
    p.position === "G"
      ? [
          [s.wins, "W"],
          [isNum(s.gaa) ? Number(s.gaa).toFixed(2) : null, "GAA"],
          [isNum(s.save_pct) ? Number(s.save_pct).toFixed(3).replace(/^0/, "") : null, "SV%"],
          [s.shutouts || null, "SO"],
        ]
      : [
          [s.goals, "G"],
          [s.assists, "A"],
          [s.points, "PTS"],
          [isNum(s.plus_minus) ? (s.plus_minus > 0 ? `+${s.plus_minus}` : s.plus_minus) : null, "+/-"],
          [s.shots, "SOG"],
        ];
  return parts
    .filter(([v]) => v !== undefined && v !== null)
    .map(([v, l]) => `<b>${esc(v)}</b> ${l}`)
    .join('<span class="dot">·</span>');
}

/** Scores are numbers in points leagues and "W-L-T" strings in category leagues. */
function scoreValue(v) {
  if (isNum(v)) return Number(v);
  const m = /^(\d+)-(\d+)-(\d+)$/.exec(String(v ?? ""));
  return m ? Number(m[1]) + Number(m[3]) / 2 : 0;
}

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

function logoHtml(team, cls = "") {
  return `<div class="logo ${cls}" data-entity="${esc(team?.entities?.standing)}">
    <span>${esc(team?.abbrev || initials(team?.name))}</span>
    ${team?.logo ? `<img src="${esc(team.logo)}" alt="" loading="lazy">` : ""}
  </div>`;
}

function headshotHtml(p) {
  const pos = p.position === "G" ? "g" : p.position === "D" ? "d" : "f";
  const injury = INJURY[p.injury];
  return `<div class="shot pos-${pos}">
    <span>${esc(initials(p.name))}</span>
    ${p.headshot ? `<img src="${esc(p.headshot)}" alt="" loading="lazy">` : ""}
    ${injury ? `<i class="inj ${injury[1]}" title="${esc(p.injury)}">${injury[0]}</i>` : ""}
  </div>`;
}

const STYLES = `
  :host {
    --efh-ice: #7dd3fc;
    --efh-blue: #2563eb;
    --efh-red: #f43f5e;
    --efh-orange: #fb923c;
    --efh-win: #34d399;
    --efh-loss: #fb7185;
    --efh-gold: #fbbf24;
    --efh-muted: var(--secondary-text-color);
    --efh-line: var(--divider-color, rgba(127, 127, 127, 0.2));
    --efh-hover: rgba(125, 211, 252, 0.08);
  }
  ha-card { overflow: hidden; container-type: inline-size; }
  .error { padding: 16px; color: var(--error-color, #db4437); }

  /* Hero: always dark ice, independent of the theme, so white text always reads. */
  .hero {
    position: relative; isolation: isolate; overflow: hidden; color: #fff; padding: 18px;
    background:
      radial-gradient(120% 140% at 100% 0%, rgba(125, 211, 252, 0.42) 0%, transparent 55%),
      radial-gradient(90% 120% at 0% 100%, rgba(37, 99, 235, 0.55) 0%, transparent 60%),
      linear-gradient(135deg, #06122a 0%, #0c2750 55%, #113c7c 100%);
  }
  /* Faint rink markings: a center line for symmetric heroes, and a face-off circle
     drawn around whichever element carries .ringed, so the two always line up. */
  .hero.centerline::before {
    content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
    background: linear-gradient(90deg, transparent calc(50% - 1px), rgba(255, 255, 255, 0.06) calc(50% - 1px), rgba(255, 255, 255, 0.06) calc(50% + 1px), transparent calc(50% + 1px));
  }
  .ringed { position: relative; }
  .ringed::after {
    content: ""; position: absolute; left: 50%; top: 50%; width: var(--ring-size, 112px); height: var(--ring-size, 112px);
    transform: translate(-50%, -50%); border-radius: 50%; pointer-events: none;
    box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.07);
  }
  .eyebrow { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.75; }
  .title { font-size: 1.35rem; font-weight: 700; line-height: 1.2; margin: 2px 0; overflow-wrap: anywhere; }
  .sub { font-size: 0.85rem; opacity: 0.8; }
  .chip {
    display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; background: rgba(255, 255, 255, 0.14);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  }
  .chip.gold { background: linear-gradient(135deg, #fde68a, #f59e0b); color: #3b2300; box-shadow: none; }

  .logo {
    position: relative; flex: none; width: 56px; height: 56px; border-radius: 50%; overflow: hidden;
    display: grid; place-items: center; cursor: pointer;
    background: radial-gradient(circle at 30% 25%, #ffffff, #dbeafe 70%);
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.22), 0 8px 22px rgba(0, 0, 0, 0.35);
    color: #0c2750; font-weight: 800; font-size: 0.8rem;
  }
  .logo img, .shot img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .logo img.broken, .shot img.broken { display: none; }
  .logo.sm { width: 32px; height: 32px; font-size: 0.6rem; box-shadow: 0 0 0 2px var(--efh-line); }
  .logo.lg { width: 76px; height: 76px; font-size: 1rem; }
  .logo.glow { box-shadow: 0 0 0 3px var(--efh-ice), 0 0 30px rgba(125, 211, 252, 0.7); }

  .shot {
    --ring: #38bdf8; position: relative; flex: none; width: 48px; height: 48px; border-radius: 50%;
    display: grid; place-items: center; font-size: 0.75rem; font-weight: 700; color: var(--efh-muted);
    background:
      radial-gradient(circle at 50% 30%, color-mix(in srgb, var(--ring) 35%, transparent), transparent 70%),
      var(--secondary-background-color, rgba(127, 127, 127, 0.12));
    box-shadow: inset 0 0 0 2px var(--ring);
  }
  .shot img { border-radius: 50%; object-position: 50% 15%; }
  .shot.pos-d { --ring: #34d399; }
  .shot.pos-g { --ring: #a78bfa; }
  .inj {
    position: absolute; right: -4px; bottom: -2px; z-index: 1; padding: 0 4px; border-radius: 6px;
    font: 700 0.58rem/1.5 system-ui, sans-serif; font-style: normal; color: #fff;
    box-shadow: 0 0 0 2px var(--card-background-color, #fff);
  }
  .inj.bad { background: #e11d48; }
  .inj.warn { background: #d97706; }

  .seg { display: inline-flex; gap: 2px; padding: 3px; border-radius: 999px; background: rgba(255, 255, 255, 0.1); flex-wrap: wrap; }
  .seg button {
    all: unset; cursor: pointer; padding: 4px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 600;
    color: rgba(255, 255, 255, 0.8); transition: background 0.2s, color 0.2s;
  }
  .seg button:hover { color: #fff; }
  .seg button[aria-pressed="true"] { background: #fff; color: #0c2750; }
  .seg button:focus-visible { outline: 2px solid var(--efh-ice); }

  .group { display: flex; justify-content: space-between; padding: 14px 16px 4px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--efh-muted); }
  .row {
    display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center;
    padding: 7px 16px; cursor: pointer; transition: background 0.2s;
  }
  .row:hover { background: var(--efh-hover); }
  .name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .meta { font-size: 0.78rem; color: var(--efh-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .meta b { color: var(--primary-text-color); font-weight: 600; }
  .dot { margin: 0 5px; opacity: 0.5; }
  .tag { font-size: 0.66rem; font-weight: 700; padding: 1px 6px; border-radius: 5px; background: var(--efh-hover); color: var(--primary-text-color); margin-right: 4px; }
  .num { text-align: right; min-width: 64px; }
  .num strong { font-size: 1.05rem; font-variant-numeric: tabular-nums; }
  .meter { height: 4px; margin-top: 4px; border-radius: 4px; background: var(--efh-line); overflow: hidden; }
  .meter i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--efh-ice), var(--efh-blue)); transform-origin: left; }
  .empty { padding: 20px 16px; color: var(--efh-muted); text-align: center; }

  /* One-time entrance animations (skipped on later updates and for reduced motion). */
  .animate .row { animation: rise 0.45s cubic-bezier(0.2, 0.8, 0.2, 1) both; animation-delay: calc(var(--i, 0) * 22ms); }
  .animate .meter i, .animate .bar i { animation: grow 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
  @keyframes rise { from { opacity: 0; transform: translateY(6px); } }
  @keyframes grow { from { transform: scaleX(0); } }
  @media (prefers-reduced-motion: reduce) { .animate * { animation: none !important; } }
`;

// ---------------------------------------------------------------------------
// Base card
// ---------------------------------------------------------------------------

class EspnBaseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._ui = {};
    // <img> errors don't bubble; catch them in the capture phase to show the fallback.
    this.shadowRoot.addEventListener("error", (e) => e.target.tagName === "IMG" && e.target.classList.add("broken"), true);
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { ...config };
    this._sig = null;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    const sig = signature(hass);
    if (sig !== this._sig) {
      this._sig = sig;
      this._update();
    }
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _update() {
    if (!this._hass || !this._config) return;
    const data = resolve(this._hass, this._config);
    const body = data.error ? `<div class="error">${esc(data.error)}</div>` : this._render(data);
    const animate = !this._rendered && !data.error;
    this.shadowRoot.innerHTML = `<style>${STYLES}${this.constructor.styles || ""}</style><ha-card class="${animate ? "animate" : ""}">${body}</ha-card>`;
    if (!data.error) this._rendered = true;
  }

  _onClick(e) {
    const win = e.target.closest("[data-window]");
    if (win) {
      this._ui.window = win.dataset.window;
      this._update();
      return;
    }
    const target = e.target.closest("[data-entity]");
    if (target?.dataset.entity) {
      this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: target.dataset.entity }, bubbles: true, composed: true }));
    }
  }
}

// ---------------------------------------------------------------------------
// Roster card
// ---------------------------------------------------------------------------

class EspnRosterCard extends EspnBaseCard {
  getCardSize() {
    return 12;
  }

  _render({ team }) {
    const players = team.players;
    // Before the season every actual total is 0, so default to projections then.
    const hasActual = players.some((p) => Number(p.points_season) > 0);
    const window = this._ui.window || this._config.window || (hasActual ? "season" : "projected");
    const total = players.reduce((sum, p) => sum + (Number(playerPoints(p, window)) || 0), 0);
    const max = Math.max(1, ...players.map((p) => Math.abs(Number(playerPoints(p, window)) || 0)));
    const injured = players.filter((p) => INJURY[p.injury]).length;

    const known = new Set(SLOT_GROUPS.flatMap(([, slots]) => slots));
    const groups = [...SLOT_GROUPS, ["Other", null]]
      .map(([label, slots]) => [label, players.filter((p) => (slots ? slots.includes(p.slot) : !known.has(p.slot)))])
      .filter(([, list]) => list.length);

    let i = 0;
    const rows = groups
      .map(([label, list]) => {
        const subtotal = list.reduce((s, p) => s + (Number(playerPoints(p, window)) || 0), 0);
        return `<div class="group"><span>${esc(label)} · ${list.length}</span><span>${pts(subtotal)}</span></div>
          ${list
            .map((p) => {
              const v = Number(playerPoints(p, window)) || 0;
              const stats = statLine(p);
              return `<div class="row" style="--i:${i++}" data-entity="${esc(team.entities.roster)}">
                ${headshotHtml(p)}
                <div style="min-width:0">
                  <div class="name">${esc(p.name)}</div>
                  <div class="meta"><span class="tag">${esc(p.position)}</span>${esc(p.nhl_team)}${stats ? `<span class="dot">·</span>${stats}` : ""}</div>
                </div>
                <div class="num">
                  <strong>${pts(playerPoints(p, window))}</strong>
                  <div class="meter"><i style="width:${Math.round((Math.abs(v) / max) * 100)}%"></i></div>
                </div>
              </div>`;
            })
            .join("")}`;
      })
      .join("");

    return `
      <div class="hero">
        <div class="head">
          <div class="ringed">${logoHtml(team, "lg")}</div>
          <div style="min-width:0;flex:1">
            <div class="eyebrow">Roster</div>
            <div class="title">${esc(team.name)}</div>
            <div class="chips">
              ${team.rank ? `<span class="chip ${team.rank === 1 ? "gold" : ""}">#${team.rank}</span>` : ""}
              <span class="chip">${esc(team.record)}</span>
              <span class="chip">${players.length} players</span>
              ${injured ? `<span class="chip">${injured} injured</span>` : ""}
            </div>
          </div>
          <div class="total">
            <div class="big">${pts(total)}</div>
            <div class="eyebrow">${esc(WINDOWS[window])}</div>
          </div>
        </div>
        <div class="seg" role="group" aria-label="Points window">
          ${Object.keys(WINDOWS)
            .map((w) => `<button data-window="${w}" aria-pressed="${w === window}">${WINDOW_SHORT[w]}</button>`)
            .join("")}
        </div>
      </div>
      ${rows || `<div class="empty">No players on this roster yet.</div>`}
      <div style="height:8px"></div>`;
  }
}
EspnRosterCard.styles = `
  .head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .total { text-align: right; }
  .big { font-size: 2rem; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums;
    background: linear-gradient(180deg, #fff, var(--efh-ice)); -webkit-background-clip: text; background-clip: text; color: transparent; }
  @container (max-width: 400px) {
    .head { flex-wrap: wrap; }
    .total { text-align: left; width: 100%; display: flex; align-items: baseline; gap: 8px; }
  }
`;

// ---------------------------------------------------------------------------
// Matchup card
// ---------------------------------------------------------------------------

class EspnMatchupCard extends EspnBaseCard {
  _render({ league, team, teams }) {
    const m = team.matchup?.attributes || {};
    const opp = teams.find((t) => t.id === m.opponent_id);
    const week = m.matchup_period ?? league.week;

    if (!opp) {
      return `<div class="hero centerline">
        <div class="top"><span class="eyebrow">${esc(league.name)}</span><span class="chip">Week ${esc(week)}</span></div>
        <div class="bye"><div class="ringed">${logoHtml(team, "lg")}</div><div class="title">${esc(team.name)}</div><div class="sub">Bye week — no matchup scheduled.</div></div>
      </div>`;
    }

    const a = scoreValue(m.score);
    const b = scoreValue(m.opponent_score);
    const share = a + b > 0 ? (a / (a + b)) * 100 : 50;
    const leader = a === b ? null : a > b ? team : opp;
    const diff = Math.abs(a - b);
    const done = m.winner && m.winner !== "UNDECIDED";
    const status = done
      ? `${leader ? `${esc(leader.name)} won` : "Tied"}`
      : leader
        ? `${esc(leader.name)} ${isNum(m.score) ? `leads by ${pts(diff)}` : "leads"}`
        : a + b > 0
          ? "All tied up"
          : "Puck drop soon";

    const scoreHtml = (score, lead) => `<div class="score ${lead ? "lead" : ""}">${isNum(score) ? pts(score) : esc(score ?? "–")}</div>`;
    const recHtml = (t) => `<div class="trec">${esc(t.record)}${t.rank ? ` · #${t.rank}` : ""}</div>`;

    // "Hot" means the last 7 days; before any games, fall back to season, then projections.
    const everyone = [...team.players, ...opp.players];
    const hotWindow = ["last_7", "season", "projected"].find((w) => everyone.some((p) => Number(playerPoints(p, w)) > 0)) || "last_7";
    const hotLabel = { last_7: "Hot · last 7 days", season: "Top · season", projected: "Top · projected" }[hotWindow];

    const hot = (t) => {
      const top = [...t.players]
        .filter((p) => !["BE", "IR"].includes(p.slot))
        .sort((x, y) => (Number(playerPoints(y, hotWindow)) || 0) - (Number(playerPoints(x, hotWindow)) || 0))
        .slice(0, 3);
      if (!top.length) return `<div class="empty">No players</div>`;
      return top
        .map(
          (p, i) => `<div class="row" style="--i:${i}" data-entity="${esc(t.entities.roster)}">
            ${headshotHtml(p)}
            <div style="min-width:0"><div class="name">${esc(p.name)}</div><div class="meta"><span class="tag">${esc(p.position)}</span>${esc(p.nhl_team)}</div></div>
            <div class="num"><strong>${pts(playerPoints(p, hotWindow))}</strong></div>
          </div>`
        )
        .join("");
    };

    return `
      <div class="hero centerline">
        <div class="top"><span class="eyebrow">${esc(league.name)}</span><span class="chip">Week ${esc(week)}</span></div>
        <div class="versus">
          ${logoHtml(team, `lg ${leader === team ? "glow" : ""}`)}<div class="vs ringed">VS</div>${logoHtml(opp, `lg ${leader === opp ? "glow" : ""}`)}
          <div class="tname">${esc(team.name)}</div><span></span><div class="tname">${esc(opp.name)}</div>
          ${recHtml(team)}<span></span>${recHtml(opp)}
          ${scoreHtml(m.score, leader === team)}<span class="dash">–</span>${scoreHtml(m.opponent_score, leader === opp)}
        </div>
        <div class="bar" role="img" aria-label="${esc(status)}"><i style="width:${share.toFixed(1)}%"></i><i style="width:${(100 - share).toFixed(1)}%"></i></div>
        <div class="status">${status}</div>
      </div>
      <div class="hotlabel">${hotLabel}</div>
      <div class="hotgrid">
        <div><div class="group"><span>${esc(team.name)}</span></div>${hot(team)}</div>
        <div><div class="group"><span>${esc(opp.name)}</span></div>${hot(opp)}</div>
      </div>
      <div style="height:8px"></div>`;
  }
}
EspnMatchupCard.styles = `
  .top { display: flex; flex-direction: column; align-items: center; gap: 6px; margin-bottom: 16px; text-align: center; }
  /* Equal side columns keep the middle column (VS) exactly on the center line. */
  .versus { display: grid; grid-template-columns: minmax(0, 1fr) 64px minmax(0, 1fr); justify-items: center; align-items: start; row-gap: 4px; text-align: center; }
  .versus > .logo { align-self: center; margin-bottom: 8px; }
  .tname { font-weight: 700; max-width: 100%; overflow-wrap: anywhere; }
  .trec { font-size: 0.78rem; opacity: 0.75; }
  .dash { align-self: center; font-size: 1.4rem; font-weight: 700; opacity: 0.35; }
  .score { font-size: 2.1rem; font-weight: 800; line-height: 1.1; font-variant-numeric: tabular-nums; opacity: 0.8; }
  .score.lead { opacity: 1; background: linear-gradient(180deg, #fff, var(--efh-ice)); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .vs { --ring-size: 118px; align-self: center; margin-bottom: 8px; font-weight: 900; font-size: 0.8rem; letter-spacing: 0.1em; width: 38px; height: 38px; border-radius: 50%;
    display: grid; place-items: center; background: rgba(255, 255, 255, 0.12); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.25); }
  .bar { display: flex; gap: 3px; height: 8px; margin-top: 14px; }
  .bar i { display: block; height: 100%; border-radius: 8px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
  .bar i:first-child { background: linear-gradient(90deg, var(--efh-blue), var(--efh-ice)); transform-origin: left; }
  .bar i:last-child { background: linear-gradient(90deg, var(--efh-orange), var(--efh-red)); transform-origin: right; }
  .status { margin-top: 8px; text-align: center; font-size: 0.85rem; font-weight: 600; opacity: 0.9; }
  .bye { display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center; }
  .bye .ringed { margin-bottom: 8px; }
  .hotlabel { padding: 14px 16px 0; text-align: center; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--efh-muted); }
  .hotgrid { display: grid; grid-template-columns: 1fr 1fr; }
  .hotgrid > div + div { border-left: 1px solid var(--efh-line); }
  .hotgrid .row { grid-template-columns: auto minmax(0, 1fr) auto; padding: 6px 12px; gap: 10px; }
  .hotgrid .num { min-width: 0; }
  .hotgrid .group { padding: 8px 12px 4px; justify-content: center; letter-spacing: 0.04em; text-transform: none; font-size: 0.8rem; color: var(--primary-text-color); }
  .hotgrid .group span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @container (max-width: 460px) {
    .hotgrid { grid-template-columns: 1fr; }
    .hotgrid > div + div { border-left: 0; border-top: 1px solid var(--efh-line); }
    .logo.lg { width: 60px; height: 60px; }
    .vs { --ring-size: 96px; }
    .versus { grid-template-columns: minmax(0, 1fr) 48px minmax(0, 1fr); }
    .score { font-size: 1.6rem; }
  }
`;

// ---------------------------------------------------------------------------
// League card
// ---------------------------------------------------------------------------

class EspnLeagueCard extends EspnBaseCard {
  getCardSize() {
    return 10;
  }

  _render({ league, team: mine, teams }) {
    const sorted = [...teams].sort(
      (x, y) => (x.rank ?? 99) - (y.rank ?? 99) || (Number(y.pf) || 0) - (Number(x.pf) || 0) || x.name.localeCompare(y.name)
    );
    const maxPf = Math.max(1, ...sorted.map((t) => Number(t.pf) || 0));
    const medal = ["gold", "silver", "bronze"];

    const rows = sorted
      .map((t, i) => {
        const rank = t.rank ?? i + 1;
        const streak = t.streak ? `<span class="streak ${t.streak[0] === "W" ? "w" : t.streak[0] === "L" ? "l" : ""}">${esc(t.streak)}</span>` : "";
        return `<div class="row ${t.id === mine.id ? "mine" : ""}" style="--i:${i}" data-entity="${esc(t.entities.standing)}">
          <div class="lead-cell"><span class="rank ${medal[rank - 1] || ""}">${rank}</span>${logoHtml(t, "sm")}</div>
          <div style="min-width:0">
            <div class="name">${esc(t.name)}</div>
            <div class="meta">${esc(t.owners.join(", ") || t.abbrev)}</div>
          </div>
          <div class="num">
            <div class="rec"><strong>${esc(t.record)}</strong>${streak}</div>
            <div class="meta">${pts(t.pf)} PF</div>
            <div class="meter"><i style="width:${Math.round(((Number(t.pf) || 0) / maxPf) * 100)}%"></i></div>
          </div>
        </div>`;
      })
      .join("");

    let matchups = "";
    if (this._config.show_matchups !== false) {
      const seen = new Set();
      const pairs = [];
      for (const t of teams) {
        const m = t.matchup?.attributes;
        if (!m || m.opponent_id == null) continue;
        const key = [t.id, m.opponent_id].sort((x, y) => x - y).join("-");
        if (seen.has(key)) continue;
        seen.add(key);
        pairs.push([t, m.score, teams.find((o) => o.id === m.opponent_id), m.opponent_score]);
      }
      const line = (t, s, other) =>
        `<div class="mline ${scoreValue(s) > scoreValue(other) ? "ahead" : ""} ${t?.id === mine.id ? "me" : ""}">
          ${logoHtml(t, "sm")}<span class="mname">${esc(t?.name ?? "—")}</span><span class="mscore">${isNum(s) ? pts(s) : esc(s ?? "–")}</span>
        </div>`;
      if (pairs.length) {
        matchups = `<div class="group"><span>Week ${esc(league.week)} matchups</span></div>
          <div class="mgrid">${pairs
            .map(([t, s, o, os]) => `<div class="mcard" data-entity="${esc(t.entities.matchup)}">${line(t, s, os)}${line(o, os, s)}</div>`)
            .join("")}</div>`;
      }
    }

    const season = isNum(league.season) ? `${league.season - 1}–${String(league.season).slice(-2)}` : "";
    return `
      <div class="hero centerline centered">
        <div class="eyebrow">Standings${season ? ` · ${esc(season)}` : ""}</div>
        <div class="ringed"><div class="title">${esc(league.name)}</div></div>
        <div class="chips">
          <span class="chip">Week ${esc(league.week)}</span>
          <span class="chip">${teams.length} teams</span>
          ${mine.rank ? `<span class="chip ${mine.rank === 1 ? "gold" : ""}">${esc(mine.name)} · #${mine.rank}</span>` : ""}
        </div>
      </div>
      ${rows}
      ${matchups}
      <div style="height:10px"></div>`;
  }
}
EspnLeagueCard.styles = `
  .centered { text-align: center; }
  .centered .ringed { --ring-size: 96px; margin: 10px 0; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .centered .chips { justify-content: center; }
  .lead-cell { display: flex; align-items: center; gap: 10px; }
  .rank { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: 0.75rem; font-weight: 800;
    background: var(--efh-hover); color: var(--primary-text-color); }
  .rank.gold { background: linear-gradient(135deg, #fde68a, #f59e0b); color: #3b2300; }
  .rank.silver { background: linear-gradient(135deg, #f1f5f9, #94a3b8); color: #1e293b; }
  .rank.bronze { background: linear-gradient(135deg, #fed7aa, #c2410c); color: #fff; }
  .row.mine { background: linear-gradient(90deg, rgba(125, 211, 252, 0.18), transparent 70%); box-shadow: inset 3px 0 0 var(--efh-ice); }
  .rec { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
  .rec strong { font-size: 0.95rem; }
  .streak { font-size: 0.65rem; font-weight: 800; padding: 1px 5px; border-radius: 5px; background: var(--efh-hover); }
  .streak.w { background: rgba(52, 211, 153, 0.18); color: #059669; }
  .streak.l { background: rgba(251, 113, 133, 0.18); color: #e11d48; }
  .num .meter { width: 72px; margin-left: auto; }
  .mgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; padding: 6px 16px 0; }
  .mcard { border-radius: 12px; padding: 8px 10px; cursor: pointer; display: grid; gap: 6px;
    background: linear-gradient(135deg, var(--efh-hover), transparent); box-shadow: inset 0 0 0 1px var(--efh-line); transition: transform 0.2s; }
  .mcard:hover { transform: translateY(-2px); }
  .mline { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 8px; color: var(--efh-muted); }
  .mline.ahead { color: var(--primary-text-color); font-weight: 700; }
  .mline.me .mname { color: var(--primary-color); }
  .mline .logo.sm { width: 24px; height: 24px; }
  .mname { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mscore { font-variant-numeric: tabular-nums; }
`;

// ---------------------------------------------------------------------------
// Visual editors
// ---------------------------------------------------------------------------

const LABELS = {
  league: "League",
  team: "Team",
  window: "Default points window",
  show_matchups: "Show this week's matchups",
};

function makeEditor(extraSchema = [], teamLabel = "Team") {
  return class extends HTMLElement {
    setConfig(config) {
      this._config = { ...config };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    _render() {
      if (!this._hass || !this._config) return;
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.computeLabel = (s) => (s.name === "team" ? teamLabel : LABELS[s.name] || s.name);
        this._form.addEventListener("value-changed", (e) => this._changed(e.detail.value));
        this.appendChild(this._form);
      }
      const leagues = getLeagues(this._hass);
      const league = leagues.find((l) => l.id === this._config.league) || leagues[0];
      const teams = league ? [...league.teams.values()].map(teamInfo).sort((a, b) => a.name.localeCompare(b.name)) : [];
      const mine = teams.find((t) => t.id === league?.myTeamId);

      const schema = [];
      if (leagues.length > 1) {
        schema.push({ name: "league", selector: { select: { mode: "dropdown", options: leagues.map((l) => ({ value: l.id, label: l.name })) } } });
      }
      schema.push({
        name: "team",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "auto", label: mine ? `My team (${mine.name})` : "My team (first team if unknown)" },
              ...teams.map((t) => ({ value: String(t.id), label: t.name })),
            ],
          },
        },
      });
      schema.push(...extraSchema);

      this._form.hass = this._hass;
      this._form.schema = schema;
      this._form.data = {
        ...this._config,
        league: this._config.league || league?.id,
        team: this._config.team != null ? String(this._config.team) : "auto",
        ...(extraSchema.some((s) => s.name === "window") ? { window: this._config.window || "auto" } : {}),
      };
    }

    _changed(value) {
      const config = { ...this._config, ...value };
      if (config.window === "auto") delete config.window;
      if (config.team === "auto" || config.team == null) delete config.team;
      else config.team = Number(config.team);
      // Only store the league when there's a choice to remember.
      if (getLeagues(this._hass).length <= 1) delete config.league;
      for (const [k, v] of Object.entries(config)) if (v === "" || v === undefined) delete config[k];
      this._config = config;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
    }
  };
}

EspnRosterCard.Editor = makeEditor([
  {
    name: "window",
    selector: {
      select: {
        mode: "dropdown",
        options: [{ value: "auto", label: "Automatic (season, or projected before games)" }, ...Object.entries(WINDOWS).map(([value, label]) => ({ value, label }))],
      },
    },
  },
]);
EspnMatchupCard.Editor = makeEditor();
EspnLeagueCard.Editor = makeEditor([{ name: "show_matchups", default: true, selector: { boolean: {} } }], "Highlighted team");

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

const CARDS = [
  ["espn-fantasy-roster-card", EspnRosterCard, "ESPN Fantasy Roster", "A fantasy hockey roster with headshots, fantasy points and stats."],
  ["espn-fantasy-matchup-card", EspnMatchupCard, "ESPN Fantasy Matchup", "This week's head-to-head matchup with live scores and hot players."],
  ["espn-fantasy-league-card", EspnLeagueCard, "ESPN Fantasy League", "League standings and this week's matchups."],
];

window.customCards = window.customCards || [];
for (const [tag, cls, name, description] of CARDS) {
  cls.getConfigElement = () => document.createElement(`${tag}-editor`);
  if (!customElements.get(tag)) customElements.define(tag, cls);
  if (!customElements.get(`${tag}-editor`)) customElements.define(`${tag}-editor`, cls.Editor);
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name, description, preview: true });
  }
}

console.info(`%c ESPN FANTASY HOCKEY %c cards ${VERSION} `, "background:#0c2750;color:#7dd3fc;font-weight:700", "background:#7dd3fc;color:#0c2750");
