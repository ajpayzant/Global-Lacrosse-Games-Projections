"""Shared state for the GLG app: settings, display preferences, overrides, cached model + simulations,
pricing helpers and UI components."""
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from glg import engine as E  # noqa: E402
from glg import store as S  # noqa: E402

GLG = ROOT / "data" / "glg"
RES_NAME, PBOX_NAME = "glg_results.csv", "glg_player_games.csv"     # stored via glg.store (local files or Gist)
NATIONS = E.NATIONS
COLOR = {"USA": "#1F3A93", "Canada": "#D52B1E", "Haudenosaunee": "#6B3FA0", "Australia": "#0E8A4F"}
ABBR = {"USA": "USA", "Canada": "CAN", "Haudenosaunee": "HAU", "Australia": "AUS"}

CSS = """
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px;}
h1 {font-weight: 750; letter-spacing: -0.02em; margin-bottom: .2rem; color:#0F172A;}
h2, h3 {font-weight: 680; letter-spacing: -0.01em; color:#0F172A;}
/* ---- sidebar: light, high-contrast ---- */
[data-testid="stSidebar"] {background: #FFFFFF; border-right: 1px solid #E2E8F0;}
[data-testid="stSidebar"] h2 {color:#0B5FFF; font-size:1.25rem; margin-bottom:0;}
[data-testid="stSidebar"] h4 {color:#334155; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; margin:1rem 0 .3rem;}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {color:#0F172A;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#64748B;}
[data-testid="stSidebar"] [data-testid="stExpander"] {border:1px solid #E2E8F0; border-radius:10px; background:#F8FAFC;}
.glg-sub {color:#64748B; font-size:.92rem; margin-bottom:1rem;}
.card {background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px; padding:18px 22px; box-shadow:0 1px 2px rgba(15,23,42,.04);}
.match {display:flex; align-items:center; justify-content:space-between; gap:16px;}
.team {display:flex; align-items:center; gap:12px; font-size:1.35rem; font-weight:700; color:#0F172A;}
.badge {display:inline-flex; align-items:center; justify-content:center; width:46px; height:46px; border-radius:12px;
        color:#fff; font-weight:800; font-size:.85rem; letter-spacing:.04em;}
.score {font-size:2.1rem; font-weight:800; color:#0F172A; text-align:center; line-height:1;}
.score small {display:block; font-size:.75rem; font-weight:600; color:#64748B; margin-top:6px; letter-spacing:.06em;}
.bar {display:flex; height:10px; border-radius:6px; overflow:hidden; margin-top:14px;}
.bar div {height:100%;}
.barlbl {display:flex; justify-content:space-between; font-size:.8rem; color:#475569; margin-top:4px;}
.kpis {display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-top:14px;}
.kpi {background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:10px 14px;}
.kpi .l {font-size:.72rem; color:#64748B; text-transform:uppercase; letter-spacing:.06em; font-weight:650;}
.kpi .v {font-size:1.25rem; font-weight:750; color:#0F172A; margin-top:2px;}
.kpi .s {font-size:.78rem; color:#475569;}
.pill {display:inline-block; padding:2px 9px; border-radius:999px; font-size:.75rem; font-weight:650; color:#fff;}
.note {font-size:.8rem; color:#64748B;}
/* ---- odds board ---- */
.mkt {background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px; padding:14px 16px; height:100%;}
.mkt .t {font-size:.74rem; font-weight:700; color:#64748B; text-transform:uppercase; letter-spacing:.07em; margin-bottom:10px;}
.tiles {display:grid; gap:10px;}
.tile {border:1px solid #E2E8F0; border-radius:10px; padding:10px 12px; background:#F8FAFC; position:relative; overflow:hidden;}
.tile .sel {font-size:.9rem; font-weight:650; color:#0F172A; display:flex; align-items:center; gap:8px;}
.tile .px {display:flex; align-items:baseline; gap:10px; margin-top:6px;}
.tile .fair {font-size:1.35rem; font-weight:800; color:#0F172A;}
.tile .book {font-size:1.0rem; font-weight:700; color:#0B5FFF;}
.tile .lbl {font-size:.66rem; color:#64748B; text-transform:uppercase; letter-spacing:.06em; margin-right:2px;}
.tile .tp {font-size:.78rem; color:#475569; margin-top:2px;}
.tile .pbar {position:absolute; left:0; bottom:0; height:4px; background:#0B5FFF; opacity:.55;}
.dot {display:inline-block; width:10px; height:10px; border-radius:3px;}
</style>
"""


def page(title, subtitle=None):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f"<div class='glg-sub'>{subtitle}</div>", unsafe_allow_html=True)


