"""simulator.py — 수위 예측 시뮬레이션 엔진."""

from __future__ import annotations
import numpy as np
from .data_library import DataLibrary, N_STATION, N_BP, BP_KM


class WaterLevelSimulator:
    """섬진강 수위 예측 시뮬레이터.

    예측 모델 (역공학 확정):
        WL(station, t+1) = c_sm + a_sm × Q(station, t)
                                + b_sm × Q(station, t-1)

    Parameters
    ----------
    dl : DataLibrary
        파라미터 및 설정 객체
    wl_true : ndarray, shape (n_time, n_bp)
        참값(수리모델) 수위 — 초기값 및 검증용
    q_station : ndarray, shape (n_time, n_bp)
        수리모델 단면 유량 — 예측 입력값

    Examples
    --------
    >>> from waterlevel_sim import DataLibrary, WaterLevelSimulator, NCReader
    >>> nc  = NCReader("data/tesr.nc")
    >>> dl  = DataLibrary("data/ParamSetforcxx.csv")
    >>> sim = WaterLevelSimulator(dl, nc.wl, nc.q_station)
    >>> result = sim.run()
    >>> result.rmse_mean
    2.04
    """

    def __init__(
        self,
        dl: DataLibrary,
        wl_true: np.ndarray,
        q_station: np.ndarray,
    ) -> None:
        self.dl        = dl
        self.wl_true   = np.asarray(wl_true,   dtype=np.float64)   # (n_time, 22)
        self.q_station = np.asarray(q_station, dtype=np.float64)   # (n_time, 22)

        self.n_time = wl_true.shape[0]
        self._result: SimResult | None = None

    # ───────────────────── 예측 1스텝 ──────────────────────────────── #

    def predict_step(
        self,
        station: int,
        q0: float,
        q1: float,
        wl_prev: float,
    ) -> float:
        """단일 스텝 수위 예측.

        Parameters
        ----------
        station  : int    1-based 스테이션 번호
        q0       : float  현재 단면 유량 [m³/s]
        q1       : float  1스텝 전 단면 유량 [m³/s]
        wl_prev  : float  직전 수위 [m] (서브모델 선택용)

        Returns
        -------
        float : 예측 수위 [m]
        """
        sm          = self.dl.get_submodel(station, wl_prev)
        a_sm, b_sm, c_sm = self.dl.get_submodel_params(station, sm)
        wl_pred     = c_sm + a_sm * q0 + b_sm * q1
        return self.dl.clip_wl(station, wl_pred)

    # ───────────────────── 전체 시뮬레이션 ─────────────────────────── #

    def run(self) -> "SimResult":
        """전체 시뮬레이션 실행.

        Returns
        -------
        SimResult : 예측 수위 배열 및 통계 포함
        """
        dl       = self.dl
        delay_max = dl.delay_max
        n_valid   = self.n_time - delay_max
        if n_valid <= 0:
            raise ValueError("delay_max >= n_time; 데이터가 너무 짧습니다.")

        # 유효 타임스텝 인덱스 (0-based)
        t_indices = np.arange(delay_max, self.n_time)

        # 예측 배열: (N_STATION, n_valid)
        wl_pred = np.zeros((N_STATION, n_valid), dtype=np.float64)

        for k, t in enumerate(t_indices):
            for p in range(1, N_STATION + 1):
                bp_col = p     # BP 인덱스 (0-based) = station (1-based) → col p

                q0 = self.q_station[t,     bp_col] if t     < self.n_time else 0.0
                q1 = self.q_station[t - 1, bp_col] if t - 1 >= 0          else 0.0

                # 직전 수위: 예측값 우선, 초기는 참값
                wl_prev = (
                    wl_pred[p - 1, k - 1]
                    if k > 0
                    else self.wl_true[t, bp_col]
                )

                wl_pred[p - 1, k] = self.predict_step(p, q0, q1, wl_prev)

        self._result = SimResult(
            wl_pred   = wl_pred,
            wl_true   = self.wl_true[t_indices, 1:21],  # stations 1..20
            t_indices = t_indices,
            bp_km     = BP_KM[1:21],
            dt_sec    = 1800,
        )
        return self._result

    @property
    def result(self) -> "SimResult":
        if self._result is None:
            raise RuntimeError("run() 을 먼저 호출하세요.")
        return self._result


# ─────────────────────────── 결과 클래스 ────────────────────────────── #

class SimResult:
    """시뮬레이션 결과 컨테이너.

    Attributes
    ----------
    wl_pred : ndarray, shape (N_STATION, n_valid)
        예측 수위 [m]
    wl_true : ndarray, shape (n_valid, N_STATION)
        참값 수위 [m]
    t_indices : ndarray
        유효 타임스텝 인덱스 (0-based)
    bp_km : ndarray
        각 스테이션의 하천 거리 [km]
    dt_sec : int
        타임스텝 [초]
    """

    def __init__(
        self,
        wl_pred: np.ndarray,
        wl_true: np.ndarray,
        t_indices: np.ndarray,
        bp_km: np.ndarray,
        dt_sec: int,
    ) -> None:
        # wl_true 정렬: (n_valid, N_STATION) → (N_STATION, n_valid)
        self.wl_pred  = wl_pred                        # (20, n_valid)
        self.wl_true  = wl_true.T                      # (20, n_valid)
        self.t_indices = t_indices
        self.bp_km    = bp_km
        self.dt_sec   = dt_sec
        self.n_valid  = wl_pred.shape[1]

        # 시간축 (시간 단위)
        self.time_hours = t_indices * dt_sec / 3600.0

        self._compute_metrics()

    def _compute_metrics(self) -> None:
        err = self.wl_pred - self.wl_true                    # (20, n_valid)
        self.rmse = np.sqrt(np.mean(err ** 2, axis=1))       # (20,)
        self.mae  = np.mean(np.abs(err),       axis=1)
        self.bias = np.mean(err,               axis=1)
        self.rmse_mean = float(np.mean(self.rmse))

    # ─── 출력 ──────────────────────────────────────────────────────── #

    def stats_table(self) -> str:
        """정확도 통계 테이블 문자열."""
        lines = [
            "  Station  거리(km)    RMSE     MAE     BIAS",
            "  ─────── ─────────  ──────  ──────  ──────",
        ]
        for p in range(N_STATION):
            lines.append(
                f"  St{p+1:2d}    {self.bp_km[p]:6.1f}  "
                f"{self.rmse[p]:8.3f}  {self.mae[p]:6.3f}  {self.bias[p]:+7.3f}"
            )
        lines.append(f"\n  평균 RMSE: {self.rmse_mean:.3f} m")
        return "\n".join(lines)

    def print_stats(self) -> None:
        print(self.stats_table())
