"""pages/4_params.py — 파라미터 탐색기"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary
from waterlevel_sim.data_library import N_STATION, EVENT_CRITERIA, BP_KM

st.set_page_config(page_title="파라미터 탐색기 — WaterLevelSim", page_icon="🔬", layout="wide")

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

# ─── 타이틀 ─────────────────────────────────────────────────── #
st.title("🔬 파라미터 탐색기")
st.caption("c_sm 히트맵 · Q계수 테이블 · 단일 스텝 계산기")
st.divider()

# ─── 데이터 로드 ─────────────────────────────────────────────── #
param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")

@st.cache_resource
def get_dl():
    return DataLibrary(param_path)

try:
    dl = get_dl()
except Exception as e:
    st.error(f"DataLibrary 로드 오류: {e}")
    st.stop()

# ─── 탭 구성 ─────────────────────────────────────────────────── #
tab1, tab2, tab3 = st.tabs(["📊 c_sm 히트맵", "📋 Q계수 테이블", "🔢 단일 스텝 계산기"])

# ── Tab 1: c_sm 히트맵 ────────────────────────────────────────── #
with tab1:
    st.subheader("기저 수위 c_sm 히트맵  (스테이션 × 서브모델)")
    c_sm_data = np.array([
        [dl.get_submodel_params(stn, sm)[2] for sm in range(4)]
        for stn in range(1, N_STATION + 1)
    ])
    df_csm = pd.DataFrame(
        c_sm_data,
        index=[f"St{i+1:02d}" for i in range(N_STATION)],
        columns=["sm=0", "sm=1", "sm=2", "sm=3"]
    )
    st.dataframe(
        df_csm.style.background_gradient(cmap="Blues", axis=None),
        use_container_width=True
    )

    st.caption("c_sm: 기저 수위 [m] — 유량 체계(sm)별 기준 수위")

    # event_criteria 표
    st.subheader("서브모델 전환 기준 수위 (event_criteria)")
    df_ec = pd.DataFrame(
        EVENT_CRITERIA,
        index=[f"St{i+1:02d}" for i in range(N_STATION)],
        columns=["c0 (sm 0→1)", "c1 (sm 1→2)", "c2 (sm 2→3)"]
    )
    st.dataframe(df_ec.style.background_gradient(cmap="Oranges", axis=None),
                 use_container_width=True)

# ── Tab 2: Q계수 테이블 ───────────────────────────────────────── #
with tab2:
    st.subheader("유량 계수 a_sm, b_sm  전체 테이블")
    sm_sel = st.radio("서브모델 선택", [0, 1, 2, 3], horizontal=True,
                      format_func=lambda x: f"sm={x}")

    rows = []
    for stn in range(1, N_STATION + 1):
        a, b, c = dl.get_submodel_params(stn, sm_sel)
        rows.append({
            "스테이션":  f"St{stn:02d}",
            "거리(km)":  BP_KM[stn],
            "a_sm":      round(a, 6),
            "b_sm":      round(b, 6),
            "c_sm(m)":   round(c, 4),
        })
    df_qcoef = pd.DataFrame(rows)
    st.dataframe(
        df_qcoef.style
            .background_gradient(subset=["a_sm"], cmap="Greens")
            .background_gradient(subset=["b_sm"], cmap="Purples"),
        use_container_width=True, hide_index=True
    )

    st.caption(
        "예측 모델: WL(t+1) = c_sm + a_sm × Q(t) + b_sm × Q(t-1)"
    )

# ── Tab 3: 단일 스텝 계산기 ──────────────────────────────────── #
with tab3:
    st.subheader("단일 스텝 수위 계산기")
    st.markdown("파라미터를 직접 입력해 예측 수위를 즉시 확인하세요.")

    c1, c2 = st.columns(2)
    with c1:
        calc_stn   = st.selectbox("스테이션", list(range(1, N_STATION + 1)),
                                  format_func=lambda x: f"St{x:02d}  ({BP_KM[x]:.1f} km)")
        wl_prev    = st.number_input("직전 수위 wl_prev [m]",
                                     value=float(EVENT_CRITERIA[calc_stn-1][0]),
                                     format="%.4f")
    with c2:
        q0 = st.number_input("현재 유량 Q(t) [m³/s]",   value=100.0, min_value=0.0, format="%.2f")
        q1 = st.number_input("직전 유량 Q(t-1) [m³/s]", value=90.0,  min_value=0.0, format="%.2f")

    sm = dl.get_submodel(calc_stn, wl_prev)
    a, b, c = dl.get_submodel_params(calc_stn, sm)
    wl_calc = c + a * q0 + b * q1
    wl_clipped = dl.clip_wl(calc_stn, wl_calc)

    st.divider()
    res_cols = st.columns(4)
    res_cols[0].metric("서브모델 (sm)", sm)
    res_cols[1].metric("a_sm",  f"{a:.6f}")
    res_cols[2].metric("b_sm",  f"{b:.6f}")
    res_cols[3].metric("c_sm",  f"{c:.4f} m")

    st.divider()
    out_cols = st.columns(2)
    out_cols[0].metric("예측 수위 (클리핑 전)", f"{wl_calc:.4f} m")
    out_cols[1].metric("예측 수위 (클리핑 후)", f"{wl_clipped:.4f} m")

    level_lo = dl.level_limit[calc_stn-1, 1]
    level_hi = dl.level_limit[calc_stn-1, 0]
    st.caption(
        f"수위 범위: {level_lo:.2f} m ~ {level_hi:.2f} m  "
        f"(level_limit St{calc_stn:02d})"
    )
    st.latex(
        rf"WL = {c:.4f} + {a:.6f} \times {q0:.1f} + {b:.6f} \times {q1:.1f} = {wl_calc:.4f}\ m"
    )
