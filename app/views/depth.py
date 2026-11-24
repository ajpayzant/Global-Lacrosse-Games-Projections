import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
C.page("Depth Chart", "No minutes or time-on-field exist in any source (PLL, NLL, sixes). Usage is measured instead: club touch share "
       "(time on the ball), shot share and defensive involvement, plus each player's sixes and national-team record.")

con = duckdb.connect(str(C.ROOT / "warehouse" / "sixes.duckdb"), read_only=True)
club = con.execute("""with p as (select 'PLL:'||player_id uid, game_id, team_id, shots, touches, ground_balls gb, caused_turnovers ct, assists
                                 from fact.pll10_player_game where season >= 2024),
                           t as (select game_id, team_id, shots ts, touches tt from fact.pll10_team_game)
                      select uid player_uid, count(*) club_gp, sum(shots)/sum(ts) shot_share, sum(touches)/nullif(sum(tt),0) club_touch_share,
                             (sum(gb)+sum(ct))/count(*) def_events_pg
                      from p join t using (game_id, team_id) group by 1""").df()
nat = con.execute("""select p.player_uid, count(*) nat_gp, sum(p.goals) nat_g, sum(t.goals) nat_tg
                     from fact.sixes_player_game p join fact.sixes_team_game t using (game_key, team)
                     where p.source='intl' group by 1""").df()
con.close()
D = P.merge(club, on="player_uid", how="left").merge(nat, on="player_uid", how="left")
D["nat_share"] = D.nat_g / D.nat_tg

team = st.segmented_control("Team", C.NATIONS, default="USA", label_visibility="collapsed") or "USA"
d = D[D.nation == team].copy()
field = d[d.pos != "G"].copy()

field = field.sort_values("depth_rank").reset_index(drop=True)
ov = C.E.load_overrides()
edited = team in ov.get("depth", {})
st.markdown(f"**{team} depth chart** — " + ("edited (saved)" if edited else "model default (data only)"))
c1, c2 = st.columns([1.45, 1])
with c1:
    tbl = pd.DataFrame({
        "player_uid": field.player_uid, "Depth rank": field.depth_rank.astype(int), "Model rank": field.depth_rank_default.astype(int),
        "Player": field.player, "Role": field.pos, "Dresses (default)": field.dressed_default, "Exp. usage": field.usage_hat,
        "Club touch share": field.club_touch_share, "Club shot share": field.shot_share, "GB+CT / gm": field.def_events_pg,
        "Nat. sixes GP": field.nat_gp, "Nat. sixes goal share": field.nat_share, "Champ Series GP": field.cs_games,
        "Usage override": [ov.get("usage", {}).get(u) for u in field.player_uid],
        "Proj goal share": field.share_g, "Proj assist share": field.share_a})
    ed = st.data_editor(
        tbl, hide_index=True, width="stretch", height=470, key=f"depth_{team}",
        disabled=[c for c in tbl.columns if c not in ("Depth rank", "Usage override")],
        column_config={"player_uid": None,
                       "Depth rank": st.column_config.NumberColumn(min_value=1, max_value=len(tbl), step=1, help="Edit to re-order; ties broken by model rank"),
                       "Exp. usage": st.column_config.NumberColumn(format="percent"),
                       "Usage override": st.column_config.NumberColumn("Usage override (share)", format="percent", min_value=0.0, max_value=0.35,
                                                                       step=0.005, help="Optional: your expected share of team usage, e.g. 0.07 = 7%. Blank = model."),
                       "Club touch share": st.column_config.NumberColumn(format="percent"),
                       "Club shot share": st.column_config.NumberColumn(format="percent"),
                       "GB+CT / gm": st.column_config.NumberColumn(format="%.1f"),
                       "Nat. sixes GP": st.column_config.NumberColumn(format="%.0f"),
                       "Nat. sixes goal share": st.column_config.NumberColumn(format="percent"),
                       "Champ Series GP": st.column_config.NumberColumn(format="%.0f"),
                       "Proj goal share": st.column_config.NumberColumn(format="percent"),
                       "Proj assist share": st.column_config.NumberColumn(format="percent")})
    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button("💾 Save depth chart", type="primary"):
        order = ed.sort_values(["Depth rank", "Model rank"]).player_uid.tolist()
        default = tbl.sort_values("Model rank").player_uid.tolist()
        ov.setdefault("usage", {})
        for r in ed.to_dict("records"):
            ov["usage"].pop(r["player_uid"], None)
            if r["Usage override"] is not None and pd.notna(r["Usage override"]):
                ov["usage"][r["player_uid"]] = float(r["Usage override"])
        ov.setdefault("depth", {})
        if order == default:
            ov["depth"].pop(team, None)
        else:
            ov["depth"][team] = order
        C.E.save_overrides(ov)
        st.cache_data.clear()
        st.rerun()
    if b2.button("Reset to model"):
        ov.get("depth", {}).pop(team, None)
        for u in field.player_uid:
            ov.get("usage", {}).pop(u, None)
        C.E.save_overrides(ov)
        st.cache_data.clear()
        st.rerun()
    g = d[d.pos == "G"]
    st.caption("Goalies: " + ", ".join(g.player) + " (not differentiated - no measurable sixes signal).")
