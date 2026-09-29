import { INJURY } from "./const.js";
import { esc, initials } from "./format.js";

/** Round team logo; the abbreviation shows through if the image is missing or fails. */
export function logoHtml(team, className = "") {
  return `<div class="logo ${className}" data-entity="${esc(team?.entities?.standing)}">
    <span>${esc(team?.abbrev || initials(team?.name))}</span>
    ${team?.logo ? `<img src="${esc(team.logo)}" alt="" loading="lazy">` : ""}
  </div>`;
}

/** Round player headshot with a position-coloured ring and an injury badge. */
export function headshotHtml(player) {
  const pos = { G: "g", D: "d" }[player.position] ?? "f";
  const injury = INJURY[player.injury];
  const badge = injury
    ? `<i class="inj ${injury[1]}" title="${esc(player.injury)}">${injury[0]}</i>`
    : "";
  return `<div class="shot pos-${pos}">
    <span>${esc(initials(player.name))}</span>
    ${player.headshot ? `<img src="${esc(player.headshot)}" alt="" loading="lazy">` : ""}
    ${badge}
  </div>`;
}

/** A player row: headshot, name and meta line, and a right-hand value block. */
export function playerRowHtml({ player, entity, index, meta, value }) {
  return `<div class="row" style="--i:${index}" data-entity="${esc(entity)}">
    ${headshotHtml(player)}
    <div class="cell">
      <div class="name">${esc(player.name)}</div>
      <div class="meta"><span class="tag">${esc(player.position)}</span>${meta}</div>
    </div>
    <div class="num">${value}</div>
  </div>`;
}

/** A thin horizontal meter; `fraction` is 0..1. */
export const meterHtml = (fraction) =>
  `<div class="meter"><i style="width:${Math.round(Math.min(1, Math.max(0, fraction)) * 100)}%"></i></div>`;

/** The lineup issues banner, or "" when the lineup is fine. */
export function lineupIssuesHtml(issues, t) {
  if (!issues?.length) return "";
  const title =
    issues.length === 1 ? t("lineup_issues_one") : t("lineup_issues_other", { n: issues.length });
  const items = issues
    .map((issue) => {
      const text = t(`issue_${issue.type}`, { player: issue.player, slot: issue.slot });
      const swap = issue.replacement
        ? ` → ${t("issue_swap", { replacement: issue.replacement })}`
        : "";
      return `<li>${esc(text)}${esc(swap)}</li>`;
    })
    .join("");
  return `<div class="issues" role="alert"><strong>⚠ ${esc(title)}</strong><ul>${items}</ul></div>`;
}
