"""GLG men's sixes projection engine (v2: talent model).

Players and teams live on one talent scale (Championship Series goals per game):
  * pros (PLL 10v10 / NLL / Championship Series) are rated from pro data (GLM prior + CS update);
  * USA & Canada Pan-Am lineups (~all pros) calibrate results-rating units to talent units;
  * every nation's international results imply how much talent its past lineups had, so a
    development squad's scoring shares are worth a development squad's talent;
  * team strength = talent of the actual GLG roster (attack), results defence adjusted for the
    roster's talent vs the lineups behind those results. Goalies: league average (no signal).
Simulation: environment x strengths, shared pace + under-dispersed counts (CS-calibrated),
WL overtime; player goals/assists allocated from simulated team goals by talent share.
Full description: reports/model_guide.md (shown on the Model & Data page).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
WH = ROOT / "warehouse" / "sixes.duckdb"
GLG = ROOT / "data" / "glg"
NATIONS = ["USA", "Canada", "Haudenosaunee", "Australia"]
ALIAS = {"United States": "USA", "US": "USA", "Team USA": "USA"}
POS = {"A": "A", "M": "M", "SSDM": "SSDM", "D": "D", "LSM": "D", "FO": "FO", "G": "G"}
NLL_POS = {"F": "A", "T": "M", "D": "D", "G": "G"}
STATS = ["g", "a", "sh", "gb", "tov"]
# average share of team touches by within-team usage rank, PLL Championship Series sixes 2023-26 (16 team-events)
DEPTH_CURVE = [0.182, 0.150, 0.134, 0.118, 0.103, 0.088, 0.078, 0.062, 0.042, 0.028, 0.020, 0.012]


@dataclass
class Settings:
    env_goals_prior: float = 16.0      # expected goals per team per GLG game before any GLG data
    env_prior_games: float = 6.0       # strength of that prior in team-games
    env_sd: float = 0.10               # log-sd of environment uncertainty (pre-tournament)
    strength_sd: float = 0.10          # log-sd of team strength uncertainty
    talent_elasticity: float = 0.85    # log team goals per log team talent (attack)
    two_pt_adj: float = 0.5            # GLG has no 2pt arc: discount talent by this x (player's 2pt goal share - 0.10)
    k_nonpro: float = 1.5              # non-pros: intl shares are stable (split-half best k~1-2), so light shrinkage
    usage_coef_rating: float = 0.754   # CS share model (n=146, R2 .624): share dev = .754 x rating-share dev
    usage_coef_touch: float = 0.449    #   + .449 x club touch-share dev (p=.013) -> data-backed "depth chart" usage
    dressed_field: int = 10            # WL Rule 3.1.1: max 12 per game incl. goalkeeper(s); USA/CAN dressed 2 G at Pan-Am
                                       # every game -> 10 field players; GLG rosters have 11 -> 1 field player sits per game
    usage_value: float = 0.573         # goal-share dev per unit of actual sixes usage-share dev (CS, n=142, R2 .705)
    depth_weight: float = 0.5          # an assumed depth-chart rank counts half as much as observed usage
    nat_role_reliability: float = 0.62 # national-team context: Pan-Am slope 0.61 on rating vs CS 0.98 -> extra x0.62
    rating_sd_no_nat: float = 0.31     # pros with NO national-team sixes games: rating 0.19 (+) role 0.25 uncertainty
    rating_sd_pro: float = 0.19        # player rating error (log-sd) for players with pro data (CS backtest)
    rating_sd_nonpro: float = 0.35     # non-pros (0.55 with no data in the backtest; intl evidence narrows it)
    k_intl_pro: float = 6.0            # pros: national-team sixes evidence (same team, format, role) vs pro prior
    k_results: float = 4.0             # credibility: results move a nation off its talent rating by n_eff/(n_eff + k)
    mismatch_scale: float = 0.5        # results games are down-weighted by exp(-max(0, rating gap - 0.3) / scale)
    usage_power: float = 1.5           # dev-squad usage flattening beta = (lineup talent / GLG talent)^power (HAU only)
    def_talent: float = 0.25           # defence also improves with roster talent (everyone plays both ways)
    worlds_continuity: float = 0.6     # FALLBACK only, used if data/glg/worlds_2023_rosters.csv lacks a nation
    hl_seasons: float = 1.0            # 10v10 season half-life
    k_update: float = 12.0             # pseudo-games for Bayesian updates of player rates (CS backtest picked 8-12; conservative end)
    k_nll: float = 8.0                 # pseudo-games weight of the NLL-derived 10v10 estimate
    worlds_weight: float = 1.0         # weight of 2023 World Championship games (only full-strength, cross-continent evidence)
    results_hl_days: float = 365.0
    assists_per_goal: float = 0.43
    phi_inner: float = 0.67            # inner team-count dispersion (with pace sd -> phi~0.8, rho~0.16)
    pace_sd: float = 0.082
    n_sims: int = 20000
    seed: int = 7
    overrides: dict = field(default_factory=dict)
    # overrides schema (all optional):
    #   env_goals: float                       force expected goals/team
    #   team:   {nation: {"att": +log, "def": +log}}
    #   player: {uid: {"out": bool, "g_mult": x, "a_mult": x, "g_rate": abs, "a_rate": abs}}
    #   game:   {game_number: {"home_mu": goals, "away_mu": goals}}


def q(con, s):
    return con.execute(s).df()


# ----------------------------------------------------------------------------- player model
class PlayerModel:
    def __init__(self, con, st: Settings):
        self.con, self.st = con, st
        d = q(con, "select player_uid, position from core.dim_player where player_uid like 'PLL:%'")
        self.pos_of = d.set_index("player_uid").position.map(POS).fillna("M")
        self.t10 = q(con, """select 'PLL:'||player_id as player_uid, season, count(*) gp, sum(goals) g, sum(assists) a,
                    sum(shots) sh, sum(ground_balls) gb, sum(turnovers) tov from fact.pll10_player_game group by 1,2""")
        self.cs = q(con, """select p.player_uid, year(p.date) y, p.position cs_pos, p.goals g, p.assists a
                    from fact.sixes_player_game p where p.source='pll_cs'""")

    def prior10(self, year, m=4.0):
        d = self.t10[self.t10.season < year].copy()
        d["w"] = 0.5 ** ((year - 1 - d.season) / self.st.hl_seasons)
        agg = d.assign(**{f"w_{s}": d.w * d[s] for s in STATS + ["gp"]}).groupby("player_uid")[[f"w_{s}" for s in STATS + ["gp"]]].sum()
        agg["n10"] = d.groupby("player_uid").gp.sum()
        agg["pos"] = agg.index.map(self.pos_of).fillna("M")
        self.pos_mean = {}
        for s in STATS:
            pm = agg.groupby("pos")[f"w_{s}"].transform("sum") / agg.groupby("pos").w_gp.transform("sum")
            self.pos_mean[s] = (agg.groupby("pos")[f"w_{s}"].sum() / agg.groupby("pos").w_gp.sum())
            agg[f"r_{s}"] = (agg[f"w_{s}"] + m * pm) / (agg.w_gp + m)
        return agg

    @staticmethod
    def X(df):
        x = pd.DataFrame({f"l_{s}": np.log(df[f"r_{s}"].astype(float) + 0.05) for s in STATS}, index=df.index)
        x["no10"] = df.no10.astype(float)
        for p in ["A", "SSDM", "D", "FO"]:
            x[f"p_{p}"] = (df.pos == p).astype(float)
        return sm.add_constant(x, has_constant="add")

    def fit(self):
        rows = []
        for y in sorted(self.cs.y.unique()):
            p10 = self.prior10(y)
            sub = self.cs[self.cs.y == y].join(p10[[f"r_{s}" for s in STATS] + ["n10"]], on="player_uid")
            sub["pos"] = sub.player_uid.map(self.pos_of).fillna("M")
            rows.append(sub[sub.cs_pos != "G"])
        D = pd.concat(rows)
        D["no10"] = D.n10.isna()
        for s in STATS:
            D[f"r_{s}"] = D[f"r_{s}"].fillna(D.pos.map(self.pos_mean[s]))
        self.glm = {t: sm.GLM(D[t], self.X(D), family=sm.families.Poisson()).fit_regularized(alpha=0.002, L1_wt=0.0)
                    for t in ("g", "a")}
        pl = D[~D.no10].drop_duplicates(["player_uid", "y"])
        self.train_q = pl.groupby("pos").r_g.quantile(0.95).to_dict()          # role-ladder thresholds
        self.train_max = {s_: pl.groupby("pos")[f"r_{s_}"].max().to_dict() for s_ in STATS}
        self.train_rows = len(D)
        return self

    def nll_bridge(self):
        """Linear map NLL per-game rates -> 10v10 per-game rates, fitted on players with both."""
        n = q(self.con, """select player_uid, sum(games_played) gp, sum(goals) g, sum(assists) a, sum(shots_on_goal) sog,
                           sum(loose_balls) lb, sum(turnovers) tov, any_value(position) npos
                           from fact.nll_player_season where is_playoffs=0 and season>='2021-22' group by 1 having sum(games_played)>0""")
        n = n.set_index("player_uid")
        for s, c in [("g", "g"), ("a", "a"), ("sh", "sog"), ("gb", "lb"), ("tov", "tov")]:
            n[f"n_{s}"] = n[c] / n.gp
        p = self.prior10(2027)
        both = p.join(n, how="inner")
        both = both[(both.n10 >= 10) & (both.gp >= 10) & (both.pos != "G")]
        coef = {}
        for s in STATS:
            m = sm.WLS(both[f"r_{s}"], sm.add_constant(both[f"n_{s}"]), weights=np.minimum(both.n10, both.gp)).fit()
            coef[s] = m.params.values
        self.nll_coef, self.nll_n = coef, len(both)
        return n

    def glg_rates(self, roster: pd.DataFrame) -> pd.DataFrame:
        st = self.st
        p10 = self.prior10(2027)
        nll = self.nll_bridge()
        R = roster.copy()
        R = R.join(p10[[f"r_{s}" for s in STATS] + ["n10", "w_gp"]], on="player_uid")
        R["pos"] = R.player_uid.map(self.pos_of)
        R = R.join(nll[["gp", "npos"] + [f"n_{s}" for s in STATS]].rename(columns={"gp": "nll_gp"}), on="player_uid")
        R.loc[R.pos.isna() & R.npos.notna(), "pos"] = R.npos.map(NLL_POS)
        R["pos"] = np.where(R.glg_position.eq("goalie"), "G", R.pos.fillna("M"))
        R["n10"] = R.n10.fillna(0)
        R["w_gp"] = R.w_gp.fillna(0)
        R["listed_pos"] = R.pos
        # blend NLL-derived 10v10-equivalent rates
        has_nll = R.nll_gp.fillna(0) >= 6
        for s in STATS:
            a, b = self.nll_coef[s]
            est = (a + b * R[f"n_{s}"]).clip(lower=0)
            base = R[f"r_{s}"].fillna(R.pos.map(self.pos_mean[s]))
            wn = np.where(has_nll, st.k_nll * np.minimum(R.nll_gp.fillna(0) / 18, 1.0), 0.0)
            R[f"r_{s}"] = np.where(has_nll, (R.w_gp * base + wn * est) / (R.w_gp + wn).replace(0, np.nan), base)
            R[f"r_{s}"] = R[f"r_{s}"].fillna(base)
        R["no10"] = (R.n10 == 0) & ~has_nll
        # ROLE, not listed position: a defender / SSDM who scores above his position's training range plays a
        # midfielder's role (e.g. a 0.55 g/gm SSDM). Ladder D -> SSDM -> M; then clip inputs to the training range.
        for lo, hi in (("D", "SSDM"), ("SSDM", "M")):
            cap = self.train_q[lo]
            up = (R.pos == lo) & (R.r_g > cap)
            R.loc[up, "pos"] = hi
        for s_ in STATS:
            qmax = R.pos.map(self.train_max[s_]).fillna(R[f"r_{s_}"])
            R[f"r_{s_}"] = np.minimum(R[f"r_{s_}"], qmax)
        R["prior_src"] = np.select([R.n10 > 0, has_nll], ["pll10" + np.where(has_nll, "+nll", ""), "nll"], "position_mean")
        field = R.pos != "G"
        for t in ("g", "a"):
            R[f"prior_{t}"] = 0.0
            R.loc[field, f"prior_{t}"] = self.glm[t].predict(self.X(R[field]))
        return R

    def evidence(self, uids):
        """Sixes evidence rows per player-game: CS (direct) and intl (raw shares; scaled later)."""
        e = q(self.con, """select p.player_uid, p.source, p.game_key, p.date, p.team, p.position, p.goals g, p.assists a,
                           t.goals tg, sum(p.assists) over (partition by p.game_key, p.team) ta
                           from fact.sixes_player_game p join fact.sixes_team_game t using (game_key, team)""")
        e = e[e.player_uid.isin(uids)].copy()
        e["w"] = 0.5 ** ((pd.Timestamp("2026-12-08") - pd.to_datetime(e.date)).dt.days / 730)
        return e


def cs_scale(con):
    s = q(con, """select avg(t.goals) g, avg(p.a) a from fact.sixes_team_game t
                  join (select game_key, team, sum(assists) a from fact.sixes_player_game group by 1,2) p using (game_key, team)
                  where t.source='pll_cs'""")
    return float(s.g[0]), float(s.a[0])


# ----------------------------------------------------------------------------- results rating
def results_games(con, st: Settings, glg_results: pd.DataFrame | None = None) -> pd.DataFrame:
    g = q(con, "select game_key, competition, date, home, away, home_goals, away_goals from fact.sixes_game where source='intl'")
    g["w"], g["env"] = 1.0, "sixes"
    w23 = pd.read_csv(GLG / "worlds_2023_games.csv")
    w23 = w23.assign(game_key="W23:" + w23.index.astype(str), competition="2023 World Championship (10v10)",
                     w=st.worlds_weight, env="worlds2023")
    parts = [g, w23[g.columns]]
    if glg_results is not None and len(glg_results):
        x = glg_results.assign(game_key="GLG:" + glg_results.game_number.astype(str), competition="GLG 2026", w=1.5, env="sixes")
        parts.append(x[g.columns])
    G = pd.concat(parts, ignore_index=True)
    G["date"] = pd.to_datetime(G.date)
    decay = 0.5 ** ((pd.Timestamp("2026-12-08") - G.date).dt.days.clip(lower=0) / st.results_hl_days)
    G["w"] = np.where(G.env == "worlds2023", G.w, G.w * decay)   # Worlds = the only cross-continent link: no decay
    return G


def fit_results(G: pd.DataFrame, ridge=1.5):
    """log mu = env_c + att_i - def_j (Poisson, weighted, ridge on att/def)."""
    teams = sorted(set(G.home) | set(G.away))
    envs = sorted(G.env.unique())
    ti, ei = {t: i for i, t in enumerate(teams)}, {e: i for i, e in enumerate(envs)}
    n, ne = len(teams), len(envs)
    h, a, e = G.home.map(ti).values, G.away.map(ti).values, G.env.map(ei).values
    yh, ya = G.home_goals.values.astype(float), G.away_goals.values.astype(float)
    wh = (G.w * G.get("c_obs_home", 1.0)).values.astype(float)
    wa = (G.w * G.get("c_obs_away", 1.0)).values.astype(float)

    def f(p):
        c, att, de = p[:ne], p[ne:ne + n], p[ne + n:]
        lh, la = c[e] + att[h] - de[a], c[e] + att[a] - de[h]
        mh, ma = np.exp(lh), np.exp(la)
        val = (wh * (mh - yh * lh) + wa * (ma - ya * la)).sum() + ridge * (att @ att + de @ de)
        rh, ra = wh * (mh - yh), wa * (ma - ya)
        gc = np.bincount(e, rh + ra, ne)
        ga = np.bincount(h, rh, n) + np.bincount(a, ra, n) + 2 * ridge * att
        gd = -np.bincount(a, rh, n) - np.bincount(h, ra, n) + 2 * ridge * de
        return val, np.concatenate([gc, ga, gd])

    p = minimize(f, np.r_[np.full(ne, 2.7), np.zeros(2 * n)], jac=True, method="L-BFGS-B").x
    return pd.DataFrame({"team": teams, "res_att": p[ne:ne + n], "res_def": p[ne + n:]}).set_index("team")


# ----------------------------------------------------------------------------- talent model
def build_model(con, st: Settings, glg_results=None, glg_player_games=None):
    """Players and teams on one talent scale (Championship Series goals/game).

    1. pro rate  = GLM prior (10v10 / NLL) updated with CS games only (no intl -> no circularity)
    2. results   = Poisson rating of nations from intl sixes + 2023 Worlds
    3. anchor    = USA & Canada Pan-Am lineups are ~all pros: log(lineup pro talent) - results attack -> scale a
    4. each nation's historical lineup talent = exp(a + results attack); a player's intl evidence =
       his share of team goals x that lineup talent (a development squad's shares are worth a
       development squad's talent, not a pro team's)
    5. player talent = Bayesian blend of pro prior and intl (+ live GLG) evidence; non-pros with no
       evidence get the nation's non-pro mean
    6. team attack = elasticity x log(GLG roster talent / mean); defence = results defence +
       def_elasticity x log(GLG roster talent / talent of the lineups that produced the results)
    """
    G_cs, A_cs = cs_scale(con)
    apg_cs = A_cs / G_cs
    pm = PlayerModel(con, st).fit()
    glg = q(con, """select r.nation, r.first_name, r.last_name, r.position glg_position, r.jersey, r.player_uid,
                    r.method link_method from src.glg_roster r""")
    lu = q(con, f"""select p.team nation, p.game_key, g.competition, g.date, p.player_uid, p.player_name, p.goals g, p.assists a,
                    case when p.position='G' then 'goalie' else 'field' end glg_position
                    from fact.sixes_player_game p join fact.sixes_game g using (game_key)
                    where p.source='intl' and p.team in ({','.join("'" + n + "'" for n in NATIONS)})""")
    others = lu[~lu.player_uid.isin(glg.player_uid)].drop_duplicates("player_uid")
    allp = pd.concat([glg, others[["nation", "player_uid", "glg_position", "player_name"]]], ignore_index=True)
    R = pm.glg_rates(allp)
    R["on_glg"] = R.player_uid.isin(glg.player_uid)
    R["has_pro"] = (R.n10 > 0) | (R.nll_gp.fillna(0) >= 6)
    ev = pm.evidence(R.player_uid.tolist())
    k = st.k_update
    # (1) pro rate: GLM prior + CS evidence
    cse = ev[ev.source == "pll_cs"].assign(wg=lambda d: d.w * d.g, wa=lambda d: d.w * d.a).groupby("player_uid").agg(
        cs_n=("w", "sum"), cs_games=("w", "size"), wg=("wg", "sum"), wa=("wa", "sum"))
    R = R.join(cse, on="player_uid")
    for c in ("cs_n", "cs_games", "wg", "wa"):
        R[c] = R[c].fillna(0)
    R["has_pro"] |= R.cs_games > 0
    for t, wc in (("g", "wg"), ("a", "wa")):
        R[f"pro_{t}"] = (R[wc] + k * R[f"prior_{t}"]) / (R.cs_n + k)
    R.loc[R.pos == "G", ["pro_g", "pro_a"]] = 0.0
    # (2) results rating
    res = fit_results(results_games(con, st, glg_results))
    # (3) anchor scale from pro-heavy lineups (USA, Canada at Pan-Am)
    lu = lu.merge(R[["player_uid", "pro_g", "has_pro", "pos"]], on="player_uid", how="left")
    lu["w"] = 0.5 ** ((pd.Timestamp("2026-12-08") - pd.to_datetime(lu.date)).dt.days / st.results_hl_days)
    lineup = lu[lu.pos != "G"].groupby(["nation", "game_key"]).agg(
        pro_talent=("pro_g", "sum"), pro_frac=("has_pro", "mean"), w=("w", "first")).reset_index()
    nat_line = lineup.groupby("nation").apply(lambda d: pd.Series({
        "lineup_pro_talent": np.average(d.pro_talent, weights=d.w), "lineup_pro_frac": np.average(d.pro_frac, weights=d.w)}),
        include_groups=False)
    anchors = [n for n in ("USA", "Canada") if n in nat_line.index and nat_line.loc[n, "lineup_pro_frac"] >= 0.8]
    a_scale = float(np.mean([np.log(nat_line.loc[n, "lineup_pro_talent"]) - res.loc[n, "res_att"] for n in anchors]))
    nat_line["hist_talent"] = np.exp(a_scale + res.reindex(nat_line.index).res_att)
    # (4) intl evidence on the talent scale: share of team goals x nation's lineup talent
    tg = lu.groupby(["nation", "game_key"]).g.transform("sum")
    ta = lu.groupby(["nation", "game_key"]).a.transform("sum")
    lu["g_share"] = lu.g / tg.replace(0, np.nan)
    lu["a_share"] = lu.a / ta.replace(0, np.nan)
    lu["T"] = lu.nation.map(nat_line.hist_talent)
    # usage flattening: top scorers on weaker lineups take a bigger share (31% weak vs 20% strong teams); when the
    # lineup was weaker than the nation's GLG roster, flatten shares s -> s^beta (renormalised) before converting.
    # GLG roster talent estimate: pros at their pro rating + non-pros at the average player of the nation's past lineups
    gf = R[R.on_glg & (R.pos != "G")]
    field_per_game = lu[lu.pos != "G"].groupby(["nation", "game_key"]).size().groupby(level=0).mean()
    per_player_hist = (nat_line.hist_talent / field_per_game.reindex(nat_line.index)).rename("pp")
    est_glg_T = (gf[gf.has_pro].groupby("nation").pro_g.sum().reindex(nat_line.index).fillna(0)
                 + gf[~gf.has_pro].groupby("nation").size().reindex(nat_line.index).fillna(0) * per_player_hist)
    est_glg_T = np.maximum(est_glg_T, nat_line.hist_talent)
    beta = np.clip((nat_line.hist_talent / est_glg_T) ** st.usage_power, 0.65, 1.0)
    # only for development-style lineups (few pros AND low overlap with the GLG roster); pro national squads keep their
    # observed usage - renormalising shares over the GLG roster already accounts for new players joining.
    overlap = lu[lu.pos != "G"].assign(o=lambda d: d.player_uid.isin(glg.player_uid)).groupby("nation").o.mean()
    nat_line["lineup_glg_overlap"] = overlap.reindex(nat_line.index)
    dev = (nat_line.lineup_pro_frac < 0.5) & (nat_line.lineup_glg_overlap < 0.5)
    beta = beta.where(dev, 1.0)
    nat_line["usage_beta"] = beta
    lu["beta"] = lu.nation.map(beta).fillna(1.0)
    lu["g_share"] = lu.g_share.fillna(0) ** lu.beta
    lu["g_share"] = lu.g_share / lu.groupby(["nation", "game_key"]).g_share.transform("sum").replace(0, np.nan)
    lu["a_share"] = lu.a_share.fillna(0) ** lu.beta
    lu["a_share"] = lu.a_share / lu.groupby(["nation", "game_key"]).a_share.transform("sum").replace(0, np.nan)
    lu["g_eq"] = lu.g_share * lu["T"]
    lu["a_eq"] = lu.a_share * lu["T"] * apg_cs
    ie = lu[lu.pos != "G"].assign(wg=lambda d: d.w * d.g_eq.fillna(0), wa=lambda d: d.w * d.a_eq.fillna(0)).groupby("player_uid").agg(
        intl_n=("w", "sum"), intl_wg=("wg", "sum"), intl_wa=("wa", "sum"), intl_games=("w", "size"))
    R = R.join(ie, on="player_uid")
    for c in ("intl_n", "intl_wg", "intl_wa", "intl_games"):
        R[c] = R[c].fillna(0)
    # non-pro prior per nation: mean intl-implied rate of that nation's non-pro field players
    np_rows = R[(~R.has_pro) & (R.intl_n > 0) & (R.pos != "G")]
    np_g = (np_rows.intl_wg / np_rows.intl_n).groupby(np_rows.nation).mean()
    np_a = (np_rows.intl_wa / np_rows.intl_n).groupby(np_rows.nation).mean()
    R["prior_used_g"] = np.where(R.has_pro, R.pro_g, R.nation.map(np_g).fillna(np_g.mean()))
    R["prior_used_a"] = np.where(R.has_pro, R.pro_a, R.nation.map(np_a).fillna(np_a.mean()))
    R["prior_kind"] = np.where(R.has_pro, R.prior_src, "non-pro (nation intl mean)")
    R["glg_games"], R["glg_g"], R["glg_a"] = 0.0, 0.0, 0.0
    if glg_player_games is not None and len(glg_player_games):
        gg = glg_player_games.groupby("player_uid").agg(n=("g", "size"), g=("g", "sum"), a=("a", "sum"))
        R = R.join(gg, on="player_uid")
        R["glg_games"], R["glg_g"], R["glg_a"] = R.n.fillna(0), R.g.fillna(0.0), R.a.fillna(0.0)
        R = R.drop(columns=["n", "g", "a"])
    # (4b) national-team role: a club-based rating predicts a player's national-team scoring share only with slope ~0.61
    # (18 Pan-Am pros). Pull each GLG team's priors 39% toward the team mean; national-team sixes games then update it.
    on = R.on_glg & (R.pos != "G")
    # club usage (time-on-ball proxy): share of PLL team touches, last two seasons with touch data
    tch = q(con, """with p as (select 'PLL:'||player_id uid, season, game_id, team_id, touches from fact.pll10_player_game
                                where touches is not null and season >= 2024),
                         t as (select game_id, team_id, touches tt from fact.pll10_team_game)
                    select uid player_uid, sum(touches)/sum(tt) touch_share, count(*) touch_gp from p join t using (game_id, team_id) group by 1""")
    R = R.merge(tch, on="player_uid", how="left")
    on = R.on_glg & (R.pos != "G")
    for t in ("g", "a"):
        col = f"prior_used_{t}"
        tot = R[on].groupby("nation")[col].transform("sum")
        r_sh = R.loc[on, col] / tot                                   # rating-implied share
        r_mean = r_sh.groupby(R.loc[on, "nation"]).transform("mean")
        ts = R.loc[on, "touch_share"]
        ts_n = ts / ts.groupby(R.loc[on, "nation"]).transform("sum") * ts.notna().groupby(R.loc[on, "nation"]).transform("sum")                / R.loc[on].groupby("nation").nation.transform("size")   # rescale touch shares to an 11-man roster share
        u_dev = (ts_n - ts_n.groupby(R.loc[on, "nation"]).transform("mean")).fillna(0.0)
        comb = r_mean + st.usage_coef_rating * (r_sh - r_mean) + st.usage_coef_touch * u_dev
        comb = r_mean + st.nat_role_reliability * (comb - r_mean)       # national-team role reliability
        R.loc[on, col] = comb.clip(lower=0.005) * tot
    R["usage_share"] = np.nan
    R.loc[on, "usage_share"] = R.loc[on, "touch_share"]
    R["nat_evidence"] = R.intl_games > 0
    # (5) talent = blend (pros: prior weight k; non-pros: k/2) with intl evidence
    kk = np.where(R.has_pro, st.k_intl_pro, st.k_nonpro)
    R["talent_g"] = (R.intl_wg + kk * R.prior_used_g) / (R.intl_n + kk)
    R["talent_a"] = (R.intl_wa + kk * R.prior_used_a) / (R.intl_n + kk)
    R.loc[R.pos == "G", ["talent_g", "talent_a"]] = 0.0
    # live GLG box scores: observed share of team goals x team talent, weight 1 per game
    if R.glg_games.sum() > 0:
        on = R.on_glg & (R.pos != "G")
        for t, col in (("g", "glg_g"), ("a", "glg_a")):
            Tt = R[on].groupby("nation")[f"talent_{t}"].sum()
            tot = R[on].groupby("nation")[col].transform("sum").reindex(R.index).replace(0, np.nan)
            obs = (R[col] / tot).fillna(0) * R.nation.map(Tt)
            n_ = R.glg_games
            R[f"talent_{t}"] = np.where(on & (n_ > 0), ((R.intl_n + kk) * R[f"talent_{t}"] + n_ * obs) / (R.intl_n + kk + n_),
                                        R[f"talent_{t}"])
    # no 2-point arc at the GLG: players whose goals leaned on 2-pointers lose a little share
    two = q(con, """with t as (select 'PLL:'||player_id uid, sum(goals) g, sum(two_point_goals) g2 from fact.pll10_player_game group by 1
                    union all select player_uid, sum(goals), sum(two_pt_goals) from fact.sixes_player_game where source='pll_cs' group by 1)
                    select uid player_uid, sum(g) g, sum(g2) g2 from t group by 1 having sum(g) >= 8""")
    s2 = (two.g2 / two.g).set_axis(two.player_uid)
    R["two_pt_share"] = R.player_uid.map(s2)
    R["two_pt_factor"] = (1 - st.two_pt_adj * (R.two_pt_share.fillna(0.10) - 0.10)).clip(0.85, 1.05)
    R["talent_g"] *= R.two_pt_factor
    R["talent_g_model"], R["talent_a_model"] = R.talent_g, R.talent_a
    # (6) player overrides
    R["active"] = True
    for uid, o in st.overrides.get("player", {}).items():
        m = R.player_uid == uid
        if o.get("out"):
            R.loc[m, "active"] = False
        if o.get("g_rate") not in (None, ""):
            R.loc[m, "talent_g"] = float(o["g_rate"])
        if o.get("a_rate") not in (None, ""):
            R.loc[m, "talent_a"] = float(o["a_rate"])
        R.loc[m, "talent_g"] *= float(o.get("g_mult", 1.0) or 1.0)
        R.loc[m, "talent_a"] *= float(o.get("a_mult", 1.0) or 1.0)
    P = R[R.on_glg].copy()
    act = P.active & (P.pos != "G")
    for t in ("g", "a"):
        tot = P[act].groupby("nation")[f"talent_{t}"].transform("sum")
        P[f"share_{t}"] = 0.0
        P.loc[act, f"share_{t}"] = P.loc[act, f"talent_{t}"] / tot
    P["player"] = P.first_name + " " + P.last_name
    # ---- depth chart: expected sixes usage (CS usage model: .69 x rating-share dev + .10 x club touch-share dev)
    P["usage_hat"] = np.nan
    P["depth_rank_default"] = np.nan
    P["depth_rank"] = np.nan
    for n_ in NATIONS:
        m = act & (P.nation == n_)
        if not m.any():
            continue
        q_ = P.loc[m]
        ts = q_.touch_share
        ts_n = (ts / ts.sum() * ts.notna().sum() / len(q_)).fillna(1 / len(q_))
        u = 1 / len(q_) + 0.69 * (q_.share_g - 1 / len(q_)) + 0.10 * (ts_n - ts_n.mean())
        u = u.clip(lower=0.005); u = u / u.sum()
        P.loc[m, "usage_hat"] = u
        P.loc[m, "depth_rank_default"] = u.rank(ascending=False, method="first")
    P["depth_rank"] = P.depth_rank_default
    # direct usage override: expected share of team usage set by the user -> full measured value of usage (0.573)
    uov = st.overrides.get("usage", {})
    for uid, target in uov.items():
        m = act & (P.player_uid == uid)
        if m.any() and target not in (None, ""):
            n_ = P.loc[m, "nation"].iloc[0]
            mt = act & (P.nation == n_)
            d_ = st.usage_value * (float(target) - P.loc[m, "usage_hat"].iloc[0])
            for t in ("g", "a"):
                v = P.loc[mt, f"share_{t}"].copy()
                v.loc[m[mt].values] = v.loc[m[mt].values] + d_
                v = v.clip(lower=0.004)
                P.loc[mt, f"share_{t}"] = v / v.sum()
    dep = st.overrides.get("depth", {})
    if dep:
        for n_, order in dep.items():
            m = act & (P.nation == n_)
            ranks = {uid: i + 1 for i, uid in enumerate([u_ for u_ in order if u_ in set(P.loc[m, "player_uid"])])}
            if ranks:
                P.loc[m, "depth_rank"] = P.loc[m, "player_uid"].map(ranks).fillna(P.loc[m, "depth_rank_default"])
        nfield = P[act].groupby("nation").size()
        for n_ in dep:
            m = act & (P.nation == n_)
            if not m.any():
                continue
            k_ = int(nfield.get(n_, 11))
            cur = np.array(DEPTH_CURVE[:k_]); cur = cur / cur.sum()
            uc = lambda r: cur[min(int(r), k_) - 1]
            delta = st.depth_weight * st.usage_value * (P.loc[m, "depth_rank"].map(uc) - P.loc[m, "depth_rank_default"].map(uc))
            for t in ("g", "a"):
                v = (P.loc[m, f"share_{t}"] + delta).clip(lower=0.004)
                P.loc[m, f"share_{t}"] = v / v.sum()
    # ---- 12-player game roster: field players below the dressed_field cut on the depth chart sit by default
    P["dressed_default"] = True
    for n_ in NATIONS:
        m = act & (P.nation == n_)
        if m.sum() > st.dressed_field:
            P.loc[m & (P.depth_rank > st.dressed_field), "dressed_default"] = False
    # lineup continuity: share of the GLG roster's talent that played in each intl team-game
    glg_tal = P[act].groupby("nation").talent_g.sum()
    on_glg = set(P.player_uid)
    lu2 = lu[lu.pos != "G"].merge(R[["player_uid", "talent_g"]], on="player_uid", how="left")
    lu2["glg_part"] = np.where(lu2.player_uid.isin(on_glg), lu2.talent_g, 0.0)
    cont = (lu2.groupby(["game_key", "nation"]).glg_part.sum() / lu2.groupby(["game_key", "nation"]).nation.first().map(glg_tal)).rename("c")
    Gw = results_games(con, st, glg_results)
    cmap = cont.to_dict()

    # 2023 Worlds continuity per nation = share of the GLG roster's talent that was on that nation's 2023 roster
    # (data/glg/worlds_2023_rosters.csv); falls back to st.worlds_continuity only if the roster file is missing.
    w23c = {}
    w23f = GLG / "worlds_2023_rosters.csv"
    if w23f.exists():
        w23 = pd.read_csv(w23f)
        w23["k"] = [f"{str(f).strip().lower()} {str(l).strip().lower()}" for f, l in zip(w23.first_name, w23.last_name)]
        Pk = P.assign(k=(P.first_name.str.strip().str.lower() + " " + P.last_name.str.strip().str.lower()))
        for n_ in NATIONS:
            names = set(w23[w23.nation == n_].k)
            if not names:
                continue
            q_ = Pk[(Pk.nation == n_) & act]
            w23c[n_] = float(q_[q_.k.isin(names)].talent_g.sum() / q_.talent_g.sum())

    def c_of(gk, team, env):
        if team not in NATIONS:
            return 1.0                       # opponents' own lineups are whatever they were; no GLG roster to compare
        if env == "worlds2023":
            return float(np.clip(w23c.get(team, st.worlds_continuity), 0.02, 1.0))
        if str(gk).startswith("GLG:"):
            return 1.0
        return float(np.clip(cmap.get((gk, team), 0.0), 0.02, 1.0))
    ch = np.array([c_of(g_, h_, e_) for g_, h_, e_ in zip(Gw.game_key, Gw.home, Gw.env)])
    ca = np.array([c_of(g_, a_, e_) for g_, a_, e_ in zip(Gw.game_key, Gw.away, Gw.env)])
    # home-goals observation informs home attack & away defence -> weight by both lineups' continuity
    Gw["c_obs_home"], Gw["c_obs_away"] = ch * ca, ch * ca
    resw = fit_results(Gw)
    # blowouts say little about elite matchups: down-weight games by the first-pass rating gap, refit
    sg = (resw.res_att + resw.res_def)
    gap = (Gw.home.map(sg) - Gw.away.map(sg)).abs().fillna(0)
    Gw["mismatch_w"] = np.exp(-np.maximum(0, gap - 0.3) / st.mismatch_scale)
    Gw["c_obs_home"] = Gw.c_obs_home * Gw.mismatch_w
    Gw["c_obs_away"] = Gw.c_obs_away * Gw.mismatch_w
    resw = fit_results(Gw)
    T = res.reindex(NATIONS).copy()
    T = T.join(resw.reindex(NATIONS).rename(columns={"res_att": "cres_att", "res_def": "cres_def"}))
    T = T.join(nat_line[["lineup_pro_frac", "hist_talent", "usage_beta"]])
    cw = pd.DataFrame({"gk": Gw.game_key, "home": Gw.home, "away": Gw.away, "ch": ch, "ca": ca, "w": Gw.w})
    mw = Gw.mismatch_w.values
    eff = {n_: float((cw.w * mw * np.where(cw.home == n_, ch * ca, 0) + cw.w * mw * np.where(cw.away == n_, ch * ca, 0)).sum()) for n_ in NATIONS}
    T["eff_results_games"] = pd.Series(eff)
    T["mean_continuity"] = cont.groupby(level=1).mean().reindex(NATIONS)
    T["glg_talent"] = glg_tal.reindex(NATIONS)
    lt = np.log(T.glg_talent) - np.log(T.glg_talent).mean()
    T["talent_att"] = st.talent_elasticity * lt
    # results move each nation off its talent rating by credibility n_eff / (n_eff + k): small samples barely move it
    T["credibility"] = T.eff_results_games / (T.eff_results_games + st.k_results)
    T["talent_def"] = st.def_talent * lt
    ra = T.cres_att - T.cres_att.mean()
    rd = T.cres_def - T.cres_def.mean()
    T["att_model"] = T.talent_att + T.credibility * (ra - T.talent_att)
    T["def_model"] = T.talent_def + T.credibility * (rd - T.talent_def)
    T["att_model"] -= T.att_model.mean()
    T["def_model"] -= T.def_model.mean()
    T["att"], T["def"] = T.att_model, T.def_model
    for n_, o in st.overrides.get("team", {}).items():
        if n_ in T.index:
            T.loc[n_, "att"] += float(o.get("att", 0.0) or 0.0)
            T.loc[n_, "def"] += float(o.get("def", 0.0) or 0.0)
    T["strength"] = T.att + T["def"]
    T["worlds2023_continuity"] = pd.Series({n_: w23c.get(n_, st.worlds_continuity) for n_ in NATIONS})
    meta = dict(a_scale=a_scale, anchors=anchors, cs_team_goals=G_cs, cs_assists_per_goal=apg_cs,
                glm_rows=int(pm.train_rows), nll_bridge_n=int(pm.nll_n), nonpro_g={k_: float(v) for k_, v in np_g.items()})
    return P, T, meta, R


def environment(st: Settings, glg_results=None):
    """Posterior expected goals per team (GLG). Returns (mean, log-sd)."""
    if st.overrides.get("env_goals"):
        return float(st.overrides["env_goals"]), st.env_sd * 0.5
    if glg_results is None or not len(glg_results):
        return st.env_goals_prior, st.env_sd
    obs = np.r_[glg_results.home_goals.values, glg_results.away_goals.values].astype(float)
    n = len(obs)
    mean = (st.env_prior_games * st.env_goals_prior + obs.sum()) / (st.env_prior_games + n)
    sd = st.env_sd * np.sqrt(st.env_prior_games / (st.env_prior_games + n))
    return mean, sd


def run(st: Settings | None = None, glg_results=None, glg_player_games=None):
    st = st or Settings()
    con = duckdb.connect(str(WH), read_only=True)
    P, T, meta, R = build_model(con, st, glg_results, glg_player_games)
    con.close()
    return P, T, environment(st, glg_results), meta


# ----------------------------------------------------------------------------- simulation
def simulate_game(T, env, st: Settings, home, away, rng, n, game_number=None):
    env_mu, env_sd = env
    th, ta = T.loc[home], T.loc[away]
    e_draw = rng.normal(0, env_sd, n)
    sh, sa = rng.normal(0, st.strength_sd, n), rng.normal(0, st.strength_sd, n)
    mu_h = env_mu * np.exp(th.att - ta["def"] + e_draw + sh - sa)
    mu_a = env_mu * np.exp(ta.att - th["def"] + e_draw + sa - sh)
    go = st.overrides.get("game", {}).get(str(game_number), {}) if game_number is not None else {}
    if go.get("home_mu"):
        mu_h = mu_h * float(go["home_mu"]) / mu_h.mean()
    if go.get("away_mu"):
        mu_a = mu_a * float(go["away_mu"]) / mu_a.mean()
    pace = np.exp(rng.normal(-st.pace_sd ** 2 / 2, st.pace_sd, n))

    def draw(mu):
        m = mu * pace
        nn = np.maximum(np.ceil(m / (1 - st.phi_inner)).astype(int), 1)
        return rng.binomial(nn, np.clip(m / nn, 0, 1))
    gh, ga = draw(mu_h), draw(mu_a)
    reg_h, reg_a = gh.copy(), ga.copy()
    tied = gh == ga
    ot = tied.copy()
    per = 3.0 / 32.0     # WL overtime: 3-minute periods until a team leads at the end of one
    while tied.any():
        idx = np.where(tied)[0]
        gh[idx] += rng.poisson(mu_h[idx] * pace[idx] * per)
        ga[idx] += rng.poisson(mu_a[idx] * pace[idx] * per)
        tied = gh == ga
    return dict(home=home, away=away, gh=gh, ga=ga, reg_h=reg_h, reg_a=reg_a, ot=ot)


def player_multipliers(P, st, n):
    """Per-sim rating multipliers (lognormal, mean 1) - the same draw is used for a player in every game of sim i,
    so tournament props carry rating uncertainty, not just game-to-game noise."""
    rng = np.random.default_rng(st.seed + 500)
    sd = np.where(P.has_pro.values, np.where(P.intl_games.fillna(0).values > 0, st.rating_sd_pro, st.rating_sd_no_nat),
                  st.rating_sd_nonpro)
    # less data -> more rating uncertainty (veterans with long records are pinned down better)
    games = (P.n10.fillna(0) + P.cs_games.fillna(0) + P.intl_games.fillna(0) + np.minimum(P.nll_gp.fillna(0), 36) / 2).values
    sd = sd * np.clip(np.sqrt(45.0 / (games + 25.0)), 0.7, 1.4)
    z = rng.standard_normal((n, len(P)))
    return pd.DataFrame(np.exp(z * sd - sd ** 2 / 2), columns=P.player_uid.values)


def scratched(P, nation, st, game_number=None):
    """Field players sitting this game: per-game lineup override if set, else the depth-chart default."""
    lo = st.overrides.get("lineups", {}).get(str(game_number), {}) if game_number is not None else {}
    if nation in lo:
        return set(lo[nation])
    q_ = P[(P.nation == nation) & P.active & (P.pos != "G")]
    return set(q_.loc[~q_.dressed_default, "player_uid"])


def allocate(team_goals, P, nation, st, rng, mult=None, game_number=None):
    """Per-sim player goals and assists for one team in one game (multinomial by share x rating draw).
    Only dressed field players (12-man game roster) receive goals; scratched players' shares are re-spread."""
    out_ = scratched(P, nation, st, game_number)
    Q = P[(P.nation == nation) & P.active & (P.pos != "G") & ~P.player_uid.isin(out_)]
    n = len(team_goals)
    if mult is None:
        mult = player_multipliers(P, st, n)
    M = mult[Q.player_uid.values].values[:n]
    pg = Q.share_g.values * M
    pa = Q.share_a.values * M
    pg, pa = pg / pg.sum(1, keepdims=True), pa / pa.sum(1, keepdims=True)
    n_ast = rng.binomial(team_goals, st.assists_per_goal)
    goals = rng.multinomial(team_goals.astype(np.int64), pg).astype(np.int16)
    asts = rng.multinomial(n_ast.astype(np.int64), pa).astype(np.int16)
    return Q.player_uid.values, goals, asts