with c2:
    f = go.Figure()
    f.add_bar(y=field.player[::-1], x=field.share_g[::-1], orientation="h", name="Goal share", marker_color=C.COLOR[team])
    f.add_bar(y=field.player[::-1], x=field.share_a[::-1], orientation="h", name="Assist share", marker_color=C.COLOR[team], opacity=0.45)
    C.fig_layout(f, 520, "Projected shares (ordered by depth rank)", legend_below=True, barmode="group", xaxis_tickformat=".0%")
    st.plotly_chart(f, width="stretch")

st.markdown("""
**How usage enters the projections (data-backed):**
- **Club touch share is in the model.** On 146 Championship Series player-events, it adds to the scoring rating when predicting a
  player's sixes goal share. R² rises from 0.607 to 0.624, p = 0.013, with fitted weights 0.754 × rating + 0.449 × usage. At Pan-Am,
  club usage predicted national-team share better than the scoring rating (shot share R² 0.36, touch share 0.28, rating 0.21; n = 16).
- **National-team role.** The combined club signal is shrunk ×0.62 toward the team average, the Pan-Am attenuation; then each
  player's own national-team sixes games update it.
- **Depth chart.** The default order is each player's expected sixes usage from the fitted Championship Series usage model:
  0.69 × rating share + 0.10 × club touch share. Experience and age were tested and add nothing (p = 0.76 and 0.26).
  Moving a player changes his goal and assist share by 0.5 × 0.573 × (usage at the new rank − usage at the model rank).
  - Usage by rank is the measured CS curve: 18%, 15%, 13%, 12%, 10%, 9%, 8%, 6%, 4%, 3%, 2%.
  - 0.573 is the measured value of usage for scoring share (CS, n = 142).
  - ½ weights an assumed rank below observed usage.
  - Shares are then renormalised within the team. Example: moving 3rd → 6th costs about 1.3 points of goal share.
- **Usage override.** Enter a player's expected share of team usage, e.g. 7%. His goal and assist shares move by 0.573 × (your
  usage − model expected usage) at full weight, because it is an explicit usage figure rather than a rank. Teammates are renormalised.
  Use it when the depth chart is not enough, e.g. a player limited by injury or known to play fewer shifts.
- **Display only:** shot share and GB+CT per game are context; they are not tested as predictors.
- **Missing data.** The PLL play-by-play has closest-defender and turnover-attribution fields, but they are empty in every game, so
  defensive involvement is limited to box-score ground balls and caused turnovers. Players with no PLL touch data (non-pros, NLL-only,
  pre-2022) use their rating only.
""")
