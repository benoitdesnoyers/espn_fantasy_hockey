/**
 * Just enough of the DOM for the cards to register and render under Node.
 * Rendering is checked through the HTML strings written to the shadow root.
 */

class ShadowRoot {
  innerHTML = "";
  addEventListener() {}
}

globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = new ShadowRoot();
    return this.shadowRoot;
  }
  dispatchEvent(event) {
    (this.events ??= []).push(event);
  }
  appendChild(child) {
    this.child = child;
  }
};

globalThis.CustomEvent = class {
  constructor(type, init) {
    this.type = type;
    this.detail = init?.detail;
  }
};

const registry = new Map();
globalThis.customElements = {
  get: (tag) => registry.get(tag),
  define: (tag, cls) => registry.set(tag, cls),
};

globalThis.window = globalThis;
globalThis.document = {
  createElement: (tag) => {
    const Element = registry.get(tag);
    return Element ? new Element() : { tag, addEventListener() {} };
  },
};

/** Create a registered card or editor element by tag. */
export const create = (tag) => new (customElements.get(tag))();

/**
 * A card's rendered markup, without its <style> block. Apostrophes and quotes are
 * unescaped for readable assertions; `<`, `>` and `&` stay escaped.
 */
export const html = (card) =>
  card.shadowRoot.innerHTML
    .replace(/<style>[\s\S]*?<\/style>/, "")
    .replaceAll("&#39;", "'")
    .replaceAll("&quot;", '"');
