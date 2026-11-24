# Men's sixes — data audit, EDA and method tests (2026-11-24)

The scripts are in `eda/` and `scripts/eda_player_bridge.py`. All tests are out of sample: each target is predicted only from data available before it.

## 1. Data audit

**Fixed:** 10v10 data only started in 2022.
- I added 2019–2021 (99 games) through the sixes-data workflow. The PLL 10v10 data now covers 2019–26: 334 games and 12,482 player-games.
- Player sums still reconcile with team totals.
- Touches and assist opportunities were not tracked before 2022, so they are NULL there.

**Remaining gaps.** None of these can be filled from the data that exists:

| Gap | Players / scope |
|---|---|
| No data in any source | 3 GLG players: Richards (AUS), Panting (AUS), Saka Thompson (HAU, goalie) |
| NLL only | Bucktooth and Tarbell (HAU) |
| No Championship Series games | All of Canada (the CS runs mid-NLL season) |
| Sixes data only from Asia-Pacific (5 games) | Australia |
| International events | 2025–26 only; PointBench has no earlier men's sixes championships |
| NLL | Season totals only, no per-game box scores |

## 2. How the format plays (Championship Series possession data)

- **Possessions:** 32.4 per team-game (sd 4.2). They are time-based, not strictly alternating: a team gets fewer possessions when its opponent scores more (r = −0.47).
- **Efficiency drives scoring.** Goals per possession average 0.59. Its variance is about 3× the variance of possession count.
- **Games are close.** 41% are decided by 2 goals or fewer, and 21% go to overtime. There is no home advantage (18.97 vs 18.74 goals).
- **2-point goals** were 17% of Championship Series goals, from 25% of shots, at a 28% conversion rate against 46% for 1-point shots. The GLG has no arc.
- **Dispersion** (Championship Series):
  - A team's goal count varies less than Poisson: variance/mean ≈ 0.80.
  - The two teams' scores are slightly positively correlated: ρ ≈ +0.16.
  - So margins are tighter than independent Poisson scores would give.
- **Scoring environment is the biggest unknown:**

  | Environment | Goals per game |
  |---|---|
  | Championship Series | 37.7 |
  | International top-4 vs top-4 | 28–32 |
  | Pan-Am USA–Canada | 23 |
  | Pan-Am Canada–Haudenosaunee | 28 |

  The GLG has PLL players and the PLL venue, but World Lacrosse rules, no 2-point goals and national-team defences.
- **Assists per goal** are scorekeeper-dependent: 0.43 at the Championship Series (PLL crew), 0.25–0.51 at international events, 0.50–0.58 in 10v10. Use 0.43 for the GLG, because the PLL's crew will keep the stats.

## 3. Signal tests

- **10v10 → sixes, player level.** The test predicts each Championship Series year using only earlier data (Poisson deviance, lower is better):

  | Method | Goals | Points |
  |---|---|---|
  | Position mean (baseline) | 1.301 | 1.491 |
  | Prior sixes history | 1.213 | 1.359 |
  | 10v10 × position ratio | 1.245 | 1.380 |
  | 10v10 Poisson GLM | 1.208 | 1.367 |
  | **GLM prior + Bayesian sixes update** | **1.173** | **1.309** |

  - For players with no prior sixes games, the GLM beats the baseline by 11% (1.239 vs 1.398).
  - Stars keep their separation: the top decile was projected at 3.48 goals per game and scored 3.54.
  - How fast old seasons are discounted barely matters (half-life 0.7 vs 1.5 seasons).
- **Distribution:** Poisson is calibrated for player goals and points. P(G≥2) was predicted 0.519 against 0.522 actual; P(Pts≥6) 0.104 against 0.108. A negative binomial is worse.
- **Sixes vs 10v10 by position**, for the same players:

  | Position | Points per game, sixes ÷ 10v10 |
  |---|---|
  | Attack | 1.5× |
  | Midfield | 2.4× |
  | Defence | 3.2× |
  | Defensive midfield | 5.0× |

  Position must be in the model.
- **Share model beats direct rates.** Player goals as team μ × share gives deviance 1.156 with league-mean team μ, against 1.175 for direct rates, and 1.075 with actual team goals.
- **PLL → international:** a player's 10v10 goals per game predicts his share of team goals at the Pan-Am event (r = 0.75 for the USA, 0.91 for Canada).
- **NLL → field:** NLL points per game correlate 0.80 with PLL points per game. NLL adds significant information on top of the prior PLL season (R² 0.784 → 0.808). For players with no PLL history it predicts the first PLL season (r = 0.63).
- **Goalies:** there is no carry-over (10v10 save % vs CS save %, r = −0.08) and no within-event stability (split-half r = 0.09). Treat goalies as roughly league average.
- **Team level, Championship Series:**
  - Roster-sum margins correlate only 0.23 with actual margins. The fitted slope is 0.31 (se 0.25), so shrink them about 70%.
  - Championship Series rosters are near-parity all-star groups. GLG talent gaps are much larger (2023 Worlds: USA 12–3 and 11–4 over Australia).
- **Team level, international:** a team-results model shaped by possessions (Binomial(40, sigmoid)) beats Poisson on totals (MAE 4.8 vs 5.4). Win-probability Brier is 0.136 against 0.25 for a coin flip (`men_game_grid.py`).
- **National-team order** from the 2023 Worlds is USA > Canada > Haudenosaunee > Australia. Australia lost all five of its games against the other three, by 3 to 9 goals.

## 4. Recommended projection method

1. **Player share.** Prior share = the 10v10 GLM rate (an NLL-based prior when PLL history is thin), converted to a share of the 13-man GLG roster. It is then Bayesian-updated with sixes shares from the CS and international events (k ≈ 5–12 games). Goalies are near 0.
2. **Team expected goals** = environment base × relative strength.
   - Strength combines the roster-sum offence (shrunk about 70%) with a nation results prior: 2023 Worlds, Pan-Am 2026, and the Asia-Pacific → Japan → Haudenosaunee chain for Australia.
   - Goalie quality is ignored.
3. **Game simulation:** under-dispersed team goals (φ ≈ 0.8) with ρ ≈ +0.16 between the two teams. Overtime is 3-minute periods until someone leads. This gives spread, total and win probability.
4. **Props:** player goals = team goals (per simulation) × share; Poisson-calibrated. Assists = 0.43 assists per goal × assist share. Points = goals + assists (1 point each, no 2-pointers).
5. **Live updating:** after each GLG session, update the environment level (the biggest uncertainty), then team strengths, then player shares. Only 4 group games come before the semifinals and final.
