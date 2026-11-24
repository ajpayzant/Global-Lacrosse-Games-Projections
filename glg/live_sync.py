"""Apply a GLG live scrape (scripts/scrape_glg_live.py output) to the projection inputs.

    python -I -m glg.live_sync glg_live        # read glg_live/*.csv, merge into the app's saved results

Writes through glg.store, i.e. to the private Gist on GitHub Actions / Streamlit Cloud (GLG_GIST_ID +
GLG_GITHUB_TOKEN set) or to data/glg/ locally:
  glg_results.csv       finals only (eventStatus 3); knockout matchups filled in as soon as they are known.
                        Manual entries for games the scrape has not finalised are kept.
  glg_player_games.csv  player box scores of finished games (game_number, player_uid, g, a, shots, touches, ...),
                        players matched to the warehouse ids by PLL official id, then name within nation.
  live_status.json      what the last sync did (shown on Results & Grading).
"""
from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from glg import store as S  # noqa: E402

GLG = ROOT / "data" / "glg"
NATION_IDS = {"USA": "USA", "US": "USA", "UNITED STATES": "USA", "TEAM USA": "USA", "CAN": "Canada", "CANADA": "Canada",
              "HAU": "Haudenosaunee", "IRQ": "Haudenosaunee", "HAUDENOSAUNEE": "Haudenosaunee", "IROQUOIS": "Haudenosaunee",
              "AUS": "Australia", "AUSTRALIA": "Australia"}
FINAL = {"3", "3.0", "final", "FINAL", "Final", "complete", "completed"}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]+", " ", s).strip()


def _nation(*vals):
    for v in vals:
        k = str(v or "").strip().upper()
        if k in NATION_IDS:
            return NATION_IDS[k]
        for key, n in NATION_IDS.items():
            if len(key) > 3 and key in k:
                return n
    return None


def _read(p):
    p = Path(p)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(p, dtype={"official_id": str, "home_id": str, "away_id": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def roster_ids():
    import duckdb
    con = duckdb.connect(str(ROOT / "warehouse" / "sixes.duckdb"), read_only=True)
    u = con.execute("select nation, first_name, last_name, player_uid from src.glg_roster").df()
    con.close()
    u["k"] = u.first_name.map(_norm) + " " + u.last_name.map(_norm)
    u["lk"] = u.last_name.map(_norm)
    u["fi"] = u.first_name.map(_norm).str[:1]
    return u


def apply(src_dir="glg_live"):
    src = Path(src_dir)
    live, box = _read(src / "results.csv"), _read(src / "player_box.csv")
    out = {"synced_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "games_seen": int(len(live)),
           "finals_applied": [], "matchups_filled": [], "box_rows": 0, "unmatched_players": [], "unmatched_teams": []}
    st_f = src / "status.json"
    if st_f.exists() and st_f.stat().st_size:
        out["scrape"] = {k: v for k, v in json.loads(st_f.read_text()).items() if k != "endpoints"}
    sch = pd.read_csv(GLG / "glg_mens_schedule.csv")
    cur = S.read_csv("glg_results.csv")
    if cur is None or cur.empty:
        cur = sch[["game_number", "date"]].assign(home="TBD", away="TBD", home_goals=float("nan"), away_goals=float("nan"))
    cur = cur.set_index("game_number")
    finals = set()
    if len(live):
        live["home_n"] = [_nation(i, n) for i, n in zip(live.get("home_id", live.home), live.home)]
        live["away_n"] = [_nation(i, n) for i, n in zip(live.get("away_id", live.away), live.away)]
        out["unmatched_teams"] = sorted(set(live.home[live.home_n.isna()].astype(str)) | set(live.away[live.away_n.isna()].astype(str)))
        for r in live[live.home_n.notna() & live.away_n.notna()].itertuples():
            g = int(r.game_number)
            if g not in cur.index:
                continue
            if str(cur.loc[g, "home"]) in ("TBD", "nan"):
                cur.loc[g, ["home", "away"]] = [r.home_n, r.away_n]
                out["matchups_filled"].append(g)
            if str(r.status) in FINAL and pd.notna(r.home_goals) and pd.notna(r.away_goals):
                cur.loc[g, ["date", "home", "away", "home_goals", "away_goals"]] = [r.date, r.home_n, r.away_n,
                                                                                    int(r.home_goals), int(r.away_goals)]
                finals.add(g)
        out["finals_applied"] = sorted(finals)
        S.write_csv("glg_results.csv", cur.reset_index())
    if len(box) and finals:
        box = box[box.game_number.isin(finals)]
        ids = roster_ids()
        team_of = {}
        for r in live[live.game_number.isin(finals)].itertuples():
            team_of[(int(r.game_number), str(r.home_id))] = r.home_n
            team_of[(int(r.game_number), str(r.away_id))] = r.away_n
        rows = []
        for b in box.itertuples():
            nat = _nation(b.team) or team_of.get((int(b.game_number), str(b.team)))
            pid = f"PLL:{str(b.official_id).zfill(6)}" if pd.notna(b.official_id) and str(b.official_id).isdigit() else None
            cand = ids[ids.player_uid == pid] if pid else ids.iloc[0:0]
            if cand.empty:
                cand = ids[(ids.k == _norm(b.first_name) + " " + _norm(b.last_name)) & ((ids.nation == nat) if nat else True)]
            if cand.empty:
                cand = ids[(ids.lk == _norm(b.last_name)) & (ids.nation == nat) & (ids.fi == _norm(b.first_name)[:1])]
            if len(cand) != 1:
                out["unmatched_players"].append(f"{b.first_name} {b.last_name} ({b.team}, G{b.game_number})")
                continue
            num = lambda v: (None if pd.isna(v) else float(v))
            rows.append({"game_number": int(b.game_number), "player_uid": cand.player_uid.iloc[0],
                         "g": int(b.goals or 0) if pd.notna(b.goals) else 0, "a": int(b.assists or 0) if pd.notna(b.assists) else 0,
                         "shots": num(b.shots), "touches": num(b.touches), "saves": num(b.saves), "goals_against": num(b.goals_against)})
        new = pd.DataFrame(rows)
        old = S.read_csv("glg_player_games.csv")
        if old is not None and len(old) and len(new):
            old = old[~old.game_number.isin(new.game_number.unique())]
        merged = pd.concat([d for d in (old, new) if d is not None and len(d)], ignore_index=True) if len(new) else old
        if merged is not None and len(merged):
            S.write_csv("glg_player_games.csv", merged)
        out["box_rows"] = int(len(new))
    S.write_json("live_status.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(apply(sys.argv[1] if len(sys.argv) > 1 else "glg_live"), indent=1, default=str))
