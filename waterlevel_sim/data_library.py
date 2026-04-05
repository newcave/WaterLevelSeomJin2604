"""data_library.py — DataLibrary.cpp Python 완전 이식."""

from __future__ import annotations
import numpy as np
import csv


# ─────────────────────────── 상수 ────────────────────────────────────── #
N_BP       = 22
N_STATION  = 20
N_SUBMODEL = 4
MAX_PARAM  = 33
AVG_VEL_KMH = 3.7869        # 평균 유속 [km/h]
DT_SEC       = 1800.0        # 기본 타임스텝 [sec]

BP_KM = np.array([
    136.0, 130.4, 128.0, 126.6, 109.2, 108.4, 104.4, 97.8,
     93.2,  89.2,  79.88, 77.8,  74.8,  61.8,  54.6, 53.8,
     47.6,  40.2,  33.5,  24.5,  15.0,  -2.0
])

# event_criteria[station-1] = [c0, c1, c2]  → 4구간 서브모델
EVENT_CRITERIA = [
    [126.7776, 128.5042, 130.2309],   # St 1  130.4 km
    [122.0603, 124.2349, 126.4095],   # St 2  128.0 km
    [120.3703, 122.6963, 125.0224],   # St 3  126.6 km
    [ 83.7325,  85.7264,  87.7203],   # St 4  109.2 km
    [ 82.0733,  83.9943,  85.9153],   # St 5  108.4 km
    [ 78.0456,  80.1987,  82.3518],   # St 6  104.4 km
    [ 71.0814,  73.6952,  76.3090],   # St 7   97.8 km
    [ 67.7283,  70.0836,  72.4389],   # St 8   93.2 km
    [ 64.5393,  67.2822,  70.0251],   # St 9   89.2 km
    [ 51.7948,  54.1438,  56.4927],   # St10   79.9 km
    [ 51.2961,  53.7181,  56.1401],   # St11   77.8 km
    [ 47.1194,  50.5704,  54.0215],   # St12   74.8 km
    [ 33.8226,  37.5367,  41.2508],   # St13   61.8 km
    [ 27.6752,  30.5207,  33.3662],   # St14   54.6 km
    [ 27.2778,  30.0653,  32.8528],   # St15   53.8 km
    [ 23.1049,  26.1572,  29.2094],   # St16   47.6 km
    [ 15.3925,  19.8886,  24.3848],   # St17   40.2 km
    [ 11.8302,  15.0740,  18.3177],   # St18   33.5 km
    [  6.7445,   9.6375,  12.5306],   # St19   24.5 km
    [  2.8425,   5.6073,   8.3721],   # St20   15.0 km
]

# level_limit[station-1] = [upper, lower]
LEVEL_LIMIT = [
    [137.0, 120.1], [133.6, 114.9], [132.3, 113.0], [ 94.7,  76.7],
    [ 92.8,  75.2], [ 89.5,  70.9], [ 83.9,  63.5], [ 79.8,  60.4],
    [ 77.8,  56.8], [ 63.8,  44.4], [ 63.6,  43.9], [ 62.5,  38.7],
    [ 50.0,  25.1], [ 41.2,  19.8], [ 40.6,  19.5], [ 37.3,  15.1],
    [ 33.9,   5.9], [ 26.6,   3.6], [ 20.4,  -1.1], [ 16.1,  -4.9],
]


