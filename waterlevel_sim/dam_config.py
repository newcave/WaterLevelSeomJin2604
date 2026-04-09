"""dam_config.py — 전체 댐 시스템 파라미터 설정

⚙️  수정 포인트가 이 파일에만 집중됩니다.
🔶 = WAMIS 실측 확인 필요 / ✅ = 확정값
"""

# ═══════════════════════════════════════════════════════════════ #
#  최적화 구조 파라미터
# ═══════════════════════════════════════════════════════════════ #

OPT_CONFIG: dict = {
    # ── 블록 구조 ────────────────────────────────────────────── #
    # OptimizationResult 역산 기준:
    # block_minutes=None → n_time/n_blocks 자동계산 (전체 커버)
    # block_minutes=330  → 고정 110h (10h 미커버 발생 → 비권장)
    "n_blocks":         20,       # ✅ 방류량 조절 구간 수 (5일/20블록=6h/블록)
    "block_minutes":    None,     # ✅ None = 자동 (전체 기간 균등 분할)
    "dt_minutes":       30,       # ✅ 기본 타임스텝 [분]

    # ── 방류 제약 ────────────────────────────────────────────── #
    "max_delta_cms":    800.0,    # ✅ 구간 간 최대 변화폭 [m³/s]

    # ── 탐색 설정 ────────────────────────────────────────────── #
    # 원본: Nelder-Mead, 500회 수준에서 수렴
    "max_iter":         500,      # ✅ 최대 반복 횟수
    "tol":              1e-4,     # ✅ 수렴 허용 오차
    "method":           "Nelder-Mead",   # ✅ 원본 방식

    # ── 시나리오별 목적함수 가중치 + 시간분포 목표 ────────────── #
    # w_penalty + w_volume = 1.0
    # front_ratio: 전반기(앞 절반 블록) 총량 비율 목표
    #   Conservative: 사전 방류 → 전반에 60% 집중
    #   Moderate:     균등 분배 → 50/50
    #   Aggressive:   후반 방류 → 전반 40%, 후반 60%
    # w_temporal: 시간분포 목표 위반 패널티 가중치
    "scenarios": {
        "Conservative": {"w_penalty": 0.3, "w_volume": 0.7,
                         "front_ratio": 0.60, "w_temporal": 500.0},
        "Moderate":     {"w_penalty": 0.5, "w_volume": 0.5,
                         "front_ratio": 0.50, "w_temporal": 300.0},
        "Aggressive":   {"w_penalty": 0.7, "w_volume": 0.3,
                         "front_ratio": 0.40, "w_temporal": 500.0},
    },
}


# ═══════════════════════════════════════════════════════════════ #
#  페널티(DS) 설정
# ═══════════════════════════════════════════════════════════════ #

PENALTY_CONFIG: dict = {
    # Danger Score (DS) 구간별 페널티
    # 고수부지선(c01) 초과부터 차감 시작
    "p_c01_c02":   -10.0,   # ✅ 고수부지 ~ 주의보
    "p_c02_c03":   -30.0,   # ✅ 주의보   ~ 경보
    "p_c03_c04":   -60.0,   # ✅ 경보     ~ 계획홍수위
    "p_exceed":   -100.0,   # ✅ 계획홍수위 초과 (하드 제약)

    "station_weights":  {},     # {} = 전 지점 동일(1.0)
    "use_time_weight":  False,
}


# ═══════════════════════════════════════════════════════════════ #
#  댐 파라미터
# ═══════════════════════════════════════════════════════════════ #

