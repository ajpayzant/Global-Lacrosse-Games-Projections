import pandas as pd
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
sch = C.schedule()
C.page("Player Projections", "Per-game projections for every scheduled game · ratings and where they come from")

games = [r for r in sch.itertuples() if r.home != "TBD"]
f1, f2, f3, f4 = st.columns([1.6, 1.4, 1.4, 1.2])
gsel = f1.selectbox("Game", ["All scheduled games"] + [f"G{int(r.game_number)} · {r.home} vs {r.away}" for r in games])
teams = f2.pills("Teams", C.NATIONS, selection_mode="multi", default=C.NATIONS)
pos = f3.pills("Role", ["A", "M", "SSDM", "D"], selection_mode="multi", default=["A", "M", "SSDM", "D"])
search = f4.text_input("Search player", "", placeholder="Search…")

rows = []
PI = P.set_index("player_uid")
for r in games:
    tag = f"G{int(r.game_number)} · {r.home} vs {r.away}"
    if gsel != "All scheduled games" and gsel != tag:
        continue
    sim = C.game(settings, r.home, r.away, int(r.game_number))
    for side in ("home", "away"):
        opp = r.away if side == "home" else r.home
        G, A = sim[f"{side}_goals"], sim[f"{side}_assists"]
        for j, u in enumerate(sim[f"{side}_uids"]):
            g, a = G[:, j], A[:, j]
            rows.append({"Game": f"G{int(r.game_number)}", "Team": sim[side], "Opp": C.ABBR[opp], "Player": PI.loc[u, "player"],
                         "Role": PI.loc[u, "pos"], "G": g, "A": a})
df = pd.DataFrame(rows)
df = df[df.Team.isin(teams or C.NATIONS) & df.Role.isin(pos or ["A", "M", "SSDM", "D"])]
if search:
    df = df[df.Player.str.contains(search, case=False)]

tab1, tab2 = st.tabs(["Game projections", "Ratings & data sources"])
with tab1:
    out = []
    m = disp["margins"]["props"]
    for r in df.itertuples():
        g, a = r.G, r.A
        pts = g + a
        row = {"Game": r.Game, "Team": C.ABBR[r.Team], "Opp": r.Opp, "Player": r.Player, "Role": r.Role,
               "G": g.mean(), "A": a.mean(), "Pts": pts.mean()}
        if disp["view"] == "Projections":
            row.update({"G 2+": (g >= 2).mean(), "G 3+": (g >= 3).mean(), "Pts 3+": (pts >= 3).mean(), "Pts 5+": (pts >= 5).mean()})
        else:
            for lbl, x, L in (("G o1.5", g, 1.5), ("G o2.5", g, 2.5), ("Pts o2.5", pts, 2.5), ("Pts o4.5", pts, 4.5)):
                pf = C.price_fields((x > L).mean(), disp, m)
                for k_ in ("Fair", "Margined"):
                    if k_ in pf:
                        row[f"{lbl} {k_}"] = pf[k_]
        out.append(row)
    o = pd.DataFrame(out).sort_values(["Pts"], ascending=False)
    fmt = {"G": "{:.2f}", "A": "{:.2f}", "Pts": "{:.2f}", **{c: "{:.0%}" for c in ["G 2+", "G 3+", "Pts 3+", "Pts 5+"] if c in o}}
    sty = o.style.format(fmt).bar(subset=["Pts"], color="#BFD4FF", vmin=0)
    st.dataframe(sty, hide_index=True, width="stretch", height=760)

with tab2:
    cols = {"player": "Player", "nation": "Team", "listed_pos": "Listed", "pos": "Role", "prior_kind": "Prior source",
            "n10": "10v10 GP", "nll_gp": "NLL GP", "cs_games": "CS GP", "intl_games": "Intl GP", "glg_games": "GLG GP",
            "prior_used_g": "Prior G/gm", "talent_g": "Rating G/gm", "share_g": "Goal share", "talent_a": "Rating A/gm",
            "share_a": "Assist share", "two_pt_factor": "No-2pt adj"}
    r = P[P.nation.isin(teams or C.NATIONS)][list(cols)].rename(columns=cols)
    if search:
        r = r[r.Player.str.contains(search, case=False)]
    r = r.sort_values(["Team", "Rating G/gm"], ascending=[True, False])
    st.dataframe(r.style.format({"10v10 GP": "{:.0f}", "NLL GP": "{:.0f}", "CS GP": "{:.0f}", "Intl GP": "{:.0f}", "GLG GP": "{:.0f}",
                                 "Prior G/gm": "{:.2f}", "Rating G/gm": "{:.2f}", "Rating A/gm": "{:.2f}",
                                 "Goal share": "{:.1%}", "Assist share": "{:.1%}", "No-2pt adj": "{:.2f}"}, na_rep="–")
                 .bar(subset=["Goal share"], color="#BFD4FF", vmin=0),
                 hide_index=True, width="stretch", height=700)
    st.caption("Ratings: goals/assists per game at Championship Series scale (≈18.9 team goals). Role = position used by the model "
               "(defenders/SSDMs who score above their position's range are rated as the next role up). Shares decide each "
               "player's slice of simulated team goals.")
