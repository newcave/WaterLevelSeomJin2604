"""pages/2_optimize.py — 섬진강댐 방류 최적화

원본 참고 이미지 재현:
  - 제목: "Possible Dam Discharge Scenarios"
  - X축: Time [h] (0~120h, 5일)
  - Y축: Flow Rate [m³/s]
  - 좌상단 텍스트: DS_Original / DS_100 / DS_200 / DS_300 / DS_500
  - 원본(점선) + 3개 시나리오(실선, 계단형)
  - 20블록 × 5.5h = 110h
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
from waterlevel_sim.npz_loader   import (load_demo, available_demos,
                                         load_with_scenario, RAINFALL_SCENARIOS)
from waterlevel_sim.dam_config   import (OPT_CONFIG, PENALTY_CONFIG,
                                         DAM_CONFIG, STATION_INFO_CSV)

st.set_page_config(page_title="댐 최적화 — WaterLevelSim",
                   page_icon="🟣", layout="wide")

ROOT      = Path(__file__).parent.parent
PARAM_CSV = str(ROOT / "data" / "ParamSetforcxx.csv")
SI_CSV    = str(ROOT / STATION_INFO_CSV)

# ═══════════════════════════════════════════════════════════════ #
#  사이드바
# ═══════════════════════════════════════════════════════════════ #
with st.sidebar:
    st.markdown("### 설정")
    event = st.selectbox("이벤트", available_demos(), index=0)

    # ── 강우 시나리오 ─────────────────────────────────────────── #
    st.divider()
    st.markdown("### 🌧️ 강우 시나리오")
    st.caption("⚠️ 단순 배율 근사 — K-River 재실행 결과 아님")
    scenario_mode = st.radio("모드", ["시나리오 선택", "직접 입력"], horizontal=True)
    if scenario_mode == "시나리오 선택":
        scenario_name = st.selectbox("강우 시나리오",
                                     ["기준 (원본)"] + list(RAINFALL_SCENARIOS.keys()))
        custom_scale  = None
        rain_scale    = (1.0 if scenario_name == "기준 (원본)"
                         else RAINFALL_SCENARIOS[scenario_name]["scale"])
    else:
        scenario_name = None
        custom_scale  = st.slider("유량 배율", 0.5, 2.0, 1.0, 0.05, format="×%.2f")
        rain_scale    = custom_scale
    st.info(f"적용 배율: **×{rain_scale:.2f}**"
            + ("" if rain_scale == 1.0 else "  ⚠️ 스케일링 근사"))
    st.divider()

    # ── 원본 UI 6개 파라미터 ──────────────────────────────────── #
    n_blocks    = st.number_input("방류량 조절 횟수",
                                  min_value=1, max_value=30,
                                  value=OPT_CONFIG["n_blocks"])
    block_scale = 100   # 총량 보존: 항상 원본 q_sj 기준 (고정)
    st.caption("💡 총방류량은 원본 q_sj 기준으로 자동 보존됩니다.")
    max_iter    = st.number_input("최적화 탐색 최대치",
                                  min_value=50, max_value=2000,
                                  value=OPT_CONFIG["max_iter"], step=50)
    max_delta   = st.number_input("조절 방류량 최대폭 [m³/s]",
                                  min_value=100, max_value=2000,
                                  value=int(OPT_CONFIG["max_delta_cms"]), step=100)
    block_min   = st.selectbox("구간 단위 [분]",
                               [330, 180, 360, 720],
                               format_func=lambda x: f"{x}분 ({x/60:.1f}h)",
                               index=0)
    init_level  = st.number_input("초기 댐 수위 [EL.m]",
                                  min_value=float(DAM_CONFIG["seomjin"]["min_op_level"]),
                                  max_value=float(DAM_CONFIG["seomjin"]["max_op_level"]),
                                  value=float(DAM_CONFIG["seomjin"]["initial_level"]),
                                  step=0.5)
    st.divider()
    with st.expander("페널티(DS) 계수"):
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
scale_tag = (f"  ⚠️ 강우 스케일링 ×{rain_scale:.2f} 적용 (근사값)"
             if rain_scale != 1.0 else "")
st.caption(
    f"방류 최적화 — 원본(Original) vs Conservative / Moderate / Aggressive"
    f"{scale_tag}"
)

# ═══════════════════════════════════════════════════════════════ #
#  데이터 로드
# ═══════════════════════════════════════════════════════════════ #
@st.cache_data
def _load(ev, sn, cs): return load_with_scenario(ev, sn, cs)

try:
    nc = _load(event, scenario_name, custom_scale)
    dl = DataLibrary(PARAM_CSV)
    si = StationInfo(SI_CSV, penalty_config={
        "p_c01_c02": p_c1, "p_c02_c03": p_c2,
        "p_c03_c04": p_c3, "p_exceed": -100.0,
        "station_weights": {}, "use_time_weight": False,
    })
except Exception as e:
    st.error(f"데이터 로드 오류: {e}"); st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  하단 설정 요약 + Station 테이블
# ═══════════════════════════════════════════════════════════════ #
col_cfg, col_tbl = st.columns([1, 2])

# 최적화 전: 사이드바 입력값 기반 추정
# 최적화 후: all_res.block_info 로 교체 (아래 run 이후 구간에서 갱신)
dt_min      = OPT_CONFIG["dt_minutes"]
_steps      = max(1, nc.n_time // int(n_blocks))
_block_h    = _steps * dt_min / 60.0
_total_h    = int(n_blocks) * _block_h
_coverage   = min(1.0, _total_h / (nc.n_time * dt_min / 60.0))

with col_cfg:
    st.subheader("설정")
    st.markdown(f"""
