# ESPN Fantasy Hockey for Home Assistant

A custom HACS integration that polls the ESPN Fantasy Hockey API for your league and exposes standings and live matchup scores as sensors.

## Installation

### HACS
1. HACS → ⋮ → **Custom repositories** → add this repository's URL, category **Integration**.
2. Install **ESPN Fantasy Hockey** and restart Home Assistant.

### Manual
Copy `custom_components/espn_fantasy_hockey` into your Home Assistant `config/custom_components/` folder and restart.

## Configuration

**Settings → Devices & services → Add integration → ESPN Fantasy Hockey**

| Field | Notes |
|---|---|
| League ID | The `leagueId=` value in your league URL. |
| Season | The year the NHL season **ends** (2026-27 → `2027`). |
| espn_s2 / SWID | Only needed for private leagues. |

### Getting the cookies (private leagues)
Log in at fantasy.espn.com, open your browser's dev tools → **Application/Storage → Cookies → espn.com**, and copy the values of `espn_s2` and `SWID` (keep the `{}` braces in SWID).

## Dashboard cards

The integration ships three cards and loads them automatically; no Lovelace resource or separate HACS plugin is needed. In a dashboard, choose **Add card** and search for "ESPN Fantasy".

| Card | Shows |
|---|---|
| **ESPN Fantasy Roster** (`custom:espn-fantasy-roster-card`) | Team header with logo, rank and record; players grouped by lineup slot with headshots, injury badges, key stats and fantasy points. Toggle between season, last 7/15/30 days and projected points. |
| **ESPN Fantasy Matchup** (`custom:espn-fantasy-matchup-card`) | This week's head-to-head: logos, records, live scores, a momentum bar and each side's top players. |
| **ESPN Fantasy League** (`custom:espn-fantasy-league-card`) | Standings with medals, streaks and points-for, plus every matchup of the week. |

Each card has a visual editor. By default it shows **your** team: when the `espn_s2`/`SWID` cookies are configured, the integration recognizes the team owned by that ESPN account. You can pick any other team (and league, if you have several) in the editor, or in YAML:

```yaml
type: custom:espn-fantasy-roster-card
team: 3            # optional; ESPN team ID, defaults to your team
window: last_7     # optional; season | last_7 | last_15 | last_30 | projected
```

## Entities

All entities belong to one device per league. Data refreshes every 15 minutes.

| Entity | State | Attributes |
|---|---|---|
| `Matchup period` | Current matchup period | season, scoring type, scoring period |
| `<Team> standing` (one per team) | Playoff seed (or final rank once the season ends) | record, wins/losses/ties, points for/against, games back, streak, owners |
| `<Team> matchup` (one per team) | Score in the current matchup: points, or `W-L-T` in category leagues | opponent, opponent score, winner |
| `<Team> roster` (one per team) | Season fantasy points of the players currently on the roster | player count, injured players, and a `players` list: position, lineup slot, NHL team, injury status, headshot URL, fantasy points (season, last 7/15/30 days, projected) and season stats (goals, assists, shots, hits, blocks, wins, saves, GAA, SV%, …) |

The `players` list is not saved in history (it's large and changes on every refresh); use it in templates, e.g. `{{ state_attr('sensor.<league>_<team>_roster', 'players') | selectattr('slot', 'eq', 'G') | map(attribute='name') | list }}`.

### Team logos
Logos that team managers uploaded themselves are only served by ESPN to logged-in users, which a browser won't do from a Home Assistant page. For private leagues (cookies configured) the integration downloads these with your cookies and serves them from Home Assistant at `/api/espn_fantasy_hockey/logo/<entry_id>/<team_id>`; ESPN's built-in logos are linked directly.
