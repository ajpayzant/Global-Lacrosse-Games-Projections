import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
C.page("Teams & Rosters", "Team strength components · roster continuity vs past international squads · player roles")

# ---------------- strength overview
t = T.copy()
cols = st.columns(4)
for c, n in zip(cols, t.sort_values("strength", ascending=False).index):
    r = t.loc[n]
    c.markdown(f"""<div class='card'><div style='display:flex;gap:10px;align-items:center'>{C.badge(n, 38)}
      <div><div style='font-weight:700'>{n}</div><div class='note'>overall {r.strength:+.2f}</div></div></div>
      <div class='kpis' style='grid-template-columns:1fr 1fr;margin-top:10px'>
        <div class='kpi'><div class='l'>Attack</div><div class='v'>{r.att:+.2f}</div></div>
        <div class='kpi'><div class='l'>Defence</div><div class='v'>{r['def']:+.2f}</div></div>
        <div class='kpi'><div class='l'>Roster talent</div><div class='v'>{r.glg_talent:.1f}</div></div>
        <div class='kpi'><div class='l'>Continuity</div><div class='v'>{r.mean_continuity:.0%}</div></div>
      </div></div>""", unsafe_allow_html=True)
st.write("")
st.markdown("### How each rating is built")
b = pd.DataFrame({
    "Talent attack": t.talent_att, "Results attack (centred)": t.cres_att - t.cres_att.mean(),
    "Results credibility": t.credibility, "Attack used": t.att,
    "Talent defence": t.talent_def, "Results defence (centred)": t.cres_def - t.cres_def.mean(), "Defence used": t["def"],
    "Effective results games": t.eff_results_games, "Usage flattening β": t.usage_beta})
st.dataframe(b.style.format("{:+.3f}", subset=[c for c in b.columns if "games" not in c and "β" not in c and "credibility" not in c])
             .format("{:.2f}", subset=["Effective results games", "Usage flattening β", "Results credibility"]), width="stretch")
st.caption("Attack used = talent attack + credibility × (results attack − talent attack); credibility = effective results games ÷ "
           "(games + k). Effective games count each past game by lineup continuity × opponent continuity × recency, and down-weight "
           "blowouts. Units: +0.10 ≈ +10.5% goals scored (attack) or −9.5% conceded (defence).")

# ---------------- continuity
st.markdown("### Roster continuity vs 2025–26 international squads")
con = duckdb.connect(str(C.ROOT / "warehouse" / "sixes.duckdb"), read_only=True)
lu = con.execute("""select p.team nation, g.competition, p.player_uid from fact.sixes_player_game p join fact.sixes_game g using(game_key)
                    where p.source='intl' and p.team in ('USA','Canada','Haudenosaunee','Australia')""").df().drop_duplicates()
con.close()
glg = set(P.player_uid)
rows = []
for (n, comp), d in lu.groupby(["nation", "competition"]):
    on = d.player_uid.isin(glg)
    rows.append({"Team": n, "Event": comp, "Players used": len(d), "On GLG roster": int(on.sum()),
                 "New to this GLG roster": int((P.nation == n).sum() - on.sum()),
                 "GLG talent present": P[P.player_uid.isin(d.player_uid[on])].talent_g.sum() / P[P.nation == n].talent_g.sum()})
st.dataframe(pd.DataFrame(rows).style.format({"GLG talent present": "{:.0%}"}).bar(subset=["GLG talent present"], color="#BFD4FF", vmin=0, vmax=1),
             hide_index=True, width="stretch")

# ---------------- roles (computed live from the warehouse + current model, so they never go stale)
st.markdown("### Player roles: pro club vs national team vs GLG projection")
nat = st.segmented_control("Team", C.NATIONS, default="USA", label_visibility="collapsed") or "USA"