| 항목 | 값 |
|------|-----|
| 방류량 조절 횟수 | **{int(n_blocks)}** 블록 |
| 블록 길이 (추정) | **{_block_h:.1f}** h |
| 최적화 기간 (추정) | **{_total_h:.0f}** h = **{_total_h/24:.1f}** 일 |
| 커버리지 (추정) | **{_coverage*100:.0f}%** |
| 총량 보존 기준 | **원본 q_sj (100%)** |
| 최적화 탐색 최대치 | **{max_iter}** 회 |
| 조절 방류량 최대폭 | **{max_delta}** m³/s |
| 초기 댐 수위 | **{init_level:.2f}** EL.m |
| 강우 배율 | **×{rain_scale:.2f}** {"⚠️근사" if rain_scale!=1.0 else "✅기준"} |
""")

with col_tbl:
    st.subheader("Station 기준 수위 (DS 판단 기준)")
    df_si = pd.DataFrame([{
        "Station":    f"{r.station_km:.3f}",
        "max":        r.wl_max, "min": r.wl_min,
        "criteria01": r.criteria01, "criteria02": r.criteria02,
        "criteria03": r.criteria03, "criteria04": r.criteria04,
        "Original S.": r.original_km,
    } for r in si.records])
    st.dataframe(df_si, use_container_width=True, hide_index=True, height=250)

st.divider()

# ═══════════════════════════════════════════════════════════════ #
#  Run 전: 기준 미리보기
# ═══════════════════════════════════════════════════════════════ #
q_sj     = DamOptimizer.extract_q_sj(nc.q_station)
q_scaled = q_sj   # 총량 보존: 원본 q_sj 그대로 사용
n_t      = len(q_sj)
t_hr     = np.arange(n_t) * nc.dt_sec / 3600   # [h]

if not run_btn:
    st.subheader("Original — 방류량 시계열")
    st.line_chart(
        pd.DataFrame({"Original [m³/s]": q_scaled}, index=t_hr),
        use_container_width=True, height=350
    )
    st.caption(f"X축: Time [h]   총 {t_hr[-1]:.1f}h ({t_hr[-1]/24:.1f}일)")
    st.info("설정 확인 후 **▶ Run** 을 누르면 3개 시나리오 최적화를 실행합니다.")
    st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  최적화 실행
# ═══════════════════════════════════════════════════════════════ #
cfg_override = {
    "n_blocks":      int(n_blocks),
    "block_minutes": int(block_min),
    "max_iter":      int(max_iter),
    "max_delta_cms": float(max_delta),
}

opt = DamOptimizer(
    dl=dl, station_info=si,
    wl_obs=nc.wl, q_station=nc.q_station,
    q_init_sj=q_scaled, opt_config=cfg_override,
)

with st.spinner("최적화 실행 중... Conservative → Moderate → Aggressive"):
    try:
        all_res: DamOptAllResult = opt.optimize_all(verbose=False)
    except Exception as e:
        st.error(f"최적화 오류: {e}"); st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  DS 레전드 (원본 그림 좌상단 텍스트 재현)
# ═══════════════════════════════════════════════════════════════ #
LABELS = {
    "Conservative": "Conservative",
    "Moderate":     "Moderate",
    "Aggressive":   "Aggressive",
}

ds_orig = list(all_res.results.values())[0].ds_init
bi      = all_res.block_info

# DS 수렴 스냅샷 (100/200/300/500회 시점)
SNAP_ITERS = [100, 200, 300, 500]

def get_ds_at(ds_history: list, n: int) -> float | None:
    """ds_history 에서 n번째 이내 최솟값 반환."""
    if not ds_history: return None
    sub = ds_history[:n] if len(ds_history) >= n else ds_history
    return min(sub)   # DS는 음수 → min = 가장 나쁜값, max = 가장 좋은값
    # 실제로는 running min(absolute) 사용
    # penalty 값이 음수이므로 가장 큰 값(0에 가까운)이 최선

def get_ds_snaps(res) -> dict[int, float]:
    h = res.ds_history
    return {n: h[min(n,len(h))-1] for n in SNAP_ITERS if len(h) >= 1}

# DS 레전드 텍스트 (원본 그림 형식 재현)
legend_parts = [f"DS_Original = {ds_orig:.4f}"]
for name, res in all_res.results.items():
    snaps = get_ds_snaps(res)
    for it, v in snaps.items():
        legend_parts.append(f"DS_{it} ({name[:4]}) = {v:.4f}")
    legend_parts.append(f"DS_Final({name[:4]}) = {res.ds_opt:.4f}")

# ═══════════════════════════════════════════════════════════════ #
#  메인 차트: Possible Dam Discharge Scenarios
# ═══════════════════════════════════════════════════════════════ #
st.subheader("Possible Dam Discharge Scenarios")
st.caption(
    f"Different constraints on DS  |  "
    f"{bi['n_blocks']}블록 × {bi['block_hours']:.1f}h "
    f"= {bi['total_hours']:.0f}h ({bi['total_days']:.1f}일)  "
    f"커버리지 {bi['coverage']*100:.0f}%"
)

# DS 정보 표시 (원본 그림 좌상단 텍스트)
info_col1, info_col2 = st.columns([1, 3])
with info_col1:
    for part in legend_parts[:6]:
        st.caption(part)

with info_col2:
    df_chart = pd.DataFrame({"Original": q_scaled}, index=t_hr)
    for name, res in all_res.results.items():
        df_chart[LABELS[name]] = res.q_timeseries
    st.line_chart(df_chart, use_container_width=True, height=420)
    st.caption("X축: Time [h]   Y축: Flow Rate [m³/s]")

# ═══════════════════════════════════════════════════════════════ #
#  DS 요약 지표
# ═══════════════════════════════════════════════════════════════ #
st.divider()
metric_cols = st.columns(4)
metric_cols[0].metric("DS_Original", f"{ds_orig:.4f}")
for col, (name, res) in zip(metric_cols[1:], all_res.results.items()):
    col.metric(LABELS[name], f"{res.ds_opt:.4f}",
               delta=f"{res.improvement:+.1f}%")

# ═══════════════════════════════════════════════════════════════ #
#  DS 수렴 차트 (원본 그림 DS vs 반복횟수)
# ═══════════════════════════════════════════════════════════════ #
with st.expander("📈 DS 수렴 과정"):
    conv_data = {}
    for name, res in all_res.results.items():
        h = res.ds_history
        if h:
            conv_data[LABELS[name]] = h
    if conv_data:
        max_len = max(len(v) for v in conv_data.values())
        df_conv = pd.DataFrame(
            {k: pd.Series(v) for k, v in conv_data.items()}
        )
        st.line_chart(df_conv, use_container_width=True, height=300)
        st.caption("X축: 함수 호출 횟수   Y축: DS (0에 가까울수록 안전)")

# ═══════════════════════════════════════════════════════════════ #
#  탭 상세
# ═══════════════════════════════════════════════════════════════ #
tab1, tab2, tab3 = st.tabs(["블록 방류량", "스테이션 DS", "수위 시계열"])

with tab1:
    blk_labels = [
        f"B{i+1}({i*bi['block_hours']:.1f}~{(i+1)*bi['block_hours']:.1f}h)"
        for i in range(bi['n_blocks'])
    ]
    df_blk = pd.DataFrame(
        {"Original(평균)": opt.q_init_blocks} |
        {LABELS[n]: r.q_blocks for n, r in all_res.results.items()},
        index=blk_labels
    )
    st.dataframe(
        df_blk.style
            .highlight_min(axis=1, color="#E8F5E9")
            .highlight_max(axis=1, color="#FFEBEE")
            .format("{:.1f}"),
        use_container_width=True
    )
    st.caption("녹색=최소, 빨간=최대 방류량 블록")

with tab2:
    st.caption("DS = Danger Score 누적값 (낮을수록 위험)")
    stn_lbl = [f"St{i+1:02d}({si.records[i].original_km:.0f}km)"
               for i in range(20)]
    df_pen = pd.DataFrame(
        {LABELS[n]: r.penalty_by_station() for n, r in all_res.results.items()},
        index=stn_lbl
    )
    st.bar_chart(df_pen, use_container_width=True, height=320)

    # 계획홍수위 초과 확인
    exceed = []
    for name, res in all_res.results.items():
        for i, rec in enumerate(si.records):
            if i >= res.wl_pred.shape[0]: continue
            mwl = float(res.wl_pred[i].max())
            if mwl > rec.criteria04:
                exceed.append({
                    "시나리오": LABELS[name],
                    "Station": f"{rec.station_km:.3f}km",
                    "최대수위": round(mwl, 3),
                    "계획홍수위": rec.criteria04,
                    "초과(m)": round(mwl - rec.criteria04, 3),
                })
    if exceed:
        st.warning("⚠️ 계획홍수위 초과 지점")
        st.dataframe(pd.DataFrame(exceed), hide_index=True,
                     use_container_width=True)
    else:
        st.success("✅ 전 시나리오 계획홍수위 초과 없음")

with tab3:
    stn_sel = st.selectbox(
        "스테이션", list(range(1, 21)),
        format_func=lambda x: f"St{x:02d} ({si.records[x-1].original_km:.1f}km)"
    )
    p   = stn_sel - 1
    rec = si.records[p]
    n_valid = list(all_res.results.values())[0].wl_pred.shape[1]
    t_hr_v  = np.arange(n_valid) * nc.dt_sec / 3600

    df_wl = pd.DataFrame({
        "criteria01": rec.criteria01,
        "criteria04": rec.criteria04,
    }, index=t_hr_v)
    for name, res in all_res.results.items():
        if p < res.wl_pred.shape[0]:
            df_wl[LABELS[name]] = res.wl_pred[p]
    st.line_chart(df_wl, use_container_width=True, height=320)
    st.caption(f"X축: Time [h]   Y축: 수위 [m]  |  "
               f"c01={rec.criteria01:.2f}m  c04={rec.criteria04:.2f}m")

# ═══════════════════════════════════════════════════════════════ #
#  다운로드
# ═══════════════════════════════════════════════════════════════ #
st.divider()
c1, c2 = st.columns(2)
with c1:
    df_dl = pd.DataFrame({"time_h": t_hr, "Original": q_scaled} |
                         {LABELS[n]: r.q_timeseries
                          for n, r in all_res.results.items()})
    st.download_button("📥 방류량 CSV",
                       df_dl.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"discharge_{event}.csv", mime="text/csv",
                       use_container_width=True)
with c2:
    df_pd = df_pen.reset_index().rename(columns={"index": "Station"})
    st.download_button("📥 DS 결과 CSV",
                       df_pd.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"ds_{event}.csv", mime="text/csv",
                       use_container_width=True)