def badge(nation, size=46):
    return (f"<span class='badge' style='background:{COLOR.get(nation, '#334155')};width:{size}px;height:{size}px'>"
            f"{ABBR.get(nation, nation[:3].upper())}</span>")


# ------------------------------------------------------------------ data access
def schedule():
    s = pd.read_csv(GLG / "glg_mens_schedule.csv")
    s["home"] = s.home_team.map(lambda x: E.ALIAS.get(x, x))
    s["away"] = s.away_team.map(lambda x: E.ALIAS.get(x, x))
    r = S.read_csv(RES_NAME)
    if r is not None and len(r):
        r = r.set_index("game_number")
        for c in ("home", "away"):
            s[c] = [r[c].get(g, x) if x == "TBD" and isinstance(r[c].get(g, None), str) else x for g, x in zip(s.game_number, s[c])]
    s["stage_lbl"] = s.stage.str.extract(r"\((.*)\)")[0].fillna(s.stage)
    return s


def results():
    r = S.read_csv(RES_NAME)
    if r is not None and len(r):
        return r[r.home_goals.notna() & r.away_goals.notna() & (r.home != "TBD")].copy()
    return pd.DataFrame(columns=["game_number", "date", "home", "away", "home_goals", "away_goals"])


def pbox():
    return S.read_csv(PBOX_NAME)


# ------------------------------------------------------------------ sidebar
def sidebar():
    """Global controls. Returns (settings, display) where display has view / odds / price / margins."""
    sb = st.sidebar
    sb.markdown("## 🥍 GLG Sixes")
    sb.caption("Men's · Dec 8–13 2026 · The St. James")
    ss = st.session_state

    def keep(key, default):
        """Widget value that survives page switches: widget key 'w_<key>' mirrored into session key '<key>'."""
        ss.setdefault(key, default)
        ss[f"w_{key}"] = ss[key]

        def _sync():
            ss[key] = ss[f"w_{key}"]
        return dict(key=f"w_{key}", on_change=_sync)
    sb.markdown("#### Display")
    view = sb.segmented_control("Mode", ["Projections", "Prices"], label_visibility="collapsed", **keep("view", "Projections")) or "Projections"
    odds = sb.segmented_control("Odds format", ["American", "Decimal", "Prob"], **keep("odds", "American")) or "American"
    price = sb.segmented_control("Price", ["Fair", "Margined", "Fair + Margined"], **keep("price", "Fair + Margined")) or "Fair + Margined"
    with sb.expander("Margins", expanded=False):
        m = {"game": st.number_input("Game lines %", 0.0, 20.0, step=0.5, **keep("m_game", 4.5)) / 100,
             "props": st.number_input("Player props %", 0.0, 30.0, step=0.5, **keep("m_props", 8.0)) / 100,
             "futures": st.number_input("Team futures %", 0.0, 60.0, step=1.0, **keep("m_fut", 15.0)) / 100,
             "player_futures": st.number_input("Player futures % (top scorer etc.)", 0.0, 80.0, step=1.0, **keep("m_pfut", 30.0)) / 100,
             "max_odds": st.number_input("Max price (American, outrights)", 1000, 100000, step=500, **keep("m_max", 25000))}
        st.caption("Power method: book p = p^k, k set so each market sums to 1 + margin (more margin on longshots). "
                   "Outright prices are capped at the max price; true probabilities are never changed.")
    with sb.expander("Model settings", expanded=False):
        env = st.slider("Pre-GLG goals / team", 12.0, 20.0, step=0.25, **keep("s_env", 16.0),
                        help="Championship Series ≈ 18.9 · elite international ≈ 14–16 · completed GLG games update it")
        ssd = st.slider("Team strength uncertainty", 0.0, 0.30, step=0.01, **keep("s_sd", 0.10))
        kr = st.slider("Results credibility k (higher = trust talent more)", 1.0, 12.0, step=0.5, **keep("s_kr", 4.0))
        ww = st.slider("2023 Worlds weight", 0.0, 2.0, step=0.1, **keep("s_ww", 1.0))
        ku = st.slider("Sixes-evidence shrinkage k (pros)", 4.0, 24.0, step=1.0, **keep("s_ku", 12.0))
        sims = st.select_slider("Simulations", [5000, 10000, 20000, 40000], **keep("s_n", 20000))
        if st.button("Reset model settings"):
            for k_ in ("s_env", "s_sd", "s_kr", "s_ww", "s_ku", "s_n"):
                ss.pop(k_, None)
            st.rerun()
    sb.caption(f"Saved data: {'GitHub Gist (cloud)' if S.backend() == 'gist' else 'local files'}")
    ov = E.load_overrides()
    n_ov = sum(len(v) if isinstance(v, dict) else 1 for k_, v in ov.items() if v)
    if n_ov:
        sb.warning(f"{n_ov} manual override(s) active")
    settings = dict(env_goals_prior=env, strength_sd=ssd, k_results=kr, worlds_weight=ww, k_update=ku,
                    n_sims=int(sims), overrides=ov)
    return settings, dict(view=view, odds=odds, price=price, margins=m)


