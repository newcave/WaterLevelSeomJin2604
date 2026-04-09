"""optimizer.py — 최적화 모듈 (통합)

[기존] FlowOptimizer  — RMSE 기반 유량 스케일 최적화 (하위 호환)
[신규] DamOptimizer   — DS(Danger Score) 기반 댐 방류 블록 최적화

핵심 설계:
    - 블록 크기 = n_time / n_blocks  (전체 기간 자동 커버)
    - 5일 데이터 / 6블록 → 블록당 20h  자동 계산
    - Nelder-Mead 최적화 (원본 방식, 빠른 수렴)
    - 반복 단계별 DS 수렴 이력 저장 (시각화용)

⚙️  설정: dam_config.py → OPT_CONFIG
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import minimize, minimize_scalar
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
#  [신규] DamOptimizer — DS(Danger Score) 기반
# ═══════════════════════════════════════════════════════════════ #

@dataclass
class DamOptResult:
    """단일 시나리오 최적화 결과."""
    scenario:        str
    q_blocks:        np.ndarray    # (n_blocks,) 최적 방류량 [m³/s]
    q_timeseries:    np.ndarray    # (n_time,)
    wl_pred:         np.ndarray    # (N_STATION, n_valid)
    ds_init:         float         # 초기 Danger Score
    ds_opt:          float         # 최적화 후 Danger Score
    improvement:     float         # 개선율 [%]
    n_calls:         int
    w_penalty:       float
    w_volume:        float
    station_info:    object        = field(repr=False)
    # 수렴 이력 (반복 단계별 DS) — 그래프용
    ds_history:      list[float]   = field(default_factory=list)
    # 블록 구조 정보
    n_blocks:        int           = 0
    block_hours:     float         = 0.0
    total_hours:     float         = 0.0

    def summary(self) -> str:
        return (
            f"[{self.scenario}]\n"
            f"  DS: {self.ds_init:.2f} → {self.ds_opt:.2f}  "
            f"({self.improvement:+.1f}%)\n"
            f"  블록: {[round(q) for q in self.q_blocks]} m³/s\n"
            f"  구조: {self.n_blocks}블록 × {self.block_hours:.1f}h "
            f"= {self.total_hours:.1f}h ({self.total_hours/24:.1f}일)\n"
            f"  호출: {self.n_calls}회"
        )

    def penalty_by_station(self) -> np.ndarray:
        n_t    = self.wl_pred.shape[1]
        scores = np.zeros(N_STATION)
        for t in range(n_t):
            scores += self.station_info.penalty_array(self.wl_pred[:, t])
        return scores


@dataclass
class DamOptAllResult:
    """3개 시나리오 전체 결과."""
    results: dict
    q_init:  np.ndarray
    block_info: dict   # n_blocks, block_hours, total_hours, steps_per_block

    def summary(self) -> str:
        lines = ["=" * 60, "전체 시나리오 최적화 결과", "=" * 60]
        for r in self.results.values():
            lines.append(r.summary())
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════ #

class DamOptimizer:
    """댐 방류 블록 최적화기 (DS 기반, Nelder-Mead).

    블록 구조 자동 계산:
        steps_per_block = n_time // n_blocks
        → 전체 시뮬레이션 기간을 항상 n_blocks 등분

    예시 (tesr 5일 데이터):
        n_time=241, n_blocks=6 → steps_per_block=40 → 20h/블록
        → 6블록 × 20h = 120h = 5일 (전체 커버)

    Parameters
    ----------
    dl           : DataLibrary
    station_info : StationInfo
    wl_obs       : ndarray (n_time, 22)
    q_station    : ndarray (n_time, 22)
    q_init_sj    : ndarray (n_time,)   초기 방류량 시계열
    opt_config   : dict, optional      OPT_CONFIG 오버라이드
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
        self._ds_hist  = []   # 수렴 이력

        # ── 블록 구조 자동 계산 ────────────────────────────── #
        self.n_blocks        = int(self.cfg["n_blocks"])
        dt_min               = self.cfg["dt_minutes"]

        # block_minutes 지정 시 사용, 없으면 전체 기간 균등 분할
        if self.cfg.get("block_minutes"):
            self.steps_per_block = int(self.cfg["block_minutes"] // dt_min)
        else:
            # 전체 기간 / n_blocks 자동 계산
            self.steps_per_block = max(1, self.n_time // self.n_blocks)

        self.block_hours  = self.steps_per_block * dt_min / 60.0
        self.total_hours  = self.n_blocks * self.block_hours

        # 원본(스케일 전) 총량 기준 저장 — 총량 보존 제약에 사용
        # q_init_sj 가 스케일링된 경우에도 원본 총량을 기준으로 함
        self.q_ref_sj = q_init_sj   # 호출 시 원본 전달 권장

        # 초기 블록 방류량
        self.q_init_blocks = self._to_blocks(self.q_init_sj)

        # 댐 제약
        sj = DAM_CONFIG["seomjin"]
        self.q_min = sj["min_discharge"]
        self.q_max = sj["max_discharge"]

    # ── 블록 정보 ────────────────────────────────────────────── #

    @property
    def block_info(self) -> dict:
        return {
            "n_blocks":        self.n_blocks,
            "steps_per_block": self.steps_per_block,
            "block_hours":     self.block_hours,
            "total_hours":     self.total_hours,
            "total_days":      self.total_hours / 24,
            "n_time":          self.n_time,
            "coverage":        min(1.0, self.total_hours /
                                   (self.n_time * self.cfg["dt_minutes"] / 60)),
        }

    def print_block_info(self):
        bi = self.block_info
        print(f"블록 구조:")
        print(f"  n_time       = {bi['n_time']} 스텝")
        print(f"  n_blocks     = {bi['n_blocks']}")
        print(f"  steps/block  = {bi['steps_per_block']}")
        print(f"  block_hours  = {bi['block_hours']:.1f} h")
        print(f"  total        = {bi['total_hours']:.1f} h = {bi['total_days']:.1f} 일")
        print(f"  커버리지     = {bi['coverage']*100:.0f}%")

    # ── 블록 ↔ 시계열 ───────────────────────────────────────── #

    def _to_blocks(self, q_ts: np.ndarray) -> np.ndarray:
        out = np.zeros(self.n_blocks)
        for b in range(self.n_blocks):
            t0 = b * self.steps_per_block
            t1 = min(t0 + self.steps_per_block, self.n_time)
            if t0 < self.n_time:
                out[b] = float(np.mean(q_ts[t0:t1]))
        return out

    def _to_timeseries(self, q_blocks: np.ndarray) -> np.ndarray:
        q_ts = np.zeros(self.n_time)
        for b in range(self.n_blocks):
            t0 = b * self.steps_per_block
            t1 = min(t0 + self.steps_per_block, self.n_time)
            if t0 < self.n_time:
                q_ts[t0:t1] = q_blocks[b]
        return q_ts

    # ── 시뮬레이션 ───────────────────────────────────────────── #

    def _simulate(self, q_blocks: np.ndarray) -> np.ndarray:
        q_ts        = self._to_timeseries(q_blocks)
        q_mod       = self.q_station.copy()
        q_mod[:, 1] = q_ts
        sim         = WaterLevelSimulator(self.dl, self.wl_obs, q_mod)
        self._calls += 1
        return sim.run().wl_pred   # (N_STATION, n_valid)

    # ── DS(Danger Score) 계산 ────────────────────────────────── #

    def _ds(self, wl_pred: np.ndarray) -> float:
        """총 Danger Score (페널티 합산, 0 이하)."""
        return self.si.total_penalty(wl_pred)

    def _volume_penalty(self, q_blocks: np.ndarray) -> float:
        """총방류량 보존 위반 페널티 (원본 q_sj 기준).

        항상 원본(스케일링 전) q_sj 총량과 비교.
        상대 오차 1% → -10점 수준으로 DS와 동일 스케일 맞춤.
        """
        q_sum_ref = float(np.sum(self.q_ref_sj))   # 원본 총량 기준
        q_sum_new = float(np.sum(self._to_timeseries(q_blocks)))
        rel_diff  = abs(q_sum_new - q_sum_ref) / (q_sum_ref + 1e-6)
        # DS 스케일과 맞춤: rel_diff 10% → -100점 (계획홍수위 초과와 동급)
        return -rel_diff * 1000.0

    def _normalize_volume(self, q_blocks: np.ndarray) -> np.ndarray:
        """총방류량을 원본과 동일하게 정규화 (하드 제약).

        블록별 비율을 유지하되 q_min/q_max 범위 내에서 스케일.
        스케일 후 클리핑으로 범위를 벗어나면 남은 총량을 균등 분배.
        """
        q_sum_ref  = float(np.sum(self.q_ref_sj))
        q_ts_new   = self._to_timeseries(q_blocks)
        q_sum_new  = float(np.sum(q_ts_new))
        if q_sum_new < 1e-6:
            # 방류량이 0에 가까우면 균등 분배
            q_mean = q_sum_ref / self.n_time
            return np.clip(np.full(self.n_blocks, q_mean), self.q_min, self.q_max)
        scale    = q_sum_ref / q_sum_new
        q_scaled = np.clip(q_blocks * scale, self.q_min, self.q_max)
        # 클리핑 후 총량 재확인 — 오차가 크면 균등 보정
        q_ts_scaled = self._to_timeseries(q_scaled)
        residual    = q_sum_ref - float(np.sum(q_ts_scaled))
        if abs(residual) > q_sum_ref * 0.01:  # 1% 이상 오차면 균등 보정
            adjust = residual / self.n_time
            q_scaled = np.clip(q_scaled + adjust, self.q_min, self.q_max)
        return q_scaled

    def _ramp_penalty(self, q_blocks: np.ndarray) -> float:
        """구간 간 급격 변화 페널티."""
        excess = np.maximum(
            0.0, np.abs(np.diff(q_blocks)) - self.cfg["max_delta_cms"]
        )
        return -float(np.sum(excess)) * 0.1

    def _temporal_penalty(self, q_blocks: np.ndarray,
                          front_ratio: float, w_temporal: float) -> float:
        """전반기/후반기 방류량 비율 목표 위반 페널티.

        Parameters
        ----------
        front_ratio : float  전반기(앞 절반) 목표 비율 (예: 0.6 = 60%)
        w_temporal  : float  위반 패널티 가중치

        Conservative (front=0.60): 사전 방류 유도
        Moderate     (front=0.50): 균등 분배
        Aggressive   (front=0.40): 후반 집중 (홍수 선제 저류)
        """
        half      = self.n_blocks // 2
        q_front   = float(np.sum(q_blocks[:half]))
        q_back    = float(np.sum(q_blocks[half:]))
        q_total   = q_front + q_back + 1e-6
        actual_fr = q_front / q_total
        diff      = abs(actual_fr - front_ratio)
        return -diff * w_temporal

    # ── 목적함수 ─────────────────────────────────────────────── #

    def _objective(self, q_blocks: np.ndarray,
                   w_penalty: float, w_volume: float,
                   front_ratio: float = 0.5,
                   w_temporal: float = 0.0) -> float:
        q_clipped = np.clip(q_blocks, self.q_min, self.q_max)
        wl        = self._simulate(q_clipped)
        ds        = self._ds(wl)
        pv        = self._volume_penalty(q_clipped)
        pr        = self._ramp_penalty(q_clipped)
        pt        = self._temporal_penalty(q_clipped, front_ratio, w_temporal)
        total     = w_penalty * ds + w_volume * pv + pr + pt
        self._ds_hist.append(ds)
        return total

    # ── 단일 시나리오 최적화 ─────────────────────────────────── #

    def optimize(self, scenario: str = "Moderate",
                 verbose: bool = True) -> DamOptResult:
        scen      = self.cfg["scenarios"][scenario]
        w_p, w_v  = scen["w_penalty"], scen["w_volume"]
        self._calls   = 0
        self._ds_hist = []

        wl_init  = self._simulate(self.q_init_blocks)
        ds_init  = self._ds(wl_init)

        if verbose:
            bi = self.block_info
            print(f"\n[{scenario}] "
                  f"{bi['n_blocks']}블록 × {bi['block_hours']:.1f}h "
                  f"= {bi['total_hours']:.0f}h ({bi['total_days']:.1f}일)")
            print(f"  초기 DS: {ds_init:.2f}")

        # 시나리오 temporal 파라미터
        front_ratio = scen.get("front_ratio", 0.5)
        w_temporal  = scen.get("w_temporal",  0.0)

        # 클리핑 보조 함수
        def obj(q):
            return self._objective(
                np.clip(q, self.q_min, self.q_max),
                w_p, w_v, front_ratio, w_temporal
            )

        # ── 초기값: 원본 블록 그대로 (시나리오별 차이는 가중치로만) ── #
        # ramp 초기화는 비현실적 집중 발생 → 제거
        x0 = self.q_init_blocks.copy()

        res = minimize(
            fun     = obj,
            x0      = x0,
            method  = self.cfg.get("method", "Nelder-Mead"),
            options = {
                "maxiter": self.cfg["max_iter"],
                "xatol":   self.cfg["tol"],
                "fatol":   self.cfg["tol"],
                "adaptive": True,
            },
        )

        # ── 총량 보존 정규화 (후처리 하드 제약) ─────────────────── #
        q_raw  = np.clip(res.x, self.q_min, self.q_max)
        q_opt  = self._normalize_volume(q_raw)
        wl_opt = self._simulate(q_opt)
        ds_opt = self._ds(wl_opt)
        improv = ((ds_opt - ds_init) / (abs(ds_init) + 1e-9)) * 100

        if verbose:
            print(f"  최적화 DS: {ds_opt:.2f} ({improv:+.1f}%)  "
                  f"호출: {self._calls}회")

        return DamOptResult(
            scenario      = scenario,
            q_blocks      = q_opt,
            q_timeseries  = self._to_timeseries(q_opt),
            wl_pred       = wl_opt,
            ds_init       = ds_init,
            ds_opt        = ds_opt,
            improvement   = improv,
            n_calls       = self._calls,
            w_penalty     = w_p,
            w_volume      = w_v,
            station_info  = self.si,
            ds_history    = self._ds_hist.copy(),
            n_blocks      = self.n_blocks,
            block_hours   = self.block_hours,
            total_hours   = self.total_hours,
        )

    # ── 전체 시나리오 ────────────────────────────────────────── #

    def optimize_all(self, verbose: bool = True) -> DamOptAllResult:
        results = {}
        for scenario in self.cfg["scenarios"]:
            results[scenario] = self.optimize(scenario, verbose=verbose)
        return DamOptAllResult(
            results    = results,
            q_init     = self.q_init_sj,
            block_info = self.block_info,
        )

    # ── 헬퍼 ────────────────────────────────────────────────── #

    @staticmethod
    def extract_q_sj(q_station: np.ndarray) -> np.ndarray:
        """q_station (n_time,22) → 섬진강댐 방류량 (n_time,)."""
        return q_station[:, 1].copy()
