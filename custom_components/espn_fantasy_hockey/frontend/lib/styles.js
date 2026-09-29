/** Styles shared by every card; each card appends its own. */
export const sharedStyles = `
  :host {
    --efh-ice: #7dd3fc;
    --efh-blue: #2563eb;
    --efh-red: #f43f5e;
    --efh-orange: #fb923c;
    --efh-muted: var(--secondary-text-color);
    --efh-line: var(--divider-color, rgba(127, 127, 127, 0.2));
    --efh-hover: rgba(125, 211, 252, 0.08);
    --efh-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  ha-card {
    overflow: hidden;
    container-type: inline-size;
    padding-bottom: 8px;
  }
  .error {
    padding: 16px;
    color: var(--error-color, #db4437);
  }

  /* Hero: always dark ice, whatever the theme, so its white text always reads. */
  .hero {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    color: #fff;
    padding: 18px;
    background:
      radial-gradient(120% 140% at 100% 0%, rgba(125, 211, 252, 0.42) 0%, transparent 55%),
      radial-gradient(90% 120% at 0% 100%, rgba(37, 99, 235, 0.55) 0%, transparent 60%),
      linear-gradient(135deg, #06122a 0%, #0c2750 55%, #113c7c 100%);
  }
  /* Rink markings: a center line on symmetric heroes, and a face-off circle
     around whichever element has .ringed, so the two always line up. */
  .hero.centerline::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background: linear-gradient(
      90deg,
      transparent calc(50% - 1px),
      rgba(255, 255, 255, 0.06) calc(50% - 1px),
      rgba(255, 255, 255, 0.06) calc(50% + 1px),
      transparent calc(50% + 1px)
    );
  }
  .ringed {
    position: relative;
  }
  .ringed::after {
    content: "";
    position: absolute;
    left: 50%;
    top: 50%;
    width: var(--ring-size, 112px);
    height: var(--ring-size, 112px);
    transform: translate(-50%, -50%);
    border-radius: 50%;
    pointer-events: none;
    box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.07);
  }
  .eyebrow {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    opacity: 0.75;
  }
  .title {
    font-size: 1.35rem;
    font-weight: 700;
    line-height: 1.2;
    margin: 2px 0;
    overflow-wrap: anywhere;
  }
  .sub {
    font-size: 0.85rem;
    opacity: 0.8;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.14);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  }
  .chip.gold {
    background: linear-gradient(135deg, #fde68a, #f59e0b);
    color: #3b2300;
    box-shadow: none;
  }

  .logo {
    position: relative;
    flex: none;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    overflow: hidden;
    display: grid;
    place-items: center;
    cursor: pointer;
    background: radial-gradient(circle at 30% 25%, #fff, #dbeafe 70%);
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.22), 0 8px 22px rgba(0, 0, 0, 0.35);
    color: #0c2750;
    font-weight: 800;
    font-size: 0.8rem;
  }
  .logo.sm {
    width: 32px;
    height: 32px;
    font-size: 0.6rem;
    box-shadow: 0 0 0 2px var(--efh-line);
  }
  .logo.lg {
    width: 76px;
    height: 76px;
    font-size: 1rem;
  }
  .logo.glow {
    box-shadow: 0 0 0 3px var(--efh-ice), 0 0 30px rgba(125, 211, 252, 0.7);
  }
  .logo img,
  .shot img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .logo img.broken,
  .shot img.broken {
    display: none;
  }

  .shot {
    --ring: #38bdf8;
    position: relative;
    flex: none;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--efh-muted);
    background:
      radial-gradient(circle at 50% 30%, color-mix(in srgb, var(--ring) 35%, transparent), transparent 70%),
      var(--secondary-background-color, rgba(127, 127, 127, 0.12));
    box-shadow: inset 0 0 0 2px var(--ring);
  }
  .shot img {
    border-radius: 50%;
    object-position: 50% 15%;
  }
  .shot.pos-d {
    --ring: #34d399;
  }
  .shot.pos-g {
    --ring: #a78bfa;
  }
  .inj {
    position: absolute;
    right: -4px;
    bottom: -2px;
    z-index: 1;
    padding: 0 4px;
    border-radius: 6px;
    font: 700 0.58rem/1.5 system-ui, sans-serif;
    color: #fff;
    box-shadow: 0 0 0 2px var(--card-background-color, #fff);
  }
  .inj.bad {
    background: #e11d48;
  }
  .inj.warn {
    background: #d97706;
  }

  .group {
    display: flex;
    justify-content: space-between;
    padding: 14px 16px 4px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--efh-muted);
  }
  .row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    padding: 7px 16px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .row:hover {
    background: var(--efh-hover);
  }
  /* Grid and flex children that must be allowed to shrink so text can ellipsize. */
  .cell {
    min-width: 0;
  }
  .name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta {
    font-size: 0.78rem;
    color: var(--efh-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .meta b {
    color: var(--primary-text-color);
    font-weight: 600;
  }
  .dot {
    margin: 0 5px;
    opacity: 0.5;
  }
  .tag {
    font-size: 0.66rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 5px;
    background: var(--efh-hover);
    color: var(--primary-text-color);
    margin-right: 4px;
  }
  .num {
    text-align: right;
    min-width: 64px;
  }
  .num strong {
    font-size: 1.05rem;
    font-variant-numeric: tabular-nums;
  }
  .meter {
    height: 4px;
    margin-top: 4px;
    border-radius: 4px;
    background: var(--efh-line);
    overflow: hidden;
  }
  .meter i {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--efh-ice), var(--efh-blue));
    transform-origin: left;
  }
  .issues {
    margin: 12px 16px 0;
    padding: 10px 12px;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(251, 146, 60, 0.16), rgba(244, 63, 94, 0.1));
    box-shadow: inset 0 0 0 1px rgba(251, 146, 60, 0.35);
    font-size: 0.85rem;
  }
  .issues ul {
    margin: 4px 0 0;
    padding-left: 18px;
  }
  .game {
    color: var(--efh-ice-text, #0284c7);
    font-weight: 600;
  }
  .empty {
    padding: 20px 16px;
    color: var(--efh-muted);
    text-align: center;
  }

  /* Entrance animations run on the first render only, and not with reduced motion. */
  .animate .row {
    animation: rise 0.45s var(--efh-ease) both;
    animation-delay: calc(var(--i, 0) * 22ms);
  }
  .animate .meter i,
  .animate .bar i {
    animation: grow 0.9s var(--efh-ease) both;
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }
  @keyframes grow {
    from {
      transform: scaleX(0);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .animate * {
      animation: none !important;
    }
  }
`;
