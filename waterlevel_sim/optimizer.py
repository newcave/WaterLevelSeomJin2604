"""optimizer.py — 최적화 모듈 (통합)

[기존] FlowOptimizer  — RMSE 기반 유량 스케일 최적화 (하위 호환)
[신규] DamOptimizer   — 페널티 기반 댐 방류 블록 최적화

⚙️  설정: dam_config.py → OPT_CONFIG / DAM_CONFIG
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import minimize, minimize_scalar, differential_evolution
from dataclasses import dataclass, field

from .data_library import DataLibrary, N_STATION, N_BP
from .simulator    import WaterLevelSimulator
from .dam_config   import OPT_CONFIG, DAM_CONFIG


# ═══════════════════════════════════════════════════════════════ #
#  [기존] FlowOptimizer — RMSE 기반  (하위 호환 유지)
# ═══════════════════════════════════════════════════════════════ #

class FlowOptimizer:
    """유량 역산 최적화기 (RMSE 기반, 기존 코드 유지)."""

    def __init__(self, dl, wl_obs, q_station_init):
        self.dl        = dl
        self.wl_obs    = np.asarray(wl_obs,         dtype=np.float64)
        self.q_station = np.asarray(q_station_init, dtype=np.float64)
        self.n_time    = wl_obs.shape[0]
        self._calls    = 0

    def _rmse_all(self, q):
        sim = WaterLevelSimulator(self.dl, self.wl_obs, q)
        res = sim.run()
        self._calls += 1
        return res.rmse_mean, res

    def _rmse_stn(self, q, p):
        sim = WaterLevelSimulator(self.dl, self.wl_obs, q)
        res = sim.run()
        self._calls += 1
        return float(res.rmse[p])

    def optimize_global(self, verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        if verbose: print(f"  초기 RMSE: {rmse0:.4f} m")
        def obj(s): return self._rmse_all(self.q_station * s[0])[0]
        res   = minimize(obj, [1.0], method='Nelder-Mead',
                         options={'xatol':1e-4,'fatol':1e-5,'maxiter':300})
        scale = float(res.x[0])
        q_opt = self.q_station * scale
        _, sr = self._rmse_all(q_opt)
        return OptResult('global', np.full(N_STATION, scale), q_opt,
                         sr, rmse0, sr.rmse_mean, self._calls)

    def optimize_per_station(self, scale_bounds=(0.05, 5.0), verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        q_opt    = self.q_station.copy()
        scales   = np.ones(N_STATION)
        for p in range(N_STATION):
            col = p + 1
            def obj_stn(s, _p=p, _c=col):
                q = q_opt.copy(); q[:, _c] *= s
                return self._rmse_stn(q, _p)
            r = minimize_scalar(obj_stn, bounds=scale_bounds, method='bounded',
                                options={'xatol':1e-4})
            scales[p] = float(r.x)
            q_opt[:, col] *= scales[p]
        _, sr = self._rmse_all(q_opt)
        return OptResult('per_station', scales, q_opt, sr, rmse0, sr.rmse_mean, self._calls)

    def optimize_timeseries(self, window=10, scale_bounds=(0.05,5.0), verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        per_res  = self.optimize_per_station(scale_bounds, verbose=False)
        q_opt    = per_res.q_optimized.copy()
        n_groups = int(np.ceil(self.n_time / window))
        for g in range(n_groups):
            t0 = g * window; t1 = min(t0 + window, self.n_time)
            def obj_grp(s, _t0=t0, _t1=t1):
                q = q_opt.copy(); q[_t0:_t1, :] *= s[0]
                return self._rmse_all(q)[0]
            res = minimize(obj_grp, [1.0], method='Nelder-Mead',
                           options={'xatol':1e-3,'fatol':1e-4,'maxiter':60})
            q_opt[t0:t1, :] *= float(res.x[0])
        _, sr = self._rmse_all(q_opt)
        return OptResult('timeseries', per_res.scales, q_opt, sr, rmse0, sr.rmse_mean, self._calls)

    def optimize(self, mode='per_station', **kwargs):
        if mode == 'global':      return self.optimize_global(**kwargs)
        if mode == 'per_station': return self.optimize_per_station(**kwargs)
        if mode == 'timeseries':  return self.optimize_timeseries(**kwargs)
        raise ValueError(f"Unknown mode: {mode!r}")


class OptResult:
    def __init__(self, mode, scales, q_optimized, sim_result,
                 rmse_init, rmse_opt, n_calls):
        self.mode        = mode
        self.scales      = scales
        self.q_optimized = q_optimized
        self.sim_result  = sim_result
        self.rmse_init   = rmse_init
        self.rmse_opt    = rmse_opt
        self.n_calls     = n_calls
        self.improvement = (1 - rmse_opt / rmse_init) * 100 if rmse_init > 0 else 0

    def summary(self):
        return (f"최적화 결과 ({self.mode})\n"
                f"  RMSE: {self.rmse_init:.4f} → {self.rmse_opt:.4f} m  "
                f"({self.improvement:.1f}% 개선)\n"
                f"  함수 호출: {self.n_calls}회")


# ═══════════════════════════════════════════════════════════════ #
#  [신규] DamOptimizer — 페널티 기반 댐 방류 블록 최적화
# ═══════════════════════════════════════════════════════════════ #

@dataclass
class DamOptResult:
    scenario:       str
    q_blocks:       np.ndarray
    q_timeseries:   np.ndarray
    wl_pred:        np.ndarray
    penalty_init:   float
    penalty_opt:    float
    improvement:    float
    n_calls:        int
    w_penalty:      float
    w_volume:       float
    station_info:   object = field(repr=False)

    def summary(self) -> str:
        return (f"[{self.scenario}]  "
                f"페널티: {self.penalty_init:.1f} → {self.penalty_opt:.1f}  "
                f"({self.improvement:+.1f}%)  "
                f"블록: {[round(q) for q in self.q_blocks]} m³/s  "
                f"호출: {self.n_calls}회")

    def penalty_by_station(self) -> np.ndarray:
        n_t    = self.wl_pred.shape[1]
        scores = np.zeros(N_STATION)
        for t in range(n_t):
            scores += self.station_info.penalty_array(self.wl_pred[:, t])
        return scores


@dataclass
class DamOptAllResult:
    results: dict
    q_init:  np.ndarray

    def summary(self) -> str:
        lines = ["=" * 60, "전체 시나리오 최적화 결과", "=" * 60]
        for r in self.results.values():
            lines.append(r.summary())
        return "\n".join(lines)


class DamOptimizer:
    """댐 방류 블록 최적화기 (페널티 기반).

    Parameters
    ----------
    dl           : DataLibrary
    station_info : StationInfo
    wl_obs       : ndarray (n_time, 22)
    q_station    : ndarray (n_time, 22)
    q_init_sj    : ndarray (n_time,)
    opt_config   : dict, optional

    Examples
    --------
    >>> opt    = DamOptimizer(dl, si, nc.wl, nc.q_station,
    ...                       DamOptimizer.extract_q_sj(nc.q_station))
    >>> result = opt.optimize("Moderate")
    """

    def __init__(self, dl, station_info, wl_obs, q_station,
                 q_init_sj, opt_config=None):
        self.dl        = dl
        self.si        = station_info
        self.wl_obs    = np.asarray(wl_obs,    dtype=np.float64)
        self.q_station = np.asarray(q_station, dtype=np.float64)
        self.q_init_sj = np.asarray(q_init_sj, dtype=np.float64)
        self.cfg       = {**OPT_CONFIG, **(opt_config or {})}
        self.n_time    = wl_obs.shape[0]
        self._calls    = 0

        self.steps_per_block = int(
            self.cfg["block_hours"] * 60 / self.cfg["dt_minutes"]
        )
        self.n_blocks        = self.cfg["n_blocks"]
        self.q_init_blocks   = self._to_blocks(self.q_init_sj)

        sj = DAM_CONFIG["seomjin"]
        self.q_min = sj["min_discharge"]
        self.q_max = sj["max_discharge"]

    # ── 블록 ↔ 시계열 ───────────────────────────────────────── #

    def _to_blocks(self, q_ts):
        out = np.zeros(self.n_blocks)
        for b in range(self.n_blocks):
            t0 = b * self.steps_per_block
            t1 = min(t0 + self.steps_per_block, self.n_time)
            out[b] = float(np.mean(q_ts[t0:t1]))
        return out

    def _to_timeseries(self, q_blocks):
        q_ts = np.zeros(self.n_time)
        for b in range(self.n_blocks):
            t0 = b * self.steps_per_block
            t1 = min(t0 + self.steps_per_block, self.n_time)
            q_ts[t0:t1] = q_blocks[b]
        return q_ts

    # ── 시뮬레이션 ───────────────────────────────────────────── #

    def _simulate(self, q_blocks):
        q_ts        = self._to_timeseries(q_blocks)
        q_mod       = self.q_station.copy()
        q_mod[:, 1] = q_ts
        sim         = WaterLevelSimulator(self.dl, self.wl_obs, q_mod)
        self._calls += 1
        return sim.run().wl_pred

    # ── 페널티 ───────────────────────────────────────────────── #

    def _flood_penalty(self, wl_pred):
        return self.si.total_penalty(wl_pred)

    def _volume_penalty(self, q_blocks):
        q_sum_init = float(np.sum(self.q_init_sj))
        q_sum_new  = float(np.sum(self._to_timeseries(q_blocks)))
        rel_diff   = abs(q_sum_new - q_sum_init) / (q_sum_init + 1e-6)
        return -rel_diff * 1000.0

    def _ramp_penalty(self, q_blocks):
        excess = np.maximum(0.0, np.abs(np.diff(q_blocks)) - self.cfg["max_delta_cms"])
        return -float(np.sum(excess)) * 0.1

    def _objective(self, q_blocks, w_penalty, w_volume):
        wl = self._simulate(q_blocks)
        return (w_penalty * self._flood_penalty(wl)
                + w_volume * self._volume_penalty(q_blocks)
                + self._ramp_penalty(q_blocks))

    # ── 최적화 ───────────────────────────────────────────────── #

    def optimize(self, scenario="Moderate", verbose=True):
        scen      = self.cfg["scenarios"][scenario]
        w_p, w_v  = scen["w_penalty"], scen["w_volume"]
        self._calls = 0

        wl_init  = self._simulate(self.q_init_blocks)
        p_init   = self._flood_penalty(wl_init)
        if verbose:
            print(f"\n[{scenario}] 초기 페널티: {p_init:.2f}")

        bounds = [(self.q_min, self.q_max)] * self.n_blocks
        res    = differential_evolution(
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
            print(f"[{scenario}] 최적화: {p_opt:.2f} ({improv:+.1f}%)  "
                  f"호출: {self._calls}회")

        return DamOptResult(
            scenario=scenario, q_blocks=q_opt,
            q_timeseries=self._to_timeseries(q_opt),
            wl_pred=wl_opt, penalty_init=p_init, penalty_opt=p_opt,
            improvement=improv, n_calls=self._calls,
            w_penalty=w_p, w_volume=w_v, station_info=self.si,
        )

    def optimize_all(self, verbose=True):
        results = {}
        for scenario in self.cfg["scenarios"]:
            results[scenario] = self.optimize(scenario, verbose=verbose)
        return DamOptAllResult(results=results, q_init=self.q_init_sj)

    @staticmethod
    def extract_q_sj(q_station):
        """q_station (n_time,22) → 섬진강댐 방류량 (n_time,)."""
        return q_station[:, 1].copy()
