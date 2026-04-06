"""pages/2_optimize.py — 유량 최적화"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary
from waterlevel_sim.optimizer import FlowOptimizer
from waterlevel_sim.npz_loader import load_demo, available_demos, load_uploaded_nc

st.set_page_config(page_title="최적화 — WaterLevelSim", page_icon="🟣", layout="wide")

# ─── 사이드바 ────────────────────────────────────────────────── #
# ─── 사이드바 네비게이션 ──────────────────────────────────────── #
with st.sidebar:
    st.image("https://raw.githubusercontent.com/streamlit/streamlit/develop/lib/streamlit/static/favicon.png",
             width=32)
    st.title("🌊 WaterLevelSim")
    st.caption("섬진강 수위 예측 시스템")
    st.divider()
    st.markdown("### 📌 페이지 이동")
    st.markdown("🏠 **홈** ← 현재 페이지")
    st.page_link("pages/1_simulation.py", label="🔵 시뮬레이션")
    st.page_link("pages/2_optimize.py",   label="🟣 최적화")
    st.page_link("pages/3_validate.py",   label="🟢 검증")
    st.page_link("pages/4_params.py",     label="🔬 파라미터 탐색기")
    st.divider()
    st.markdown("""
**데이터**: 내장 NPZ (NC 불필요)  
**이벤트**: tesr / tesr2 / tesr3  
**스테이션**: 섬진강 20개 BP
""")

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
    scale_min = st.slider("스케일 최솟값", 0.01, 1.0, 0.05)
    scale_max = st.slider("스케일 최댓값", 1.0, 10.0, 5.0)
    run_btn = st.button("▶ 최적화 실행", type="primary", use_container_width=True)

# ─── 타이틀 ─────────────────────────────────────────────────── #
st.title("🟣 유량 최적화")
st.caption("FlowOptimizer 파라미터 조절 → RMSE 개선")
st.divider()

# ─── 데이터 로드 ─────────────────────────────────────────────── #
@st.cache_data
def get_demo(event):
    return load_demo(event)

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")

try:
    nc = get_demo(event)
    dl = DataLibrary(param_path)
except Exception as e:
    st.error(f"데이터 로드 오류: {e}")
    st.stop()

# ─── 최적화 실행 ─────────────────────────────────────────────── #
if not run_btn:
    st.info("사이드바에서 설정 후 **▶ 최적화 실행** 버튼을 누르세요.")
    st.stop()

opt = FlowOptimizer(dl, nc.wl, nc.q_station)

with st.spinner(f"최적화 실행 중... ({mode})"):
    try:
        kwargs = {"scale_bounds": (scale_min, scale_max), "verbose": False}
        if mode == "timeseries":
            kwargs["window"] = window
        if mode == "global":
            kwargs = {"verbose": False}
        result = opt.optimize(mode=mode, **kwargs)
    except Exception as e:
        st.error(f"최적화 오류: {e}")
        st.stop()

# ─── 결과 요약 ───────────────────────────────────────────────── #
col1, col2, col3, col4 = st.columns(4)
col1.metric("초기 RMSE",  f"{result.rmse_init:.4f} m")
col2.metric("최적화 RMSE", f"{result.rmse_opt:.4f} m", delta=f"-{result.rmse_init - result.rmse_opt:.4f} m")
col3.metric("개선율",      f"{result.improvement:.1f} %")
col4.metric("함수 호출",   f"{result.n_calls} 회")

st.divider()

# ─── 스케일 인수 시각화 ──────────────────────────────────────── #
N_STATION = 20
st.subheader("스테이션별 스케일 인수")
df_scale = pd.DataFrame({
    "스테이션": [f"St{i+1:02d}" for i in range(N_STATION)],
    "스케일":   result.scales,
}).set_index("스테이션")
st.bar_chart(df_scale, use_container_width=True)

# ─── RMSE 비교 ───────────────────────────────────────────────── #
st.subheader("최적화 전후 RMSE 비교")
sr = result.sim_result
df_cmp = pd.DataFrame({
    "스테이션":   [f"St{i+1:02d}" for i in range(N_STATION)],
    "최적화 RMSE": sr.rmse.round(4),
    "거리(km)":    sr.bp_km,
}).set_index("스테이션")
st.bar_chart(df_cmp["최적화 RMSE"], use_container_width=True)

# ─── 시계열 미리보기 ─────────────────────────────────────────── #
st.subheader("수위 시계열 미리보기")
stn = st.selectbox("스테이션", list(range(1, N_STATION+1)),
                   format_func=lambda x: f"St{x:02d}  ({sr.bp_km[x-1]:.1f} km)")
p = stn - 1
df_ts = pd.DataFrame({
    "시간(h)": sr.time_hours,
    "예측(m)": sr.wl_pred[p],
    "참값(m)": sr.wl_true[p],
}).set_index("시간(h)")
st.line_chart(df_ts, use_container_width=True)

# ─── 상세 테이블 ─────────────────────────────────────────────── #
with st.expander("📋 전체 스테이션 최적화 결과"):
    df_full = pd.DataFrame({
        "스테이션":  [f"St{i+1:02d}" for i in range(N_STATION)],
        "거리(km)":  sr.bp_km,
        "스케일":    result.scales.round(4),
        "RMSE(m)":   sr.rmse.round(4),
        "MAE(m)":    sr.mae.round(4),
        "BIAS(m)":   sr.bias.round(4),
    })
    st.dataframe(df_full, use_container_width=True, hide_index=True)
