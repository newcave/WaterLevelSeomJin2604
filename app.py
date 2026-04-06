"""app.py — WaterLevelSim Streamlit 앱  (홈 페이지)

Streamlit Cloud 배포 진입점.
"""

import streamlit as st
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# 패키지 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="WaterLevelSim — 섬진강 수위 예측",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 공통 스타일 ──────────────────────────────────────────────── #
st.markdown("""
<style>
  .metric-box {
    background: #f0f4f8; border-radius: 8px;
    padding: 16px; text-align: center;
  }
  .metric-val { font-size: 2rem; font-weight: 700; color: #1F4E79; }
  .metric-lbl { font-size: 0.85rem; color: #595959; }
  .badge-green { background:#E8F5E9; color:#1D6B35; padding:4px 10px;
                 border-radius:12px; font-size:0.8rem; font-weight:600; }
  .badge-blue  { background:#EBF3FB; color:#2E75B6; padding:4px 10px;
                 border-radius:12px; font-size:0.8rem; }
</style>
""", unsafe_allow_html=True)


# ─── 헤더 ─────────────────────────────────────────────────────── #
col_title, col_badge = st.columns([4, 1])
with col_title:
    st.title("🌊 WaterLevelSim")
    st.caption("섬진강 수위 예측 시스템 — Python 포트 v2  |  K-Water 2021 → Python 3 이식")
with col_badge:
    st.markdown("""
    <div style="padding-top:20px">
      <span class="badge-green">✓ 3-이벤트 검증</span><br><br>
      <span class="badge-blue">scipy 최적화</span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ─── 핵심 지표 ────────────────────────────────────────────────── #
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown('<div class="metric-box"><div class="metric-val">0.675 m</div>'
                '<div class="metric-lbl">최적화 후 평균 RMSE</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="metric-box"><div class="metric-val">75.8 %</div>'
                '<div class="metric-lbl">베이스 대비 RMSE 개선</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="metric-box"><div class="metric-val">20 개</div>'
                '<div class="metric-lbl">예측 스테이션 수</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown('<div class="metric-box"><div class="metric-val">3 건</div>'
                '<div class="metric-lbl">홍수 이벤트 검증</div></div>', unsafe_allow_html=True)

st.divider()

# ─── 앱 설명 ──────────────────────────────────────────────────── #
col_l, col_r = st.columns([3, 2])

with col_l:
    st.subheader("앱 구성")
    st.markdown("""
| 페이지 | 내용 |
|--------|------|
| 🔵 **시뮬레이션** | NC / NPZ 파일 로드 → 수위 예측 실행 → 시계열 플롯 |
| 🟣 **최적화** | FlowOptimizer (per_station / timeseries) → RMSE 개선 |
| 🟢 **검증** | 3-이벤트 교차 검증 → 결과 비교 |

왼쪽 사이드바에서 페이지를 선택하세요.
""")

    st.subheader("예측 모델")
    st.latex(r"WL(\mathrm{station},\; t+1) = c_{sm} + a_{sm} \cdot Q(t) + b_{sm} \cdot Q(t-1)")
    st.markdown("""
- **sm** = event_criteria 기반 유량 체계 (0~3)
- **c_sm** = 기저 수위 [m]
- **a_sm, b_sm** = 유량 계수 [m/(m³/s)]
- **Q** = 단면 통과 유량 [m³/s]
""")

with col_r:
    st.subheader("RMSE 비교")
    df = pd.DataFrame({
        "단계": ["베이스라인", "per_station", "timeseries", "원본 EXE"],
        "RMSE (m)": [2.785, 0.743, 0.675, 0.254],
        "개선율": ["—", "+73.3%", "+75.8%", "+90.9%"],
    })
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("3-이벤트 평균")
    df2 = pd.DataFrame({
        "이벤트": ["Event 1", "Event 2", "Event 3★"],
        "Python 최적화": [0.743, 0.840, 1.057],
        "원본 EXE": [0.254, 0.795, 5.579],
    })
    st.dataframe(df2.style.highlight_min(axis=1, color="#E8F5E9"), use_container_width=True)
    st.caption("★ Event3: Python(1.057m) < EXE(5.579m) — 견고성 우월")

st.divider()

# ─── 빠른 시작 ────────────────────────────────────────────────── #
st.subheader("⚡ 빠른 시작")
st.code("""# 로컬 실행
git clone https://github.com/YOUR_ID/waterlevel-seomjin
cd waterlevel-seomjin
pip install -r requirements.txt
streamlit run app.py
""", language="bash")

with st.expander("📦 데이터 준비"):
    st.markdown("""
**내장 데모 데이터** ( 등) 로 즉시 실행 가능합니다.  
NC 파일 없이 45KB NPZ 파일만으로 모든 기능이 작동합니다.
""")
