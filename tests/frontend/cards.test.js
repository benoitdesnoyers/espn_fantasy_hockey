import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { create, html } from "./dom-shim.js";
import { makeHass, TEAMS } from "./fixtures.js";
import { LANGUAGES } from "../../custom_components/espn_fantasy_hockey/frontend/lib/i18n.js";

await import("../../custom_components/espn_fantasy_hockey/frontend/espn-fantasy-cards.js");

const render = (type, config = {}, hass = makeHass()) => {
  const card = create(`espn-fantasy-${type}-card`);
  card.setConfig(config);
  card.hass = hass;
  return html(card);
};

describe("registration", () => {
  it("registers every card and its editor for the card picker", () => {
    const types = window.customCards.map((c) => c.type);
    for (const type of ["roster", "matchup", "league"]) {
      const tag = `espn-fantasy-${type}-card`;
      assert.ok(types.includes(tag), tag);
      assert.ok(customElements.get(tag));
      assert.ok(customElements.get(`${tag}-editor`));
    }
  });
});

describe("all cards", () => {
  for (const type of ["roster", "matchup", "league"]) {
    it(`${type}: explains when no league is configured`, () => {
      const out = render(type, {}, { states: {}, entities: {} });
      assert.match(out, /No ESPN Fantasy Hockey league found/);
    });

    it(`${type}: escapes names from ESPN`, () => {
      const teams = TEAMS.map((t) =>
        t.id === 1 ? { ...t, name: "<img src=x onerror=alert(1)>" } : t,
      );
      const out = render(type, {}, makeHass({ teams }));
      assert.doesNotMatch(out, /<img src=x/);
      assert.match(out, /&lt;img src=x onerror=alert\(1\)&gt;/);
    });

    it(`${type}: renders no undefined or NaN`, () => {
      assert.doesNotMatch(render(type), /undefined|NaN/);
    });
  }
});

describe("roster card", () => {
  it("shows the user's own team by default", () => {
    assert.match(render("roster"), /Ice Wolves/);
    assert.doesNotMatch(render("roster"), /Opp Onent/);
  });

  it("shows another team when configured", () => {
    assert.match(render("roster", { team: 2 }), /Opp Onent/);
  });

  it("groups players by lineup slot, in order", () => {
    const out = render("roster");
    const order = ["Forwards", "Defense", "Goalies", "Bench", "Injured reserve"].map((g) =>
      out.indexOf(`${g} ·`),
    );
    assert.ok(
      order.every((i) => i >= 0),
      `missing group: ${order}`,
    );
    assert.deepEqual(
      order,
      [...order].sort((a, b) => a - b),
    );
  });

  it("uses season points once games have been played, projections before", () => {
    assert.match(render("roster"), /aria-pressed="true">Season</);

    const preseason = makeHass({
      rosters: {
        1: [{ ...makeHass().states["sensor.t1_roster"].attributes.players[0], points_season: 0 }],
      },
    });
    assert.match(render("roster", {}, preseason), /aria-pressed="true">Proj</);
  });

  it("honours a configured points window", () => {
    const out = render("roster", { window: "last_7" });
    assert.match(out, /aria-pressed="true">7D</);
    assert.match(out, /Last 7 days/);
  });

  it("summarises skater and goalie stats", () => {
    const out = render("roster");
    assert.match(out, /<b>20<\/b> G/);
    assert.match(out, /<b>\+7<\/b> \+\/-/);
    assert.match(out, /<b>2\.46<\/b> GAA/);
    assert.match(out, /<b>\.912<\/b> SV%/);
  });

  it("badges injured players", () => {
    assert.match(render("roster"), /class="inj bad" title="OUT">OUT</);
  });
});

describe("matchup card", () => {
  it("shows both teams and who leads", () => {
    const out = render("matchup");
    assert.match(out, /Ice Wolves/);
    assert.match(out, /Blue Liners/);
    assert.match(out, /Ice Wolves leads by 17\.2/);
  });

  it("features this week's top active players once games are played", () => {
    const out = render("matchup");
    assert.match(out, /This week/);
    // Search after the lineup banner, which also names a player.
    const list = out.slice(out.indexOf('class="hotlabel"'));
    assert.ok(list.indexOf("Dee Fence") < list.indexOf("Alex Forward"), "30.4 before 22.1");
    assert.doesNotMatch(list, /Benny Bench/); // on the bench
    assert.match(out, /3\.5 today/);
    assert.match(out, /class="game">vs MTL /);
  });

  it("falls back to the last 7 days before the matchup has points", () => {
    const hass = makeHass();
    for (const kind of ["matchup", "roster"]) {
      for (const team of [1, 2]) {
        for (const player of hass.states[`sensor.t${team}_${kind}`].attributes.players) {
          delete player.points_matchup;
        }
      }
    }
    assert.match(render("matchup", {}, hass), /Hot · last 7 days/);
  });

  it("shows projected scores", () => {
    const out = render("matchup");
    assert.match(out, /Proj\. 120\.5/);
    assert.match(out, /Proj\. 101\.3/);
  });

  it("warns about the user's lineup, and only for their team", () => {
    assert.match(
      render("matchup"),
      /1 lineup issue.*Alex Forward has no game today → Benny Bench plays today/s,
    );
    assert.doesNotMatch(render("matchup", { team: 2 }), /lineup issue/);
  });

  it("handles a bye week", () => {
    assert.match(render("matchup", { team: 3 }), /Bye week/);
  });

  it("shows categories instead of players in category leagues", () => {
    const categories = [
      { abbreviation: "G", score: 7, opponent_score: 4, result: "WIN" },
      { abbreviation: "GAA", score: 2.9, opponent_score: 2.1, result: "LOSS" },
    ];
    const out = render("matchup", {}, makeHass({ categoryLeague: true, categories }));
    assert.match(out, /Categories/);
    assert.match(out, /<span class="won">7<\/span>\s*<span class="cat-name">G<\/span>/);
    assert.match(out, /<span class="cat-name">GAA<\/span>\s*<span class="won">2\.1<\/span>/);
    assert.doesNotMatch(out, /This week/);
  });
});

