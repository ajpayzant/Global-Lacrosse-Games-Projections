"""One-time: copy locally saved app state (overrides, results, box scores, snapshots) into the Gist backend.
    set GLG_GIST_ID=...  &  set GLG_GITHUB_TOKEN=...   then   python -I scripts/migrate_to_gist.py
"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from glg import store as S

if S.backend() != "gist":
    sys.exit("Set GLG_GIST_ID and GLG_GITHUB_TOKEN first.")
local = S.LOCAL
for name in ("overrides.json", "glg_results.csv", "glg_player_games.csv"):
    p = local / name
    if p.exists():
        S.write(name, p.read_text(encoding="utf-8")); print("copied", name)
snaps = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted(S.SNAPDIR.glob("snapshot_*.json"))}
if snaps:
    S.write_json("snapshots.json", {**S.snapshots(), **snaps}); print("copied", len(snaps), "snapshots")
print("done")
