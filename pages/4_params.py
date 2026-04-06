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

st.title("🔬 파라미터 탐색기")
st.caption("c_sm 히트맵 · Q계수 테이블 · 단일 스텝 계산기")
st.divider()

param_path = str(Path(__file__).parent.parent / "data" / "ParamSetforcxx.csv")

@st.cache_resource
def get_dl(): return DataLibrary(param_path)

try:
    dl = get_dl()
except Exception as e:
    st.error(f"DataLibrary 로드 오류: {e}"); st.stop()

tab1, tab2, tab3 = st.tabs(["📊 c_sm 히트맵", "📋 Q계수 테이블", "🔢 단일 스텝 계산기"])

with tab1:
    st.subheader("기저 수위 c_sm 히트맵  (스테이션 × 서브모델)")
    c_sm_data = np.array([
        [dl.get_submodel_params(s, sm)[2] for sm in range(4)]
        for s in range(1, N_STATION + 1)
    ])
    df_csm = pd.DataFrame(c_sm_data,
                          index=[f"St{i+1:02d}" for i in range(N_STATION)],
                          columns=["sm=0","sm=1","sm=2","sm=3"])
    st.dataframe(df_csm.style.background_gradient(cmap="Blues", axis=None),
                 use_container_width=True)
    st.subheader("서브모델 전환 기준 수위")
    df_ec = pd.DataFrame(EVENT_CRITERIA,
                         index=[f"St{i+1:02d}" for i in range(N_STATION)],
                         columns=["c0 (sm 0→1)","c1 (sm 1→2)","c2 (sm 2→3)"])
    st.dataframe(df_ec.style.background_gradient(cmap="Oranges", axis=None),
                 use_container_width=True)

with tab2:
    st.subheader("유량 계수 a_sm, b_sm  전체 테이블")
    sm_sel = st.radio("서브모델", [0,1,2,3], horizontal=True,
                      format_func=lambda x: f"sm={x}")
    rows = [{"스테이션": f"St{s:02d}", "거리(km)": BP_KM[s],
             "a_sm": round(dl.get_submodel_params(s,sm_sel)[0],6),
             "b_sm": round(dl.get_submodel_params(s,sm_sel)[1],6),
             "c_sm(m)": round(dl.get_submodel_params(s,sm_sel)[2],4)}
            for s in range(1, N_STATION+1)]
    st.dataframe(
        pd.DataFrame(rows).style
            .background_gradient(subset=["a_sm"], cmap="Greens")
            .background_gradient(subset=["b_sm"], cmap="Purples"),
        use_container_width=True, hide_index=True)
    st.caption("예측 모델: WL(t+1) = c_sm + a_sm × Q(t) + b_sm × Q(t-1)")

with tab3:
    st.subheader("단일 스텝 수위 계산기")
    c1, c2 = st.columns(2)
    with c1:
        calc_stn = st.selectbox("스테이션", list(range(1, N_STATION+1)),
                                format_func=lambda x: f"St{x:02d}  ({BP_KM[x]:.1f} km)")
        wl_prev  = st.number_input("직전 수위 wl_prev [m]",
                                   value=float(EVENT_CRITERIA[calc_stn-1][0]), format="%.4f")
    with c2:
        q0 = st.number_input("현재 유량 Q(t) [m³/s]",   value=100.0, min_value=0.0, format="%.2f")
        q1 = st.number_input("직전 유량 Q(t-1) [m³/s]", value=90.0,  min_value=0.0, format="%.2f")

    sm = dl.get_submodel(calc_stn, wl_prev)
    a, b, c = dl.get_submodel_params(calc_stn, sm)
    wl_calc    = c + a*q0 + b*q1
    wl_clipped = dl.clip_wl(calc_stn, wl_calc)
    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("서브모델 (sm)", sm)
    r2.metric("a_sm", f"{a:.6f}")
    r3.metric("b_sm", f"{b:.6f}")
    r4.metric("c_sm", f"{c:.4f} m")
    st.divider()
    o1, o2 = st.columns(2)
    o1.metric("예측 수위 (클리핑 전)", f"{wl_calc:.4f} m")
    o2.metric("예측 수위 (클리핑 후)", f"{wl_clipped:.4f} m")
    lo, hi = dl.level_limit[calc_stn-1, 1], dl.level_limit[calc_stn-1, 0]
    st.caption(f"수위 범위: {lo:.2f} ~ {hi:.2f} m")
    st.latex(rf"WL = {c:.4f} + {a:.6f} \times {q0:.1f} + {b:.6f} \times {q1:.1f} = {wl_calc:.4f}\ m")
