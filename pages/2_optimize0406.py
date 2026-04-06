"""pages/2_optimize.py — 댐 방류 최적화

원본 UI(섬진강댐_시뮬레이터) 재현:
  ┌──────────────────────────────────────────────────────┐
  │  섬진강댐  방류량 시계열  (기준 + 3 시나리오)        │
  ├──────────────┬───────────────────────────────────────┤
  │  설정 패널   │  Station 기준 수위 테이블              │
  │  6개 파라미터│  (criteria01~04)                      │
  └──────────────┴───────────────────────────────────────┘
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary
from waterlevel_sim.optimizer    import DamOptimizer, DamOptAllResult
from waterlevel_sim.station_info import StationInfo
from waterlevel_sim.npz_loader   import load_demo, available_demos
from waterlevel_sim.dam_config   import (
    OPT_CONFIG, PENALTY_CONFIG, DAM_CONFIG, STATION_INFO_CSV
)

st.set_page_config(page_title="댐 최적화 — WaterLevelSim",
                   page_icon="🟣", layout="wide")

ROOT      = Path(__file__).parent.parent
PARAM_CSV = str(ROOT / "data" / "ParamSetforcxx.csv")
SI_CSV    = str(ROOT / STATION_INFO_CSV)

# ═══════════════════════════════════════════════════════════════ #
#  사이드바 — 설정 패널 (원본 UI 좌측 패널 재현)
# ═══════════════════════════════════════════════════════════════ #
with st.sidebar:
    st.markdown("### 설정")

    event = st.selectbox("이벤트", available_demos(), index=0)
    st.divider()

    # ── 원본 UI 6개 파라미터 ────────────────────────────────── #
    n_blocks    = st.number_input("방류량 조절 횟수",
                                  min_value=1, max_value=20,
                                  value=OPT_CONFIG["n_blocks"])
    block_scale = st.number_input("방류량 조절 스케일",
                                  min_value=10, max_value=500,
                                  value=100,
                                  help="초기 방류량 대비 % (100=기준)")
    max_iter    = st.number_input("최적화 탐색 최대치",
                                  min_value=100, max_value=5000,
                                  value=OPT_CONFIG["max_iter"], step=100)
    max_delta   = st.number_input("조절 방류량 최대폭",
                                  min_value=100, max_value=2000,
                                  value=int(OPT_CONFIG["max_delta_cms"]),
                                  step=100)
    block_hours = st.selectbox("구간 단위 [시간]",
                               [3, 6, 12],
                               index=[3,6,12].index(OPT_CONFIG["block_hours"]))
    init_level  = st.number_input("초기 댐 수위 [EL.m]",
                                  min_value=float(DAM_CONFIG["seomjin"]["min_op_level"]),
                                  max_value=float(DAM_CONFIG["seomjin"]["max_op_level"]),
                                  value=float(DAM_CONFIG["seomjin"]["initial_level"]),
                                  step=0.5)
    st.divider()

    with st.expander("페널티 계수"):
        p_c1 = st.slider("고수부지~주의보",  -50.0,  0.0,
                          float(PENALTY_CONFIG["p_c01_c02"]), 1.0)
        p_c2 = st.slider("주의보~경보",      -80.0,  0.0,
                          float(PENALTY_CONFIG["p_c02_c03"]), 1.0)
        p_c3 = st.slider("경보~계획홍수위", -100.0,  0.0,
                          float(PENALTY_CONFIG["p_c03_c04"]), 1.0)

    run_btn = st.button("▶ Run", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════ #
#  타이틀
# ═══════════════════════════════════════════════════════════════ #
st.title("섬진강댐")
st.caption("방류 최적화 시뮬레이터 — 기준(최초) vs Conservative / Moderate / Aggressive")

# ═══════════════════════════════════════════════════════════════ #
#  데이터 로드
# ═══════════════════════════════════════════════════════════════ #
@st.cache_data
def get_demo(ev): return load_demo(ev)

try:
    nc = get_demo(event)
    dl = DataLibrary(PARAM_CSV)
    si = StationInfo(SI_CSV, penalty_config={
        "p_c01_c02": p_c1, "p_c02_c03": p_c2,
        "p_c03_c04": p_c3, "p_exceed": -100.0,
        "station_weights": {}, "use_time_weight": False,
    })
except Exception as e:
    st.error(f"데이터 로드 오류: {e}"); st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  하단 2컬럼: 설정 요약 + Station 테이블  (원본 UI 하단 재현)
# ═══════════════════════════════════════════════════════════════ #
col_cfg, col_tbl = st.columns([1, 2])

with col_cfg:
    st.subheader("설정 요약")
    st.markdown(f"""
