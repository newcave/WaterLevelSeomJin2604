"""station_info.py — 관심 지점 정보 및 페널티 점수 체계

StationInfo_BankHeight_EventCriteria.csv 기반
- 20개 하천기본계획 측선 정보
- criteria01~04 기반 페널티 점수 산정
- 페널티 계수는 PENALTY_CONFIG로 별도 관리 (언제든 수정 가능)

관계:
    OriginalStation (≈ BP_KM)  ←→  Station (측선번호)
    EVENT_CRITERIA (서브모델 전환용, data_library.py) 와 별개
"""

from __future__ import annotations
import numpy as np
import csv
from pathlib import Path
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────── #
#  페널티 계수 설정  ← 여기만 수정하면 전체 반영
# ─────────────────────────────────────────────────────────────── #

PENALTY_CONFIG = {
    # 구간별 최대 페널티 (각 구간 내에서 선형 보간)
    "p_c01_c02":  -10.0,   # 고수부지선 ~ 홍수주의보  구간 최대 차감
    "p_c02_c03":  -30.0,   # 홍수주의보  ~ 홍수경보   구간 최대 차감
    "p_c03_c04":  -60.0,   # 홍수경보    ~ 계획홍수위 구간 최대 차감
    "p_exceed":  -100.0,   # 계획홍수위 초과 (하드 제약)

    # 지점별 가중치 (1.0 = 동일, 추후 인구/자산 기준 조정 가능)
    # key: OriginalStation (float), value: 가중치
    "station_weights": {},   # 비어있으면 모든 지점 1.0

    # 시간 가중치 사용 여부 (추후 확장)
    "use_time_weight": False,
}


# ─────────────────────────────────────────────────────────────── #
#  데이터 클래스
# ─────────────────────────────────────────────────────────────── #

@dataclass
class StationRecord:
    """단일 관심 지점 정보."""
    station_km:      float   # 하천기본계획 측선 위치 [km]
    original_km:     float   # K-River BP_KM (매핑 키)
    wl_max:          float   # 물리적 최대 수위 [m]
    wl_min:          float   # 물리적 최소 수위 [m]
    criteria01:      float   # 고수부지선 (주의 시작)  [m]
    criteria02:      float   # 홍수 주의보             [m]
    criteria03:      float   # 홍수 경보               [m]
    criteria04:      float   # 계획 홍수위 (하드 제약) [m]

    @property
    def criteria(self) -> list[float]:
        return [self.criteria01, self.criteria02,
                self.criteria03, self.criteria04]

    @property
    def interval(self) -> float:
        """criteria 등간격 크기 [m]."""
        return (self.criteria04 - self.criteria01) / 3.0

    def level_label(self, wl: float) -> str:
        """수위 → 단계 레이블."""
        if wl < self.criteria01: return "정상"
        if wl < self.criteria02: return "⚠️ 고수부지"
        if wl < self.criteria03: return "🟠 홍수주의보"
        if wl < self.criteria04: return "🔴 홍수경보"
        return "🚨 계획홍수위초과"


# ─────────────────────────────────────────────────────────────── #
#  StationInfo 로더
# ─────────────────────────────────────────────────────────────── #

