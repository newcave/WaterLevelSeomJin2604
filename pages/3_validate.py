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

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    optimize = st.checkbox("최적화 적용 (per_station)", value=True)
    run_btn  = st.button("▶ 전체 검증 실행", type="primary", use_container_width=True)

st.title("🟢 3-이벤트 교차 검증")
st.caption("tesr / tesr2 / tesr3 이벤트 → RMSE 비교 → CSV 다운로드")
st.divider()

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")
EVENTS    = available_demos()
N_STATION = 20

@st.cache_data
def get_demo(ev): return load_demo(ev)

if not run_btn:
    st.info("사이드바에서 **▶ 전체 검증 실행**을 누르세요.")
    st.subheader("📊 기준 비교표 (사전 계산값)")
    st.dataframe(
        pd.DataFrame({
            "이벤트":        ["Event 1 (tesr)", "Event 2 (tesr2)", "Event 3★ (tesr3)"],
            "Python 최적화": [0.743, 0.840, 1.057],
            "원본 EXE":      [0.254, 0.795, 5.579],
        }).style.highlight_min(axis=1, color="#E8F5E9",
                               subset=["Python 최적화", "원본 EXE"]),
        use_container_width=True, hide_index=True
    )
    st.caption("★ Event3: Python(1.057m) < EXE(5.579m) — 견고성 우월")
    st.stop()

all_rmse      = {}
all_rmse_mean = {}
progress = st.progress(0, text="검증 준비 중...")
dl = DataLibrary(param_path)

for i, ev in enumerate(EVENTS):
    progress.progress(i / len(EVENTS), text=f"{ev} 처리 중...")
    try:
        nc = get_demo(ev)
        if optimize:
            opt = FlowOptimizer(dl, nc.wl, nc.q_station)
            res = opt.optimize("per_station", verbose=False)
            sr  = res.sim_result
        else:
            sr = WaterLevelSimulator(dl, nc.wl, nc.q_station).run()
        all_rmse[ev]      = sr.rmse
        all_rmse_mean[ev] = sr.rmse_mean
    except Exception as e:
        st.warning(f"{ev} 오류: {e}")
        all_rmse[ev]      = np.full(N_STATION, np.nan)
        all_rmse_mean[ev] = np.nan

progress.progress(1.0, text="완료!")

cols = st.columns(len(EVENTS))
for c, ev in zip(cols, EVENTS):
    val = all_rmse_mean[ev]
    c.metric(ev, f"{val:.4f} m" if not np.isnan(val) else "오류")

st.divider()
st.subheader("스테이션별 RMSE 비교")
df_cmp = pd.DataFrame({"스테이션": [f"St{i+1:02d}" for i in range(N_STATION)]})
for ev in EVENTS:
    df_cmp[ev] = all_rmse[ev].round(4)
st.dataframe(df_cmp, use_container_width=True, hide_index=True)
st.bar_chart(df_cmp.set_index("스테이션"), use_container_width=True)

st.divider()
st.download_button(
    label="📥 결과 CSV 다운로드",
    data=df_cmp.to_csv(index=False).encode("utf-8-sig"),
    file_name="validation_rmse.csv",
    mime="text/csv",
    type="primary"
)
