import { resolve, signature } from "./data.js";
import { esc } from "./format.js";
import { translator } from "./i18n.js";
import { sharedStyles } from "./styles.js";

/**
 * Common card plumbing: config, change detection, rendering into shadow DOM,
 * image fallbacks and click handling. Subclasses implement `render(data)` and
 * may set a static `styles` string.
 */
export class BaseCard extends HTMLElement {
  static styles = "";

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._ui = {};
    // <img> errors don't bubble; catch them while capturing to reveal the fallback.
    this.shadowRoot.addEventListener(
      "error",
      (e) => e.target.tagName === "IMG" && e.target.classList.add("broken"),
      true,
    );
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { ...config };
    this._signature = null;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    // Re-render on data changes and when the user switches language.
    const sig = signature(hass) + (hass.locale?.language ?? hass.language ?? "");
    if (sig !== this._signature) {
      this._signature = sig;
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
    this.t = translator(this._hass);
    const data = resolve(this._hass, this._config);
    const body = data.error
      ? `<div class="error">${esc(this.t(data.error))}</div>`
      : this.render(data);
    const animate = !data.error && !this._rendered;
    this.shadowRoot.innerHTML = `
      <style>${sharedStyles}${this.constructor.styles}</style>
      <ha-card class="${animate ? "animate" : ""}">${body}</ha-card>`;
    if (!data.error) this._rendered = true;
  }

  _onClick(e) {
    const windowButton = e.target.closest("[data-window]");
    if (windowButton) {
      this._ui.window = windowButton.dataset.window;
      this._update();
      return;
    }
    const entityId = e.target.closest("[data-entity]")?.dataset.entity;
    if (entityId) {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId },
          bubbles: true,
          composed: true,
        }),
      );
    }
  }
}
