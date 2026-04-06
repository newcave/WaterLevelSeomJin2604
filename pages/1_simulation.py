"""pages/1_simulation.py — 수위 시뮬레이션"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary, WaterLevelSimulator
from waterlevel_sim.npz_loader import load_demo, available_demos, load_uploaded_nc

st.set_page_config(page_title="시뮬레이션 — WaterLevelSim", page_icon="🔵", layout="wide")

# ─── 사이드바 ────────────────────────────────────────────────── #
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    data_src = st.radio("데이터 소스", ["내장 데모 NPZ", "NC 파일 업로드"])
    if data_src == "내장 데모 NPZ":
        demos = available_demos()
        event = st.selectbox("이벤트 선택", demos, index=0)
    else:
        nc_file = st.file_uploader("NC 파일 업로드", type=["nc"])

# ─── 타이틀 ─────────────────────────────────────────────────── #
st.title("🔵 수위 시뮬레이션")
st.caption("NPZ/NC 로드 → 수위 예측 → 시계열·RMSE·산점도")
st.divider()

# ─── 데이터 로드 ─────────────────────────────────────────────── #
@st.cache_data
def get_demo(event):
    return load_demo(event)

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")

try:
    if data_src == "내장 데모 NPZ":
        nc = get_demo(event)
    else:
        if nc_file is None:
            st.info("NC 파일을 업로드하세요.")
            st.stop()
        nc = load_uploaded_nc(nc_file)

    dl  = DataLibrary(param_path)
    sim = WaterLevelSimulator(dl, nc.wl, nc.q_station)

    with st.spinner("시뮬레이션 실행 중..."):
        result = sim.run()

except FileNotFoundError as e:
    st.error(f"파일을 찾을 수 없습니다: {e}")
    st.stop()
except Exception as e:
    st.error(f"오류 발생: {e}")
    st.stop()

# ─── 핵심 지표 ───────────────────────────────────────────────── #
c1, c2, c3, c4 = st.columns(4)
c1.metric("평균 RMSE",  f"{result.rmse_mean:.3f} m")
c2.metric("최소 RMSE",  f"{result.rmse.min():.3f} m")
c3.metric("최대 RMSE",  f"{result.rmse.max():.3f} m")
c4.metric("유효 스텝수", f"{result.n_valid}")

st.divider()

# ─── 스테이션 선택 ───────────────────────────────────────────── #
N_STATION = 20
col_ctrl, col_chart = st.columns([1, 3])

with col_ctrl:
    stn = st.selectbox(
        "스테이션 선택",
        options=list(range(1, N_STATION + 1)),
        format_func=lambda x: f"St{x:02d}  ({result.bp_km[x-1]:.1f} km)"
    )

p = stn - 1
pred = result.wl_pred[p]
true = result.wl_true[p]
time = result.time_hours

with col_chart:
    st.subheader(f"St{stn:02d} 수위 시계열  ({result.bp_km[p]:.1f} km)")
    df_ts = pd.DataFrame({
        "시간(h)":   time,
        "예측(m)":   pred,
        "참값(m)":   true,
    }).set_index("시간(h)")
    st.line_chart(df_ts, use_container_width=True)

# ─── RMSE 막대그래프 ─────────────────────────────────────────── #
st.subheader("스테이션별 RMSE")
df_rmse = pd.DataFrame({
    "스테이션": [f"St{i+1:02d}" for i in range(N_STATION)],
    "RMSE (m)": result.rmse,
    "거리 (km)": result.bp_km,
}).set_index("스테이션")
st.bar_chart(df_rmse["RMSE (m)"], use_container_width=True)

# ─── 산점도 (예측 vs 참값) ───────────────────────────────────── #
st.subheader(f"St{stn:02d} 산점도 — 예측 vs 참값")
df_scatter = pd.DataFrame({"참값 (m)": true, "예측 (m)": pred})
st.scatter_chart(df_scatter, x="참값 (m)", y="예측 (m)", use_container_width=True)

# ─── 통계 테이블 ─────────────────────────────────────────────── #
with st.expander("📋 전체 스테이션 통계 테이블"):
    df_stats = pd.DataFrame({
        "스테이션": [f"St{i+1:02d}" for i in range(N_STATION)],
        "거리(km)":  result.bp_km,
        "RMSE(m)":   result.rmse.round(4),
        "MAE(m)":    result.mae.round(4),
        "BIAS(m)":   result.bias.round(4),
    })
    st.dataframe(df_stats, use_container_width=True, hide_index=True)
