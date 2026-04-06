"""dam_config.py — 전체 댐 시스템 파라미터 설정

⚙️  수정 포인트가 이 파일에만 집중됩니다.
    dam_correlation.py / dam_reservoir.py / optimizer.py 는
    이 파일을 참조만 합니다.

수정 방법:
    (A) 이 파일 직접 편집
    (B) 런타임 오버라이드:
        from waterlevel_sim.dam_config import DAM_CONFIG, OPT_CONFIG
        DAM_CONFIG["seomjin"]["initial_level"] = 192.5
    (C) pages/2_optimize.py UI 슬라이더로 조작 (OPT_CONFIG 연동)

🔶 = WAMIS 실측 계수 확보 후 교체 권장
✅ = 확정값
"""

# ═══════════════════════════════════════════════════════════════ #
#  최적화 구조 파라미터
# ═══════════════════════════════════════════════════════════════ #

OPT_CONFIG: dict = {
    # ── 블록 구조 ────────────────────────────────────────────── #
    "n_blocks":         6,        # ✅ 방류량 조절 구간 수 (UI 기준)
    "block_hours":      6,        # ✅ 구간 길이 [시간] (3 or 6)
    "dt_minutes":       30,       # ✅ 기본 타임스텝 [분] (NC 파일 기준)

    # ── 방류 제약 ────────────────────────────────────────────── #
    "max_delta_cms":    800.0,    # ✅ 구간 간 최대 변화폭 [m³/s] (UI 기준)

    # ── 탐색 설정 ────────────────────────────────────────────── #
    "max_iter":         1000,     # ✅ 최대 반복 횟수 (UI 기준)
    "tol":              1e-4,     # ✅ 수렴 허용 오차
    "seed":             42,       # ✅ 난수 시드 (재현성)

    # ── 시나리오별 목적함수 가중치 ────────────────────────────── #
    # w_penalty + w_volume = 1.0  (합이 1이 되어야 함)
    "scenarios": {
        "Conservative": {"w_penalty": 0.3, "w_volume": 0.7},  # 저수지 우선
        "Moderate":     {"w_penalty": 0.5, "w_volume": 0.5},  # 균형
        "Aggressive":   {"w_penalty": 0.7, "w_volume": 0.3},  # 홍수 피해 우선
    },
}


# ═══════════════════════════════════════════════════════════════ #
#  페널티 설정
# ═══════════════════════════════════════════════════════════════ #

PENALTY_CONFIG: dict = {
    # ── 구간별 최대 페널티 (구간 내 선형 보간) ────────────────── #
    # 수위 구간:  정상 → c01 → c02 → c03 → c04 →  초과
    # 페널티:      0      0    -10   -40  -100   -100 (하드)
    "p_c01_c02":   -10.0,   # ✅ 고수부지선 ~ 홍수주의보 구간 최대
    "p_c02_c03":   -30.0,   # ✅ 홍수주의보 ~ 홍수경보   구간 최대
    "p_c03_c04":   -60.0,   # ✅ 홍수경보   ~ 계획홍수위 구간 최대
    "p_exceed":   -100.0,   # ✅ 계획홍수위 초과 (하드 제약)

    # ── 지점별 가중치 ─────────────────────────────────────────── #
    # key: OriginalStation(float), value: 가중치 (기본 1.0)
    # 예: 중요 지점 가중치 상향: {97.8: 2.0, 93.2: 2.0}
    "station_weights": {},      # ✅ 비어있으면 전 지점 1.0

    # ── 시간 가중치 ───────────────────────────────────────────── #
    "use_time_weight":  False,  # 🔶 피크 시간대 가중치 (추후 확장)
}


# ═══════════════════════════════════════════════════════════════ #
#  댐 파라미터
# ═══════════════════════════════════════════════════════════════ #