class StationInfo:
    """StationInfo CSV 로더 및 페널티 계산기.

    Parameters
    ----------
    csv_path : str | Path
        StationInfo_BankHeight_EventCriteria.csv 경로
    penalty_config : dict, optional
        PENALTY_CONFIG 덮어쓰기 (기본: 모듈 상단 PENALTY_CONFIG)

    Attributes
    ----------
    records : list[StationRecord]
        20개 지점 정보 (OriginalStation 오름차순)
    bp_to_record : dict[float, StationRecord]
        OriginalStation → StationRecord 매핑

    Examples
    --------
    >>> si = StationInfo("data/StationInfo_BankHeight_EventCriteria.csv")
    >>> p  = si.penalty(wl=128.0, original_km=130.4)
    >>> si.penalty_array(wl_pred)   # (20,) 배열 반환
    """

    def __init__(
        self,
        csv_path: str | Path,
        penalty_config: dict | None = None,
    ) -> None:
        self.cfg     = {**PENALTY_CONFIG, **(penalty_config or {})}
        self.records = self._load(csv_path)

        # OriginalStation → StationRecord 빠른 조회
        self.bp_to_record: dict[float, StationRecord] = {
            r.original_km: r for r in self.records
        }
        # 인덱스 순서 (BP_KM 내림차순 = 상류→하류)
        self.original_kms = [r.original_km for r in self.records]

    # ── 로드 ─────────────────────────────────────────────────── #

    def _load(self, path: str | Path) -> list[StationRecord]:
        records = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                records.append(StationRecord(
                    station_km  = float(row["Station"]),
                    original_km = float(row["OriginalStation"]),
                    wl_max      = float(row["max"]),
                    wl_min      = float(row["min"]),
                    criteria01  = float(row["criteria01"]),
                    criteria02  = float(row["criteria02"]),
                    criteria03  = float(row["criteria03"]),
                    criteria04  = float(row["criteria04"]),
                ))
        # OriginalStation 내림차순 정렬 (상류→하류)
        records.sort(key=lambda r: r.original_km, reverse=True)
        return records

    # ── 단일 지점 페널티 ─────────────────────────────────────── #

    def penalty(self, wl: float, original_km: float) -> float:
        """단일 지점 수위 → 페널티 점수.

        Parameters
        ----------
        wl          : float  예측 수위 [m]
        original_km : float  OriginalStation (BP_KM)

        Returns
        -------
        float : 0 이하 페널티 점수
        """
        rec = self.bp_to_record.get(original_km)
        if rec is None:
            return 0.0

        c1, c2, c3, c4 = rec.criteria
        cfg = self.cfg
        weight = cfg["station_weights"].get(original_km, 1.0)

        if wl <= c1:
            score = 0.0
        elif wl <= c2:
            score = cfg["p_c01_c02"] * (wl - c1) / (c2 - c1)
        elif wl <= c3:
            score = cfg["p_c01_c02"] + cfg["p_c02_c03"] * (wl - c2) / (c3 - c2)
        elif wl <= c4:
            score = (cfg["p_c01_c02"] + cfg["p_c02_c03"]
                     + cfg["p_c03_c04"] * (wl - c3) / (c4 - c3))
        else:
            score = cfg["p_exceed"]

        return float(score * weight)

    # ── 배열 페널티 ──────────────────────────────────────────── #

    def penalty_array(
        self,
        wl_pred: np.ndarray,
        t_idx: int | None = None,
    ) -> np.ndarray:
        """20개 지점 수위 배열 → 페널티 배열.

        Parameters
        ----------
        wl_pred : ndarray, shape (20,) or (20, n_time)
            예측 수위. 1D면 단일 타임스텝, 2D면 전체 시계열
        t_idx   : int, optional
            2D 입력 시 특정 타임스텝 인덱스

        Returns
        -------
        ndarray, shape (20,)  페널티 점수 배열
        """
        if wl_pred.ndim == 2:
            wl = wl_pred[:, t_idx] if t_idx is not None else wl_pred.mean(axis=1)
        else:
            wl = wl_pred

        return np.array([
            self.penalty(float(wl[i]), self.original_kms[i])
            for i in range(len(self.records))
        ])

    def total_penalty(self, wl_pred: np.ndarray) -> float:
        """전체 시계열 총 페널티 합산.

        Parameters
        ----------
        wl_pred : ndarray, shape (20, n_time)

        Returns
        -------
        float : 총 페널티 (0 이하)
        """
        total = 0.0
        n_time = wl_pred.shape[1] if wl_pred.ndim == 2 else 1
        for t in range(n_time):
            arr = self.penalty_array(wl_pred, t_idx=t)
            total += float(arr.sum())
        return total

    # ── 정보 출력 ────────────────────────────────────────────── #

    def summary(self) -> str:
        lines = [
            "StationInfo 요약 (20개 관심 지점)",
            f"  {'St_km':>8}  {'BP_km':>7}  {'min':>7}  {'c01':>7}  "
            f"{'c02':>7}  {'c03':>7}  {'c04':>7}  {'max':>7}",
            "  " + "─" * 72,
        ]
        for r in self.records:
            lines.append(
                f"  {r.station_km:>8.3f}  {r.original_km:>7.2f}  "
                f"{r.wl_min:>7.2f}  {r.criteria01:>7.4f}  "
                f"{r.criteria02:>7.4f}  {r.criteria03:>7.4f}  "
                f"{r.criteria04:>7.4f}  {r.wl_max:>7.2f}"
            )
        lines.append(f"\n  페널티 설정: {self.cfg}")
        return "\n".join(lines)

    def penalty_config_summary(self) -> str:
        """현재 페널티 설정 출력."""
        cfg = self.cfg
        return (
            "페널티 계수 설정\n"
            f"  고수부지선~주의보 구간 최대: {cfg['p_c01_c02']:>7.1f} 점\n"
            f"  주의보~경보       구간 최대: {cfg['p_c02_c03']:>7.1f} 점\n"
            f"  경보~계획홍수위   구간 최대: {cfg['p_c03_c04']:>7.1f} 점\n"
            f"  계획홍수위 초과             : {cfg['p_exceed']:>7.1f} 점 (하드 제약)\n"
            f"  지점별 가중치               : "
            f"{'기본 1.0 (균등)' if not cfg['station_weights'] else cfg['station_weights']}\n"
            f"  시간 가중치                 : {cfg['use_time_weight']}"
        )
