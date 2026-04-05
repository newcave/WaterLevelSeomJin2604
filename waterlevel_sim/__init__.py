"""
waterlevel_sim
==============
섬진강 수위 예측 시스템 Python 포트
원본: WaterLevelSim (C++/Windows, K-Water 2021)

주요 클래스:
    DataLibrary      - 데이터 관리 및 파라미터 로더
    WaterLevelSimulator - 수위 예측 엔진
    NCReader         - NetCDF 입출력

역공학 확정 예측 모델::

    WL(station, t+1) = c_sm + a_sm * Q(station, t) + b_sm * Q(station, t-1)

    sm   = get_submodel(WL_prev, event_criteria[station])  # 유량 체계 선택
    a_sm = params[station-1, station+1+3*sm]
    b_sm = params[station-1, station+2+3*sm]
    c_sm = params[station-1, station+3+3*sm]  # 기저 수위 [m]
"""

from .data_library import DataLibrary
from .simulator import WaterLevelSimulator
from .nc_reader import NCReader
from .metrics import compute_metrics

__version__ = "1.0.0"
__all__ = ["DataLibrary", "WaterLevelSimulator", "NCReader", "compute_metrics"]

from .routing import FlowRouter
from .optimizer import FlowOptimizer, OptResult

__all__ += ["FlowRouter", "FlowOptimizer", "OptResult"]

from .npz_loader import NPZData, load_demo, available_demos, load_uploaded_nc
__all__ += ["NPZData", "load_demo", "available_demos", "load_uploaded_nc"]
