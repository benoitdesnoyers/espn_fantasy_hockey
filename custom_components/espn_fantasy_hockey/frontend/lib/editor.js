import { getLeagues, teamInfo } from "./data.js";
import { translator } from "./i18n.js";

/** Field name -> translation key for its label. */
const LABELS = {
  league: "league",
  window: "default_window",
  show_matchups: "show_matchups",
  show_activity: "show_activity",
};

/** Sentinel for "follow the default" in dropdowns, which can't hold an empty value. */
export const AUTO = "auto";

export const dropdown = (name, options) => ({
  name,
  selector: { select: { mode: "dropdown", options } },
});

/**
 * Build a visual editor element class for a card.
 *
 * Every editor offers a team picker (and a league picker when several leagues
 * are configured); `extraSchema(t)` returns card-specific ha-form fields, and
 * `teamLabel` is the translation key for the team picker's label.
 */
export function makeEditor({ extraSchema = () => [], teamLabel = "team" } = {}) {
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
      const t = translator(this._hass);
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.addEventListener("value-changed", (e) => this._changed(e.detail.value));
        this.appendChild(this._form);
      }

      const leagues = getLeagues(this._hass);
      const league = leagues.find((l) => l.id === this._config.league) ?? leagues[0];
      const teams = league
        ? [...league.teams.values()].map(teamInfo).sort((a, b) => a.name.localeCompare(b.name))
        : [];
      const mine = teams.find((team) => team.id === league?.myTeamId);
      const extra = extraSchema(t);

      const schema = [];
      if (leagues.length > 1) {
        schema.push(
          dropdown(
            "league",
            leagues.map((l) => ({ value: l.id, label: l.name })),
          ),
        );
      }
      schema.push(
        dropdown("team", [
          {
            value: AUTO,
            label: mine ? t("my_team", { team: mine.name }) : t("my_team_unknown"),
          },
          ...teams.map((team) => ({ value: String(team.id), label: team.name })),
        ]),
        ...extra,
      );

      this._form.hass = this._hass;
      this._form.computeLabel = (field) =>
        t(field.name === "team" ? teamLabel : (LABELS[field.name] ?? field.name));
      this._form.schema = schema;
      this._form.data = {
        ...this._config,
        league: this._config.league ?? league?.id,
        team: this._config.team != null ? String(this._config.team) : AUTO,
        ...(extra.some((field) => field.name === "window")
          ? { window: this._config.window ?? AUTO }
          : {}),
      };
    }

    _changed(value) {
      const config = { ...this._config, ...value };
      if (config.window === AUTO) delete config.window;
      if (config.team === AUTO || config.team == null) delete config.team;
      else config.team = Number(config.team);
      // Only remember the league when there's a choice to remember.
      if (getLeagues(this._hass).length <= 1) delete config.league;
      for (const [key, v] of Object.entries(config)) {
        if (v === "" || v === undefined) delete config[key];
      }
      this._config = config;
      this.dispatchEvent(
        new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
      );
    }
  };
}
