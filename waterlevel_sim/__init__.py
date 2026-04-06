"""
waterlevel_sim
==============
섬진강 수위 예측 + 댐 방류 최적화 시스템
원본: WaterLevelSim (C++/Windows, K-Water 2021) Python 포트 v2

역공학 확정 예측 모델::

    WL(station, t+1) = c_sm + a_sm * Q(station, t) + b_sm * Q(station, t-1)

    sm   = get_submodel(WL_prev, event_criteria[station])
    a_sm = params[station-1, station+1+3*sm]
    b_sm = params[station-1, station+2+3*sm]
    c_sm = params[station-1, station+3+3*sm]

댐 방류 최적화::

    minimize  Σ penalty(WL_pred[station, t])
    s.t.      Σ Q_release ≈ 총방류량 유지
              Q_min ≤ Q_release[block] ≤ Q_max
              |ΔQ| ≤ max_delta_cms
"""

# ── 기존 (수정 없음) ─────────────────────────────────────────── #
from .data_library import DataLibrary
from .simulator    import WaterLevelSimulator
from .nc_reader    import NCReader
from .metrics      import compute_metrics
from .routing      import FlowRouter
from .npz_loader   import NPZData, load_demo, available_demos, load_uploaded_nc

# ── 신규 ─────────────────────────────────────────────────────── #
from .dam_config      import DAM_CONFIG, OPT_CONFIG, PENALTY_CONFIG
from .dam_correlation import DamCurve, SeomjinDam, JuamDam
from .station_info    import StationInfo, StationRecord, PENALTY_CONFIG
from .optimizer       import DamOptimizer, DamOptResult, DamOptAllResult

__version__ = "2.0.0"

__all__ = [
    # 기존
    "DataLibrary", "WaterLevelSimulator", "NCReader", "compute_metrics",
    "FlowRouter",
    "NPZData", "load_demo", "available_demos", "load_uploaded_nc",
    # 신규
    "DAM_CONFIG", "OPT_CONFIG", "PENALTY_CONFIG",
    "DamCurve", "SeomjinDam", "JuamDam",
    "StationInfo", "StationRecord",
    "DamOptimizer", "DamOptResult", "DamOptAllResult",
]