def game_with_players(T, P, env, st, home, away, game_number=None, n=None, mult=None):
    rng = np.random.default_rng(st.seed + (game_number or 0))
    n = n or st.n_sims
    s = simulate_game(T, env, st, home, away, rng, n, game_number)
    mult = player_multipliers(P, st, n) if mult is None else mult
    for side, tg in (("home", s["gh"]), ("away", s["ga"])):
        s[f"{side}_uids"], s[f"{side}_goals"], s[f"{side}_assists"] = allocate(tg, P, s[side], st, rng, mult, game_number)
    return s


def game_summary(sim):
    gh, ga = sim["gh"], sim["ga"]
    m, tot = gh - ga, gh + ga
    ph = (gh > ga).mean()
    return dict(home=sim["home"], away=sim["away"], p_home=ph, p_away=1 - ph, exp_home=gh.mean(), exp_away=ga.mean(),
                exp_total=tot.mean(), exp_margin=m.mean(), median_margin=float(np.median(m)), p_ot=sim["ot"].mean(),
                home_q10=np.percentile(gh, 10), home_q90=np.percentile(gh, 90),
                away_q10=np.percentile(ga, 10), away_q90=np.percentile(ga, 90))


MIN_SPREAD = 1.5   # sixes games cannot end tied (OT until a lead), so +/-0.5 is the moneyline: spreads start at 1.5


