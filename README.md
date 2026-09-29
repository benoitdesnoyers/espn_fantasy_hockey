# ESPN Fantasy Hockey for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=benoitdesnoyers&repository=espn_fantasy_hockey&category=integration)

A custom integration for your [ESPN Fantasy Hockey](https://fantasy.espn.com/hockey/) league, with dashboard cards included. Available in English and French.

- **Standings, matchups and rosters** as sensors, with player stats, fantasy points and headshots.
- **Live matchups:** each player's points today and this week, tonight's NHL games, and projected scores.
- **Lineup alerts:** injured starters, starters without a game while a benched player could play, and empty slots, with suggested swaps.
- **League activity:** adds, drops, waiver claims and trades, as an event you can automate on.
- **Three dashboard cards** (Roster, Matchup, League), installed automatically.
- **Smart polling:** fast during NHL games, slow when nothing is happening.
- **Season rollover:** switch to next season in one click, keeping your entities and dashboards.
- Points and category leagues, public and private.

## Requirements

- Home Assistant 2025.2 or newer. The integration's icon appears from 2026.3.
- For a private league: the `espn_s2` and `SWID` cookies of an ESPN account in the league.

## Installation

### HACS

The quickest way is the **Open in HACS** button at the top of this page, which opens the integration in your own Home Assistant. Or, manually:

1. In HACS, open ⋮ → **Custom repositories**, add `https://github.com/benoitdesnoyers/espn_fantasy_hockey` with the category **Integration**. (Inclusion in the HACS default list is pending; once it's in, you can skip this step.)
2. Search for **ESPN Fantasy Hockey**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/espn_fantasy_hockey` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

**Settings → Devices & services → Add integration → ESPN Fantasy Hockey**

| Field          | Notes                                                |
| -------------- | ---------------------------------------------------- |
| League ID      | The `leagueId=` value in your league URL.            |
| Season         | The year the NHL season **ends** (2026-27 → `2027`). |
| espn_s2 / SWID | Only needed for private leagues.                     |

Add the integration once per league.

### Getting the cookies (private leagues)

Log in at fantasy.espn.com, open your browser's dev tools → **Application/Storage → Cookies → espn.com**, and copy the values of `espn_s2` and `SWID` (keep the `{}` braces in SWID). With the cookies, the integration also knows which team is yours.

The cookies last about a year. When ESPN stops accepting them, Home Assistant asks for new ones.

### Options

**Settings → Devices & services → ESPN Fantasy Hockey → Configure**

| Option                       | Default   | Range     | Notes                                                                                                             |
| ---------------------------- | --------- | --------- | ----------------------------------------------------------------------------------------------------------------- |
| My team                      | Automatic | —         | Used for lineup alerts and as the cards' default. Automatic uses your cookies; public leagues need a choice here. |
| Update interval during games | 2 min     | 1–15 min  | From 15 minutes before an NHL game starts until 3½ hours after.                                                   |
| Update interval on game days | 15 min    | 5–120 min | Outside games. With no NHL game in the next 24 hours, updates are hourly.                                         |

Independently of these, transactions are checked every 15 minutes, and the NHL schedule and the next-season check once a day.

### New seasons

Once ESPN renews your league, **Settings → Repairs** offers to switch the integration to the new season. Entities and dashboards stay the same and start showing the new season's data.

## Dashboard cards

The integration ships three cards and loads them automatically; no Lovelace resource or separate HACS plugin is needed. In a dashboard, choose **Add card** and search for "ESPN Fantasy". Cards follow your Home Assistant language (English or French) and theme.

| Card                                                          | Shows                                                                                                                                                                                                                                               |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ESPN Fantasy Roster** (`custom:espn-fantasy-roster-card`)   | Team header with logo, rank and record; lineup alerts; players grouped by lineup slot with headshots, injury badges, tonight's game, key stats and fantasy points. Toggle between today, this week, season, last 7/15/30 days and projected points. |
| **ESPN Fantasy Matchup** (`custom:espn-fantasy-matchup-card`) | This week's head-to-head: logos, records, live and projected scores, a momentum bar, lineup alerts, and each side's top players this week with today's points. Category leagues get a category-by-category breakdown.                               |
| **ESPN Fantasy League** (`custom:espn-fantasy-league-card`)   | Standings with medals, streaks and points-for, every matchup of the week, and recent adds, drops and trades.                                                                                                                                        |

Click a team or player to open the underlying sensor. Each card has a visual editor; by default it shows **your** team. In YAML, all options are optional:

```yaml
type: custom:espn-fantasy-roster-card
team: 3 # ESPN team ID; defaults to your team
league: <device id> # only if you have several leagues; defaults to the first
window: last_7 # today | matchup | season | last_7 | last_15 | last_30 | projected
```

```yaml
type: custom:espn-fantasy-matchup-card
team: 3
```

```yaml
type: custom:espn-fantasy-league-card
team: 3 # the team to highlight
show_matchups: true
show_activity: true
```

## Entities

All entities belong to one device per league.

| Entity                           | State                                                                | Attributes                                                                                                                                                                                                                                                                                               |
| -------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Matchup period`                 | Current matchup period                                               | league name, season, scoring type, whether it's a category league, your team's ID, current update interval                                                                                                                                                                                               |
| `Lineup issues`                  | Number of problems in your lineup today                              | `issues`: injured starters, starters with no game while a benched player could play, empty slots, each with a suggested replacement and a ready-to-send `message`. Unavailable until your team is known.                                                                                                 |
| `Latest transaction`             | The league's latest add, drop, waiver claim or trade                 | `recent`: the last 10, with team, players added/dropped/traded and date                                                                                                                                                                                                                                  |
| `Transactions` (event)           | Fires for each new transaction                                       | event type `free_agent`, `waiver` or `trade`; team, `added`, `dropped`, `traded`, `description`                                                                                                                                                                                                          |
| `<Team> standing` (one per team) | Playoff seed (or final rank once the season ends)                    | record, wins/losses/ties, points for/against, games back, streak, owners                                                                                                                                                                                                                                 |
| `<Team> matchup` (one per team)  | Score in the current matchup: points, or `W-L-T` in category leagues | opponent and score, projected scores (an estimate), each player's points today and this week with tonight's game, and per-category results in category leagues                                                                                                                                           |
| `<Team> roster` (one per team)   | Season fantasy points of the players currently on the roster         | player count, injured players, and a `players` list: position, lineup slot, NHL team, injury status, headshot URL, tonight's game, fantasy points (today, this week, season, last 7/15/30 days, projected) and season stats (goals, assists, shots, hits, blocks, wins, saves, GAA, SV%, time on ice, …) |

The `players` lists are not saved in history (they're large and change on every refresh); use them in templates, e.g. `{{ state_attr('sensor.<league>_<team>_roster', 'players') | selectattr('slot', 'eq', 'G') | map(attribute='name') | list }}`.

Each new transaction is also fired on the Home Assistant event bus as `espn_fantasy_hockey_transaction`, with the same data plus `config_entry_id`, for YAML automations.

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

Replace `my_league` with your league's entity ID prefix, and the `notify` action with yours.

### Team logos

Logos that team managers uploaded themselves are only served by ESPN to logged-in users, which a browser won't do from a Home Assistant page. For private leagues (cookies configured) the integration downloads these with your cookies and serves them from Home Assistant at `/api/espn_fantasy_hockey/logo/<entry_id>/<team_id>`; ESPN's built-in logos are linked directly. That address works without logging in to Home Assistant (images can't send your login), but it only ever serves team logos, and your cookies never leave Home Assistant.

## Troubleshooting

- **The cards don't show up or look outdated:** hard-refresh the browser (Ctrl/Cmd+Shift+R). In the Companion app: **Settings → Companion app → Debugging → Reset frontend cache**.
- **"Failed to set up" or authentication errors:** your cookies have probably expired; follow the notification to enter new ones.
- **Lineup issues is unavailable:** your team isn't known. Choose it in the options.
- **Something else:** enable debug logging and check the log.

  ```yaml
  logger:
    logs:
      custom_components.espn_fantasy_hockey: debug
  ```

  When reporting a bug, attach the diagnostics: **Settings → Devices & services → ESPN Fantasy Hockey → ⋮ → Download diagnostics**. Your cookies and owners' names are removed from it.

## Limitations

- This integration uses ESPN's unofficial fantasy API, which can change without notice. It isn't affiliated with or endorsed by ESPN or the NHL.
- Projected scores are estimates (see above). A longer opening or playoff week is under-counted.
- Category leagues are supported but have been tested less than points leagues. Please report anything odd.

## Development

Python tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) against sanitized ESPN responses in `tests/fixtures/` (a league, the NHL schedule, transactions and player names); the cards are tested with Node's built-in test runner.

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

## Changelog and license

See [CHANGELOG.md](CHANGELOG.md) for release notes. Released under the [MIT license](LICENSE).