| 항목 | 값 |
|------|-----|
| 방류량 조절 횟수 | **{n_blocks}** |
| 방류량 조절 스케일 | **{block_scale}** |
| 최적화 탐색 최대치 | **{max_iter}** |
| 조절 방류량 최대폭 | **{max_delta}** m³/s |
| 구간 단위 | **{block_hours}** 시간 |
| 초기 댐 수위 | **{init_level:.2f}** EL.m |
""")

with col_tbl:
    st.subheader("Station 기준 수위")
    df_si = pd.DataFrame([{
        "Station":    f"{r.station_km:.3f}",
        "max":        r.wl_max,
        "min":        r.wl_min,
        "criteria01": r.criteria01,
        "criteria02": r.criteria02,
        "criteria03": r.criteria03,
        "criteria04": r.criteria04,
        "Original S.": r.original_km,
    } for r in si.records])
    st.dataframe(df_si, use_container_width=True,
                 hide_index=True, height=250)

st.divider()

# ═══════════════════════════════════════════════════════════════ #
#  Run 전: 기준 방류량 미리보기
# ═══════════════════════════════════════════════════════════════ #
q_sj  = DamOptimizer.extract_q_sj(nc.q_station)
n_t   = len(q_sj)
t_min = np.arange(n_t) * 30

if not run_btn:
    st.subheader("기준(최초) 운영모의 — 방류량")
    st.line_chart(
        pd.DataFrame({"기준(최초) 운영모의 [m³/s]": q_sj}, index=t_min),
        use_container_width=True, height=350
    )
    st.caption("X축: [min.]   Y축: [m³/s]")
    st.info("설정 확인 후 **▶ Run** 을 누르면 3개 시나리오 최적화를 실행합니다.")
    st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  최적화 실행
# ═══════════════════════════════════════════════════════════════ #
cfg_override = {
    "n_blocks":      int(n_blocks),
    "block_hours":   int(block_hours),
    "max_iter":      int(max_iter),
    "max_delta_cms": float(max_delta),
}

# 스케일 적용 초기 방류량
q_sj_scaled = q_sj * (block_scale / 100.0)

opt = DamOptimizer(
    dl           = dl,
    station_info = si,
    wl_obs       = nc.wl,
    q_station    = nc.q_station,
    q_init_sj    = q_sj_scaled,
    opt_config   = cfg_override,
)

with st.spinner("최적화 실행 중... Conservative → Moderate → Aggressive"):
    try:
        all_res: DamOptAllResult = opt.optimize_all(verbose=False)
    except Exception as e:
        st.error(f"최적화 오류: {e}"); st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  메인 차트 — 원본 UI 재현
#  기준(최초) / [2]최적화(총방류↑) / [1]최적화 / [3]최적화(총방류↓)
# ═══════════════════════════════════════════════════════════════ #
LABELS = {
    "Conservative": "[2] 최적화 운영모의(총 방류 증가시)",
    "Moderate":     "[1] 최적화 운영모의",
    "Aggressive":   "[3] 최적화 운영모의(총 방류 감소시)",
}

st.subheader("섬진강댐 — 방류량 비교")
df_chart = pd.DataFrame({"기준(최초) 운영모의": q_sj_scaled}, index=t_min)
for name, res in all_res.results.items():
    df_chart[LABELS[name]] = res.q_timeseries

st.line_chart(df_chart, use_container_width=True, height=400)
st.caption("X축: [min.]   Y축: [m³/s]")

# ═══════════════════════════════════════════════════════════════ #
#  요약 지표
# ═══════════════════════════════════════════════════════════════ #
st.divider()
cols = st.columns(4)
cols[0].metric("기준 페널티",
               f"{list(all_res.results.values())[0].penalty_init:.1f}")
name_kr = {"Conservative": "[2] 보수적", "Moderate": "[1] 균형", "Aggressive": "[3] 적극적"}
for col, (name, res) in zip(cols[1:], all_res.results.items()):
    col.metric(name_kr[name], f"{res.penalty_opt:.1f}",
               delta=f"{res.improvement:+.1f}%")

# ═══════════════════════════════════════════════════════════════ #
#  탭 상세
# ═══════════════════════════════════════════════════════════════ #
tab1, tab2, tab3 = st.tabs(["블록 방류량", "스테이션 페널티", "수위 시계열"])

with tab1:
    blk_labels = [f"B{i+1}({i*block_hours}~{(i+1)*block_hours}h)"
                  for i in range(int(n_blocks))]
    df_blk = pd.DataFrame(
        {"기준(평균)": opt.q_init_blocks} |
        {name_kr[n]: r.q_blocks for n, r in all_res.results.items()},
        index=blk_labels
    )
    st.dataframe(
        df_blk.style
            .highlight_min(axis=1, color="#E8F5E9")
            .highlight_max(axis=1, color="#FFEBEE")
            .format("{:.1f}"),
        use_container_width=True
    )

with tab2:
    stn_lbl = [f"St{i+1:02d}({si.records[i].original_km:.0f}km)" for i in range(20)]
    df_pen  = pd.DataFrame(
        {name_kr[n]: r.penalty_by_station() for n, r in all_res.results.items()},
        index=stn_lbl
    )
    st.bar_chart(df_pen, use_container_width=True, height=320)

    exceed = []
    for name, res in all_res.results.items():
        for i, rec in enumerate(si.records):
            if i >= res.wl_pred.shape[0]: continue
            mwl = float(res.wl_pred[i].max())
            if mwl > rec.criteria04:
                exceed.append({"시나리오": name_kr[name],
                               "Station": f"{rec.station_km:.3f}km",
                               "최대수위": round(mwl,3),
                               "계획홍수위": rec.criteria04,
                               "초과(m)": round(mwl-rec.criteria04,3)})
    if exceed:
        st.warning("⚠️ 계획홍수위 초과 지점")
        st.dataframe(pd.DataFrame(exceed)
                     .style.background_gradient(subset=["초과(m)"], cmap="Reds"),
                     hide_index=True, use_container_width=True)
    else:
        st.success("✅ 전 시나리오 계획홍수위 초과 없음")

with tab3:
    stn_sel = st.selectbox("스테이션", list(range(1,21)),
                           format_func=lambda x:
                           f"St{x:02d} ({si.records[x-1].original_km:.1f}km)")
    p   = stn_sel - 1
    rec = si.records[p]
    n_valid = list(all_res.results.values())[0].wl_pred.shape[1]
    t_hr_v  = np.arange(n_valid) * 30 / 60

    df_wl = pd.DataFrame({"시간(h)": t_hr_v,
                          "criteria01": rec.criteria01,
                          "criteria04": rec.criteria04})
    for name, res in all_res.results.items():
        if p < res.wl_pred.shape[0]:
            df_wl[name_kr[name]] = res.wl_pred[p]
    st.line_chart(df_wl.set_index("시간(h)"), use_container_width=True, height=320)

# ═══════════════════════════════════════════════════════════════ #
#  다운로드
# ═══════════════════════════════════════════════════════════════ #
st.divider()
c1, c2 = st.columns(2)
with c1:
    df_dl = pd.DataFrame({"time_min": t_min, "기준": q_sj_scaled} |
                         {LABELS[n]: r.q_timeseries
                          for n, r in all_res.results.items()})
    st.download_button("📥 방류량 CSV",
                       df_dl.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"discharge_{event}.csv", mime="text/csv",
                       use_container_width=True)
with c2:
    df_pd = df_pen.reset_index().rename(columns={"index": "Station"})
    st.download_button("📥 페널티 CSV",
                       df_pd.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"penalty_{event}.csv", mime="text/csv",
                       use_container_width=True)