describe("league card", () => {
  it("orders standings by rank and highlights the user's team", () => {
    const out = render("league");
    // Search after the hero, which also names the user's team in a chip.
    const rows = out.slice(out.indexOf('class="row'));
    const positions = ["Blue Liners", "Ice Wolves", "Top Shelf"].map((n) => rows.indexOf(n));
    assert.deepEqual(
      positions,
      [...positions].sort((a, b) => a - b),
    );
    assert.match(out, /class="row mine"[^>]*data-entity="sensor\.t1_standing"/);
  });

  it("lists each matchup once", () => {
    const out = render("league");
    assert.equal(out.match(/class="mcard"/g).length, 1);
  });

  it("can hide the matchups", () => {
    assert.doesNotMatch(render("league", { show_matchups: false }), /class="mcard"/);
  });

  it("lists recent activity, and can hide it", () => {
    assert.match(
      render("league"),
      /Recent activity.*Blue Liners added New Guy and dropped Old Guy/s,
    );
    assert.doesNotMatch(render("league", { show_activity: false }), /Recent activity/);
  });
});

describe("roster card, live data", () => {
  it("offers today's and this week's points", () => {
    const out = render("roster", { window: "matchup" });
    assert.match(out, /aria-pressed="true">Week</);
    assert.match(out, /<strong>30\.4<\/strong>/);
  });

  it("shows tonight's opponent and start time", () => {
    assert.match(render("roster"), /class="game">vs MTL \d/);
  });

  it("shows the lineup banner on the user's team only", () => {
    assert.match(render("roster"), /class="issues"/);
    assert.doesNotMatch(render("roster", { team: 2 }), /class="issues"/);
    assert.doesNotMatch(render("roster", {}, makeHass({ issues: [] })), /class="issues"/);
  });

  it("hides fantasy points in category leagues", () => {
    const out = render("roster", {}, makeHass({ categoryLeague: true }));
    assert.doesNotMatch(out, /class="seg"/);
    assert.doesNotMatch(out, /class="big"/);
    assert.match(out, /<b>20<\/b> G/); // stats remain
  });
});

describe("French", () => {
  const fr = () => makeHass({ language: "fr" });

  it("translates the roster card", () => {
    const out = render("roster", {}, fr());
    assert.match(out, /Effectif/);
    assert.match(out, /Attaquants · 1/);
    assert.match(out, /1 problème d'alignement/);
    assert.match(out, /Alex Forward ne joue pas aujourd'hui → Benny Bench joue aujourd'hui/);
  });

  it("translates the matchup and league cards", () => {
    assert.match(render("matchup", {}, fr()), /Ice Wolves mène par 17\.2/);
    const league = render("league", {}, fr());
    assert.match(league, /Classement/);
    assert.match(league, /Blue Liners a ajouté New Guy et a retiré Old Guy/);
  });

  it("translates the editor", () => {
    const editor = create("espn-fantasy-league-card-editor");
    editor.hass = fr();
    editor.setConfig({});
    const team = editor.child.schema.find((f) => f.name === "team");
    assert.equal(team.selector.select.options[0].label, "Mon équipe (Ice Wolves)");
    assert.equal(editor.child.computeLabel({ name: "team" }), "Équipe en évidence");
  });

  it("falls back to English for other languages", () => {
    assert.match(render("roster", {}, makeHass({ language: "de" })), /Forwards · 1/);
  });
});

describe("editor", () => {
  let editor;
  beforeEach(() => {
    editor = create("espn-fantasy-roster-card-editor");
    editor.hass = makeHass();
    editor.setConfig({});
  });

  it("offers the user's team first, then every team", () => {
    const team = editor.child.schema.find((f) => f.name === "team");
    const labels = team.selector.select.options.map((o) => o.label);
    assert.deepEqual(labels, ["My team (Ice Wolves)", "Blue Liners", "Ice Wolves", "Top Shelf"]);
  });

  it("stores picked values and drops automatic ones", () => {
    editor._changed({ team: "2", window: "auto" });
    assert.deepEqual(editor.events.at(-1).detail.config, { team: 2 });

    editor._changed({ team: "auto", window: "last_7" });
    assert.deepEqual(editor.events.at(-1).detail.config, { window: "last_7" });
  });
});

describe("translations", () => {
  it("French covers every English string", () => {
    assert.deepEqual(Object.keys(LANGUAGES.fr).sort(), Object.keys(LANGUAGES.en).sort());
  });
});