def fav_spread(sim):
    """Favourite and the main spread from its side: the line >= 1.5 whose cover probability is closest to 50%."""
    m = sim["gh"] - sim["ga"]
    fav_home = (m > 0).mean() >= 0.5
    mf = m if fav_home else -m
    L = min((x + 0.5 for x in range(1, 40)), key=lambda v: abs((mf > v).mean() - 0.5))
    return fav_home, max(L, MIN_SPREAD)


def spread_ladder(sim, n_each_side=2):
    """Alternate spread lines from the home side (favourite negative), never inside +/-1.5."""
    fav_home, L = fav_spread(sim)
    fav_lines = sorted({x for x in (L + d for d in range(-n_each_side, n_each_side + 1)) if x >= MIN_SPREAD})
    while len(fav_lines) < 2 * n_each_side + 1:
        fav_lines.append(fav_lines[-1] + 1)
    return [(-x if fav_home else x) for x in fav_lines]


def main_lines(sim):
    """Main spread (quoted for the HOME team: negative = home favourite, |line| >= 1.5) and main total (half-point,
    closest to 50/50)."""
    fav_home, L = fav_spread(sim)
    tot = sim["gh"] + sim["ga"]
    tl = min((x + 0.5 for x in range(5, 80)), key=lambda v: abs((tot > v).mean() - 0.5))
    return (-L if fav_home else L), tl