DAM_CONFIG: dict = {

    "seomjin": {
        "name":   "섬진강댐 (옥정호)",
        "index":  0,

        # ── 제원 ✅ ──────────────────────────────────────────── #
        "total_volume_m3":  466e6,
        "flood_level":      198.00,
        "normal_high":      193.50,
        "low_level":        150.00,
        "min_op_level":     150.00,
        "max_op_level":     198.00,
        "initial_level":    191.00,   # 🔶 이벤트별 실측값 교체

        # ── 방류 제약 ✅ ─────────────────────────────────────── #
        # OptimizationResult 실측 범위: 215~2057 m³/s
        # 최적화 결과 범위:             330~1306 m³/s
        "min_discharge":      100.0,  # 최소 방류량 (유지수량)
        "max_discharge":     1800.0,  # ✅ 절대 상한 [m³/s] — UI 슬라이더 연동
        "max_discharge_hard": 1800.0, # 하드 제약 (초과 시 강제 클리핑)
        "init_discharge":     220.5,  # ✅ OptimizationResult 초기값

        # ── 수위-저수용량 3차 다항식 ─────────────────────────── #
        # 피팅 오차: 최대 ±17백만m³ (3.7%) 🔶 WAMIS 실계수 교체 권장
        "volume_poly": {
            "a":  3.105344e+03,
            "b": -1.287254e+06,
            "c":  1.761390e+08,
            "d": -7.935120e+09,
        },
        # 구간별 WAMIS 계수 (확보 시 채움, 비어있으면 통합식 사용)
        "volume_segments": [
            [150.00, 183.30,  0.0,  0.0,  0.0,  0.0],  # 🔶
            [183.30, 186.85,  0.0,  0.0,  0.0,  0.0],  # 🔶 부분확보 대기
            [186.85, 193.50,  0.0,  0.0,  0.0,  0.0],  # 🔶
            [193.50, 198.00,  0.0,  0.0,  0.0,  0.0],  # 🔶
        ],
    },

    "juam": {
        "name":   "주암댐",
        "index":  1,
        "total_volume_m3":  457e6,
        "flood_level":      165.50,   # 🔶
        "normal_high":      162.00,   # 🔶
        "low_level":        123.00,   # 🔶
        "min_op_level":     123.00,
        "max_op_level":     165.50,
        "initial_level":    160.00,   # 🔶
        "min_discharge":     50.0,
        "max_discharge":   2000.0,
        "init_discharge":   232.4,
        "volume_poly": {
            "a":  2.639311e+03,
            "b": -8.350894e+05,
            "c":  8.726684e+07,
            "d": -3.009870e+09,
        },
        "volume_segments": [
            [123.00, 165.50,  0.0,  0.0,  0.0,  0.0],  # 🔶
        ],
    },
}


# ═══════════════════════════════════════════════════════════════ #
#  기타
# ═══════════════════════════════════════════════════════════════ #

STATION_INFO_CSV = "data/StationInfo_BankHeight_EventCriteria.csv"


def validate() -> tuple:
    warnings = []
    for sname, sw in OPT_CONFIG["scenarios"].items():
        s = sw["w_penalty"] + sw["w_volume"]
        if abs(s - 1.0) > 1e-6:
            warnings.append(f"시나리오 {sname} 가중치 합={s:.3f}")
    bm = OPT_CONFIG["block_minutes"]
    dt = OPT_CONFIG["dt_minutes"]
    nb = OPT_CONFIG["n_blocks"]
    if bm is None:
        spb = 241 // nb
        total_h = spb * nb * dt / 60
        warnings_info = [
            f"블록 구조: {nb}블록 × 자동 ({spb}스텝/블록 = {spb*dt/60:.1f}h)",
            f"tesr 기준 커버: {total_h:.1f}h ({total_h/24:.1f}일) / 120h = {total_h/120*100:.0f}%",
        ]
    else:
        steps = bm // dt
        total_h = nb * bm / 60
        warnings_info = [
            f"블록 구조: {nb}블록 × {bm}min = {total_h:.1f}h ({total_h/24:.2f}일)",
            f"⚠️  tesr 120h 커버리지: {total_h/120*100:.0f}%",
        ]
    return warnings, warnings_info


if __name__ == "__main__":
    warns, info = validate()
    for i in info: print(f"ℹ️  {i}")
    if warns:
        for w in warns: print(f"⚠️  {w}")
    else:
        print("✅ 설정값 유효성 검사 통과")
