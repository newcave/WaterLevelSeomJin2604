"""optimizer.py — 유량 역산 최적화 모듈 (EinsOpt 간이 대체)

세 가지 모드:
  'global'     — 단일 스케일 인수 (빠름)
  'per_station'— 스테이션별 독립 스케일 (권장, ~3초)
  'timeseries' — 타임스텝 그룹별 스케일 (정밀, ~30초)
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize, minimize_scalar
from .data_library import DataLibrary, N_STATION, N_BP
from .simulator import WaterLevelSimulator


class FlowOptimizer:
    """유량 역산 최적화기 (EinsOpt 대체).

    Parameters
    ----------
    dl            : DataLibrary
    wl_obs        : ndarray (n_time, N_BP)  관측/참값 수위
    q_station_init: ndarray (n_time, N_BP)  초기 단면 유량

    Examples
    --------
    >>> opt = FlowOptimizer(dl, nc.wl, nc.q_station)
    >>> r = opt.optimize('per_station')
    >>> print(r.summary())
    """

    def __init__(self, dl, wl_obs, q_station_init):
        self.dl        = dl
        self.wl_obs    = np.asarray(wl_obs,         dtype=np.float64)
        self.q_station = np.asarray(q_station_init, dtype=np.float64)
        self.n_time    = wl_obs.shape[0]
        self._calls    = 0

    # ── 목적 함수 ─────────────────────────────────────────────── #
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

    # ── Global ────────────────────────────────────────────────── #
    def optimize_global(self, scale_bounds=(0.05, 5.0), verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        if verbose: print(f"  초기 RMSE: {rmse0:.4f} m")

        def obj(s):
            return self._rmse_all(self.q_station * s[0])[0]

        res = minimize(obj, [1.0], method='Nelder-Mead',
                       options={'xatol':1e-4,'fatol':1e-5,'maxiter':300})
        scale = float(res.x[0])
        q_opt = self.q_station * scale
        _, sim_res = self._rmse_all(q_opt)
        if verbose:
            print(f"  최적 스케일: {scale:.4f}")
            print(f"  최적화 RMSE: {sim_res.rmse_mean:.4f} m  (개선 {(1-sim_res.rmse_mean/rmse0)*100:.1f}%)")
        return OptResult('global', np.full(N_STATION, scale), q_opt,
                         sim_res, rmse0, sim_res.rmse_mean, self._calls)

    # ── Per-station ───────────────────────────────────────────── #
    def optimize_per_station(self, scale_bounds=(0.05, 5.0), verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        if verbose: print(f"  초기 RMSE: {rmse0:.4f} m")

        q_opt    = self.q_station.copy()
        scales   = np.ones(N_STATION)

        for p in range(N_STATION):
            stn = p + 1
            col = stn   # BP column index = station (1-based)

            def obj_stn(s, _p=p, _col=col):
                q_try = q_opt.copy()
                q_try[:, _col] *= s
                return self._rmse_stn(q_try, _p)

            r = minimize_scalar(obj_stn, bounds=scale_bounds, method='bounded',
                                options={'xatol':1e-4})
            scales[p] = float(r.x)
            q_opt[:, col] *= scales[p]

            if verbose and (p % 5 == 4 or p == N_STATION - 1):
                print(f"  St{stn:2d}  scale={scales[p]:.4f}  RMSE={r.fun:.4f} m")

        _, sim_res = self._rmse_all(q_opt)
        if verbose:
            print(f"\n  최적화 완료: {rmse0:.4f} → {sim_res.rmse_mean:.4f} m  "
                  f"(개선 {(1-sim_res.rmse_mean/rmse0)*100:.1f}%)")
        return OptResult('per_station', scales, q_opt, sim_res, rmse0, sim_res.rmse_mean, self._calls)

    # ── Timeseries ────────────────────────────────────────────── #
    def optimize_timeseries(self, window=10, scale_bounds=(0.05,5.0), verbose=True):
        self._calls = 0
        rmse0, _ = self._rmse_all(self.q_station)
        if verbose: print(f"  초기 RMSE: {rmse0:.4f} m")

        # 먼저 per_station으로 기반 확보
        per_res = self.optimize_per_station(scale_bounds, verbose=False)
        q_opt   = per_res.q_optimized.copy()

        # 그룹별 정밀 최적화
        n_groups = int(np.ceil(self.n_time / window))
        if verbose: print(f"  그룹별 세밀 조정: {n_groups}그룹 × {window}스텝")

        for g in range(n_groups):
            t0 = g * window; t1 = min(t0 + window, self.n_time)

            def obj_grp(s, _t0=t0, _t1=t1):
                q_try = q_opt.copy()
                q_try[_t0:_t1, :] *= s[0]
                return self._rmse_all(q_try)[0]

            res = minimize(obj_grp, [1.0], method='Nelder-Mead',
                           options={'xatol':1e-3,'fatol':1e-4,'maxiter':60})
            q_opt[t0:t1, :] *= float(res.x[0])

        _, sim_res = self._rmse_all(q_opt)
        if verbose:
            print(f"  최종 RMSE: {sim_res.rmse_mean:.4f} m")
        return OptResult('timeseries', per_res.scales, q_opt, sim_res, rmse0, sim_res.rmse_mean, self._calls)

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
                f"  함수 호출: {self.n_calls}회\n"
                f"  스케일 범위: {self.scales.min():.3f} ~ {self.scales.max():.3f}")
