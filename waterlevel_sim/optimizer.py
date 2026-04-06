"""optimizer.py — 댐 방류 최적화 (페널티 기반 블록 최적화)

⚙️  설정 변경: dam_config.py → OPT_CONFIG / PENALTY_CONFIG / DAM_CONFIG

목적:
    N개 블록 단위 방류량 결정 → 하류 페널티 최소화 + 총방류량 보존

시나리오:
    Conservative / Moderate / Aggressive (가중치 차이)
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import differential_evolution
from dataclasses import dataclass, field

from .data_library import DataLibrary, N_STATION
from .simulator    import WaterLevelSimulator
from .station_info import StationInfo
from .dam_config   import OPT_CONFIG, DAM_CONFIG


# ═══════════════════════════════════════════════════════════════ #
#  결과 컨테이너
# ═══════════════════════════════════════════════════════════════ #

@dataclass
class DamOptResult:
    scenario:       str
    q_blocks:       np.ndarray   # (n_blocks,) 최적 방류량 [m³/s]
    q_timeseries:   np.ndarray   # (n_time,)
    wl_pred:        np.ndarray   # (N_STATION, n_valid)
    penalty_init:   float
    penalty_opt:    float
    improvement:    float        # % (음수일수록 개선)
    n_calls:        int
    w_penalty:      float
    w_volume:       float
    station_info:   StationInfo  = field(repr=False)

    def summary(self) -> str:
        return (
            f"[{self.scenario}]  "
            f"페널티: {self.penalty_init:.1f} → {self.penalty_opt:.1f}  "
            f"({self.improvement:+.1f}%)  "
            f"블록: {[round(q) for q in self.q_blocks]} m³/s  "
            f"호출: {self.n_calls}회"
        )

    def penalty_by_station(self) -> np.ndarray:
        """스테이션별 누적 페널티 (n_time 합산)."""
        n_t    = self.wl_pred.shape[1]
        scores = np.zeros(N_STATION)
        for t in range(n_t):
            scores += self.station_info.penalty_array(self.wl_pred[:, t])
        return scores


@dataclass
class DamOptAllResult:
    results: dict[str, DamOptResult]
    q_init:  np.ndarray

    def summary(self) -> str:
        lines = ["=" * 60, "전체 시나리오 최적화 결과", "=" * 60]
        for r in self.results.values():
            lines.append(r.summary())
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════ #
#  DamOptimizer
# ═══════════════════════════════════════════════════════════════ #

class DamOptimizer:
    """댐 방류 블록 최적화기.

    Parameters
    ----------
    dl           : DataLibrary
    station_info : StationInfo
    wl_obs       : ndarray (n_time, 22)
    q_station    : ndarray (n_time, 22)
    q_init_sj    : ndarray (n_time,)   초기 방류량 시계열
    opt_config   : dict, optional      OPT_CONFIG 오버라이드

    Examples
    --------
    >>> opt = DamOptimizer(dl, si, nc.wl, nc.q_station,
    ...                   DamOptimizer.extract_q_sj(nc.q_station))
    >>> result = opt.optimize("Moderate")
    >>> all_r  = opt.optimize_all()
    """

    def __init__(
        self,
        dl:           DataLibrary,
        station_info: StationInfo,
        wl_obs:       np.ndarray,
        q_station:    np.ndarray,
        q_init_sj:    np.ndarray,
        opt_config:   dict | None = None,
    ) -> None:
        self.dl        = dl
        self.si        = station_info
        self.wl_obs    = np.asarray(wl_obs,    dtype=np.float64)
        self.q_station = np.asarray(q_station, dtype=np.float64)
        self.q_init_sj = np.asarray(q_init_sj, dtype=np.float64)
        self.cfg       = {**OPT_CONFIG, **(opt_config or {})}
        self.n_time    = wl_obs.shape[0]
        self._calls    = 0

        # 블록 구조
        self.steps_per_block = int(
            self.cfg["block_hours"] * 60 / self.cfg["dt_minutes"]
        )
        self.n_blocks = self.cfg["n_blocks"]

        # 초기 블록 방류량
        self.q_init_blocks = self._to_blocks(self.q_init_sj)

        # 댐 제약
        sj = DAM_CONFIG["seomjin"]
        self.q_min = sj["min_discharge"]
        self.q_max = sj["max_discharge"]

    # ── 블록 ↔ 시계열 ───────────────────────────────────────── #

    def _to_blocks(self, q_ts: np.ndarray) -> np.ndarray:
        out = np.zeros(self.n_blocks)
        for b in range(self.n_blocks):
            t0, t1 = b * self.steps_per_block, min((b+1) * self.steps_per_block, self.n_time)
            out[b] = float(np.mean(q_ts[t0:t1]))
        return out

    def _to_timeseries(self, q_blocks: np.ndarray) -> np.ndarray:
        q_ts = np.zeros(self.n_time)
        for b in range(self.n_blocks):
            t0, t1 = b * self.steps_per_block, min((b+1) * self.steps_per_block, self.n_time)
            q_ts[t0:t1] = q_blocks[b]
        return q_ts

    # ── 시뮬레이션 ───────────────────────────────────────────── #

    def _simulate(self, q_blocks: np.ndarray) -> np.ndarray:
        q_ts       = self._to_timeseries(q_blocks)
        q_mod      = self.q_station.copy()
        q_mod[:, 1] = q_ts          # BP index 1 = 섬진강댐 직하류
        sim        = WaterLevelSimulator(self.dl, self.wl_obs, q_mod)
        self._calls += 1
        return sim.run().wl_pred    # (N_STATION, n_valid)

    # ── 페널티 ───────────────────────────────────────────────── #

    def _flood_penalty(self, wl_pred: np.ndarray) -> float:
        return self.si.total_penalty(wl_pred)

    def _volume_penalty(self, q_blocks: np.ndarray) -> float:
        """총방류량 보존 위반 → 패널티."""
        q_sum_init = float(np.sum(self.q_init_sj))
        q_sum_new  = float(np.sum(self._to_timeseries(q_blocks)))
        rel_diff   = abs(q_sum_new - q_sum_init) / (q_sum_init + 1e-6)
        return -rel_diff * 1000.0   # 1% 차이 ≈ -10점

    def _ramp_penalty(self, q_blocks: np.ndarray) -> float:
        """구간 간 급격 변화 → 패널티."""
        excess = np.maximum(0.0, np.abs(np.diff(q_blocks)) - self.cfg["max_delta_cms"])
        return -float(np.sum(excess)) * 0.1

    # ── 목적함수 ─────────────────────────────────────────────── #

    def _objective(self, q_blocks: np.ndarray, w_penalty: float, w_volume: float) -> float:
        wl   = self._simulate(q_blocks)
        pf   = self._flood_penalty(wl)
        pv   = self._volume_penalty(q_blocks)
        pr   = self._ramp_penalty(q_blocks)
        # scipy는 최소화 → 페널티는 음수이므로 부호 그대로
        return w_penalty * pf + w_volume * pv + pr

    # ── 단일 시나리오 최적화 ─────────────────────────────────── #

    def optimize(self, scenario: str = "Moderate", verbose: bool = True) -> DamOptResult:
        scen      = self.cfg["scenarios"][scenario]
        w_p, w_v  = scen["w_penalty"], scen["w_volume"]
        self._calls = 0

        wl_init    = self._simulate(self.q_init_blocks)
        p_init     = self._flood_penalty(wl_init)

        if verbose:
            print(f"\n[{scenario}] 초기 페널티: {p_init:.2f}  "
                  f"(w_penalty={w_p}, w_volume={w_v})")

        bounds = [(self.q_min, self.q_max)] * self.n_blocks

        res = differential_evolution(
            func    = lambda q: self._objective(q, w_p, w_v),
            bounds  = bounds,
            maxiter = max(10, self.cfg["max_iter"] // 15),
            tol     = self.cfg["tol"],
            seed    = self.cfg["seed"],
            polish  = True,
            workers = 1,
        )

        q_opt  = res.x
        wl_opt = self._simulate(q_opt)
        p_opt  = self._flood_penalty(wl_opt)
        improv = ((p_opt - p_init) / (abs(p_init) + 1e-9)) * 100

        if verbose:
            print(f"[{scenario}] 최적화 페널티: {p_opt:.2f} ({improv:+.1f}%)  "
                  f"방류: {[round(q) for q in q_opt]}  호출: {self._calls}회")

        return DamOptResult(
            scenario     = scenario,
            q_blocks     = q_opt,
            q_timeseries = self._to_timeseries(q_opt),
            wl_pred      = wl_opt,
            penalty_init = p_init,
            penalty_opt  = p_opt,
            improvement  = improv,
            n_calls      = self._calls,
            w_penalty    = w_p,
            w_volume     = w_v,
            station_info = self.si,
        )

    # ── 전체 시나리오 ────────────────────────────────────────── #

    def optimize_all(self, verbose: bool = True) -> DamOptAllResult:
        results = {}
        for scenario in self.cfg["scenarios"]:
            results[scenario] = self.optimize(scenario, verbose=verbose)
        return DamOptAllResult(results=results, q_init=self.q_init_sj)

    # ── 헬퍼 ────────────────────────────────────────────────── #

    @staticmethod
    def extract_q_sj(q_station: np.ndarray) -> np.ndarray:
        """q_station (n_time,22) → 섬진강댐 방류량 (n_time,)."""
        return q_station[:, 1].copy()
