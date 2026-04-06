"""pages/3_validate.py — 3-이벤트 교차 검증"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary, WaterLevelSimulator
from waterlevel_sim.optimizer import FlowOptimizer
from waterlevel_sim.npz_loader import load_demo, available_demos

st.set_page_config(page_title="검증 — WaterLevelSim", page_icon="🟢", layout="wide")

# ─── 사이드바 ────────────────────────────────────────────────── #
with st.sidebar:
    st.title("🌊 WaterLevelSim")
    st.caption("섬진강 수위 예측 시스템")
    st.divider()
    st.markdown("### 📌 페이지 이동")
    if st.button("🏠 홈",              use_container_width=True): st.switch_page("app.py")
    if st.button("🔵 시뮬레이션",      use_container_width=True): st.switch_page("pages/1_simulation.py")
    if st.button("🟣 최적화",          use_container_width=True): st.switch_page("pages/2_optimize.py")
    if st.button("🟢 검증",            use_container_width=True): st.switch_page("pages/3_validate.py")
    if st.button("🔬 파라미터 탐색기", use_container_width=True): st.switch_page("pages/4_params.py")
    st.divider()

    st.markdown("### ⚙️ 설정")
    optimize = st.checkbox("최적화 적용 (per_station)", value=True)
    run_btn  = st.button("▶ 전체 검증 실행", type="primary", use_container_width=True)

# ─── 타이틀 ─────────────────────────────────────────────────── #
st.title("🟢 3-이벤트 교차 검증")
st.caption("tesr / tesr2 / tesr3 이벤트 → RMSE 비교 → CSV 다운로드")
st.divider()

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")
EVENTS = available_demos()
N_STATION = 20

if not run_btn:
    st.info("사이드바에서 **▶ 전체 검증 실행**을 누르세요.")

    # 기준 표 표시
    st.subheader("📊 기준 비교표 (사전 계산값)")
    df_ref = pd.DataFrame({
        "이벤트":        ["Event 1 (tesr)", "Event 2 (tesr2)", "Event 3★ (tesr3)"],
        "Python 최적화": [0.743, 0.840, 1.057],
        "원본 EXE":      [0.254, 0.795, 5.579],
    })
    st.dataframe(
        df_ref.style.highlight_min(
            axis=1, color="#E8F5E9",
            subset=["Python 최적화", "원본 EXE"]
        ),
        use_container_width=True, hide_index=True
    )
    st.caption("★ Event3: Python(1.057m) < EXE(5.579m) — 견고성 우월")
    st.stop()

# ─── 검증 실행 ───────────────────────────────────────────────── #
@st.cache_data
def get_demo(event):
    return load_demo(event)

all_rmse   = {}   # event → ndarray(20)
all_rmse_mean = {}

progress = st.progress(0, text="검증 준비 중...")
dl = DataLibrary(param_path)

for i, ev in enumerate(EVENTS):
    progress.progress((i) / len(EVENTS), text=f"{ev} 처리 중...")
    try:
        nc  = get_demo(ev)
        if optimize:
            opt = FlowOptimizer(dl, nc.wl, nc.q_station)
            res = opt.optimize("per_station", verbose=False)
            sr  = res.sim_result
        else:
            sim = WaterLevelSimulator(dl, nc.wl, nc.q_station)
            sr  = sim.run()
        all_rmse[ev]      = sr.rmse
        all_rmse_mean[ev] = sr.rmse_mean
    except Exception as e:
        st.warning(f"{ev} 오류: {e}")
        all_rmse[ev]      = np.full(N_STATION, np.nan)
        all_rmse_mean[ev] = np.nan

progress.progress(1.0, text="완료!")

# ─── 결과 요약 ───────────────────────────────────────────────── #
st.subheader("이벤트별 평균 RMSE")
cols = st.columns(len(EVENTS))
for c, ev in zip(cols, EVENTS):
    c.metric(ev, f"{all_rmse_mean[ev]:.4f} m" if not np.isnan(all_rmse_mean[ev]) else "오류")

st.divider()

# ─── RMSE 비교 테이블 ────────────────────────────────────────── #
st.subheader("스테이션별 RMSE 비교")
df_cmp = pd.DataFrame({"스테이션": [f"St{i+1:02d}" for i in range(N_STATION)]})
for ev in EVENTS:
    df_cmp[ev] = all_rmse[ev].round(4)
st.dataframe(df_cmp, use_container_width=True, hide_index=True)

# ─── RMSE 차트 ───────────────────────────────────────────────── #
st.subheader("스테이션별 RMSE 시각화")
df_chart = df_cmp.set_index("스테이션")[list(EVENTS)]
st.bar_chart(df_chart, use_container_width=True)

# ─── CSV 다운로드 ────────────────────────────────────────────── #
st.divider()
csv = df_cmp.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="📥 결과 CSV 다운로드",
    data=csv,
    file_name="validation_rmse.csv",
    mime="text/csv",
    type="primary"
)
