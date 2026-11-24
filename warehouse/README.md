# Men's sixes warehouse (`sixes.duckdb`)

This warehouse supports men's 6v6 projections for the Lexus Global Lacrosse Games (Dec 8–13 2026). It combines PLL 10v10, the PLL Championship Series, international sixes and the NLL in one database, with one ID per person.

The database was built offline by the data pipeline: scrapers, parsers and the warehouse builder. That pipeline and its raw scrape caches stay outside this repo. The app opens the file read-only. New GLG results do not change this file; the "GLG results update" Action merges them into the app's saved data (the Gist). Quality-check results are in `qa.checks` and shown on the Model & Data page.

## Sources

| Source | Coverage | Origin |
|---|---|---|
| PLL 10v10 | 2019–26, 334 games (regular season + playoffs) | PLL stats API box scores |
| PLL Championship Series | 2023–26, 34 games | PLL stats API box scores, including touches and possessions |
| PLL player bios | Every player listed 2021–27: country, DOB, college, position | PLL stats API player lists |
| International sixes | 175 men's games in 5 events: WL Pan-Am, Asia-Pacific and European 2026, PALA Cup 2025, EuroLax 2026 | World Lacrosse / PointBench game pages |
| NLL | Player-season stats for 2018-19 to 2025-26 (no 2020-21 season), regular season + playoffs | nll.com stats |
| GLG | Men's rosters for 4 nations × 13 players, plus the 7-game schedule | PLL GLG nation pages and federation announcements (`data/glg/README_glg.md`) |

## Tables

- **core.dim_player** — one row per person, keyed by `player_uid`.
  - The key is `PLL:<officialId>` when the person has a PLL record.
  - Otherwise it is `INTL:<nation>:<name>`, `NLL:<id>` or `GLG:<nation>:<name>`.
- **core.xwalk_player** — maps every source key to a `player_uid`, with the matching method and a confidence level.
- **fact.sixes_game / sixes_team_game / sixes_player_game** — the Championship Series and international sixes in one unit system.
  - `goals` counts every goal once. The GLG has no 2-point goals, so this is the unit to model.
  - `two_pt_goals` and `points` are kept only for the Championship Series.
  - A stat is NULL where the source doesn't record it or where we judged it unreliable; see the caveats below.
- **fact.pll10_player_game / pll10_team_game** — 10v10 box scores.
- **fact.nll_player_season** — NLL season lines, linked to `player_uid`.
- **mart.player_format_summary** — per player and format (`pll10`, `pll_cs`, `intl`):
  - games played and totals;
  - per-game rates;
  - `goal_share` and `assist_share` (the player's share of his team's goals).
- **mart.team_sixes_summary** — per team and event: goals for and against, shots, shooting %, possessions, goals per possession, turnovers.
- **mart.nll_player_summary** — NLL regular-season rates from 2022-23 onward.
- **mart.glg_roster_profile** — each GLG player with how they were linked and their data in every format.
- **src.*** — the cleaned per-source tables the facts are built from, kept for audit.

## Identity matching

- **PLL people** are matched by `officialId`, which is exact.
- **International players** are matched to the PLL only for the GLG nations. A match needs:
  - an exact or nickname-equivalent name; and
  - a PLL country code consistent with the nation: USA→USA, Canada→CAN, Haudenosaunee→USA/CAN/IRQ, Australia→AUS.
- **Players from other nations** are never matched to the PLL. This avoids false matches on common names.
- **PointBench spelling variants** within the same team and last name are merged when the first names are at least 0.8 similar (e.g. Obrigh/Olbrigh Tallchief).
- **NLL→PLL** matching uses the name only when that name is unique on both sides. The NLL data has no date of birth to confirm a match.
- **GLG roster** matching runs in this order: manual alias (`data/glg/manual_aliases.csv`), then PLL, then that nation's international identity, then NLL.
  - 49 of the 52 rostered players have history in at least one source.
  - Thomas Richards (AUS), Brayden Panting (AUS) and Saka Thompson (HAU, goalie) have none.

## Data caveats

1. **PLL shots on goal are about 1.5–2 per game higher than opponent saves plus goals**, in both 10v10 and Championship Series data. This is a PLL definition, not an error. Compute save % as saves / (saves + GA).
2. **PLL 10v10 `total_possessions` is not a real possession count** (it averages about 8.6 per team). Don't use it.
   - Championship Series possessions are real: 32.4 per team-game.
   - They are missing for the 2023 semifinals and final, and are stored as NULL there.
3. **Championship Series team turnovers are about 1.1 per game above the player total.** The difference is unassigned team turnovers such as shot-clock violations.
4. **The Championship Series had a 2-point arc** (about 3.3 two-point goals per team-game); the GLG does not. Use `goals` and the shot counts. Long-range shooting will be lower at the GLG.
5. **PointBench reliability varies by event** (`src.intl_event_reliability`):
   - Shots are trustworthy only in the Pan-Am and European events.
   - Saves are trustworthy in Pan-Am, European and Asia-Pacific.
   - Ground balls and caused turnovers are trustworthy only in Pan-Am and European.
   - The PALA Cup has a goal log only; player goals and assists are derived from it.
   - The assisted-goal rate depends on the scorekeeper: 0.24 at EuroLax up to 0.51 at the European event.
   - Untrustworthy values are stored as NULL in the fact tables.
6. **The PointBench player box disagrees with the goal log by one goal in 3 of 350 team-games.** Team totals come from the score and the goal log, which agree everywhere.
7. **Rosters differ by event.** International games are national teams. The Championship Series is PLL clubs with 2-point goals and longer rosters. Both are in the facts, labelled by `source`, `competition` and `team_level`.
8. **GLG data coverage by nation.** "Has data" means at least one game or season in that source; full counts are in `mart.glg_roster_profile`.

   | Nation | PLL 10v10 | Championship Series | International sixes | NLL | No data |
   |---|---|---|---|---|---|
   | USA | 13 | 6 | 9 | 6 | 0 |
   | Canada | 13 | 0 | 4 | 12 | 0 |
   | Haudenosaunee | 5 | 1 | 6 | 7 | 1 |
   | Australia | 0 | 0 | 11 | 0 | 2 |

   - **Canada:** none of the 13 has played the Championship Series. It runs in February, mid-NLL season, so NLL players skip it. Canada's sixes evidence is the Pan-Am event (4 players). Its priors have to come from 10v10 and NLL.
   - **Australia:** the only data is the 2026 Asia-Pacific event, 5 games for 11 players. Australia never played the Americas teams, so its strength relative to them can't be measured from results.
9. **NLL:** 2021-22 Albany FireWolves player goals sum 10 short of the team total; the other 95 team-seasons match exactly.
