"""app.py — 라우터 전용"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="WaterLevelSim — 섬진강 수위 예측",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/0_home.py",       title="홈",           icon="🏠"),
    st.Page("pages/1_simulation.py", title="시뮬레이션",   icon="🔵"),
    st.Page("pages/2_optimize.py",   title="최적화",       icon="🟣"),
    st.Page("pages/3_validate.py",   title="검증",         icon="🟢"),
    st.Page("pages/4_params.py",     title="파라미터 탐색기", icon="🔬"),
])
pg.run()
