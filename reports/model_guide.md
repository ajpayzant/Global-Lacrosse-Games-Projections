# GLG Men's Sixes Projections: how the model and data work

This guide is current as of 2026-11-24 and matches `glg/engine.py`. Everything is fitted or measured from data unless a line says otherwise.

## 0. Game rules (World Lacrosse Sixes Rule Book 2026-28, Feb 2026; confirmed as the GLG rules)
- **Format:**
  - 6 players a side: 5 field players and 1 goalkeeper (Rule 3.1.3).
  - Four 8-minute quarters on a running clock. All clocks stop on whistles in the last 2 minutes of Q4 (Rules 5.1.1, 5.2.2).
  - The model's 8 × 4 timing and CS/international calibration already reflect this.
- **Game roster: at most 12 players per game, including goalkeeper(s)**, listed 20 minutes before the game (Rules 3.1.1–3.1.2).
  - GLG rosters have 13 (11 field, 2 G), so **one player sits each game**.
  - **Default dressing: 10 field + 2 G, with the field player ranked 11th on the Depth Chart sitting.** The USA and Canada dressed 12 with 2 goalies in every Pan-Am game.
  - Per-game scratches can be set in Game Center → Lineups.
- **Overtime:** full 3-minute periods of stopped time, 2 minutes apart, repeated until a team leads at the end of a period. Not sudden death (Rule 5.1.4).
  - The model simulates exactly this.
  - Stopped-clock scoring was checked in the international goal logs, minutes 30–32 vs 0–30: ratio 1.07 overall, lower in close games. So no OT rate adjustment is made.
- **Restarts:**
  - Each quarter and OT period starts with a center draw (Rule 6.4.1).
  - After a goal, the goalkeeper restarts (Rule 6.5.7). There are no faceoffs after goals, so faceoff specialists matter little.
- **Shot clock:** 30 seconds. It resets on a shot hitting the pipe or the goalkeeper in the crease, and on any change of possession (Rule 5.3.1). There is a 10-second count to cross midfield (Rule 6.9).
- **Fouls:**
  - Minor fouls: possession, or 30 seconds if the opponent had the ball (Rule 7.1.2).
  - Majors: 1 minute.
  - Same as the international data the model is fitted on.
- **Timeouts:** one per team per half, 60 seconds (Rule 6.10.4).
- **Scoring:** no 2-point goals; every goal is worth 1.

## 1. Data used

| Source | Coverage | Used for |
|---|---|---|
| **PLL 10v10** box scores | 2019–2026, 334 games, 12,482 player-games (regular season + playoffs; touches tracked from 2022) | Player priors: per-game rates, position, club usage (touch share) |
| **PLL Championship Series** (6v6) | 2023–2026, 34 games (PLL API, full box scores including touches and possessions) | Training the 10v10→sixes model; sixes evidence for players; the usage model; dispersion calibration |
| **International sixes** (World Lacrosse via PointBench) | 175 men's games, 2025–26: Pan-Am, Asia-Pacific, European, PALA Cup, EuroLax | Nation results ratings; non-pro player ratings; national-team usage |
| **NLL** season stats | 2018-19 to 2025-26, 3,532 player-season rows (nll.com) | Priors for players thin on PLL data, via an NLL→10v10 bridge fitted on 84 players with both |
| **2023 World Championship** (10v10) | 15 games among the GLG nations (+ Japan as the link to Asia-Pacific), plus 2023 rosters (USA, CAN, AUS 23 each; HAU 5 of 23 verifiable) | The only full-strength results linking Australia to the Americas, weighted by real roster overlap |
| **GLG rosters and schedule** | 4 nations × 13 players, 7 men's games | Projection targets |
| **Live GLG results** | GitHub Action "GLG results update" scrapes completed games from the PLL stats API nightly (or on demand); manual entry on Results & Grading also works | Live updating of environment, team ratings and player shares |

- **Identity:** each person has one ID across sources: PLL official ID, else a nation-specific international, NLL or GLG ID.
- **Name matching:** exact, nickname or prefix match, plus a nationality check. International and NLL records for the same person are merged.
- **Data quality:** checks are in the Data & coverage tab.

