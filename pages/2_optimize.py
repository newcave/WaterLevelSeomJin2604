"""pages/2_optimize.py — 섬진강댐 방류 최적화

(1) session_state: 페이지 이동 후 복귀 시 설정·결과 유지
(2) 누적 결과: 여러 번 Run → 결과 누적 + 비교 + 일괄 다운로드
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from waterlevel_sim import DataLibrary
from waterlevel_sim.optimizer    import DamOptimizer, DamOptAllResult
from waterlevel_sim.station_info import StationInfo
from waterlevel_sim.npz_loader   import (load_with_scenario, available_demos,
                                         RAINFALL_SCENARIOS)
from waterlevel_sim.dam_config   import (OPT_CONFIG, PENALTY_CONFIG,
                                         DAM_CONFIG, STATION_INFO_CSV)

st.set_page_config(page_title="댐 최적화 — WaterLevelSim",
                   page_icon="🟣", layout="wide")

ROOT      = Path(__file__).parent.parent
PARAM_CSV = str(ROOT / "data" / "ParamSetforcxx.csv")
SI_CSV    = str(ROOT / STATION_INFO_CSV)

LABELS = {
    "Conservative": "Conservative (사전방류↑)",
    "Moderate":     "Moderate (균등)",
    "Aggressive":   "Aggressive (후반방류↑)",
}
_BM_MAP = {
    "자동 (n_time 균등 분할)": None,
    "330분 (5.5h)": 330, "180분 (3h)": 180,
    "360분 (6h)":   360, "720분 (12h)": 720,
}

# ═══════════════════════════════════════════════════════════════ #
#  렌더링 헬퍼 함수
# ═══════════════════════════════════════════════════════════════ #

def render_result(rec: dict, LABELS: dict, is_latest: bool = False):
    """단일 Run 결과 렌더링."""
    bi        = rec["bi"]
    all_res   = rec["all_res_obj"]
    si        = rec["si_obj"]
    t_hr      = np.array(rec["t_hr"])
    q_orig    = np.array(rec["q_orig"])
    ds_orig   = rec["ds_orig"]
    max_disc  = rec["max_discharge"]

    prefix = "📌 최신 결과" if is_latest else f"📂 {rec['label']}"
    with st.expander(prefix, expanded=is_latest):

        # DS 수렴 레전드
        SNAP = [100, 200, 300, 500]
        legend_parts = [f"DS_Original = {ds_orig:.4f}"]
        for name, res in all_res.results.items():
            h = res.ds_history
            for n in SNAP:
                if len(h) >= 1:
                    v = h[min(n, len(h)) - 1]
                    legend_parts.append(f"DS_{n} ({name[:4]}) = {v:.4f}")
            legend_parts.append(f"DS_Final({name[:4]}) = {res.ds_opt:.4f}")

        # 메인 차트
        st.markdown(f"**Possible Dam Discharge Scenarios**")
        st.caption(
            f"{bi['n_blocks']}블록 × {bi['block_hours']:.1f}h "
            f"= {bi['total_hours']:.0f}h ({bi['total_days']:.1f}일)  "
            f"커버리지 {bi['coverage']*100:.0f}%  |  "
            f"강우배율 ×{rec['rain_scale']:.2f}  |  "
            f"최대방류 {max_disc} m³/s"
        )

        info_c, chart_c = st.columns([1, 3])
        with info_c:
            for p in legend_parts[:8]:
                st.caption(p)

        with chart_c:
            df_chart = pd.DataFrame({"Original": q_orig}, index=t_hr)
            for name, res in all_res.results.items():
                df_chart[LABELS[name]] = res.q_timeseries
            st.line_chart(df_chart, use_container_width=True, height=350)
            st.caption(f"X축: Time [h]   Y축: Flow Rate [m³/s]   "
                       f"⛔ 최대 허용: {max_disc} m³/s")

        # DS 지표
        cols = st.columns(4)
        cols[0].metric("DS_Original", f"{ds_orig:.4f}")
        for col, (name, res) in zip(cols[1:], all_res.results.items()):
            cols[list(all_res.results.keys()).index(name) + 1].metric(
                LABELS[name], f"{res.ds_opt:.4f}",
                delta=f"{res.improvement:+.1f}%"
            )

        # 탭 상세
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📈 DS 수렴", "📦 블록 방류량", "📊 스테이션 DS", "🌊 수위 시계열"]
        )

        with tab1:
            conv = {LABELS[n]: pd.Series(res.ds_history)
                    for n, res in all_res.results.items() if res.ds_history}
            if conv:
                st.line_chart(pd.DataFrame(conv),
                              use_container_width=True, height=280)
                st.caption("X축: 함수 호출 횟수   Y축: DS (0에 가까울수록 안전)")

        with tab2:
            blk_labels = [
                f"B{i+1}({i*bi['block_hours']:.1f}~{(i+1)*bi['block_hours']:.1f}h)"
                for i in range(bi["n_blocks"])
            ]
            df_blk = pd.DataFrame(
                {"Original(평균)": np.array(rec["q_orig"])
                    [:bi["n_blocks"] * bi["steps_per_block"]]
                    .reshape(bi["n_blocks"], bi["steps_per_block"]).mean(axis=1)
                 if len(rec["q_orig"]) >= bi["n_blocks"] * bi["steps_per_block"]
                 else np.zeros(bi["n_blocks"])} |
                {LABELS[n]: res.q_blocks for n, res in all_res.results.items()},
                index=blk_labels
            )
            st.dataframe(
                df_blk.style
                    .highlight_min(axis=1, color="#E8F5E9")
                    .highlight_max(axis=1, color="#FFEBEE")
                    .format("{:.1f}"),
                use_container_width=True
            )

        with tab3:
            stn_lbl = [f"St{i+1:02d}({si.records[i].original_km:.0f}km)"
                       for i in range(20)]
            df_pen = pd.DataFrame(
                {LABELS[n]: res.penalty_by_station()
                 for n, res in all_res.results.items()},
                index=stn_lbl
            )
            st.bar_chart(df_pen, use_container_width=True, height=280)
            exceed = []
            for name, res in all_res.results.items():
                for i, r in enumerate(si.records):
                    if i >= res.wl_pred.shape[0]: continue
                    mwl = float(res.wl_pred[i].max())
                    if mwl > r.criteria04:
                        exceed.append({"시나리오": LABELS[name],
                                       "Station": f"{r.station_km:.3f}km",
                                       "최대수위": round(mwl, 3),
                                       "계획홍수위": r.criteria04,
                                       "초과(m)": round(mwl - r.criteria04, 3)})
            if exceed:
                st.warning("⚠️ 계획홍수위 초과")
                st.dataframe(pd.DataFrame(exceed),
                             hide_index=True, use_container_width=True)
            else:
                st.success("✅ 전 시나리오 계획홍수위 초과 없음")

        with tab4:
            stn_sel = st.selectbox(
                "스테이션", list(range(1, 21)),
                format_func=lambda x: f"St{x:02d} ({si.records[x-1].original_km:.1f}km)",
                key=f"stn_{rec['label'][:20]}"
            )
            p   = stn_sel - 1
            rec_si = si.records[p]
            n_valid = list(all_res.results.values())[0].wl_pred.shape[1]
            t_v = np.arange(n_valid) * 1800 / 3600
            df_wl = pd.DataFrame({
                "c01": rec_si.criteria01,
                "c04": rec_si.criteria04,
            }, index=t_v)
            for name, res in all_res.results.items():
                if p < res.wl_pred.shape[0]:
                    df_wl[LABELS[name]] = res.wl_pred[p]
            st.line_chart(df_wl, use_container_width=True, height=280)

        # 개별 다운로드
        dl_c1, dl_c2 = st.columns(2)
        ts_label = datetime.now().strftime("%H%M%S")
        with dl_c1:
            df_dl = pd.DataFrame({"time_h": t_hr, "Original": q_orig} |
                                  {LABELS[n]: res.q_timeseries
                                   for n, res in all_res.results.items()})
            st.download_button(
                "📥 방류량 CSV",
                df_dl.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"discharge_{rec['event']}_{ts_label}.csv",
                mime="text/csv", use_container_width=True,
                key=f"dl_q_{rec['label'][:20]}"
            )
        with dl_c2:
            st.download_button(
                "📥 DS 결과 CSV",
                df_pen.reset_index().rename(columns={"index": "Station"})
                      .to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ds_{rec['event']}_{ts_label}.csv",
                mime="text/csv", use_container_width=True,
                key=f"dl_ds_{rec['label'][:20]}"
            )


def show_history_summary(history: list, LABELS: dict):
    """누적 결과 요약 비교표."""
    if len(history) < 2:
        return
    st.divider()
    st.subheader(f"📊 누적 결과 비교 ({len(history)}건)")

    rows = []
    for rec in history:
        row = {
            "실행":      rec["label"].split("  ")[0],
            "이벤트":    rec["event"],
            "강우배율":  f"×{rec['rain_scale']:.2f}",
            "블록수":    rec["n_blocks"],
            "maxQ":      rec["max_discharge"],
            "DS_Original": f"{rec['ds_orig']:.2f}",
        }
        for name, scen in rec["scenarios"].items():
            short = name[:4]
            row[f"DS_{short}"] = f"{scen['ds_opt']:.2f}"
            row[f"개선_{short}"] = f"{scen['improvement']:+.1f}%"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # 일괄 다운로드
    df_all_q = None
    for i, rec in enumerate(history):
        t_hr  = np.array(rec["t_hr"])
        q_orig = np.array(rec["q_orig"])
        tag   = rec["label"].split("  ")[0]
        df_tmp = pd.DataFrame({"time_h": t_hr, f"{tag}_Original": q_orig} |
                               {f"{tag}_{n[:4]}": np.array(s["q_ts"])
                                for n, s in rec["scenarios"].items()})
        df_all_q = df_tmp if df_all_q is None else df_all_q.join(
            df_tmp.drop(columns=["time_h"]), how="outer"
        )

    if df_all_q is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            f"📥 전체 {len(history)}건 방류량 일괄 다운로드",
            data=df_all_q.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"discharge_all_{ts}.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════ #
#  (1) session_state 초기화
# ═══════════════════════════════════════════════════════════════ #

def _def(key, val):
    if key not in st.session_state:
        st.session_state[key] = val

_def("opt_event",         available_demos()[0])
_def("opt_scenario_mode", "시나리오 선택")
_def("opt_scenario_name", "기준 (원본)")
_def("opt_custom_scale",  1.0)
_def("opt_n_blocks",      int(OPT_CONFIG["n_blocks"]))
_def("opt_max_iter",      int(OPT_CONFIG["max_iter"]))
_def("opt_max_delta",     int(OPT_CONFIG["max_delta_cms"]))
_def("opt_max_discharge", int(DAM_CONFIG["seomjin"]["max_discharge"]))
_def("opt_block_min_opt", "자동 (n_time 균등 분할)")
_def("opt_init_level",    float(DAM_CONFIG["seomjin"]["initial_level"]))
_def("opt_p_c1",          float(PENALTY_CONFIG["p_c01_c02"]))
_def("opt_p_c2",          float(PENALTY_CONFIG["p_c02_c03"]))
_def("opt_p_c3",          float(PENALTY_CONFIG["p_c03_c04"]))
_def("opt_history",       [])

# ═══════════════════════════════════════════════════════════════ #
#  사이드바
# ═══════════════════════════════════════════════════════════════ #
with st.sidebar:
    st.markdown("### 이벤트 / 강우")
    st.selectbox("이벤트", available_demos(), key="opt_event")
    st.divider()

    st.markdown("### 🌧️ 강우 시나리오")
    st.caption("⚠️ 단순 배율 근사 — K-River 재실행 결과 아님")
    st.radio("모드", ["시나리오 선택", "직접 입력"],
             horizontal=True, key="opt_scenario_mode")

    if st.session_state.opt_scenario_mode == "시나리오 선택":
        st.selectbox("강우 시나리오",
                     ["기준 (원본)"] + list(RAINFALL_SCENARIOS.keys()),
                     key="opt_scenario_name")
        rain_scale   = (1.0 if st.session_state.opt_scenario_name == "기준 (원본)"
                        else RAINFALL_SCENARIOS[st.session_state.opt_scenario_name]["scale"])
        custom_scale = None
        sn_arg       = st.session_state.opt_scenario_name
    else:
        st.slider("유량 배율", 0.5, 2.0, step=0.05,
                  format="×%.2f", key="opt_custom_scale")
        rain_scale   = st.session_state.opt_custom_scale
        custom_scale = rain_scale
        sn_arg       = None

    st.info(f"적용 배율: **×{rain_scale:.2f}**"
            + ("" if rain_scale == 1.0 else "  ⚠️ 스케일링 근사"))
    st.divider()

    st.markdown("### ⚙️ 최적화 파라미터")
    st.number_input("방류량 조절 횟수",
                    min_value=1, max_value=30, key="opt_n_blocks")
    st.caption("💡 총방류량은 원본 q_sj 기준으로 자동 보존됩니다.")
    st.number_input("최적화 탐색 최대치",
                    min_value=50, max_value=2000, step=50, key="opt_max_iter")
    st.number_input("조절 방류량 최대폭 [m³/s]",
                    min_value=100, max_value=2000, step=100, key="opt_max_delta")
    st.divider()

    st.markdown("### 🚧 방류량 제약")
    st.slider("최대 허용 방류량 [m³/s]",
              min_value=500,
              max_value=int(DAM_CONFIG["seomjin"]["max_discharge_hard"]),
              step=100, key="opt_max_discharge",
              help="이 값을 초과하는 방류는 절대 허용되지 않습니다.")
    st.caption(f"⛔ 하드 제약: **{st.session_state.opt_max_discharge} m³/s** 초과 불가")

    st.selectbox("구간 단위 [분]", list(_BM_MAP.keys()),
                 key="opt_block_min_opt",
                 help="자동: 전체 기간을 n_blocks 등분")
    st.number_input("초기 댐 수위 [EL.m]",
                    min_value=float(DAM_CONFIG["seomjin"]["min_op_level"]),
                    max_value=float(DAM_CONFIG["seomjin"]["max_op_level"]),
                    step=0.5, key="opt_init_level")
    st.divider()

    with st.expander("페널티(DS) 계수"):
        st.slider("고수부지~주의보",  -50.0,  0.0, step=1.0, key="opt_p_c1")
        st.slider("주의보~경보",      -80.0,  0.0, step=1.0, key="opt_p_c2")
        st.slider("경보~계획홍수위", -100.0,  0.0, step=1.0, key="opt_p_c3")

    st.divider()
    run_btn   = st.button("▶ Run",        type="primary",   use_container_width=True)
    clear_btn = st.button("🗑 결과 초기화", use_container_width=True)

# ─── 단축 변수 ───────────────────────────────────────────────── #
S             = st.session_state
event         = S.opt_event
block_min     = _BM_MAP[S.opt_block_min_opt]
n_blocks      = S.opt_n_blocks
max_iter      = S.opt_max_iter
max_delta     = S.opt_max_delta
max_discharge = S.opt_max_discharge
init_level    = S.opt_init_level
p_c1, p_c2, p_c3 = S.opt_p_c1, S.opt_p_c2, S.opt_p_c3

if clear_btn:
    st.session_state.opt_history = []
    st.rerun()

# ═══════════════════════════════════════════════════════════════ #
#  타이틀
# ═══════════════════════════════════════════════════════════════ #
st.title("섬진강댐")
scale_tag = f"  ⚠️ 강우 스케일링 ×{rain_scale:.2f}" if rain_scale != 1.0 else ""
st.caption(f"방류 최적화 — Original vs Conservative / Moderate / Aggressive{scale_tag}")

# ═══════════════════════════════════════════════════════════════ #
#  데이터 로드
# ═══════════════════════════════════════════════════════════════ #
@st.cache_data
def _load(ev, sn, cs): return load_with_scenario(ev, sn, cs)

try:
    nc = _load(event, sn_arg, custom_scale)
    dl = DataLibrary(PARAM_CSV)
    si = StationInfo(SI_CSV, penalty_config={
        "p_c01_c02": p_c1, "p_c02_c03": p_c2,
        "p_c03_c04": p_c3, "p_exceed": -100.0,
        "station_weights": {}, "use_time_weight": False,
    })
except Exception as e:
    st.error(f"데이터 로드 오류: {e}"); st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  설정 요약 + Station 테이블
# ═══════════════════════════════════════════════════════════════ #
col_cfg, col_tbl = st.columns([1, 2])
dt_min   = OPT_CONFIG["dt_minutes"]
_steps   = max(1, nc.n_time // int(n_blocks)) if not block_min else block_min // dt_min
_block_h = _steps * dt_min / 60.0
_total_h = int(n_blocks) * _block_h
_cov     = min(100, _total_h / (nc.n_time * dt_min / 60) * 100)

with col_cfg:
    st.subheader("설정")
    st.markdown(f"""
