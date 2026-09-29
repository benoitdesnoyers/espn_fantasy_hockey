const HTML_ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

/** Escape a value for interpolation into HTML text or attributes. */
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

export const isNum = (value) => value !== null && value !== "" && !Number.isNaN(Number(value));

/** Fantasy points with one decimal, or an en dash when unknown. */
export const pts = (value, digits = 1) => (isNum(value) ? Number(value).toFixed(digits) : "–");

export const initials = (name) =>
  String(name || "?")
    .split(/\s+/)
    .map((word) => word[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

export const playerPoints = (player, window) => player[`points_${window}`] ?? null;

const signed = (n) => (n > 0 ? `+${n}` : n);

/** A compact stats summary: skaters show G/A/PTS/+-/SOG, goalies W/GAA/SV%/SO. */
export function statLine(player) {
  const s = player.stats ?? {};
  const parts =
    player.position === "G"
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
          [isNum(s.plus_minus) ? signed(s.plus_minus) : null, "+/-"],
          [s.shots, "SOG"],
        ];
  return parts
    .filter(([value]) => value != null)
    .map(([value, label]) => `<b>${esc(value)}</b> ${label}`)
    .join('<span class="dot">·</span>');
}

/**
 * A comparable number for a matchup score: points leagues report a number,
 * category leagues a "W-L-T" string (ties count half).
 */
export function scoreValue(score) {
  if (isNum(score)) return Number(score);
  const match = /^(\d+)-(\d+)-(\d+)$/.exec(String(score ?? ""));
  return match ? Number(match[1]) + Number(match[3]) / 2 : 0;
}

/** A score as displayed: points to one decimal, W-L-T strings as-is. */
export const scoreText = (score) => (isNum(score) ? pts(score) : esc(score ?? "–"));

/** A game's local start time ("7:00 PM", "19 h 00"), in the user's language. */
export const clock = (iso, lang) =>
  new Date(iso).toLocaleTimeString(lang, { hour: "numeric", minute: "2-digit" });

/** "vs MTL 7:00 PM" for a player whose team plays today, else "". */
export const gameText = (player, lang) =>
  player.game_today ? `${player.opponent_today} ${clock(player.game_today, lang)}` : "";

/** A transaction from the latest_transaction sensor, described in the user's language. */
export function transactionText(item, t) {
  const actions = ["added", "dropped", "traded"]
    .filter((kind) => item[kind]?.length)
    .map((kind) => t(kind, { players: item[kind].join(", ") }));
  return `${item.team ?? t("a_team")} ${actions.join(t("and"))}`.trim();
}