**Not used** (tested or unavailable):
- **Minutes or time on field:** they exist in no source. The PLL play-by-play has closest-defender and turnover-attribution fields, but they are empty.
- **Goalie quality:** no measurable sixes signal (10v10 → CS save % r = −0.08; split-half r = 0.09).
- **Experience and age:** not significant for sixes usage or scoring (p = 0.76 and 0.26).
- **College and junior stats:** collected during research, but there is no data to calibrate them, so they are not used.
- **Betting markets.**

## 2. Player model
All player ratings are **goals (and assists) per game at Championship Series scale**, about 18.9 team goals per game.

1. **Pro prior.** A Poisson GLM is trained on 676 CS player-games.
   - Inputs: each player's 10v10 rates (goals, assists, shots, ground balls, turnovers), decayed with a 1-season half-life and shrunk to the position mean, plus his role.
   - **Role, not listed position:** a defender or SSDM who scores above his position's 95th percentile is rated as the next role up (D → SSDM → M). Inputs are capped at the training range.
   - **NLL bridge:** players with NLL data get NLL rates converted to 10v10 equivalents and blended with their PLL rates, weighted by sample size.
2. **No 2-point arc at the GLG.** Players whose goals leaned on 2-pointers are discounted by 0.5 × (2-point share − 10%), between 0.85 and 1.05. In practice this is Piseno, Logan and Campbell.
3. **Championship Series update.** Bayesian, k = 12 pseudo-games. The CS backtest chose 8–12; 12 is the conservative end.
4. **Usage (the depth-chart signal).** Within each team, prior share deviation = 0.754 × rating-share deviation + 0.449 × club touch-share deviation.
   - Fitted on CS, n = 146: R² 0.607 → 0.624; touch p = 0.013.
   - At Pan-Am, club usage predicted national-team share better than the rating did.
5. **National-team role.** The combined club signal is shrunk ×0.62 toward the team average. Pan-Am pros give slope 0.61, against 0.98 for CS.
6. **National-team sixes evidence.**
   - Pros: k = 6.
   - Non-pros: k = 1.5, because international shares are stable (the split-half optimum is 1–2).
   - **International evidence is put on the talent scale** as the player's share of team goals × the talent of the lineup he played in (section 3). A development squad's shares are worth a development squad's talent.
   - **Development-squad usage flattening:** a weak team's top scorer takes 31.5% of team goals, against 19.5% on strong teams.
     - Shares from lineups with few pros and low GLG overlap are flattened: s → s^β, with β = (lineup talent ÷ GLG talent)^1.5, between 0.65 and 1.
     - Currently this applies only to Haudenosaunee (β 0.81).
7. **Non-pros with no data** get their nation's non-pro average.
8. **Live GLG box scores** update player ratings at 1 pseudo-game per GLG game.
9. **Shares.** Goal and assist shares = each active field player's rating ÷ the team total. Goalies get 0.

