# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Breaking:** the roster stat `toi_per_game` (a `"m:ss"` string) is now
  `toi_per_game_seconds` (a number of seconds).
- Team sensor names now come from translations (`"{team} standing"`, etc.);
  entity IDs and displayed names are unchanged.
- The dashboard cards are split into ES modules and served under a versioned
  path, so browsers always load a matching set after an update.
- The private logo cache holds one image per team instead of growing without bound.

### Added

- **Lineup alerts:** a `Lineup issues` sensor flags injured starters, starters
  without a game while a benched player could play, and empty slots, with
  suggested swaps. Shown in the Roster and Matchup cards.
- **Live matchups:** each player's points today and this week, tonight's NHL
  game, and estimated projected scores, in the sensors and the Matchup card.
- **Smarter polling:** every 2 minutes during NHL games, 15 minutes on game
  days, hourly otherwise.
- **League activity:** a `Transactions` event entity and a `Latest transaction`
  sensor for adds, drops, waiver claims and trades; recent activity in the
  League card.
- **Options:** choose your team and the update intervals.
- **Category leagues:** per-category results in the matchup sensor and card.
- **Season rollover:** a Repairs issue offers to switch to the new season once
  ESPN renews the league, keeping entities and dashboards.
- **French** translations for the integration and the cards.
- **Diagnostics** download, with cookies and owner names removed.
- Test suite for the integration (config flow, setup, sensors, logo proxy and
  ESPN parsing) and for the cards.
- Ruff, Prettier and ESLint configuration, pre-commit hooks, and a CI workflow
  running linters and tests.
- This changelog.

### Removed

- `strings.json`, which duplicated `translations/en.json`.

## [0.2.2] - 2026-09-28

### Fixed

- `manifest.json` contained unresolved merge-conflict markers in 0.2.1.

### Added

- MIT license.
- Brand icons shown by Home Assistant 2026.3 and later.

## [0.2.1] - 2026-09-28

Broken release (invalid `manifest.json`); use 0.2.2.

### Added

- Hassfest and HACS validation workflow.

### Fixed

- Removed a stray symlink included in 0.2.0.

## [0.2.0] - 2026-09-28

### Added

- Roster, Matchup and League dashboard cards, bundled with the integration.
- Per-team roster sensors with player stats, fantasy points and headshots.
- Proxy for custom team logos that ESPN only serves to logged-in users.
- Automatic detection of the user's own team from the `SWID` cookie.

[Unreleased]: https://github.com/benoitdesnoyers/espn_fantasy_hockey/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/benoitdesnoyers/espn_fantasy_hockey/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/benoitdesnoyers/espn_fantasy_hockey/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/benoitdesnoyers/espn_fantasy_hockey/releases/tag/v0.2.0
