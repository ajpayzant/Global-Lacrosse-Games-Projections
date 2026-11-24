import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
sch = C.schedule()
res = C.results()
done = res.set_index("game_number") if len(res) else None
C.page("Game Center", f"Environment {env[0]:.2f} goals/team (±{env[1]:.0%}) · {disp['view']} view")

# ---------------- game selector
games = [r for r in sch.itertuples() if r.home != "TBD"]
labels = {f"G{int(r.game_number)} · {pd.Timestamp(r.date):%a %b %d} {r.local_time_ET} · {r.home} vs {r.away} · {r.stage_lbl}": (r.home, r.away, int(r.game_number)) for r in games}
for i, x in enumerate(C.NATIONS):
    for y in C.NATIONS[i + 1:]:
        labels[f"Hypothetical · {x} vs {y}"] = (x, y, None)
c1, c2 = st.columns([3, 1])
pick = c1.selectbox("Game", list(labels), label_visibility="collapsed")
h, a, gn = labels[pick]
row = next((r for r in games if gn is not None and int(r.game_number) == gn), None)
sim = C.game(settings, h, a, gn)               # always simulated in the scheduled orientation (game overrides are by side)
final = None
if done is not None and gn in done.index:
    final = f"{done.loc[gn, 'home']} {int(done.loc[gn, 'home_goals'])} – {int(done.loc[gn, 'away_goals'])} {done.loc[gn, 'away']}"
if c2.toggle("Swap sides", False):
    h, a = a, h
    sim = C.swap_sim(sim)
g = C.E.game_summary(sim)
sp, tl = C.E.main_lines(sim)
C.match_card(h, a, g, sp, tl, final)
st.write("")

section = st.segmented_control("Section", ["Game lines", "Player props", "Lineups", "Distributions"], default="Game lines",
                               label_visibility="collapsed") or "Game lines"
m_game, m_props = disp["margins"]["game"], disp["margins"]["props"]

