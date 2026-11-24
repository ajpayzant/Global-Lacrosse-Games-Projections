import numpy as np
import pandas as pd
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
ov = C.E.load_overrides()
ov.setdefault("team", {}); ov.setdefault("player", {}); ov.setdefault("game", {})

C.page("Ratings & Overrides", "Manual adjustments apply to every game, prop and tournament market until cleared")
st.caption("Overrides are saved to data/glg/overrides.json and apply everywhere (games, props, tournament) until cleared.")

# ------------------------------------------------------------------ environment
st.subheader("Scoring environment")
c = st.columns(3)
c[0].metric("Current expected goals / team", f"{env[0]:.2f}", f"±{env[1]:.0%}", delta_color="off")
force = c[1].number_input("Force goals / team (0 = model)", 0.0, 25.0, float(ov.get("env_goals") or 0.0), 0.25)

# ------------------------------------------------------------------ teams
st.subheader("Team ratings (log goal-rate units)")
t = T[["glg_talent", "hist_talent", "mean_continuity", "cres_att", "cres_def", "att_model", "def_model"]].copy()
t["att_adj"] = [float(ov["team"].get(n, {}).get("att", 0.0)) for n in t.index]
t["def_adj"] = [float(ov["team"].get(n, {}).get("def", 0.0)) for n in t.index]
t["attack"] = t.att_model + t.att_adj
t["defence"] = t.def_model + t.def_adj
t["overall"] = t.attack + t.defence
t = t.reset_index().rename(columns={"team": "nation"})
ed_t = st.data_editor(
    t, hide_index=True, width="stretch",
    disabled=[c_ for c_ in t.columns if c_ not in ("att_adj", "def_adj")],
    column_config={"glg_talent": st.column_config.NumberColumn("GLG roster talent", format="%.1f"),
                   "hist_talent": st.column_config.NumberColumn("Talent of lineups in results", format="%.1f"),
                   "mean_continuity": st.column_config.NumberColumn("Lineup continuity", format="%.2f"),
                   "cres_att": st.column_config.NumberColumn("Results attack", format="%+.3f"),
                   "cres_def": st.column_config.NumberColumn("Results defence", format="%+.3f"),
                   "att_model": st.column_config.NumberColumn("Model attack", format="%+.3f"),
                   "def_model": st.column_config.NumberColumn("Model defence", format="%+.3f"),
                   "att_adj": st.column_config.NumberColumn("Attack override (+/-)", format="%+.3f", step=0.01),
                   "def_adj": st.column_config.NumberColumn("Defence override (+/-)", format="%+.3f", step=0.01),
                   "attack": st.column_config.NumberColumn("Attack used", format="%+.3f"),
                   "defence": st.column_config.NumberColumn("Defence used", format="%+.3f"),
                   "overall": st.column_config.NumberColumn("Overall", format="%+.3f")})
st.caption("+0.10 attack ≈ +10.5% goals scored; +0.10 defence ≈ −9.5% goals conceded. Model attack = roster-talent attack + "
           "credibility × (results attack − talent attack); defence likewise with a 0.25 × talent term. Credibility = effective "
           "results games ÷ (games + k), where games are weighted by lineup continuity (incl. real 2023 Worlds rosters), recency "
           "and blowout down-weighting.")

# ------------------------------------------------------------------ players
st.subheader("Player ratings")
nat = st.radio("Nation", C.NATIONS, horizontal=True)
pp = P[P.nation == nat].copy()
po = ov["player"]
tbl = pd.DataFrame({
    "player_uid": pp.player_uid, "Player": pp.player, "Pos": pp.pos, "Source": pp.prior_kind,
    "Model G/gm": pp.talent_g_model, "Model A/gm": pp.talent_a_model,
    "OUT": [bool(po.get(u, {}).get("out", False)) for u in pp.player_uid],
    "G mult": [float(po.get(u, {}).get("g_mult", 1.0)) for u in pp.player_uid],
    "A mult": [float(po.get(u, {}).get("a_mult", 1.0)) for u in pp.player_uid],
    "Set G/gm": [po.get(u, {}).get("g_rate") for u in pp.player_uid],
    "Set A/gm": [po.get(u, {}).get("a_rate") for u in pp.player_uid],
    "Used G/gm": pp.talent_g, "Goal share": pp.share_g, "Assist share": pp.share_a})
