"""npz_loader.py — NPZ 형식 데이터 로더 + 강우 시나리오 스케일링

⚠️  강우 시나리오 스케일링 주의사항:
    - q_in / q_station 에 단순 배율을 적용한 근사값입니다.
    - 실제 강우 공간 분포, 시간 지연, 유역 응답 특성은 반영되지 않습니다.
    - 정밀 분석이 필요한 경우 K-River 재실행 후 NC 파일을 교체하세요.
    - 본 스케일링은 운영 의사결정 지원용 1차 근사로만 활용하세요.
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
from dataclasses import dataclass

DATA_DIR = Path(__file__).parent.parent / "data"

# ── 강우 시나리오 기본 정의 ──────────────────────────────────── #
# 필요 시 dam_config.py 로 이동 가능
RAINFALL_SCENARIOS: dict[str, dict] = {
    "약우 (50년 빈도)":    {"scale": 0.70, "label": "Dry",      "color": "#4CAF50"},
    "기준 (100년 빈도)":   {"scale": 1.00, "label": "Base",     "color": "#2196F3"},
    "강우 (200년 빈도)":   {"scale": 1.30, "label": "Heavy",    "color": "#FF9800"},
    "극한 (PMF/2020년)":   {"scale": 1.60, "label": "Extreme",  "color": "#F44336"},
}


# ═══════════════════════════════════════════════════════════════ #
#  NPZData
# ═══════════════════════════════════════════════════════════════ #

class NPZData:
    """NPZ 데이터 컨테이너 — NCReader 호환 인터페이스.

    Attributes
    ----------
    wl         : (n_time, 22)  수위 시계열 [m]
    q_station  : (n_time, 22)  단면 유량 [m³/s]
    q_in       : (n_bc,   22)  경계 유입 유량 [m³/s]
    dt_sec     : int           타임스텝 [초]
    start_date : str
    scenario_label : str       스케일링 적용 시 시나리오 이름
    scale          : float     적용된 스케일 배율
    """

    def __init__(self, npz_path: str | Path) -> None:
        d = np.load(npz_path, allow_pickle=True)
        self.wl            = d["wl"].astype(np.float64)
        self.q_station     = d["q_station"].astype(np.float64)
        self.q_in          = d["q_in"].astype(np.float64)
        self.dt_sec        = int(d["dt_sec"][0])
        self.start_date    = str(d["start_date"][0])
        self.n_time        = self.wl.shape[0]
        self.source        = str(npz_path)
        self.scenario_label = "원본 데이터"
        self.scale          = 1.0
        self.is_scaled      = False

    def apply_scale(self, scale: float, label: str = "") -> "NPZData":
        """강우 스케일링 적용 — 새 NPZData 반환 (원본 불변).

        ⚠️  단순 배율 근사입니다. K-River 재실행 결과가 아닙니다.

        Parameters
        ----------
        scale : float  배율 (1.0 = 기준, 1.3 = 130%)
        label : str    시나리오 이름

        Returns
        -------
        NPZData  스케일링된 새 인스턴스
        """
        scaled              = object.__new__(NPZData)
        scaled.wl           = self.wl.copy()          # 수위는 유지 (초기 조건)
        scaled.q_station    = self.q_station * scale   # 유량 스케일링
        scaled.q_in         = self.q_in      * scale   # 유입량 스케일링
        scaled.dt_sec       = self.dt_sec
        scaled.start_date   = self.start_date
        scaled.n_time       = self.n_time
        scaled.source       = self.source
        scaled.scale        = scale
        scaled.scenario_label = label or f"×{scale:.2f} 스케일링"
        scaled.is_scaled    = True
        return scaled

    def summary(self) -> str:
        scaled_note = (
            f"\n  ⚠️  스케일링 적용: ×{self.scale:.2f}  [{self.scenario_label}]"
            f"\n      (단순 배율 근사 — K-River 재실행 결과 아님)"
            if self.is_scaled else ""
        )
        return (
            f"NPZ 데이터: {Path(self.source).name}\n"
            f"  StartDate  : {self.start_date}\n"
            f"  TimeStep   : {self.dt_sec} s  ({self.dt_sec/60:.0f} min)\n"
            f"  n_time     : {self.n_time} steps\n"
            f"  WL shape   : {self.wl.shape}\n"
            f"  Q_station  : {self.q_station.shape}\n"
            f"  Q_in       : {self.q_in.shape}"
            f"{scaled_note}"
        )


# ═══════════════════════════════════════════════════════════════ #
#  로더 함수
# ═══════════════════════════════════════════════════════════════ #

def load_demo(event: str = "tesr") -> NPZData:
    """내장 데모 데이터 로드.

    Parameters
    ----------
    event : str — 'tesr' | 'tesr2' | 'tesr3'
    """
    path = DATA_DIR / f"{event}_demo.npz"
    if not path.exists():
        raise FileNotFoundError(f"데모 데이터 없음: {path}")
    return NPZData(path)


def available_demos() -> list[str]:
    """사용 가능한 데모 이벤트 목록."""
    return sorted(
        p.stem.replace("_demo", "")
        for p in DATA_DIR.glob("*_demo.npz")
    )


def load_with_scenario(
    event: str,
    scenario_name: str | None = None,
    custom_scale: float | None = None,
) -> NPZData:
    """이벤트 + 강우 시나리오 로드.

    Parameters
    ----------
    event         : str    기본 이벤트 ('tesr' 등)
    scenario_name : str    RAINFALL_SCENARIOS 키
                           None 이면 원본 반환
    custom_scale  : float  직접 배율 지정 (슬라이더 연동)
                           scenario_name 보다 우선

    Returns
    -------
    NPZData  (스케일링 적용 또는 원본)

    Examples
    --------
    >>> nc = load_with_scenario("tesr", "강우 (200년 빈도)")
    >>> nc = load_with_scenario("tesr", custom_scale=1.45)
    """
    base = load_demo(event)

    if custom_scale is not None:
        label = f"사용자 정의 ×{custom_scale:.2f}"
        return base.apply_scale(custom_scale, label)

    if scenario_name and scenario_name in RAINFALL_SCENARIOS:
        cfg   = RAINFALL_SCENARIOS[scenario_name]
        return base.apply_scale(cfg["scale"], scenario_name)

    return base   # 원본


def load_uploaded_nc(uploaded_file) -> NPZData:
    """Streamlit 업로드 파일(NC) 로드."""
    import tempfile, os
    from waterlevel_sim.nc_reader import NCReader
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    try:
        nc = NCReader(tmp_path)
    finally:
        os.unlink(tmp_path)
    return nc
