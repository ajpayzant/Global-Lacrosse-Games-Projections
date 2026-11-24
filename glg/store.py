"""Persistent storage for everything the user saves in the app: overrides, results, player box scores, snapshots.

Backends
  local (default)  files in data/glg/ (snapshots in data/glg/snapshots/*.json)
  gist             a private GitHub Gist - used on Streamlit Cloud, whose filesystem is wiped on restart/redeploy.
                   Enabled when both GLG_GIST_ID and GLG_GITHUB_TOKEN are set (Streamlit secrets at root level are
                   exposed as environment variables). The token needs only the "gist" scope.

Files (same names in both backends)
  overrides.json, glg_results.csv, glg_player_games.csv, snapshots.json ({snapshot_name: snapshot})
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "glg"
SNAPDIR = LOCAL / "snapshots"
_cache: dict = {"t": 0.0, "files": None}
TTL = 20.0


def _env(k):
    v = os.environ.get(k)
    if v:
        return v
    try:                                   # Streamlit secrets (nested or root) when running inside Streamlit
        import streamlit as st
        return st.secrets.get(k) or st.secrets.get("glg", {}).get(k)
    except Exception:
        return None


def backend():
    return "gist" if (_env("GLG_GIST_ID") and _env("GLG_GITHUB_TOKEN")) else "local"


def _gist_req(method, body=None):
    gid, tok = _env("GLG_GIST_ID"), _env("GLG_GITHUB_TOKEN")
    req = urllib.request.Request(f"https://api.github.com/gists/{gid}", method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "glg-projections"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _gist_files(force=False):
    if not force and _cache["files"] is not None and time.time() - _cache["t"] < TTL:
        return _cache["files"]
    g = _gist_req("GET")
    files = {}
    for name, f in g.get("files", {}).items():
        content = f.get("content", "")
        if f.get("truncated") and f.get("raw_url"):
            with urllib.request.urlopen(f["raw_url"], timeout=30) as r:
                content = r.read().decode("utf-8")
        files[name] = content
    _cache.update(t=time.time(), files=files)
    return files


def read(name: str) -> str | None:
    if backend() == "gist":
        c = _gist_files().get(name)
        return c if c not in (None, "", "{}\n") or name.endswith(".json") else c
    if name == "snapshots.json":
        snaps = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(SNAPDIR.glob("snapshot_*.json"))}
        return json.dumps(snaps) if snaps else None
    p = LOCAL / name
    return p.read_text(encoding="utf-8") if p.exists() else None


def write(name: str, text: str) -> None:
    if backend() == "gist":
        _gist_req("PATCH", {"files": {name: {"content": text if text.strip() else " "}}})
        _cache["files"] = None
        return
    LOCAL.mkdir(parents=True, exist_ok=True)
    (LOCAL / name).write_text(text, encoding="utf-8")


# ---- typed helpers
def read_json(name, default):
    t = read(name)
    try:
        return json.loads(t) if t and t.strip() else default
    except json.JSONDecodeError:
        return default


def write_json(name, obj):
    write(name, json.dumps(obj, indent=1, default=str))


def read_csv(name):
    import io
    import pandas as pd
    t = read(name)
    if not t or not t.strip():
        return None
    return pd.read_csv(io.StringIO(t))


def write_csv(name, df):
    write(name, df.to_csv(index=False))


def snapshots() -> dict:
    return read_json("snapshots.json", {})


def add_snapshot(key: str, snap: dict):
    if backend() == "gist":
        s = snapshots()
        s[key] = snap
        write_json("snapshots.json", s)
    else:
        SNAPDIR.mkdir(parents=True, exist_ok=True)
        (SNAPDIR / f"{key}.json").write_text(json.dumps(snap), encoding="utf-8")
