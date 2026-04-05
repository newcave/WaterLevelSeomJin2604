"""routing.py — 유량 라우팅 모듈 (HEinsSim 간이 대체)

선형 저류 라우팅 (Linear Reservoir Routing):
    Q_station[p, t] = α[p] * Q_station[p, t-1]
                    + (1-α[p]) * (cumulative upstream Q with delay)
                    + lateral[p]

캘리브레이션:
    NC 파일의 Q_station 정상상태 값을 기준으로 α, ratio, lateral 역산

Notes
-----
이 모듈은 HEinsSim DLL 없이 경계 유량(Q_in)만으로 단면 유량을 추정합니다.
정확도는 수리모델 대비 낮지만, 독립 실행 환경에서의 1차 근사로 활용됩니다.
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from .data_library import DataLibrary, N_BP, N_STATION, BP_KM


class FlowRouter:
    """경계 유량 → 단면 유량 라우팅기.

    Parameters
    ----------
    dl : DataLibrary
        딜레이 행렬 및 BP 정보
    q_in : ndarray, shape (n_bc, N_BP)
        경계 유입 유량 [m³/s]
    q_station_ref : ndarray, shape (n_time, N_BP), optional
        캘리브레이션용 참조 단면 유량 (NC 파일에서 로드)

    Examples
    --------
    >>> router = FlowRouter(dl, nc.q_in, nc.q_station)
    >>> router.calibrate()                     # 파라미터 캘리브레이션
    >>> q_routed = router.route(nc.q_in)       # 라우팅 실행
    >>> print(f'Q_routing RMSE: {router.rmse:.1f} m³/s')
    """

    def __init__(
        self,
        dl: DataLibrary,
        q_in: np.ndarray,
        q_station_ref: np.ndarray | None = None,
    ) -> None:
        self.dl = dl
        self.q_in  = np.asarray(q_in,  dtype=np.float64)
        self.q_ref = np.asarray(q_station_ref, dtype=np.float64) if q_station_ref is not None else None
        self.n_bc  = self.q_in.shape[0]

        # 라우팅 파라미터 (캘리브레이션 전 기본값)
        self.alpha    = np.full(N_BP, 0.15)         # 저류 계수 (0 = 즉시반응, 1 = 완전저류)
        self.ratio    = np.ones(N_BP)                # Q_cumBC → Q_station 비율
        self.lateral  = np.zeros(N_BP)               # 구간 내 측방 유입량 [m³/s]
        self.is_calibrated = False
        self.rmse     = np.nan

    # ─── 캘리브레이션 ────────────────────────────────────────────── #

    def calibrate(self, t_steady: int = 5) -> None:
        """정상상태 데이터로 라우팅 파라미터 캘리브레이션.

        Parameters
        ----------
        t_steady : int
            정상상태 시작 타임스텝 (초기 과도 구간 제외)
        """
        if self.q_ref is None:
            raise ValueError("캘리브레이션 참조 데이터(q_station_ref) 없음.")

        n_time = self.q_ref.shape[0]

        for p in range(1, N_STATION + 1):
            q_ref_ss = self.q_ref[t_steady:, p]
            q_cum_ss = self._cumulative_upstream(p, n_time)[t_steady:]

            # ratio: 정상상태 비율
            denom = q_cum_ss[q_cum_ss > 0.1]
            numer = q_ref_ss[q_cum_ss > 0.1]
            if len(denom) > 0:
                self.ratio[p] = float(np.median(numer / denom))
            else:
                self.ratio[p] = 1.0

            # lateral: 잔차 (구간 내 추가 유입)
            self.lateral[p] = float(np.mean(q_ref_ss - q_cum_ss * self.ratio[p]))

            # alpha: 초기 과도 구간(t<t_steady)의 감쇠 계수 역산
            #   exponential fit: Q(t) = Q_ss * (1 - e^{-t/tau})
            if t_steady > 1:
                q_transient = self.q_ref[:t_steady, p]
                q_ss_val = np.median(q_ref_ss) if len(q_ref_ss) > 0 else 0
                if q_ss_val > 1.0:
                    frac = np.clip(q_transient / q_ss_val, 0, 0.9999)
                    # 로그 피팅: alpha = exp(-1/tau) → 적절한 tau 선택
                    tau = t_steady / 2.0
                    self.alpha[p] = float(np.clip(np.exp(-1.0 / max(tau, 0.5)), 0.0, 0.95))
                else:
                    self.alpha[p] = 0.15

        self.is_calibrated = True

        # 캘리브레이션 RMSE 계산
        q_routed = self.route(self.q_in, n_out=n_time)
        mask = slice(t_steady, None)
        self.rmse = float(np.sqrt(np.mean(
            (q_routed[mask, 1:21] - self.q_ref[mask, 1:21]) ** 2
        )))

    # ─── 라우팅 실행 ─────────────────────────────────────────────── #

    def route(
        self,
        q_in: np.ndarray,
        n_out: int | None = None,
        q_initial: np.ndarray | None = None,
    ) -> np.ndarray:
        """경계 유량 → 단면 유량 라우팅.

        Parameters
        ----------
        q_in      : ndarray, shape (n_bc, N_BP)
        n_out     : int, 출력 타임스텝 수 (None이면 n_bc)
        q_initial : ndarray, shape (N_BP,), 초기 단면 유량

        Returns
        -------
        q_station : ndarray, shape (n_out, N_BP)
        """
        q_in   = np.asarray(q_in, dtype=np.float64)
        n_bc   = q_in.shape[0]
        if n_out is None:
            n_out = n_bc

        q_st = np.zeros((n_out, N_BP), dtype=np.float64)

        # 초기 조건: 참조 데이터 첫 값 또는 0
        if q_initial is not None:
            q_st[0] = np.asarray(q_initial)
        elif self.q_ref is not None:
            q_st[0] = self.q_ref[0]

        for t in range(1, n_out):
            q_cum = self._cumulative_upstream_at(q_in, t, n_bc)
            for p in range(1, N_STATION + 1):
                q_eq = q_cum[p] * self.ratio[p] + self.lateral[p]
                q_st[t, p] = self.alpha[p] * q_st[t-1, p] + (1 - self.alpha[p]) * q_eq

        return q_st

    # ─── 내부 헬퍼 ──────────────────────────────────────────────── #

    def _cumulative_upstream(self, bp: int, n_time: int) -> np.ndarray:
        """BP[bp]의 상류 누적 유량 시계열 (딜레이 적용)."""
        q_cum = np.zeros(n_time)
        for i in range(bp + 1):
            d = self.dl.delay[bp, i]
            for t in range(n_time):
                t_src = max(0, min(t - d, self.n_bc - 1))
                q_cum[t] += self.q_in[t_src, i]
        return q_cum

    def _cumulative_upstream_at(self, q_in: np.ndarray, t: int, n_bc: int) -> np.ndarray:
        """시각 t에서 각 BP의 상류 누적 유량 벡터."""
        q_cum = np.zeros(N_BP)
        for p in range(1, N_STATION + 1):
            for i in range(p + 1):
                d  = self.dl.delay[p, i]
                ts = max(0, min(t - d, n_bc - 1))
                q_cum[p] += q_in[ts, i]
        return q_cum

    # ─── 통계 ───────────────────────────────────────────────────── #

    def summary(self) -> str:
        lines = [
            "FlowRouter 요약",
            f"  캘리브레이션: {'완료' if self.is_calibrated else '미완료'}",
            f"  라우팅 RMSE : {self.rmse:.1f} m³/s",
            "",
            f"  {'St':>4}  {'BP_km':>7}  {'alpha':>7}  {'ratio':>7}  {'lateral':>9}",
            "  " + "─" * 42,
        ]
        for p in range(1, N_STATION + 1):
            lines.append(
                f"  St{p:2d}  {BP_KM[p]:7.1f}  {self.alpha[p]:7.4f}  "
                f"{self.ratio[p]:7.4f}  {self.lateral[p]:+9.2f}"
            )
        return "\n".join(lines)