DAM_CONFIG: dict = {

    # ─────────────────────────────────────────────────────────── #
    #  섬진강댐 (옥정호)
    # ─────────────────────────────────────────────────────────── #
    "seomjin": {
        "name":   "섬진강댐 (옥정호)",
        "index":  0,              # C++ index_dam = 0

        # ── 기본 제원 ✅ ─────────────────────────────────────── #
        "total_volume_m3":  466e6,   # 총저수용량 [m³]
        "flood_level":      198.00,  # 계획홍수위 [EL.m]
        "normal_high":      193.50,  # 상시만수위 [EL.m]
        "low_level":        150.00,  # 저수위     [EL.m]
        "min_op_level":     150.00,  # 운영 최저수위
        "max_op_level":     198.00,  # 운영 최고수위

        # ── 초기 조건 🔶 (홍수 이벤트 시작 시 실측값으로 교체) ── #
        "initial_level":    191.00,  # 초기 저수위 [EL.m]

        # ── 방류 제약 ✅ ─────────────────────────────────────── #
        # OptimizationResult 기준: 원본 220~2057 m³/s
        # 최적화 결과 범위:        330~1306 m³/s
        "min_discharge":    100.0,   # 최소 방류량 [m³/s]  (최소 유지수량)
        "max_discharge":   2500.0,   # 최대 방류량 [m³/s]  (방류 설비 한계)
        "init_discharge":   220.5,   # 기본 초기 방류량 [m³/s]

        # ── 수위-저수용량 3차 다항식 계수 ────────────────────── #
        # V(h) = a·h³ + b·h² + c·h + d  [m³]
        # 피팅 앵커: (150,0) (170,65M) (185,250M) (193.5,466M) (198,566M)
        # 오차: ±3~17백만m³ (최대 3.7%)  🔶 WAMIS 실계수 확보 후 교체
        #
        # 구간별 단일 계수 (전 구간 통합 피팅)
        "volume_poly": {
            "a":  3.105344e+03,   # h³ 계수
            "b": -1.287254e+06,   # h² 계수
            "c":  1.761390e+08,   # h  계수
            "d": -7.935120e+09,   # 상수항
        },
        # 구간별 별도 계수 (WAMIS 확보 후 채움, 비어있으면 위 통합식 사용)
        # 형식: [h_min, h_max, a, b, c, d]
        "volume_segments": [
            # [  h_min,   h_max,    a,    b,    c,    d  ]
            [150.00, 183.30,  0.0,  0.0,  0.0,  0.0],  # 🔶
            [183.30, 186.85,  0.0,  0.0,  0.0,  0.0],  # 🔶 부분 확보 대기
            [186.85, 193.50,  0.0,  0.0,  0.0,  0.0],  # 🔶
            [193.50, 198.00,  0.0,  0.0,  0.0,  0.0],  # 🔶
        ],
    },

    # ─────────────────────────────────────────────────────────── #
    #  주암댐
    # ─────────────────────────────────────────────────────────── #
    "juam": {
        "name":   "주암댐",
        "index":  1,              # C++ index_dam = 1

        # ── 기본 제원 🔶 ─────────────────────────────────────── #
        "total_volume_m3":  457e6,
        "flood_level":      165.50,  # 계획홍수위 🔶
        "normal_high":      162.00,  # 상시만수위 🔶
        "low_level":        123.00,  # 저수위     🔶
        "min_op_level":     123.00,
        "max_op_level":     165.50,

        # ── 초기 조건 🔶 ─────────────────────────────────────── #
        "initial_level":    160.00,

        # ── 방류 제약 🔶 ─────────────────────────────────────── #
        # OptimizationResult JA 범위: 103~1121 m³/s
        "min_discharge":     50.0,
        "max_discharge":    2000.0,
        "init_discharge":    232.4,  # OptimizationResult 초기값

        # ── 수위-저수용량 계수 ────────────────────────────────── #
        # 피팅 앵커: (123,0) (145,130M) (162,457M) (165.5,510M)
        # 오차: ±1~25백만m³  🔶
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
#  StationInfo CSV 경로 (상대 경로)
# ═══════════════════════════════════════════════════════════════ #

STATION_INFO_CSV = "data/StationInfo_BankHeight_EventCriteria.csv"


# ═══════════════════════════════════════════════════════════════ #
#  유효성 검사
# ═══════════════════════════════════════════════════════════════ #

def validate() -> list[str]:
    """설정값 유효성 검사. 경고 메시지 목록 반환."""
    warnings = []
    for key, d in DAM_CONFIG.items():
        # 시나리오 가중치 합 확인
        for sname, sw in OPT_CONFIG["scenarios"].items():
            s = sw["w_penalty"] + sw["w_volume"]
            if abs(s - 1.0) > 1e-6:
                warnings.append(f"시나리오 {sname} 가중치 합 = {s:.3f} (1.0 이어야 함)")
        # 방류 범위
        if d["min_discharge"] >= d["max_discharge"]:
            warnings.append(f"{key}: min_discharge >= max_discharge")
        # 수위 범위
        if d["min_op_level"] >= d["max_op_level"]:
            warnings.append(f"{key}: min_op_level >= max_op_level")
        # 초기 수위
        if not (d["min_op_level"] <= d["initial_level"] <= d["max_op_level"]):
            warnings.append(f"{key}: initial_level {d['initial_level']} 운영 범위 벗어남")
    return warnings


if __name__ == "__main__":
    warns = validate()
    if warns:
        print("⚠️  설정 경고:")
        for w in warns:
            print(f"   {w}")
    else:
        print("✅ 설정값 유효성 검사 통과")

    print("\n─── OPT_CONFIG ───")
    for k, v in OPT_CONFIG.items():
        print(f"  {k}: {v}")

    print("\n─── PENALTY_CONFIG ───")
    for k, v in PENALTY_CONFIG.items():
        print(f"  {k}: {v}")

    for dam_key in DAM_CONFIG:
        d = DAM_CONFIG[dam_key]
        print(f"\n─── {d['name']} ───")
        for k, v in d.items():
            if k not in ("volume_segments", "volume_poly"):
                print(f"  {k}: {v}")
        print(f"  volume_poly: {d['volume_poly']}")
        segs = d["volume_segments"]
        filled = sum(1 for s in segs if s[2] != 0.0)
        print(f"  volume_segments: {len(segs)}개 구간, {filled}개 확보")