| 항목 | 값 |
|------|-----|
| 방류량 조절 횟수 | **{int(n_blocks)}** 블록 |
| 블록 길이 (추정) | **{_block_h:.1f}** h |
| 최적화 기간 (추정) | **{_total_h:.0f}** h = **{_total_h/24:.1f}** 일 |
| 커버리지 (추정) | **{_cov:.0f}%** |
| 최대 허용 방류량 | **{max_discharge}** m³/s |
| 최적화 탐색 최대치 | **{max_iter}** 회 |
| 조절 방류량 최대폭 | **{max_delta}** m³/s |
| 초기 댐 수위 | **{init_level:.2f}** EL.m |
| 강우 배율 | **×{rain_scale:.2f}** {"⚠️근사" if rain_scale!=1.0 else "✅기준"} |
| 누적 결과 수 | **{len(S.opt_history)}** 건 |
""")

with col_tbl:
    st.subheader("Station 기준 수위 (DS 판단 기준)")
    df_si = pd.DataFrame([{
        "Station": f"{r.station_km:.3f}", "max": r.wl_max, "min": r.wl_min,
        "c01": r.criteria01, "c02": r.criteria02,
        "c03": r.criteria03, "c04": r.criteria04, "BP_km": r.original_km,
    } for r in si.records])
    st.dataframe(df_si, use_container_width=True, hide_index=True, height=250)

st.divider()

# ═══════════════════════════════════════════════════════════════ #
#  Run 전 미리보기
# ═══════════════════════════════════════════════════════════════ #
q_sj = DamOptimizer.extract_q_sj(nc.q_station)
n_t  = len(q_sj)
t_hr = np.arange(n_t) * nc.dt_sec / 3600

if not run_btn:
    st.subheader("Original — 방류량 시계열")
    st.line_chart(pd.DataFrame({"Original [m³/s]": q_sj}, index=t_hr),
                  use_container_width=True, height=300)
    st.caption(f"X축: Time [h]   총 {t_hr[-1]:.1f}h ({t_hr[-1]/24:.1f}일)")
    st.info("설정 확인 후 **▶ Run** 을 누르면 3개 시나리오 최적화를 실행합니다.")

    # 기존 누적 결과 표시
    for rec in reversed(S.opt_history):
        render_result(rec, LABELS, is_latest=False)
    show_history_summary(S.opt_history, LABELS)
    st.stop()

# ═══════════════════════════════════════════════════════════════ #
#  최적화 실행
# ═══════════════════════════════════════════════════════════════ #
cfg_override = {
    "n_blocks":      int(n_blocks),
    "block_minutes": block_min,
    "max_iter":      int(max_iter),
    "max_delta_cms": float(max_delta),
    "q_max":         float(max_discharge),
    "q_max_hard":    float(max_discharge),
}

opt = DamOptimizer(dl=dl, station_info=si,
                   wl_obs=nc.wl, q_station=nc.q_station,
                   q_init_sj=q_sj, opt_config=cfg_override)

with st.spinner("최적화 실행 중... Conservative → Moderate → Aggressive"):
    try:
        all_res: DamOptAllResult = opt.optimize_all(verbose=False)
    except Exception as e:
        st.error(f"최적화 오류: {e}"); st.stop()

# ─── 결과 누적 저장 ─────────────────────────────────────────── #
bi      = all_res.block_info
ds_orig = list(all_res.results.values())[0].ds_init
ts_now  = datetime.now().strftime("%H:%M:%S")
run_no  = len(S.opt_history) + 1
run_label = (f"Run#{run_no}  "
             f"[{event} ×{rain_scale:.2f} | {int(n_blocks)}블록 "
             f"| maxQ={max_discharge} | iter={max_iter}]  {ts_now}")

record = {
    "label":        run_label,
    "event":        event,
    "rain_scale":   rain_scale,
    "n_blocks":     bi["n_blocks"],
    "block_hours":  bi["block_hours"],
    "total_hours":  bi["total_hours"],
    "max_discharge":max_discharge,
    "max_iter":     max_iter,
    "ds_orig":      ds_orig,
    "t_hr":         t_hr.tolist(),
    "q_orig":       q_sj.tolist(),
    "bi":           bi,
    "all_res_obj":  all_res,
    "si_obj":       si,
    "scenarios": {
        name: {
            "ds_opt":      res.ds_opt,
            "improvement": res.improvement,
            "q_blocks":    res.q_blocks.tolist(),
            "q_ts":        res.q_timeseries.tolist(),
            "ds_history":  res.ds_history,
        }
        for name, res in all_res.results.items()
    },
}
S.opt_history.append(record)

# ═══════════════════════════════════════════════════════════════ #
#  결과 표시
# ═══════════════════════════════════════════════════════════════ #
st.success(f"✅ {run_label}")

# 최신 결과 (펼쳐진 상태)
render_result(record, LABELS, is_latest=True)

# 이전 결과들 (접힌 상태)
if len(S.opt_history) > 1:
    st.divider()
    st.subheader(f"📂 이전 결과 ({len(S.opt_history)-1}건)")
    for rec in reversed(S.opt_history[:-1]):
        render_result(rec, LABELS, is_latest=False)

# 누적 비교표 + 일괄 다운로드
show_history_summary(S.opt_history, LABELS)
