"""GLG Men's Sixes Projections — entry point (multi-page).

    python -m streamlit run app/glg_app.py --server.port 8690
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))   # views import `common`

st.set_page_config(page_title="GLG Sixes Projections", layout="wide", page_icon="🥍")
pages = [
    st.Page("views/game_center.py", title="Game Center", icon="🎯", default=True),
    st.Page("views/players.py", title="Player Projections", icon="👤"),
    st.Page("views/tournament.py", title="Tournament", icon="🏆"),
    st.Page("views/teams.py", title="Teams & Rosters", icon="🛡️"),
    st.Page("views/depth.py", title="Depth Chart", icon="📊"),
    st.Page("views/overrides.py", title="Ratings & Overrides", icon="🎛️"),
    st.Page("views/results.py", title="Results & Grading", icon="📋"),
    st.Page("views/method.py", title="Model & Data", icon="📚"),
]
st.navigation(pages).run()
