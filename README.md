# ESPN Fantasy Hockey for Home Assistant

A custom HACS integration for your ESPN Fantasy Hockey league: standings, live matchups, rosters and player stats as sensors, lineup alerts, league transactions, and three dashboard cards. English and French.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add this repository's URL, category **Integration**.
2. Install **ESPN Fantasy Hockey** and restart Home Assistant.

### Manual

Copy `custom_components/espn_fantasy_hockey` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

**Settings → Devices & services → Add integration → ESPN Fantasy Hockey**

| Field          | Notes                                                |
| -------------- | ---------------------------------------------------- |
| League ID      | The `leagueId=` value in your league URL.            |
| Season         | The year the NHL season **ends** (2026-27 → `2027`). |
| espn_s2 / SWID | Only needed for private leagues.                     |

### Getting the cookies (private leagues)

Log in at fantasy.espn.com, open your browser's dev tools → **Application/Storage → Cookies → espn.com**, and copy the values of `espn_s2` and `SWID` (keep the `{}` braces in SWID). With the cookies, the integration also knows which team is yours.

### Options

**Settings → Devices & services → ESPN Fantasy Hockey → Configure**

| Option                       | Default   | Notes                                                                          |
| ---------------------------- | --------- | ------------------------------------------------------------------------------ |
| My team                      | Automatic | Used for lineup alerts and as the cards' default. Automatic uses your cookies. |
| Update interval during games | 2 min     | While NHL games are being played.                                              |
| Update interval on game days | 15 min    | Outside games. With no NHL game in the next day, updates are hourly.           |

### New seasons

Once ESPN renews your league, **Settings → Repairs** offers to switch the integration to the new season. Entities and dashboards stay the same.

## Dashboard cards

The integration ships three cards and loads them automatically; no Lovelace resource or separate HACS plugin is needed. In a dashboard, choose **Add card** and search for "ESPN Fantasy". Cards follow your Home Assistant language (English or French).

| Card                                                          | Shows                                                                                                                                                                                                                                               |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ESPN Fantasy Roster** (`custom:espn-fantasy-roster-card`)   | Team header with logo, rank and record; lineup alerts; players grouped by lineup slot with headshots, injury badges, tonight's game, key stats and fantasy points. Toggle between today, this week, season, last 7/15/30 days and projected points. |
| **ESPN Fantasy Matchup** (`custom:espn-fantasy-matchup-card`) | This week's head-to-head: logos, records, live and projected scores, a momentum bar, lineup alerts, and each side's top players this week with today's points. Category leagues get a category-by-category breakdown.                               |
| **ESPN Fantasy League** (`custom:espn-fantasy-league-card`)   | Standings with medals, streaks and points-for, every matchup of the week, and recent adds, drops and trades.                                                                                                                                        |

Each card has a visual editor. By default it shows **your** team; you can pick any other team (and league, if you have several) in the editor, or in YAML:

```yaml
type: custom:espn-fantasy-roster-card
team: 3 # optional; ESPN team ID, defaults to your team
window: last_7 # optional; today | matchup | season | last_7 | last_15 | last_30 | projected
```

## Entities

All entities belong to one device per league.

| Entity                           | State                                                                | Attributes                                                                                                                                                                                                                                                                                               |
| -------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Matchup period`                 | Current matchup period                                               | season, scoring type, your team's ID, current update interval                                                                                                                                                                                                                                            |
| `Lineup issues`                  | Number of problems in your lineup today                              | `issues`: injured starters, starters with no game while a benched player could play, empty slots — each with a suggested replacement and a ready-to-send `message`                                                                                                                                       |
| `Latest transaction`             | The league's latest add, drop, waiver claim or trade                 | `recent`: the last 10, with team, players added/dropped/traded and date                                                                                                                                                                                                                                  |
| `Transactions` (event)           | Fires for each new transaction                                       | event type `free_agent`, `waiver` or `trade`; team, `added`, `dropped`, `traded`, `description`                                                                                                                                                                                                          |
| `<Team> standing` (one per team) | Playoff seed (or final rank once the season ends)                    | record, wins/losses/ties, points for/against, games back, streak, owners                                                                                                                                                                                                                                 |
| `<Team> matchup` (one per team)  | Score in the current matchup: points, or `W-L-T` in category leagues | opponent and score, projected scores (an estimate), each player's points today and this week with tonight's game, and per-category results in category leagues                                                                                                                                           |
| `<Team> roster` (one per team)   | Season fantasy points of the players currently on the roster         | player count, injured players, and a `players` list: position, lineup slot, NHL team, injury status, headshot URL, tonight's game, fantasy points (today, this week, season, last 7/15/30 days, projected) and season stats (goals, assists, shots, hits, blocks, wins, saves, GAA, SV%, time on ice, …) |

The `players` lists are not saved in history (they're large and change on every refresh); use them in templates, e.g. `{{ state_attr('sensor.<league>_<team>_roster', 'players') | selectattr('slot', 'eq', 'G') | map(attribute='name') | list }}`.

**Projected scores** are estimates: ESPN doesn't publish matchup projections for hockey, so each healthy starter's projected season points are spread over 82 games and multiplied by their NHL team's remaining games this week (Monday to Sunday).

### Automation examples

Lineup reminder before tonight's games:

```yaml
triggers:
  - trigger: time
    at: "17:00:00"
conditions:
  - condition: numeric_state
    entity_id: sensor.my_league_lineup_issues
    above: 0
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: Check your lineup
      message: >
        {{ state_attr('sensor.my_league_lineup_issues', 'issues')
           | map(attribute='message') | join('\n') }}
```

League transactions:

```yaml
triggers:
  - trigger: state
    entity_id: event.my_league_transactions
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: "{{ trigger.to_state.attributes.description }}"
```

### Team logos

Logos that team managers uploaded themselves are only served by ESPN to logged-in users, which a browser won't do from a Home Assistant page. For private leagues (cookies configured) the integration downloads these with your cookies and serves them from Home Assistant at `/api/espn_fantasy_hockey/logo/<entry_id>/<team_id>`; ESPN's built-in logos are linked directly.

### Diagnostics

**Settings → Devices & services → ESPN Fantasy Hockey → ⋮ → Download diagnostics** gives the parsed league data for bug reports, with your cookies and owners' names removed.

## Development

Python tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) against sanitized ESPN responses in `tests/fixtures/`; the cards are tested with Node's built-in test runner.

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
npm install

pytest                  # integration tests
npm test                # card tests
ruff check . && ruff format --check .
npm run lint            # ESLint + Prettier

pip install pre-commit && pre-commit install   # run the linters on every commit
```

The cards are plain ES modules in `custom_components/espn_fantasy_hockey/frontend/`, served by the integration without a build step. When bumping the version, update both `manifest.json` and `frontend/lib/const.js` (a test checks they match) and add an entry to `CHANGELOG.md`.