if section == "Game lines":
    if disp["view"] == "Prices":
        gh, ga = sim["gh"], sim["ga"]
        marg, tot = gh - ga, gh + ga
        ch, ca = C.COLOR.get(h), C.COLOR.get(a)
        ph = float((gh > ga).mean())
        # ---- headline markets
        c1, c2, c3 = st.columns(3)
        with c1:
            C.market_card("Moneyline", [C.tile_html(h, ph, disp, m_game, color=ch), C.tile_html(a, 1 - ph, disp, m_game, color=ca)])
        with c2:
            pc = float((marg + sp > 0).mean())
            fav_, dog_ = (h, a) if sp < 0 else (a, h)
            C.market_card(f"Spread · main {fav_} {-abs(sp):+.1f}",
                          [C.tile_html(f"{h} {sp:+.1f}", pc, disp, m_game, color=ch),
                           C.tile_html(f"{a} {-sp:+.1f}", 1 - pc, disp, m_game, color=ca)])
        with c3:
            po = float((tot > tl).mean())
            C.market_card(f"Total · main {tl}", [C.tile_html(f"Over {tl}", po, disp, m_game), C.tile_html(f"Under {tl}", 1 - po, disp, m_game)])
        st.write("")
        # ---- alternate lines with ladder charts
        a1, a2 = st.columns(2)
        with a1:
            lines_sp = [v for v in (x + 0.5 for x in range(int(np.floor(sp)) - 7, int(np.floor(sp)) + 8)) if abs(v) >= C.E.MIN_SPREAD]
            lab_sp = [f"{v:+.1f}" for v in lines_sp]
            Ls = float(st.select_slider(f"Alternate spread ({h})", options=lab_sp, value=f"{sp:+.1f}" if f"{sp:+.1f}" in lab_sp else lab_sp[len(lab_sp) // 2]))
            pc = float((marg + Ls > 0).mean())
            C.market_card(f"Spread {h} {Ls:+.1f}", [C.tile_html(f"{h} {Ls:+.1f}", pc, disp, m_game, color=ch),
                                                     C.tile_html(f"{a} {-Ls:+.1f}", 1 - pc, disp, m_game, color=ca)])
            lad = go.Figure(go.Scatter(x=lines_sp, y=[(marg + L_ > 0).mean() for L_ in lines_sp], mode="lines+markers", line=dict(color=ch)))
            lad.add_vline(x=Ls, line_dash="dot", line_color="#94A3B8")
            C.fig_layout(lad, 230, None, yaxis_tickformat=".0%", xaxis_title=f"{h} spread", yaxis_title="cover %")
            st.plotly_chart(lad, width="stretch", key="lad_sp")
        with a2:
            lines_t = [x + 0.5 for x in range(int(np.floor(tl)) - 7, int(np.floor(tl)) + 7)]
            Lt = st.select_slider("Alternate total", options=lines_t, value=tl if tl in lines_t else lines_t[7])
            po = float((tot > Lt).mean())
            C.market_card(f"Total {Lt}", [C.tile_html(f"Over {Lt}", po, disp, m_game), C.tile_html(f"Under {Lt}", 1 - po, disp, m_game)])
            lad = go.Figure(go.Scatter(x=lines_t, y=[(tot > L_).mean() for L_ in lines_t], mode="lines+markers", line=dict(color="#0B5FFF")))
            lad.add_vline(x=Lt, line_dash="dot", line_color="#94A3B8")
            C.fig_layout(lad, 230, None, yaxis_tickformat=".0%", xaxis_title="total line", yaxis_title="over %")
            st.plotly_chart(lad, width="stretch", key="lad_tot")
        # ---- team totals + regulation 3-way
        b1, b2, b3 = st.columns([1, 1, 1.4])
        for col, g_, nm, cl in ((b1, gh, h, ch), (b2, ga, a, ca)):
            with col:
                med = float(np.round(np.median(g_))) + 0.5
                L_ = st.select_slider(f"{nm} team total", options=[med + d for d in range(-4, 5)], value=med, key=f"tt_{nm}")
                pov = float((g_ > L_).mean())
                C.market_card(f"{nm} team total {L_}", [C.tile_html(f"Over {L_}", pov, disp, m_game, color=cl),
                                                         C.tile_html(f"Under {L_}", 1 - pov, disp, m_game, color=cl)])
        with b3:
            rh, ra = sim["reg_h"], sim["reg_a"]
            probs = [float((rh > ra).mean()), float((rh == ra).mean()), float((ra > rh).mean())]
            book = C.E.power_margin(probs, m_game)
            st.write("")
            st.write("")
            C.market_card("Regulation result (3-way)", [C.tile_html(h, probs[0], disp, m_game, book[0], ch),
                                                         C.tile_html("Tie → OT", probs[1], disp, m_game, book[1]),
                                                         C.tile_html(a, probs[2], disp, m_game, book[2], ca)], cols=3)
        with st.expander("All game markets as a table"):
            st.dataframe(C.style_prices(C.game_markets(sim, disp, m_game)), hide_index=True, width="stretch", height=520)
        st.caption(f"Fair = 1 / true probability. Book = margined at {m_game:.1%} (power method). The bar under each price is "
                   "the true probability. Odds format and fair / book display are in the sidebar.")
    else:
        m, tot = sim["gh"] - sim["ga"], sim["gh"] + sim["ga"]
        proj = pd.DataFrame([
            {"Metric": f"{h} win probability", "Value": f"{g['p_home']:.1%}"},
            {"Metric": f"{a} win probability", "Value": f"{g['p_away']:.1%}"},
            {"Metric": "Projected score", "Value": f"{g['exp_home']:.2f} – {g['exp_away']:.2f}"},
            {"Metric": "Expected margin (mean / median)", "Value": f"{g['exp_margin']:+.2f} / {g['median_margin']:+.0f}"},
            {"Metric": "Expected total", "Value": f"{g['exp_total']:.2f}"},
            {"Metric": f"P({h} by 3+)", "Value": f"{(m >= 3).mean():.1%}"},
            {"Metric": f"P({a} by 3+)", "Value": f"{(m <= -3).mean():.1%}"},
            {"Metric": "P(one-goal game)", "Value": f"{(np.abs(m) == 1).mean():.1%}"},
            {"Metric": "P(overtime)", "Value": f"{g['p_ot']:.1%}"},
            {"Metric": "Team strengths (log)", "Value": f"{h} {T.loc[h, 'strength']:+.2f} · {a} {T.loc[a, 'strength']:+.2f}"}])
        cc = st.columns([1, 1])
        cc[0].dataframe(proj, hide_index=True, width="stretch", height=390)
        sc = pd.crosstab(np.clip(sim["gh"], 5, 30), np.clip(sim["ga"], 5, 30), normalize=True)
        fig = go.Figure(go.Heatmap(z=sc.values, x=sc.columns, y=sc.index, colorscale="Blues",
                                   hovertemplate=h + " %{y} – " + a + " %{x}: %{z:.2%}<extra></extra>"))
        C.fig_layout(fig, 400, "Final score probability", xaxis_title=a, yaxis_title=h)
        cc[1].plotly_chart(fig, width="stretch")

elif section == "Player props":
    PI = P.set_index("player_uid")
    f1, f2, f3, f4 = st.columns([1.1, 1.3, 1.6, 1.1])
    stat = f1.segmented_control("Market", ["Goals", "Assists", "Points"], default="Points") or "Points"
    team = f2.segmented_control("Team", ["Both", C.ABBR[h], C.ABBR[a]], default="Both") or "Both"
    line_opts = {"Goals": [0.5, 1.5, 2.5, 3.5, 4.5], "Assists": [0.5, 1.5, 2.5, 3.5],
                 "Points": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]}[stat]
    L = f3.select_slider("Line", options=line_opts, value={"Goals": 1.5, "Assists": 0.5, "Points": 2.5}[stat])
    sort = f4.selectbox("Sort", ["Projection", "Over %", "Player"])
    rows, dists = [], {}
    for side in ("home", "away"):
        if team != "Both" and C.ABBR[sim[side]] != team:
            continue
        G, A = sim[f"{side}_goals"], sim[f"{side}_assists"]
        for j, u in enumerate(sim[f"{side}_uids"]):
            x = {"Goals": G[:, j], "Assists": A[:, j], "Points": G[:, j] + A[:, j]}[stat]
            po = float((x > L).mean())
            r = {"Team": C.ABBR[sim[side]], "Player": PI.loc[u, "player"], "Role": PI.loc[u, "pos"], "Proj": float(x.mean()), "Over %": po}
            if disp["view"] == "Prices":
                fo, fu = C.price_fields(po, disp, m_props), C.price_fields(1 - po, disp, m_props)
                for side_, f_ in (("Over", fo), ("Under", fu)):
                    for k_, lbl_ in (("Fair", "fair"), ("Margined", "book")):
                        if k_ in f_:
                            r[f"{side_} {lbl_}"] = f_[k_]
            rows.append(r)
            dists[PI.loc[u, "player"]] = (sim[side], G[:, j], A[:, j])
    df = pd.DataFrame(rows)
    df = df.sort_values({"Projection": "Proj", "Over %": "Over %", "Player": "Player"}[sort], ascending=(sort == "Player"))
    left, right = st.columns([1.55, 1])
    with left:
        st.markdown(f"**{stat} — over {L}**")
        st.dataframe(df, hide_index=True, width="stretch", height=min(42 + 35 * len(df), 760),
                     column_config={"Proj": st.column_config.NumberColumn(f"Proj {stat.lower()}", format="%.2f"),
                                    "Over %": st.column_config.ProgressColumn(f"P(over {L})", min_value=0, max_value=1, format="percent")})
    with right:
        who = st.selectbox("Player detail", list(df.Player))
        nat, G_, A_ = dists[who]
        X = {"Goals": G_, "Assists": A_, "Points": G_ + A_}[stat]
        xs = np.arange(0, max(int(np.percentile(X, 99.5)), 3) + 1)
        fig = go.Figure(go.Bar(x=xs, y=[(X == v).mean() for v in xs],
                               marker_color=[C.COLOR.get(nat) if v > L else "#CBD5E1" for v in xs]))
        C.fig_layout(fig, 260, f"{who}: {stat.lower()} distribution (over {L} in colour)", yaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch", key="pdist")
        lad = []
        for Lx in line_opts:
            po = float((X > Lx).mean())
            r = {"Line": Lx, "Over %": po}
            fo, fu = C.price_fields(po, disp, m_props), C.price_fields(1 - po, disp, m_props)
            for side_, f_ in (("Over", fo), ("Under", fu)):
                for k_, lbl_ in (("Fair", "fair"), ("Margined", "book")):
                    if k_ in f_:
                        r[f"{side_} {lbl_}"] = f_[k_]
            lad.append(r)
        st.dataframe(pd.DataFrame(lad), hide_index=True, width="stretch",
                     column_config={"Over %": st.column_config.ProgressColumn("P(over)", min_value=0, max_value=1, format="percent")})
        st.caption(f"Expected: {G_.mean():.2f} G · {A_.mean():.2f} A · {(G_ + A_).mean():.2f} pts")
    st.caption("Points = goals + assists (no 2-pointers). Only dressed players are listed (12-man game roster). "
               + (f"Book prices margined at {m_props:.1%} (power method, two-way)." if disp["view"] == "Prices" else
                  "Switch the sidebar to Prices for fair / book odds in the board."))

elif section == "Lineups":
    st.markdown("**Game-day lineups** — World Lacrosse Rule 3.1.1 allows **12 players per game** (incl. goalkeepers); the "
                "eligible list is due 20 minutes before the game (Rule 3.1.2). GLG rosters have 13, so one player sits. "
                "Default: 10 field + 2 goalies dressed (the USA/Canada Pan-Am pattern), with the lowest field player on the "
                "Depth Chart sitting. Set the actual scratches here once the list is out.")
    if gn is None:
        st.info("Lineups can be set for scheduled games only (hypothetical matchups use the depth-chart default).")
    else:
        ov = C.E.load_overrides()
        lo = ov.get("lineups", {}).get(str(gn), {})
        cols = st.columns(2)
        new = {}
        for col, nat in zip(cols, (row.home, row.away)):
            q_ = P[(P.nation == nat) & P.active & (P.pos != "G")].sort_values("depth_rank")
            names = dict(zip(q_.player, q_.player_uid))
            default_out = [n for n, u in names.items() if u in C.E.scratched(P, nat, C.E.Settings(**settings), gn)]
            pick_ = col.multiselect(f"{nat}: field players NOT dressed", list(names), default_out, key=f"lu_{gn}_{nat}")
            new[nat] = [names[n] for n in pick_]
            col.caption(f"{len(q_) - len(pick_)} field players dressed" + (" · custom lineup saved" if nat in lo else " · depth-chart default"))
        b1, b2, _ = st.columns([1, 1, 3])
        if b1.button("💾 Save lineups for this game", type="primary"):
            ov.setdefault("lineups", {})[str(gn)] = new
            C.E.save_overrides(ov); st.cache_data.clear(); st.rerun()
        if b2.button("Use depth-chart default"):
            ov.get("lineups", {}).pop(str(gn), None)
            C.E.save_overrides(ov); st.cache_data.clear(); st.rerun()
        st.caption("Scratched players get no props for this game; their share of team goals goes to the dressed players.")

else:
    m, tot = sim["gh"] - sim["ga"], sim["gh"] + sim["ga"]
    cc = st.columns(2)
    xs = np.arange(m.min(), m.max() + 1)
    f1 = go.Figure(go.Bar(x=xs, y=[(m == x).mean() for x in xs], marker_color=[C.COLOR[h] if x > 0 else C.COLOR[a] for x in xs]))
    C.fig_layout(f1, 340, f"Margin ({h} − {a})", yaxis_tickformat=".0%")
    xt = np.arange(tot.min(), tot.max() + 1)
    f2 = go.Figure(go.Bar(x=xt, y=[(tot == x).mean() for x in xt], marker_color="#0B5FFF"))
    f2.add_vline(x=tl, line_dash="dash", line_color="#0F172A", annotation_text=f"main {tl}")
    C.fig_layout(f2, 340, "Total goals", yaxis_tickformat=".0%")
    cc[0].plotly_chart(f1, width="stretch")
    cc[1].plotly_chart(f2, width="stretch")
