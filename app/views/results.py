import json
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
sch = C.schedule()
C.page("Results & Grading", "Snapshot → enter scores → grade")

st.subheader("Automatic results updates")
ls_ = C.S.read_json("live_status.json", None)
if ls_:
    st.success(f"Last update {ls_.get('synced_utc', '?')} UTC · finals applied: {ls_.get('finals_applied') or 'none yet'} · "
               f"player box rows: {ls_.get('box_rows', 0)}"
               + (f" · unmatched players: {', '.join(ls_['unmatched_players'])}" if ls_.get("unmatched_players") else ""))
else:
    st.info("No automatic update has run yet.")
st.caption("The GitHub Action 'GLG results update' scrapes completed games from the PLL stats API every night after the "
           "day's games (and on demand: repo → Actions → GLG results update → Run workflow) and merges finals and player box "
           "scores here. Manual entries below still work and are kept for games the scrape has not finalised.")

st.subheader("1 · Snapshot before each session")
st.caption("Freezes current projections for every un-played game, so grading compares against what we priced pre-game.")
if st.button("📸 Snapshot projections now"):
    res = C.results()
    done = set(res.game_number.astype(int)) if len(res) else set()
    snaps = []
    for r in sch.itertuples():
        if r.home == "TBD" or int(r.game_number) in done:
            continue
        s = C.game(settings, r.home, r.away, int(r.game_number))
        g = C.E.game_summary(s)
        sp, tl = C.E.main_lines(s)
        pl = {}
        for side in ("home", "away"):
            for j, u in enumerate(s[f"{side}_uids"]):
                pl[u] = {"g": float(s[f"{side}_goals"][:, j].mean()), "a": float(s[f"{side}_assists"][:, j].mean()),
                         "p_g2": float((s[f"{side}_goals"][:, j] >= 2).mean())}
        snaps.append({"game_number": int(r.game_number), **{k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in g.items()},
                      "spread": sp, "p_cover": float(((s["gh"] - s["ga"]) + sp > 0).mean()), "total": tl,
                      "p_over": float(((s["gh"] + s["ga"]) > tl).mean()), "players": pl})
    key = f"snapshot_{datetime.now():%Y%m%d_%H%M%S}"
    C.S.add_snapshot(key, {"settings": settings, "games": snaps})
    st.success(f"Saved {key} ({len(snaps)} games)")

st.subheader("2 · Enter final scores")
base = sch[["game_number", "date", "home", "away"]].copy()
saved = C.S.read_csv(C.RES_NAME)
if saved is not None and len(saved):
    base = base.drop(columns=["home", "away"]).merge(saved[["game_number", "home", "away", "home_goals", "away_goals"]], on="game_number", how="left")
    sch_i = sch.set_index("game_number")
    base["home"] = base.home.fillna(pd.Series(sch_i.home.reindex(base.game_number).values, index=base.index))
    base["away"] = base.away.fillna(pd.Series(sch_i.away.reindex(base.game_number).values, index=base.index))
else:
    base["home_goals"], base["away_goals"] = np.nan, np.nan
ed = st.data_editor(base[["game_number", "date", "home", "away", "home_goals", "away_goals"]], hide_index=True, width="stretch",
                    disabled=["game_number", "date"],
                    column_config={"home": st.column_config.SelectboxColumn(options=C.NATIONS + ["TBD"]),
                                   "away": st.column_config.SelectboxColumn(options=C.NATIONS + ["TBD"]),
                                   "home_goals": st.column_config.NumberColumn("Home final (incl. OT)", step=1),
                                   "away_goals": st.column_config.NumberColumn("Away final (incl. OT)", step=1)})
st.caption("Set semifinal / final teams here once known (they then appear in the Game Center).")
if st.button("💾 Save scores", type="primary"):
    C.S.write_csv(C.RES_NAME, ed)
    st.cache_data.clear()
    st.success("Saved — environment, team ratings and tournament updated.")
    st.rerun()

st.subheader("3 · Player box scores (optional, updates player shares)")
uid_map = P[["player_uid", "player", "nation"]]
st.download_button("Download player id list", uid_map.to_csv(index=False), "glg_player_ids.csv")
up = st.file_uploader("Upload CSV with columns game_number, player_uid, g, a", type="csv")
if up is not None:
    b = pd.read_csv(up)
    miss = set(b.player_uid) - set(P.player_uid)
    if miss:
        st.error(f"Unknown player_uid(s): {sorted(miss)[:5]}")
    else:
        C.S.write_csv(C.PBOX_NAME, b)
        st.cache_data.clear()
        st.success(f"Saved {len(b)} rows.")

st.subheader("4 · Grading")
snaps = C.S.snapshots()
res = C.results()
if not snaps or not len(res):
    st.info("Appears once a snapshot exists and a final score is saved.")
else:
    latest = {}
    for name in sorted(snaps):
        for g in snaps[name]["games"]:
            latest[g["game_number"]] = (name, g)
    rr = res.set_index("game_number")
    rows = []
    for gn, (fn, g) in sorted(latest.items()):
        if gn not in rr.index:
            continue
        r = rr.loc[gn]
        hw = float(r.home_goals > r.away_goals)
        m, t = r.home_goals - r.away_goals, r.home_goals + r.away_goals
        rows.append({"Game": gn, "Matchup": f"{g['home']} vs {g['away']}", "Snapshot": fn,
                     "Proj": f"{g['exp_home']:.1f}–{g['exp_away']:.1f}", "Final": f"{int(r.home_goals)}–{int(r.away_goals)}",
                     "P(home win)": g["p_home"], "Brier": (g["p_home"] - hw) ** 2,
                     "Spread": g["spread"], "Covered": bool(m + g["spread"] > 0), "Total": g["total"], "Over": bool(t > g["total"]),
                     "Margin err": m - g["exp_margin"], "Total err": t - g["exp_total"]})
    if rows:
        d = pd.DataFrame(rows)
        st.dataframe(d.style.format({"P(home win)": "{:.1%}", "Brier": "{:.3f}", "Margin err": "{:+.1f}", "Total err": "{:+.1f}"}), hide_index=True, width="stretch")
        st.write(f"Mean Brier **{d.Brier.mean():.3f}** (coin 0.250) · margin MAE **{d['Margin err'].abs().mean():.1f}** · "
                 f"total bias **{d['Total err'].mean():+.1f}** goals")
        b = C.pbox()
        if b is not None:
            pr = [{"g": x.g, "pg": latest[x.game_number][1]["players"].get(x.player_uid, {}).get("g"), "a": x.a,
                   "pa": latest[x.game_number][1]["players"].get(x.player_uid, {}).get("a")}
                  for x in b.itertuples() if x.game_number in latest]
            pr = pd.DataFrame([p for p in pr if p["pg"] is not None])
            if len(pr):
                st.write(f"Players (n={len(pr)}): goals MAE {(pr.g - pr.pg).abs().mean():.2f}, bias {(pr.g - pr.pg).mean():+.2f}; "
                         f"assists MAE {(pr.a - pr.pa).abs().mean():.2f}")