def _keys(settings):
    r, b = results(), pbox()
    return json.dumps(settings, sort_keys=True), (r.to_json() if len(r) else ""), (b.to_json() if b is not None else "")


@st.cache_data(show_spinner="Rating players and teams…")
def _model(sk, rk, bk):
    s = E.Settings(**json.loads(sk))
    return E.run(s, pd.read_json(io.StringIO(rk)) if rk else None, pd.read_json(io.StringIO(bk)) if bk else None)


def model(settings):
    return _model(*_keys(settings))


@st.cache_data(show_spinner="Simulating…", max_entries=64)
def _game(sk, rk, bk, home, away, game_number):
    s = E.Settings(**json.loads(sk))
    P, T, env, _ = _model(sk, rk, bk)
    return E.game_with_players(T, P, env, s, home, away, game_number)


def game(settings, home, away, game_number=None):
    return _game(*_keys(settings), home, away, game_number)


def swap_sim(sim):
    """Same simulation viewed from the other side (display only)."""
    s = dict(sim)
    for x, y in (("home", "away"), ("gh", "ga"), ("reg_h", "reg_a"), ("home_uids", "away_uids"),
                 ("home_goals", "away_goals"), ("home_assists", "away_assists")):
        s[x], s[y] = sim[y], sim[x]
    return s


@st.cache_data(show_spinner="Simulating tournament…")
def _tourn(sk, rk, bk):
    s = E.Settings(**json.loads(sk))
    P, T, env, _ = _model(sk, rk, bk)
    return E.tournament(T, P, env, s, schedule(), pd.read_json(io.StringIO(rk)) if rk else None)


def tournament(settings):
    return _tourn(*_keys(settings))


# ------------------------------------------------------------------ pricing
def fmt_odds(p, mode):
    p = float(np.clip(p, 1e-4, 0.9999))
    if mode == "Decimal":
        return f"{1 / p:.2f}"
    if mode == "Prob":
        return f"{p:.1%}"
    return E.fmt_american(p)


def price_fields(p, disp, margin, book_p=None):
    """Columns for one selection given display prefs. book_p = pre-computed margined prob (multi-way markets)."""
    bp = float(book_p) if book_p is not None else float(E.margined([p], margin)[0])
    out = {"True %": float(p)}
    if disp["price"] in ("Fair", "Fair + Margined"):
        out["Fair"] = fmt_odds(p, disp["odds"])
    if disp["price"] in ("Margined", "Fair + Margined"):
        out["Margined"] = fmt_odds(bp, disp["odds"])
    return out


def game_markets(sim, disp, margin):
    gh, ga, h, a = sim["gh"], sim["ga"], sim["home"], sim["away"]
    m, tot = gh - ga, gh + ga
    sp, tl = E.main_lines(sim)
    rows = []

    def two(market, s1, p1, s2):
        rows.append({"Market": market, "Selection": s1, **price_fields(p1, disp, margin)})
        rows.append({"Market": market, "Selection": s2, **price_fields(1 - p1, disp, margin)})
    two("Moneyline", h, (gh > ga).mean(), a)
    for L in E.spread_ladder(sim):
        two("Spread ★" if L == sp else "Spread", f"{h} {L:+.1f}", (m + L > 0).mean(), f"{a} {-L:+.1f}")
    for L in sorted({tl - 2, tl - 1, tl, tl + 1, tl + 2}):
        two("Total ★" if L == tl else "Total", f"Over {L}", (tot > L).mean(), f"Under {L}")
    for g_, nm in ((gh, h), (ga, a)):
        L = float(np.round(np.median(g_))) + 0.5
        two(f"{nm} team total", f"Over {L}", (g_ > L).mean(), f"Under {L}")
    rh, ra = sim["reg_h"], sim["reg_a"]
    probs = [(rh > ra).mean(), (rh == ra).mean(), (ra > rh).mean()]
    book = E.power_margin(probs, margin)
    for sel, p, b in zip((f"{h} in regulation", "Tied after regulation", f"{a} in regulation"), probs, book):
        rows.append({"Market": "Regulation 3-way", "Selection": sel, **price_fields(p, disp, margin, b)})
    return pd.DataFrame(rows)