def tournament(T, P, env, st: Settings, schedule: pd.DataFrame, glg_results=None, n=None):
    """Full tournament with players: remaining pool games, seeding 1v4 / 2v3 (wins, goal diff, goals for),
    semis, final. Returns team futures, per-player tournament totals, raw sims."""
    n = n or max(st.n_sims, 40000)       # futures need resolution in the tails
    rng = np.random.default_rng(st.seed + 99)
    done = {} if glg_results is None or not len(glg_results) else {int(r.game_number): r for r in glg_results.itertuples()}
    uids = P[P.active & (P.pos != "G")].player_uid.values
    ui = {u: i for i, u in enumerate(uids)}
    mult = player_multipliers(P, st, n)
    tot_g = np.zeros((n, len(uids)), dtype=np.int32)
    tot_a = np.zeros((n, len(uids)), dtype=np.int32)
    games_played = np.zeros((n, 4), dtype=np.int8)
    wins = {t: np.zeros(n) for t in NATIONS}
    gd = {t: np.zeros(n) for t in NATIONS}
    gf = {t: np.zeros(n) for t in NATIONS}
    pool = schedule[schedule.stage.str.startswith("group")]

    def add(s, rows=None, src=None):
        rows = np.arange(n) if rows is None else rows
        src = rows if src is None else src
        for side in ("home", "away"):
            for j, u in enumerate(s[f"{side}_uids"]):
                tot_g[rows, ui[u]] += s[f"{side}_goals"][src, j]
                tot_a[rows, ui[u]] += s[f"{side}_assists"][src, j]

    for r in pool.itertuples():
        h, a = ALIAS.get(r.home_team, r.home_team), ALIAS.get(r.away_team, r.away_team)
        if int(r.game_number) in done:
            d = done[int(r.game_number)]
            gh, ga = np.full(n, int(d.home_goals)), np.full(n, int(d.away_goals))
        else:
            s = game_with_players(T, P, env, st, h, a, int(r.game_number), n, mult)
            gh, ga = s["gh"], s["ga"]
            add(s)
        wins[h] += gh > ga; wins[a] += ga > gh
        gd[h] += gh - ga; gd[a] += ga - gh
        gf[h] += gh; gf[a] += ga
    key = np.stack([wins[t] * 1e6 + (gd[t] + 500) * 1e3 + gf[t] + rng.random(n) for t in NATIONS], axis=1)
    order = np.argsort(-key, axis=1)
    pair = {}
    for i in range(4):
        for j in range(i + 1, 4):
            pair[(i, j)] = game_with_players(T, P, env, st, NATIONS[i], NATIONS[j], 100 + i * 4 + j, n, mult)

    def play(x, y, perm=None):
        win = np.empty(n, dtype=int)
        for (i, j), s in pair.items():
            m = ((x == i) & (y == j)) | ((x == j) & (y == i))
            if not m.any():
                continue
            idx = np.where(m)[0]
            src = idx if perm is None else perm[idx]
            hw = s["gh"][src] > s["ga"][src]
            win[idx] = np.where(hw, i, j)
            add(s, idx, src)
        return win
    s1, s2, s3, s4 = order[:, 0], order[:, 1], order[:, 2], order[:, 3]
    # knockout games already known: use the entered matchups and fix completed results
    ko = {int(r.game_number): r for r in schedule.itertuples() if str(r.stage).lower().startswith(("semi", "final"))}
    idx_of = {t: i for i, t in enumerate(NATIONS)}

    def known(gnum):
        r = ko.get(gnum)
        if r is None:
            return None
        h_, a_ = ALIAS.get(str(r.home_team), str(r.home_team)), ALIAS.get(str(r.away_team), str(r.away_team))
        h_ = getattr(r, "home", h_) if h_ == "TBD" else h_
        a_ = getattr(r, "away", a_) if a_ == "TBD" else a_
        return (h_, a_) if h_ in idx_of and a_ in idx_of else None

    def fixed_winner(gnum):
        d = done.get(gnum)
        if d is None or str(d.home) not in idx_of:
            return None
        return idx_of[d.home] if d.home_goals > d.away_goals else idx_of[d.away]
    semis = sorted(g_ for g_ in ko if str(ko[g_].stage).lower().startswith("semi"))
    final_g = next((g_ for g_ in ko if str(ko[g_].stage).lower().startswith("final")), None)
    winners = []
    for gnum, (x_, y_) in zip(semis, ((s1, s4), (s2, s3))):
        km = known(gnum)
        if km:
            x_, y_ = np.full(n, idx_of[km[0]]), np.full(n, idx_of[km[1]])
        fw = fixed_winner(gnum)
        winners.append(np.full(n, fw) if fw is not None else play(x_, y_))
    while len(winners) < 2:
        winners.append(play(s1, s4) if not winners else play(s2, s3))
    w1, w2 = winners
    fw = fixed_winner(final_g) if final_g else None
    win_f = np.full(n, fw) if fw is not None else play(w1, w2, rng.permutation(n))     # final: independent draw
    teams = pd.DataFrame({"nation": NATIONS,
                          "p_top_seed": [(order[:, 0] == i).mean() for i in range(4)],
                          "p_reach_final": [((w1 == i) | (w2 == i)).mean() for i in range(4)],
                          "p_champion": [(win_f == i).mean() for i in range(4)],
                          "exp_pool_wins": [wins[t].mean() for t in NATIONS]})
    pts = tot_g + tot_a

    def leader(x):
        mx = x.max(axis=1, keepdims=True)
        tie = (x == mx)
        return (tie / tie.sum(axis=1, keepdims=True)).mean(0)      # dead-heat split
    PI = P.set_index("player_uid")
    players = pd.DataFrame({"player_uid": uids, "player": PI.loc[uids, "player"].values, "nation": PI.loc[uids, "nation"].values,
                            "exp_goals": tot_g.mean(0), "exp_assists": tot_a.mean(0), "exp_points": pts.mean(0),
                            "p_top_goalscorer": leader(tot_g), "p_top_points": leader(pts)})
    return teams, players, dict(goals=tot_g, assists=tot_a, uids=uids)


