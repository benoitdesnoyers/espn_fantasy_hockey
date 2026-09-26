# ESPN Fantasy Hockey for Home Assistant

A custom integration (installable through HACS) that polls the ESPN Fantasy Hockey API for your league and exposes standings and live matchup scores as sensors.

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

## Entities

All entities belong to one device per league. Data refreshes every 15 minutes.

| Entity | State | Attributes |
|---|---|---|
| `Matchup period` | Current matchup period | season, scoring type, scoring period |
| `<Team> standing` (one per team) | Playoff seed (or final rank once the season ends) | record, wins/losses/ties, points for/against, games back, streak, owners |
| `<Team> matchup` (one per team) | Score in the current matchup: points, or `W-L-T` in category leagues | opponent, opponent score, winner |
