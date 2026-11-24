# Calibration review (2026-11-24): USA strength, Traynor, rosters and roles, small samples

## Why the USA was too strong
- **Roster talent is level:** USA 31.0, Canada 30.7. The USA's edge came entirely from results.
- **USA results** included blowouts of weak Pan-Am teams (33–4 Chile, 28–12 Jamaica, 25–10 Puerto Rico). Those say little about elite matchups.
- **Canada's Pan-Am squad** had only 4 of 13 GLG players (16% of roster talent). Its results were rightly discounted, but the shrinkage then pulled Canada toward the all-teams average instead of toward its talent.
- **Fixes:**
  - Games are down-weighted by rating gap: weight exp(−max(0, gap − 0.3)/0.5).
  - Results now move a nation off its talent rating only by credibility = effective games ÷ (effective games + 4).
- **USA vs Canada:** 73% → **61%**. Tournament: USA 58%, Canada 35%.

## Matt Traynor
- **His 10v10 rate is real:** 1.65 goals and 6 shots per game over 23 games, among the most for any PLL midfielder.
- **The midfielder lift is measured, not assumed.** Across the Championship Series, high-volume midfielders produce at least what the regression predicts (top tier: 3.00 predicted, 3.24 actual).
- **The excess was three hot 2026 Championship Series games** (6.3 goals per game). The pro sixes-evidence weight is raised from 8 to 12 pseudo-games, the conservative end of what the backtest chose.
- **Result:** he remains the top projected scorer (talent 4.46 vs Dhane Smith 4.29) and is top-goalscorer favourite at about 27%. Supported, but a small-sample-driven edge.

## Roles and rosters
- **Listed position → role:** a defender or SSDM who scores above his position's 95th percentile in the training data is rated as the next role up (D → SSDM → M), and inputs are capped at the training range.
  - Before this, Zach Currier, an SSDM at 0.55 goals per game (twice the training maximum), was being extrapolated to 3.7.
- **Usage concentration:** on weak teams the top scorer takes 31.5% of team goals, on strong teams 19.5%.
  - Shares earned on a lineup weaker than the player's GLG team are flattened (s → s^β, renormalised).
  - β = (lineup talent ÷ GLG roster talent)^1.5, kept between 0.65 and 1.
- **Continuity with 2025–26 international squads:**

  | Nation | GLG players at the event | GLG roster talent present |
  |---|---|---|
  | Australia | 11 of 13 | 82% |
  | USA | 9 of 13 | 70% |
  | Haudenosaunee | 2–5 of 13 | 20–36% |
  | Canada | 4 of 13 | 16% |

  The full player role table is on the Teams & Rosters page.

## Small samples
- **International shares within an event are stable.** The split-half test is best at k ≈ 1–2 pseudo-games, so non-pros use k = 3 (was 4).
- **Pros keep k = 12**, because their sixes evidence crosses formats and contexts.
- **Nation results:** credibility weighting as above.
- **The 2023 Worlds** are weighted 1.0 at an assumed 60% continuity. They are the only full-strength evidence and the only link between Australia and the Americas.

## Player tournament review vs national-team sixes evidence (2026-11-24)
**Comparison sets:** the two national squads closest to their GLG rosters.

| | USA at Pan-Am 2026 | Australia at Asia-Pacific 2026 |
|---|---|---|
| GLG players at the event | 9 of 13 | 11 of 13 |
| Share of GLG roster talent present | 70% | 82% |

Shares were compared rather than goals, because those opponents were much weaker than GLG opponents.

**Before:**
- Rank order was right (USA r 0.61, Australia 0.98).
- Australia's shares were far too flat: true spread 0.039 vs 0.022 projected; top share 18.1% observed vs 12.5% projected.
- The USA's Pan-Am scorers were under-projected: Weisshaar and Mackesy 14.3% observed vs about 10.5%, Kirst 12.2% vs 7.0%.

