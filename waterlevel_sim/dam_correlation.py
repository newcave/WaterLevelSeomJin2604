"""dam_correlation.py — 수위-저수용량 관계곡선

⚙️  계수 수정: dam_config.py → DAM_CONFIG[key]["volume_poly"]
               구간 계수 확보 시: DAM_CONFIG[key]["volume_segments"]

C++ 대응:
    Seomjin::GetVolume(h)  →  SeomjinDam.get_volume(h)
    Juam::GetVolume(h)     →  JuamDam.get_volume(h)
"""

from __future__ import annotations
import numpy as np
from .dam_config import DAM_CONFIG


class DamCurve:
    """수위-저수용량 관계곡선.

    우선순위:
        1. volume_segments 에 계수가 있으면 구간별 3차 다항식
        2. 없으면 volume_poly (전 구간 통합 3차 다항식) 사용
    """

    def __init__(self, key: str) -> None:
        self.cfg   = DAM_CONFIG[key]
        self.h_min = self.cfg["min_op_level"]
        self.h_max = self.cfg["max_op_level"]
        p          = self.cfg["volume_poly"]
        self._poly = (p["a"], p["b"], p["c"], p["d"])

    # ── 저수량 ───────────────────────────────────────────────── #

    def get_volume(self, h: float) -> float:
        """수위 → 저수량 [m³]."""
        # 구간별 계수 우선
        for seg in self.cfg["volume_segments"]:
            h_lo, h_hi, a, b, c, d = seg
            if h_lo < h <= h_hi and not (a == b == c == d == 0.0):
                return float(np.clip(a*h**3 + b*h**2 + c*h + d, 0.0, None))
        # 통합 다항식 폴백
        a, b, c, d = self._poly
        return float(np.clip(a*h**3 + b*h**2 + c*h + d, 0.0, None))

    # ── 수위 역산 (Regula-Falsi, C++ 동일) ──────────────────── #

    def get_level(self, volume: float) -> float:
        """저수량 → 수위 [EL.m]."""
        v_min = self.get_volume(self.h_min)
        v_max = self.get_volume(self.h_max)
        if volume <= v_min: return self.h_min
        if volume >= v_max: return self.h_max

        f  = lambda h: self.get_volume(h) - volume
        h1, h2 = self.h_min, self.h_max
        for _ in range(50):  # 브래킷 확장
            if f(h1) * f(h2) <= 0: break
            h1 -= 1.0 if f(h1) > 0 else 0.0
            h2 += 1.0 if f(h2) < 0 else 0.0

        h_new, last = h2, 1
        for _ in range(1000):
            denom = f(h1) - f(h2)
            if abs(denom) < 1e-15: break
            h_new = h2 - f(h2) * (h1 - h2) / denom
            ref   = h1 if last == 1 else h2
            err   = abs((h_new - ref) / ref) if abs(ref) > 1e-15 else abs(h_new - ref)
            if err < 1e-10: break
            if f(h1) * f(h_new) > 0: h1, last = h_new, 1
            else:                     h2, last = h_new, 2

        return float(np.clip(h_new, self.h_min, self.h_max))

    def summary(self) -> str:
        cfg   = self.cfg
        segs  = cfg["volume_segments"]
        ok    = sum(1 for s in segs if s[2] != 0.0)
        lines = [
            f"댐: {cfg['name']}",
            f"  홍수위 {cfg['flood_level']:.2f} / "
            f"만수위 {cfg['normal_high']:.2f} / "
            f"저수위 {cfg['low_level']:.2f} EL.m",
            f"  총저수용량: {cfg['total_volume_m3']/1e6:.0f} 백만m³",
            f"  곡선: 통합 3차 다항식 + {ok}/{len(segs)}구간 확보",
        ]
        return "\n".join(lines)


# ── 싱글턴 ───────────────────────────────────────────────────── #
SeomjinDam = DamCurve("seomjin")
JuamDam    = DamCurve("juam")

def sj_get_volume(h: float) -> float: return SeomjinDam.get_volume(h)
def sj_get_level(v: float)  -> float: return SeomjinDam.get_level(v)
def ja_get_volume(h: float) -> float: return JuamDam.get_volume(h)
def ja_get_level(v: float)  -> float: return JuamDam.get_level(v)