# ----------------------------------------------------------------------------- pricing
def to_american(p):
    p = float(np.clip(p, 1e-4, 1 - 1e-4))
    return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p


def fmt_american(p):
    o = to_american(p)
    return f"{o:+.0f}" if abs(o) < 100000 else ("-99999" if o < 0 else "+99999")


def power_margin(probs, margin):
    """Power method: book probabilities q_i = p_i ** k with k < 1 chosen so sum(q) = 1 + margin.
    Keeps favourites below 100% and puts more of the margin on longshots (the usual book shape)."""
    p = np.clip(np.asarray(probs, dtype=float), 1e-6, 1 - 1e-9)
    target = p.sum() * (1 + margin) if abs(p.sum() - 1) > 1e-6 else 1 + margin
    if margin <= 0:
        return p
    lo, hi = 1e-3, 1.0
    for _ in range(60):
        k = (lo + hi) / 2
        if (p ** k).sum() > target:
            lo = k
        else:
            hi = k
    return np.clip(p ** ((lo + hi) / 2), 1e-6, 0.9999)


def cap_prob(p, max_american):
    """Book probability floor implied by a maximum price (e.g. +25000 -> 0.40%)."""
    return 100.0 / (max_american + 100.0)


def book_probs(p, margin, max_american=None, multiway=True):
    """Margined book probabilities: power method (whole market when multiway, else two-way), then a price cap."""
    p = np.asarray(p, dtype=float)
    q = power_margin(p, margin) if multiway else np.array([margined([x], margin)[0] for x in p])
    if max_american:
        q = np.maximum(q, cap_prob(p, max_american))
    return q


def margined(probs, margin):
    """Two-way when one probability is given (complement added), otherwise the full market."""
    p = np.atleast_1d(np.asarray(probs, dtype=float))
    if len(p) == 1:
        return power_margin([p[0], 1 - p[0]], margin)[:1]
    return power_margin(p, margin)


def price(p_true, margin):
    """True prob -> fair and margined prices (American + decimal) for one side of a two-way market."""
    pm = float(margined([p_true, 1 - p_true], margin)[0])
    return {"true_p": float(p_true), "fair_am": fmt_american(p_true), "fair_dec": 1 / max(float(p_true), 1e-4),
            "book_p": pm, "book_am": fmt_american(pm), "book_dec": 1 / pm}




def load_overrides():
    from glg import store
    return store.read_json("overrides.json", {})


def save_overrides(o):
    from glg import store
    store.write_json("overrides.json", o)