**Causes and fixes:**
1. **Usage flattening was being applied to pro national squads.** It is now restricted to development-style lineups (pro fraction < 0.5 and GLG overlap < 0.5, i.e. Haudenosaunee). Renormalising shares over the GLG roster already accounts for new players.
2. **National-team sixes evidence for pros now has its own weight** (k = 6, was 12). It is the most relevant context: same team, format and role.
3. **Non-pro shrinkage lowered to k = 1.5**, in line with the split-half optimum of 1–2.
4. **Player rating uncertainty is now simulated.**
   - The CS backtest puts it at log-sd 0.19 for players with 10v10 data and 0.55 without.
   - Non-pros use 0.35, because international evidence narrows it.
   - Each player's uncertainty is scaled by his data volume, between 0.7× and 1.4×.
   - One draw is made per player per simulated tournament, so it carries through all his games. This widens futures and tournament props.

**After:**
- Spread of shares: Australia 0.034 vs 0.039 true; USA 0.025 vs 0.026.
- Correlation with observed shares: USA 0.77, Australia 0.98.

**Top goalscorer:**

| Player | Probability |
|---|---|
| Traynor | 24.7% |
| Dhane Smith | 13.5% |
| Weisshaar | 7.6% |
| Chris Kavanagh | 6.8% |
| Poitras | 6.7% |
| Sunday | 6.6% |

- **Traynor's price is fragile.** He has no national-team sixes evidence; his rating rests on 23 PLL games and 3 CS games. Sensitivity: rating ×0.9 → 16.9%; ×0.8 → 9.6%.
- His edge comes from three things: the top USA rating, the highest-scoring team, and up to 4 games (the USA reaches the final 85% of the time).
- To price him more conservatively, use a goal multiplier override.

## National-team role for players with no national sixes games (2026-11-24)
- **Club ratings predict national-team scoring shares only moderately.** Across the 18 pros at Pan-Am 2026: slope 0.61 (se 0.32), correlation 0.42. Club-to-club sixes gives slope 0.87.
- **Big USA misses:**
  - McAdorey: 14.5% implied → 7.1% actual.
  - Campbell: 12.5% → 7.1%.
  - Kirst: 7.5% → 12.2%.
- **Change:**
  - Every GLG team's priors are pulled 39% toward the team mean (nat_role_reliability 0.61). National-team sixes games then update them.
  - Pros with no national sixes games get rating sd 0.31: rating error 0.19 combined with role uncertainty 0.25, measured from the Pan-Am residuals.
- **Traynor** (no national sixes games; 3 club CS games):
  - Goal share 14.6% → 12.7%.
  - Top goalscorer 24.7% → 16.6%.
  - Top points 27.1% → 19.0%.
- **Newcomer usage setting: removed.** It was a judgement call with no data behind it, and the user asked for no subjective adjustments.


## Usage / depth chart (data-backed), 2026-11-24
- **No source records minutes or time on field.**
  - The PLL play-by-play has closest-defender and turnover-attribution fields, but they are empty in every game.
  - The NLL and PointBench have none.
- **Usage proxy:** club touch share (time on the ball), from PLL box scores 2024–26.
- **Tests:**
  - **Championship Series** (n = 146 player-events): sixes goal share is best explained by 0.754 × rating-share deviation + 0.449 × touch-share deviation. R² 0.607 → 0.624; touch-share p = 0.013.
    - Shot share adds less (p = 0.11).
    - Adding touches as a per-game GLM feature changes deviance by under 1%.
  - **Pan-Am** (n = 16 pros): club shot share predicts national-team goal share better than the scoring rating (R² 0.36 and 0.28 for touch share, vs 0.21).
- **Model:**
  - Share priors use the CS combination, then the national-team factor ×0.62 (Pan-Am attenuation relative to CS), then each player's national-team games update them.
  - Players with no touch data use the rating part only.
- **Effect:** Traynor's club touch share is 8.4% (a finisher), against 13–14% for Chris Kavanagh, Mackesy, Sowers and Pat Kavanagh.
  - Traynor top points 12.7%, top goalscorer 11.3%.
  - Chris Kavanagh 11.6% / 10.7%.
  - Team odds unchanged.
- **Depth Chart page** (`app/views/depth.py`): tiers by projected point share, club usage, shot share, GB+CT per game, national sixes games and share, CS games, projected shares. Tiers and GB+CT are display only.