@st.cache_data(show_spinner=False)
def role_inputs():
    con = duckdb.connect(str(C.ROOT / "warehouse" / "sixes.duckdb"), read_only=True)
    pll = con.execute("""with p as (select 'PLL:'||player_id uid, season, game_id, team_id, goals, assists, shots from fact.pll10_player_game),
                              t as (select game_id, team_id, goals tg, shots ts from fact.pll10_team_game)
                         select uid player_uid, count(*) pll_gp, max(season) last_pll_season, sum(goals+assists)/count(*) pll_ppg,
                                sum(goals)/sum(tg) club_goal_share, sum(shots)/sum(ts) club_shot_share
                         from p join t using (game_id, team_id) group by 1""").df()
    nll = con.execute("""select player_uid, any_value(position) nll_pos, sum(points)/sum(games_played) nll_ppg
                         from fact.nll_player_season where season >= '2024-25' and is_playoffs = 0 group by 1""").df()
    sh = con.execute("""select p.player_uid, p.source, sum(p.goals)/sum(t.goals) as goal_share from fact.sixes_player_game p
                        join fact.sixes_team_game t using (game_key, team) group by 1, 2""").df()
    con.close()
    sh = sh.pivot(index="player_uid", columns="source", values="goal_share").rename(columns={"pll_cs": "cs_goal_share", "intl": "intl_goal_share"})
    return pll, nll, sh.reset_index()


pll, nll, sh = role_inputs()
d = P[(P.nation == nat) & (P.pos != "G")].merge(pll, on="player_uid", how="left").merge(nll, on="player_uid", how="left").merge(sh, on="player_uid", how="left")
for c in ("cs_goal_share", "intl_goal_share"):
    if c not in d:
        d[c] = np.nan
flag = np.full(len(d), "", dtype=object)
flag[(d.intl_goal_share.notna() & (d.share_g < 0.6 * d.intl_goal_share)).values] = "smaller role than at past intl event"
flag[(d.intl_goal_share.notna() & (d.share_g > 1.6 * d.intl_goal_share)).values] = "bigger role than at past intl event"
flag[(d.intl_goal_share.isna() & d.club_goal_share.notna() & (d.share_g > 1.6 * d.club_goal_share * 10 / 11)).values] = "bigger role than at PLL club"
d["flag"] = flag
show = d[["player", "listed_pos", "pos", "prior_kind", "pll_gp", "last_pll_season", "pll_ppg", "club_goal_share", "club_shot_share",
          "nll_pos", "nll_ppg", "cs_goal_share", "intl_goal_share", "share_g", "flag"]].rename(columns={
    "player": "Player", "listed_pos": "Listed", "pos": "Role", "prior_kind": "Source", "pll_gp": "PLL GP", "last_pll_season": "Last PLL season",
    "pll_ppg": "PLL pts/gm", "club_goal_share": "PLL club goal share", "club_shot_share": "PLL club shot share", "nll_pos": "NLL pos",
    "nll_ppg": "NLL pts/gm", "cs_goal_share": "Champ Series share", "intl_goal_share": "Past intl share", "share_g": "GLG projected share",
    "flag": "Flag"}).sort_values("GLG projected share", ascending=False)
pct = ["PLL club goal share", "PLL club shot share", "Champ Series share", "Past intl share", "GLG projected share"]
st.dataframe(show.style.format({**{c: "{:.1%}" for c in pct}, "NLL pts/gm": "{:.2f}", "PLL pts/gm": "{:.2f}", "PLL GP": "{:.0f}",
                                "Last PLL season": "{:.0f}"}, na_rep="–")
             .bar(subset=["GLG projected share"], color="#BFD4FF", vmin=0), hide_index=True, width="stretch", height=520)
st.caption("PLL columns cover every PLL season 2019–26 (e.g. Lyle Thompson: 19 games in 2021–22, his last PLL seasons). Club shares are "
           "over 10 field players and GLG shares over 11. NLL pts/gm is regular season 2024-25 onward. Flags mark big role changes; they "
           "are informational and do not change projections.")
