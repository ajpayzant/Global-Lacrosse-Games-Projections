import duckdb
import pandas as pd
import streamlit as st

import common as C

settings, disp = C.sidebar()
P, T, env, meta = C.model(settings)
C.page("Model & Data", "How the projections are built, what data feeds them, how they were validated")
t1, t2, t3, t4 = st.tabs(["How the model works", "Data & coverage", "Validation & calibration", "Pre-build analysis (archive)"])

with t1:
    st.markdown((C.ROOT / "reports" / "model_guide.md").read_text(encoding="utf-8"))
    st.caption(f"Live values: anchor a = {meta['a_scale']:.3f} ({', '.join(meta['anchors'])} Pan-Am lineups) · GLM trained on "
               f"{meta['glm_rows']} CS player-games · NLL bridge n = {meta['nll_bridge_n']} · CS team goals {meta['cs_team_goals']:.2f}, "
               f"assists/goal {meta['cs_assists_per_goal']:.3f} · environment now {env[0]:.2f} goals/team (±{env[1]:.0%}).")
    t = T[["glg_talent", "hist_talent", "mean_continuity", "worlds2023_continuity", "eff_results_games", "credibility", "usage_beta",
           "att", "def", "strength"]].rename(columns={
        "glg_talent": "GLG roster talent", "hist_talent": "Talent of lineups in results", "mean_continuity": "2025-26 intl continuity",
        "worlds2023_continuity": "2023 Worlds continuity", "eff_results_games": "Effective results games", "credibility": "Results credibility",
        "usage_beta": "Usage flattening β", "att": "Attack", "def": "Defence", "strength": "Overall"})
    st.markdown("**Current team components**")
    st.dataframe(t.style.format("{:.2f}"), width="stretch")

with t2:
    con = duckdb.connect(str(C.ROOT / "warehouse" / "sixes.duckdb"), read_only=True)
    q = lambda s: con.execute(s).df()
    src = pd.DataFrame([
        {"Source": "PLL 10v10", "Rows": int(q("select count(*) n from fact.pll10_player_game").n[0]),
         "Games": int(q("select count(distinct game_id) n from fact.pll10_player_game").n[0]), "Span": "2019–2026"},
        {"Source": "PLL Championship Series (6v6)", "Rows": int(q("select count(*) n from fact.sixes_player_game where source='pll_cs'").n[0]),
         "Games": int(q("select count(*) n from fact.sixes_game where source='pll_cs'").n[0]), "Span": "2023–2026"},
        {"Source": "International sixes (men)", "Rows": int(q("select count(*) n from fact.sixes_player_game where source='intl'").n[0]),
         "Games": int(q("select count(*) n from fact.sixes_game where source='intl'").n[0]), "Span": "2025–2026"},
        {"Source": "NLL player-seasons", "Rows": int(q("select count(*) n from fact.nll_player_season").n[0]), "Games": None, "Span": "2018-19–2025-26"},
        {"Source": "2023 World Championship (10v10)", "Rows": 15, "Games": 15, "Span": "2023"}])
    st.markdown("**Sources in the warehouse**")
    st.dataframe(src, hide_index=True, width="stretch")
    st.markdown("**GLG roster coverage (players with any data in each source)**")
    st.dataframe(q("""select nation, count(*) players, count(pll10_games) "PLL 10v10", count(cs_games) "Champ Series",
                      count(intl_games) "Intl sixes", count(nll_games_since_2223) "NLL (2022-23+)",
                      sum(case when coalesce(pll10_games,0)+coalesce(cs_games,0)+coalesce(intl_games,0)+coalesce(nll_games_since_2223,0)=0
                          then 1 else 0 end) "No data" from mart.glg_roster_profile group by 1 order by 1"""), hide_index=True)
    st.markdown("**Data quality checks** (from the warehouse build)")
    st.dataframe(q("select scope, name, pass_rate, n, detail from qa.checks order by scope, name"), hide_index=True, width="stretch",
                 column_config={"pass_rate": st.column_config.ProgressColumn("Pass rate", min_value=0, max_value=1, format="%.3f")})
    st.caption("Checks below 100% are explained in the detail column or in warehouse/README.md, e.g. PLL shots-on-goal "
               "counts ~2 on-target shots per game that are neither saves nor goals, which is why save % uses saves/(saves+GA).")
    con.close()

with t3:
    st.markdown((C.ROOT / "reports" / "calibration_v3.md").read_text(encoding="utf-8"))

with t4:
    st.info("Archive: the exploratory analysis written before the engine was built. Several recommendations were later refined "
            "(see Validation & calibration). The model guide is the current description.")
    st.markdown((C.ROOT / "reports" / "eda_findings.md").read_text(encoding="utf-8"))