class DataLibrary:
    """DataLibrary.cpp → Python 이식.

    Parameters
    ----------
    param_csv : str
        ParamSetforcxx.csv 경로
    num_interpolation : int
        타임스텝 보간 분할 수 (기본 2)

    Examples
    --------
    >>> dl = DataLibrary("data/ParamSetforcxx.csv")
    >>> dl.get_submodel(station=1, wl=125.0)
    0
    >>> a, b, c = dl.get_submodel_params(station=1, sm=0)
    """

    def __init__(self, param_csv: str, num_interpolation: int = 2) -> None:
        self.num_interpolation = num_interpolation
        self.bp_km       = BP_KM.copy()
        self.event_criteria = np.array(EVENT_CRITERIA)   # (20, 3)
        self.level_limit    = np.array(LEVEL_LIMIT)       # (20, 2)

        # 파라미터 로드: (20, 33) — 모든 값 포함 (0 포함)
        self.params = self._load_params(param_csv)        # (N_STATION, MAX_PARAM)

        # 딜레이 행렬 계산 (보간 타임스텝 단위)
        self.delay = self._compute_delay()               # (N_BP, N_BP)
        self.delay_max = int(self.delay.max())

    # ──────────────────── 초기화 헬퍼 ──────────────────────────────── #

    def _load_params(self, path: str) -> np.ndarray:
        """CSV → (N_STATION, MAX_PARAM) ndarray."""
        params = np.zeros((N_STATION, MAX_PARAM), dtype=np.float64)
        with open(path, newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i >= N_STATION:
                    break
                for j, val in enumerate(row):
                    if j < MAX_PARAM:
                        try:
                            params[i, j] = float(val)
                        except ValueError:
                            pass
        return params

    def _compute_delay(self) -> np.ndarray:
        """delay[j, i] = BP[i] → BP[j] 도달 딜레이 (보간 스텝)."""
        delay = np.zeros((N_BP, N_BP), dtype=int)
        for j in range(N_BP):
            for i in range(j + 1):
                dist_km   = self.bp_km[i] - self.bp_km[j]   # 상류→하류 (양수)
                vel_km_step = AVG_VEL_KMH * 3600.0 / 1000.0  # km/step (1 step=1h)
                delay[j, i] = round(
                    self.num_interpolation * dist_km / vel_km_step
                )
        return delay

    # ──────────────────── 서브모델 ──────────────────────────────────── #

    def get_submodel(self, station: int, wl: float) -> int:
        """현재 수위로 유량 체계 (0~3) 결정.

        Parameters
        ----------
        station : int   1-based (1..20)
        wl      : float 현재 수위 [m]
        """
        c = self.event_criteria[station - 1]
        if   wl < c[0]: return 0
        elif wl < c[1]: return 1
        elif wl < c[2]: return 2
        else:           return 3

    def get_submodel_params(self, station: int, sm: int) -> tuple[float, float, float]:
        """서브모델 파라미터 (a_sm, b_sm, c_sm) 반환.

        Parameters
        ----------
        station : int  1-based
        sm      : int  서브모델 인덱스 (0..3)

        Notes
        -----
        C++ UpdateParam_level: param_trained[point][point + 1 + 3*sm]
        Python (0-indexed): params[station-1][station + 1 + 3*sm]
        """
        base = station + 1 + 3 * sm   # 0-based index
        p = self.params[station - 1]
        return float(p[base]), float(p[base + 1]), float(p[base + 2])

    def clip_wl(self, station: int, wl: float) -> float:
        """level_limit 범위로 수위 클리핑."""
        lo, hi = self.level_limit[station - 1, 1], self.level_limit[station - 1, 0]
        return float(np.clip(wl, lo, hi))

    # ──────────────────── 정보 출력 ─────────────────────────────────── #

    def summary(self) -> str:
        lines = [
            "DataLibrary 요약",
            f"  스테이션 수      : {N_STATION}",
            f"  BP 수            : {N_BP}",
            f"  보간 분할 수     : {self.num_interpolation}",
            f"  딜레이 최대      : {self.delay_max} 스텝",
            f"  파라미터 배열    : {self.params.shape}",
            "",
            "  Station  BP_km   AR1       c_sm0      c_sm1      c_sm2      c_sm3",
            "  ──────── ──────  ────────  ─────────  ─────────  ─────────  ─────────",
        ]
        for stn in range(1, N_STATION + 1):
            ar1 = self.params[stn - 1, 0]
            csm = [self.get_submodel_params(stn, sm)[2] for sm in range(4)]
            lines.append(
                f"  St{stn:2d}    {BP_KM[stn]:6.1f}  {ar1:8.6f}  "
                + "  ".join(f"{c:9.4f}" for c in csm)
            )
        return "\n".join(lines)
