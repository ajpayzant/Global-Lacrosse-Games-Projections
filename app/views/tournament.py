import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
teams, players, raw = C.tournament(settings)
mf, mp = disp["margins"]["futures"], disp["margins"]["props"]
mpf, cap = disp["margins"]["player_futures"], disp["margins"]["max_odds"]
C.page("Tournament", "Pool play (2 games each) → semifinals 1v4 / 2v3 → final · completed games fixed at their real scores")

# ---------------- team futures
cc = st.columns([1.1, 1])
with cc[0]:
    st.markdown("### Team futures")
    mkt = st.segmented_control("Futures market", ["Winner", "Reach final", "Top seed"], default="Winner", label_visibility="collapsed") or "Winner"
    col = {"Winner": "p_champion", "Reach final": "p_reach_final", "Top seed": "p_top_seed"}[mkt]
    tt = teams.sort_values(col, ascending=False)
    book = C.E.book_probs(tt[col].values, mf, cap, multiway=(mkt != "Reach final"))
    rows = []
    for r, b in zip(tt.itertuples(), book):
        base = {"Team": r.nation, "Exp pool wins": r.exp_pool_wins}
        if disp["view"] == "Projections":
            rows.append({**base, "Probability": getattr(r, col)})
        else:
            rows.append({**base, **C.price_fields(getattr(r, col), disp, mf, b)})
    d = pd.DataFrame(rows)
    st.dataframe(d.style.format({"Probability": "{:.1%}", "True %": "{:.1%}", "Exp pool wins": "{:.2f}"}), hide_index=True, width="stretch")
with cc[1]:
    t = teams.sort_values("p_champion")
    fig = go.Figure()
    for col_, nm, op in (("p_champion", "Win", 1.0), ("p_reach_final", "Final", 0.45)):
        fig.add_bar(y=t.nation, x=t[col_], orientation="h", name=nm, marker_color=[C.COLOR[n] for n in t.nation], opacity=op)
    C.fig_layout(fig, 320, "Win / reach final probability", legend_below=True, barmode="overlay", xaxis_tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

# ---------------- player tournament markets
st.markdown("### Player tournament markets")
f1, f2, f3 = st.columns([1.6, 1.4, 1.2])
kind = f1.segmented_control("Player market", ["Top goalscorer", "Top points", "Goals O/U", "Points O/U"], default="Top goalscorer",
                            label_visibility="collapsed") or "Top goalscorer"
tsel = f2.pills("Teams", C.NATIONS, selection_mode="multi", default=C.NATIONS, label_visibility="collapsed")
search = f3.text_input("Search", "", placeholder="Search player…", label_visibility="collapsed")
G, A, uids = raw["goals"], raw["assists"], raw["uids"]
pl = players.copy()
if kind in ("Top goalscorer", "Top points"):
    col = "p_top_goalscorer" if kind == "Top goalscorer" else "p_top_points"
    pl = pl.sort_values(col, ascending=False)
    pl["book"] = C.E.book_probs(pl[col].values, mpf, cap)    # the whole field is one market; capped at the max price
    view = pl[pl.nation.isin(tsel or C.NATIONS)]
    if search:
        view = view[view.player.str.contains(search, case=False)]
    rows = []
    for r in view.itertuples():
        base = {"Player": r.player, "Team": C.ABBR[r.nation], "Exp goals": r.exp_goals, "Exp points": r.exp_points}
        rows.append({**base, "Probability": getattr(r, col)} if disp["view"] == "Projections"
                    else {**base, **C.price_fields(getattr(r, col), disp, mf, r.book)})
    d = pd.DataFrame(rows)
    st.dataframe(d.style.format({"Probability": "{:.1%}", "True %": "{:.1%}", "Exp goals": "{:.1f}", "Exp points": "{:.1f}"}),
                 hide_index=True, width="stretch", height=640)
    st.caption(f"Dead heats split. Players play 3 games, or 4 if their team reaches the final. Margin {mpf:.0%} (power method), "
               f"prices capped at +{cap:,}. 40,000 tournament simulations; true probabilities below ~0.05% are not reliable.")
else:
    X = G if kind == "Goals O/U" else G + A
    PI = P.set_index("player_uid")
    rows = []
    for j, u in enumerate(uids):
        if PI.loc[u, "nation"] not in (tsel or C.NATIONS) or (search and search.lower() not in PI.loc[u, "player"].lower()):
            continue
        x = X[:, j]
        L = float(np.floor(np.median(x))) + 0.5
        p = float((x > L).mean())
        row = {"Player": PI.loc[u, "player"], "Team": C.ABBR[PI.loc[u, "nation"]], "Expected": x.mean(), "Line": L}
        if disp["view"] == "Projections":
            row.update({"P(over)": p, "10th pct": np.percentile(x, 10), "90th pct": np.percentile(x, 90)})
        else:
            for side, q in (("Over", p), ("Under", 1 - p)):
                pf = C.price_fields(q, disp, mp)
                for k_ in ("Fair", "Margined"):
                    if k_ in pf:
                        row[f"{side} {k_}"] = pf[k_]
        rows.append(row)
    d = pd.DataFrame(rows).sort_values("Expected", ascending=False)
    st.dataframe(d.style.format({"Expected": "{:.2f}", "P(over)": "{:.1%}", "10th pct": "{:.0f}", "90th pct": "{:.0f}"}),
                 hide_index=True, width="stretch", height=640)