def reorder_by_moves(current_order, old_rank, new_rank):
    """Depth-chart 'move' semantics. current_order: uids top->bottom. old_rank/new_rank: {uid: rank}.
    Each player whose rank was edited is moved to that position (others shift by one); untouched players keep
    their relative order. Several moves are applied from the top rank down. Returns the new uid order."""
    order = list(current_order)
    moved = sorted((u for u in order if int(new_rank[u]) != int(old_rank[u])), key=lambda u: int(new_rank[u]))
    for u in moved:
        order.remove(u)
    for u in moved:
        order.insert(max(0, min(int(new_rank[u]) - 1, len(order))), u)
    return order


def fig_layout(fig, height, title=None, legend_below=False, **kw):
    """Consistent Plotly layout with margins sized for the title and legend (nothing clipped)."""
    fig.update_layout(height=height, title=dict(text=title, x=0, xanchor="left", font=dict(size=14)) if title else None,
                      margin=dict(t=56 if title else 18, b=70 if legend_below else 36, l=10, r=10),
                      plot_bgcolor="white", paper_bgcolor="white", font=dict(color="#0F172A"),
                      legend=dict(orientation="h", y=-0.18, x=0) if legend_below else None, **kw)
    fig.update_xaxes(automargin=True, gridcolor="#EEF2F7")
    fig.update_yaxes(automargin=True, gridcolor="#EEF2F7")
    return fig


def tile_html(sel, p, disp, margin, book_p=None, color=None):
    """One price tile: selection, fair + margined price (per display prefs), true %, probability bar."""
    f = price_fields(p, disp, margin, book_p)
    dot = f"<span class='dot' style='background:{color}'></span>" if color else ""
    parts = []
    if "Fair" in f:
        parts.append(f"<span><span class='lbl'>fair</span><span class='fair'>{f['Fair']}</span></span>")
    if "Margined" in f:
        parts.append(f"<span><span class='lbl'>book</span><span class='book'>{f['Margined']}</span></span>")
    return (f"<div class='tile'><div class='sel'>{dot}{sel}</div><div class='px'>{''.join(parts)}</div>"
            f"<div class='tp'>true {p:.1%}</div><div class='pbar' style='width:{min(p, 1) * 100:.1f}%'></div></div>")


def market_card(title, tiles, cols=2):
    st.markdown(f"<div class='mkt'><div class='t'>{title}</div><div class='tiles' style='grid-template-columns:repeat({cols},1fr)'>"
                + "".join(tiles) + "</div></div>", unsafe_allow_html=True)


def style_prices(df):
    return df.style.format({"True %": "{:.1%}"}, na_rep="")


# ------------------------------------------------------------------ components
def match_card(h, a, g, sp, tl, final=None):
    ph = g["p_home"]
    fin = f"<div class='note' style='text-align:center;margin-top:6px'>FINAL {final}</div>" if final else ""
    st.markdown(f"""
<div class='card'>
  <div class='match'>
    <div class='team'>{badge(h)} {h}</div>
    <div class='score'>{g['exp_home']:.1f} – {g['exp_away']:.1f}<small>PROJECTED SCORE</small></div>
    <div class='team' style='flex-direction:row-reverse'>{badge(a)} {a}</div>
  </div>{fin}
  <div class='bar'><div style='width:{ph * 100:.1f}%;background:{COLOR.get(h)}'></div>
                   <div style='width:{(1 - ph) * 100:.1f}%;background:{COLOR.get(a)}'></div></div>
  <div class='barlbl'><span>{h} {ph:.1%}</span><span>{a} {1 - ph:.1%}</span></div>
  <div class='kpis'>
    <div class='kpi'><div class='l'>Spread (favourite)</div><div class='v'>{(ABBR.get(h, h) + ' ' + format(sp, '+.1f')) if sp < 0 else (ABBR.get(a, a) + ' ' + format(-sp, '+.1f'))}</div><div class='s'>median margin {g['median_margin']:+.0f} ({ABBR.get(h, h)})</div></div>
    <div class='kpi'><div class='l'>Total</div><div class='v'>{tl}</div><div class='s'>mean {g['exp_total']:.1f}</div></div>
    <div class='kpi'><div class='l'>{ABBR.get(h, h)} 80% range</div><div class='v'>{g['home_q10']:.0f}–{g['home_q90']:.0f}</div><div class='s'>goals</div></div>
    <div class='kpi'><div class='l'>{ABBR.get(a, a)} 80% range</div><div class='v'>{g['away_q10']:.0f}–{g['away_q90']:.0f}</div><div class='s'>goals</div></div>
    <div class='kpi'><div class='l'>Overtime</div><div class='v'>{g['p_ot']:.1%}</div><div class='s'>3-min periods</div></div>
  </div>
</div>""", unsafe_allow_html=True)