ed_p = st.data_editor(
    tbl, hide_index=True, width="stretch", key=f"pe_{nat}",
    disabled=["player_uid", "Player", "Pos", "Source", "Model G/gm", "Model A/gm", "Used G/gm", "Goal share", "Assist share"],
    column_config={"player_uid": None,
                   "Model G/gm": st.column_config.NumberColumn(format="%.2f"), "Model A/gm": st.column_config.NumberColumn(format="%.2f"),
                   "G mult": st.column_config.NumberColumn(format="%.2f", step=0.05, min_value=0.0, max_value=3.0),
                   "A mult": st.column_config.NumberColumn(format="%.2f", step=0.05, min_value=0.0, max_value=3.0),
                   "Set G/gm": st.column_config.NumberColumn("Set G/gm (absolute)", format="%.2f", step=0.1),
                   "Set A/gm": st.column_config.NumberColumn("Set A/gm (absolute)", format="%.2f", step=0.1),
                   "Used G/gm": st.column_config.NumberColumn(format="%.2f"),
                   "Goal share": st.column_config.NumberColumn(format="percent"), "Assist share": st.column_config.NumberColumn(format="percent")})
st.caption("Ratings are goals/assists per game at Championship Series scale; shares within the team decide each player's slice "
           "of simulated team goals. OUT removes a player and re-spreads his share.")

# ------------------------------------------------------------------ game-level
st.subheader("Game-level overrides (expected goals)")
sch = C.schedule()
g_rows = pd.DataFrame([{"game_number": int(r.game_number), "Game": f"G{int(r.game_number)} {r.home} vs {r.away}",
                        "Home exp goals": (ov["game"].get(str(int(r.game_number)), {}) or {}).get("home_mu"),
                        "Away exp goals": (ov["game"].get(str(int(r.game_number)), {}) or {}).get("away_mu")}
                       for r in sch.itertuples() if r.home != "TBD"])
ed_g = st.data_editor(g_rows, hide_index=True, disabled=["game_number", "Game"], width="stretch",
                      column_config={"game_number": None})
st.caption("Leave blank to use the model. A value rescales that team's simulated expected goals for that game only.")

b = st.columns(3)
if b[0].button("💾 Save overrides", type="primary"):
    new = {"env_goals": force or None, "team": {}, "player": dict(ov["player"]), "game": {}, "depth": ov.get("depth", {}), "usage": ov.get("usage", {}),
           "lineups": ov.get("lineups", {})}
    for r in ed_t.to_dict("records"):
        if abs(r["att_adj"] or 0) > 1e-9 or abs(r["def_adj"] or 0) > 1e-9:
            new["team"][r["nation"]] = {"att": float(r["att_adj"] or 0), "def": float(r["def_adj"] or 0)}
    for r in ed_p.to_dict("records"):
        d = {}
        if r["OUT"]:
            d["out"] = True
        if r["G mult"] is not None and abs(float(r["G mult"]) - 1) > 1e-9:
            d["g_mult"] = float(r["G mult"])
        if r["A mult"] is not None and abs(float(r["A mult"]) - 1) > 1e-9:
            d["a_mult"] = float(r["A mult"])
        if r["Set G/gm"] is not None and pd.notna(r["Set G/gm"]):
            d["g_rate"] = float(r["Set G/gm"])
        if r["Set A/gm"] is not None and pd.notna(r["Set A/gm"]):
            d["a_rate"] = float(r["Set A/gm"])
        new["player"].pop(r["player_uid"], None)
        if d:
            new["player"][r["player_uid"]] = d
    for r in ed_g.to_dict("records"):
        d = {}
        if r["Home exp goals"] is not None and pd.notna(r["Home exp goals"]):
            d["home_mu"] = float(r["Home exp goals"])
        if r["Away exp goals"] is not None and pd.notna(r["Away exp goals"]):
            d["away_mu"] = float(r["Away exp goals"])
        if d:
            new["game"][str(r["game_number"])] = d
    C.E.save_overrides(new)
    st.cache_data.clear()
    st.success("Saved.")
    st.rerun()
if b[1].button("Clear ALL overrides"):
    C.E.save_overrides({})
    st.cache_data.clear()
    st.rerun()
b[2].download_button("Download overrides.json", data=__import__("json").dumps(ov, indent=1), file_name="overrides.json")
