"""app.py — WaterLevelSim 홈 페이지"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="WaterLevelSim — 섬진강 수위 예측",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 사이드바 네비게이션 ──────────────────────────────────────── #
with st.sidebar:
    st.image("https://raw.githubusercontent.com/streamlit/streamlit/develop/lib/streamlit/static/favicon.png",
             width=32)
    st.title("🌊 WaterLevelSim")
    st.caption("섬진강 수위 예측 시스템")
    st.divider()

    st.markdown("### 📌 페이지 이동")
    if st.button("🏠 홈",           use_container_width=True): st.switch_page("app.py")
    if st.button("🔵 시뮬레이션",   use_container_width=True): st.switch_page("pages/1_🔵_시뮬레이션.py")
    if st.button("🟣 최적화",       use_container_width=True): st.switch_page("pages/2_🟣_최적화.py")
    if st.button("🟢 검증",         use_container_width=True): st.switch_page("pages/3_🟢_검증.py")
    if st.button("🔬 파라미터 탐색기", use_container_width=True): st.switch_page("pages/4_🔬_파라미터탐색기.py")

    st.divider()
    st.markdown("""
**데이터**: 내장 NPZ (NC 불필요)  
**이벤트**: tesr / tesr2 / tesr3  
**스테이션**: 섬진강 20개 BP
""")

# ─── 스타일 ──────────────────────────────────────────────────── #
st.markdown("""
<style>
  .metric-box {
    background:#f0f4f8; border-radius:8px;
    padding:16px; text-align:center;
  }
  .metric-val { font-size:2rem; font-weight:700; color:#1F4E79; }
  .metric-lbl { font-size:0.85rem; color:#595959; }
</style>
""", unsafe_allow_html=True)

# ─── 헤더 ────────────────────────────────────────────────────── #
st.title("🌊 WaterLevelSim")
st.caption("섬진강 수위 예측 시스템 — Python 포트 v2  |  K-Water 2021 → Python 3 이식")
st.divider()

# ─── 핵심 지표 ───────────────────────────────────────────────── #
c1, c2, c3, c4 = st.columns(4)
c1.markdown('<div class="metric-box"><div class="metric-val">0.675 m</div>'
            '<div class="metric-lbl">최적화 후 평균 RMSE</div></div>', unsafe_allow_html=True)
c2.markdown('<div class="metric-box"><div class="metric-val">75.8 %</div>'
            '<div class="metric-lbl">베이스 대비 RMSE 개선</div></div>', unsafe_allow_html=True)
c3.markdown('<div class="metric-box"><div class="metric-val">20 개</div>'
            '<div class="metric-lbl">예측 스테이션 수</div></div>', unsafe_allow_html=True)
c4.markdown('<div class="metric-box"><div class="metric-val">3 건</div>'
            '<div class="metric-lbl">홍수 이벤트 검증</div></div>', unsafe_allow_html=True)

st.divider()

# ─── 본문 ────────────────────────────────────────────────────── #
col_l, col_r = st.columns([3, 2])

with col_l:
    st.subheader("앱 구성")
    st.markdown("""
| 페이지 | 내용 |
|--------|------|
| 🔵 **시뮬레이션** | NPZ 로드 → 수위 예측 → 시계열·RMSE·산점도 |
| 🟣 **최적화** | FlowOptimizer 파라미터 조절 → RMSE 개선 |
| 🟢 **검증** | 3-이벤트 교차 검증 → CSV 다운로드 |
| 🔬 **파라미터 탐색기** | c_sm 히트맵, Q계수, 단일 스텝 계산기 |
""")

    st.subheader("예측 모델")
    st.latex(r"WL(\text{station},\; t+1) = c_{sm} + a_{sm} \cdot Q(t) + b_{sm} \cdot Q(t-1)")
    st.markdown("""
- **sm** = event_criteria 기반 유량 체계 (0~3)
- **c_sm** = 기저 수위 [m]
- **a_sm, b_sm** = 유량 계수 [m/(m³/s)]
- **Q** = 단면 통과 유량 [m³/s]
""")

with col_r:
    st.subheader("RMSE 비교")
    df = pd.DataFrame({
        "단계":     ["베이스라인", "per_station", "timeseries", "원본 EXE"],
        "RMSE (m)": [2.785, 0.743, 0.675, 0.254],
        "개선율":   ["—", "+73.3%", "+75.8%", "+90.9%"],
    })
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("3-이벤트 평균")
    df2 = pd.DataFrame({
        "이벤트":       ["Event 1", "Event 2", "Event 3★"],
        "Python 최적화": [0.743, 0.840, 1.057],
        "원본 EXE":     [0.254, 0.795, 5.579],
    })
    # highlight_min: 숫자 열만 지정 (문자열 포함 오류 방지)
    st.dataframe(
        df2.style.highlight_min(
            axis=1, color="#E8F5E9",
            subset=["Python 최적화", "원본 EXE"]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("★ Event3: Python(1.057m) < EXE(5.579m) — 견고성 우월")

st.divider()

st.subheader("⚡ 빠른 시작")
st.code("""git clone https://github.com/newcave/WaterLevelSeomJin2604
cd WaterLevelSeomJin2604
pip install -r requirements.txt
streamlit run app.py
""", language="bash")

with st.expander("📦 데이터 준비"):
    st.markdown("""
**내장 데모 데이터** (NPZ, 45KB × 3개) 로 즉시 실행 가능합니다.  
NC 파일 없이 모든 기능이 작동합니다.
""")