## Depth-chart usage system (2026-11-24)
**Tests** (CS, 142 player-events, deviations within team):
- **Sixes usage** (CS touch share) is explained by rating share (0.69, p < 0.001) and club touch share (0.10). R² 0.53.
- **Experience and age add nothing:** log career PLL games p = 0.76; age p = 0.26.
  - For goal share: experience p = 0.80, age p = 0.22.
  - Pan-Am agrees: veterans were not used more (Kirst over-performed; McAdorey and Campbell under-performed).
- **Seniority is not supported**, so it is not modelled.
- **Actual usage is very valuable:** goal share = 0.548 × rating dev + 0.573 × usage dev, R² 0.705 vs 0.62 without usage.

**System:**
- **Default depth chart:** expected usage = 0.69 × rating share + 0.10 × club touch share, which sets the rank. At default ranks the projections are unchanged.
- **Usage by rank** (CS curve, 16 team-events): 18.2, 15.0, 13.4, 11.8, 10.3, 8.8, 7.8, 6.2, 4.2, 2.8, 2.0%.
- **Edits:** Δshare = 0.5 × 0.573 × (curve[new rank] − curve[model rank]), then renormalised within the team. The 0.5 is because an assumed rank is less reliable than observed usage.
- **Example:** Traynor, model rank 3 → 6 takes his goal share from 11.8% to 10.5%. The share moves to Sowers, Weisshaar and Pat Kavanagh.
- **Traynor's only sixes usage evidence:** Atlas, CS 2026, usage rank 2 (15.4% of touches).
- **Storage:** `overrides.json → depth: {nation: [uid order]}`. Edit on the Depth Chart page.

## 2023 Worlds continuity measured from rosters (2026-11-24)
The assumed 60% continuity is replaced by real overlap between each nation's 2023 Worlds roster and its GLG roster. Rosters are in `data/glg/worlds_2023_rosters.csv`; sources are in `README_worlds2023.md`.

| Nation | GLG field players on the 2023 roster | Share of GLG talent | Players |
|---|---|---|---|
| USA | 2 of 11 | 14% | Sowers, Logan |
| Canada | 6 of 11 | 55% | Berg, Byrne, Petterson, Rogers, Currier, Dhane Smith |
| Australia | 3 of 11 | 30% | Baker, Panting, Walker |
| Haudenosaunee | 2 known | ≥ 19% | Lyle Thompson, Piseno |

Haudenosaunee's 2023 roster could not be fully verified (5 of 23 names), so the verified minimum is used rather than an assumption.

**Result:**
- **The USA's 2023 dominance came mostly from different players.**
- **USA vs Canada:** 60% → **54%**.
- **Champion:** USA 49.7%, Canada 43.1%, Haudenosaunee 4.7%, Australia 2.5%.
- **The remaining USA edge** comes from 2025–26 results: Pan-Am, where the USA lineup had 70% GLG continuity and beat Canada 12–11.


## World Lacrosse Sixes rule book review (2026-11-24)
- **New and material: the 12-player game roster** (Rule 3.1.1).
  - GLG teams list 13, so 1 sits per game.
  - Data: national teams dressed the full 12 in Pan-Am, Asia-Pacific and European games. The USA and Canada dressed 2 goalies every Pan-Am game.
  - Model: 10 field players dressed per game; the 11th on the depth chart sits by default; per-game override on Game Center → Lineups.
  - Effect: the dressed players' shares rise by the scratched player's share (about 4%, split among the 10). The scratched player gets 0.
- **Overtime** (Rule 5.1.4): full 3-minute stopped-time periods until a lead. This matches the model.
  - Stopped-clock scoring rate vs running clock in international goal logs: 1.07 overall, 0.62 in close games, so it was not changed.
- **Confirmed as already modelled:** 4 × 8 running clock (stopped in the last 2 minutes), 30-second shot clock with resets, 10-second count, goalie restart after goals, draws to start periods, 30-second minors and 1-minute majors, no 2-point goals.
- **Not in the rule book:** semifinal seeding.
