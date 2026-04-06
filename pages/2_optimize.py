"""pages/2_optimize.py — 유량 최적화"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary
from waterlevel_sim.optimizer import FlowOptimizer
from waterlevel_sim.npz_loader import load_demo, available_demos

st.set_page_config(page_title="최적화 — WaterLevelSim", page_icon="🟣", layout="wide")

with st.sidebar:
    st.markdown("### ⚙️ 설정")
    demos  = available_demos()
    event  = st.selectbox("이벤트 선택", demos, index=0)
    mode   = st.selectbox(
        "최적화 모드",
        ["per_station", "global", "timeseries"],
        help="per_station: 스테이션별 독립(권장) | global: 단일 스케일 | timeseries: 그룹별 정밀"
    )
    if mode == "timeseries":
        window = st.slider("그룹 윈도우 크기", 5, 30, 10)
    else:
        window = 10
    scale_min = st.slider("스케일 최솟값", 0.01, 1.0, 0.05)
    scale_max = st.slider("스케일 최댓값", 1.0, 10.0, 5.0)
    run_btn = st.button("▶ 최적화 실행", type="primary", use_container_width=True)

st.title("🟣 유량 최적화")
st.caption("FlowOptimizer 파라미터 조절 → RMSE 개선")
st.divider()

@st.cache_data
def get_demo(ev): return load_demo(ev)

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")

try:
    nc = get_demo(event)
    dl = DataLibrary(param_path)
except Exception as e:
    st.error(f"데이터 로드 오류: {e}"); st.stop()

if not run_btn:
    st.info("사이드바에서 설정 후 **▶ 최적화 실행** 버튼을 누르세요.")
    st.stop()

opt = FlowOptimizer(dl, nc.wl, nc.q_station)
with st.spinner(f"최적화 실행 중... ({mode})"):
    try:
        if mode == "global":
            result = opt.optimize("global", verbose=False)
        elif mode == "timeseries":
            result = opt.optimize("timeseries", scale_bounds=(scale_min, scale_max), window=window, verbose=False)
        else:
            result = opt.optimize("per_station", scale_bounds=(scale_min, scale_max), verbose=False)
    except Exception as e:
        st.error(f"최적화 오류: {e}"); st.stop()

N_STATION = 20
col1, col2, col3, col4 = st.columns(4)
col1.metric("초기 RMSE",   f"{result.rmse_init:.4f} m")
col2.metric("최적화 RMSE", f"{result.rmse_opt:.4f} m", delta=f"-{result.rmse_init - result.rmse_opt:.4f} m")
col3.metric("개선율",      f"{result.improvement:.1f} %")
col4.metric("함수 호출",   f"{result.n_calls} 회")
st.divider()

sr = result.sim_result
st.subheader("스테이션별 스케일 인수")
st.bar_chart(pd.DataFrame({"스케일": result.scales},
             index=[f"St{i+1:02d}" for i in range(N_STATION)]))

st.subheader("최적화 후 RMSE")
st.bar_chart(pd.DataFrame({"RMSE(m)": sr.rmse.round(4)},
             index=[f"St{i+1:02d}" for i in range(N_STATION)]))

st.subheader("수위 시계열 미리보기")
stn = st.selectbox("스테이션", list(range(1, N_STATION+1)),
                   format_func=lambda x: f"St{x:02d}  ({sr.bp_km[x-1]:.1f} km)")
p = stn - 1
st.line_chart(pd.DataFrame({"예측(m)": sr.wl_pred[p], "참값(m)": sr.wl_true[p]},
              index=sr.time_hours), use_container_width=True)

with st.expander("📋 전체 스테이션 결과"):
    st.dataframe(pd.DataFrame({
        "스테이션": [f"St{i+1:02d}" for i in range(N_STATION)],
        "거리(km)": sr.bp_km, "스케일": result.scales.round(4),
        "RMSE(m)":  sr.rmse.round(4), "MAE(m)": sr.mae.round(4), "BIAS(m)": sr.bias.round(4),
    }), use_container_width=True, hide_index=True)