## 3. Team model
- **Roster talent** = the sum of active field players' goal ratings. The anchor (a = 2.45) comes from the USA and Canada Pan-Am lineups, which were almost all pros; it converts results ratings into talent units.
- **Results rating:** a Poisson attack/defence model.
  - Inputs: 2025–26 international sixes (one scoring intercept) and the 2023 Worlds (own intercept, weight 1.0, no time decay).
  - Every game is weighted by **lineup continuity** (the share of the GLG roster's talent that played) for both teams.
  - **2023 Worlds continuity comes from real rosters:** USA 14%, CAN 55%, AUS 30%, HAU ≥ 19% (partial roster, verified minimum).
  - Blowouts are down-weighted: exp(−max(0, gap − 0.3) ÷ 0.5).
  - Time half-life: 365 days.
- **Combining the two:**
  - Attack = 0.85 × log(roster talent ÷ mean) + credibility × (results attack − talent attack).
  - Defence = 0.25 × talent term + credibility × (results defence − talent term).
  - Credibility = effective results games ÷ (games + 4). Currently USA 0.15, CAN 0.17, HAU 0.24, AUS 0.32.
  - Results move ratings only as far as their relevant sample supports.
- **Goalies** are treated as league average.

## 4. Environment, simulation and players
- **Scoring environment:** expected goals per team, prior 16.0. Championship Series ≈ 18.9 (with a 2-point arc); elite international games ≈ 14–16. It updates with completed GLG games at a prior weight of 6 team-games. Its uncertainty (±10% log-sd) narrows as games are played.
- **Game simulation:** 20,000 runs per game; 40,000 for the tournament.
  - Expected goals = environment × exp(attack − opponent defence). Each run draws the environment and both team strengths (±10% log-sd).
  - A shared pace factor plus under-dispersed team counts are calibrated to the CS: margin sd 5.0, total sd 5.9, score correlation +0.16.
  - Overtime follows World Lacrosse rules: 3-minute periods until a team leads at the end of one.
- **Player rating uncertainty.** Each run draws each player's true level once, so it carries through all his games in a simulated tournament. Log-sd, measured in the CS backtest:
  - 0.19 for pros with national-team sixes games;
  - 0.31 for pros without (rating 0.19 combined with national role 0.25);
  - 0.35 for non-pros;
  - all scaled 0.7–1.4× by data volume.
- **Props:** simulated team goals are split by goal share. Assists = 0.43 per goal (the PLL stat-crew rate), split by assist share. Points = goals + assists (no 2-pointers). Poisson-type tails were calibrated in the CS backtest.
- **Tournament:** remaining pool games, then seeding 1v4 / 2v3 on pool wins → goal difference → goals for. Completed games, and semifinal or final matchups entered on Results & Grading, are fixed at their real values. **The seeding rule is assumed; it hasn't been published.** Then semis and the final; there is no third-place game.

## 5. Depth chart and usage override
- **Default depth chart:** expected sixes usage = 0.69 × rating share + 0.10 × club touch share. This is the fitted CS usage model; R² 0.53.
- **Re-ranking a player:** Δshare = 0.5 × 0.573 × (usage at the new rank − usage at the model rank), then renormalised within the team.
  - The usage-by-rank curve is measured from 16 CS team-events: 18.2%, 15.0%, 13.4%, 11.8% … 2.0%.
  - 0.573 is the measured value of usage for scoring share.
  - The 0.5 weight is because an assumed rank is less reliable than observed usage.
- **Usage override:** set a player's expected usage share directly. Δshare = 0.573 × (your value − the model's), at full weight.
- **Defaults leave projections unchanged.** Edits are saved in `data/glg/overrides.json`.

## 6. Pricing
- **True probability** comes from the simulation. The fair price is 1/p.
- **Spreads:** quoted with the favourite negative and the underdog positive, and never inside ±1.5. A game cannot end tied (overtime runs until a lead), so ±0.5 is just the moneyline.
  - The main line is the line of 1.5 or more, from the favourite's side, whose cover probability is closest to 50%.
- **Margined prices** use the power method: book p = p^k, with k chosen so each market sums to 1 + margin. This puts most of the margin on longshots.
  - Defaults: game lines 4.5%, props 8% (two-way), team futures 15%, player futures 30%. All are in the sidebar.
  - Outright prices are capped at a maximum price (default +25,000).
  - **True probabilities are never altered by pricing.**

## 7. Overrides and saved data
Every override applies everywhere and stays until you clear it. Overrides, scores, box scores and snapshots are saved through `glg/store.py`: local files when running locally, a private GitHub Gist on Streamlit Cloud. The sidebar shows which is active.

| Override | Where |
|---|---|
| Environment | Ratings & Overrides |
| Team attack and defence (log units) | Ratings & Overrides |
| Player out, goal/assist multipliers, absolute rates | Ratings & Overrides |
| Game-level expected goals | Ratings & Overrides |
| Depth chart, usage override | Depth Chart |

## 8. Known limits
- Haudenosaunee's 2023 roster is only partly verified, so their Worlds games count at a verified minimum overlap.
- Three players have no data in any source (Richards and Panting, AUS; Saka Thompson, HAU goalie). They are rated at the nation's non-pro average, with wide uncertainty.
- The scoring environment for a PLL-run, World Lacrosse-rules national tournament has no direct precedent. It is the largest source of uncertainty in totals until GLG games are entered.
- **Still unknown:**
  - The semifinal seeding rule (1v4 / 2v3 is assumed).
  - Who actually sits each game. The default is the bottom of the depth chart; set the real lineups in Game Center → Lineups.
- The automated results update needs the repository secrets in the README; the PLL API only publishes GLG games once they start.
