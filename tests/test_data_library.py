"""tests/test_data_library.py — DataLibrary 단위 테스트"""
import pytest
import numpy as np
from waterlevel_sim import DataLibrary
from waterlevel_sim.data_library import (
    N_STATION, N_BP, N_SUBMODEL, MAX_PARAM, BP_KM, EVENT_CRITERIA, LEVEL_LIMIT
)


class TestDataLibraryInit:
    """DataLibrary 초기화 테스트."""

    def test_params_shape(self, dl):
        assert dl.params.shape == (N_STATION, MAX_PARAM)

    def test_params_nonzero_count(self, dl):
        """각 스테이션의 비零 파라미터 수가 station+13과 일치."""
        for stn in range(1, N_STATION + 1):
            nonzero = np.count_nonzero(dl.params[stn - 1])
            expected = stn + 13    # station + 1 (AR leading) + 12 (4 submodels × 3)
            assert nonzero == expected, \
                f"St{stn}: nonzero={nonzero}, expected={expected}"

    def test_bp_km_length(self, dl):
        assert len(dl.bp_km) == N_BP

    def test_event_criteria_shape(self, dl):
        assert dl.event_criteria.shape == (N_STATION, 3)

    def test_level_limit_shape(self, dl):
        assert dl.level_limit.shape == (N_STATION, 2)

    def test_delay_matrix_shape(self, dl):
        assert dl.delay.shape == (N_BP, N_BP)

    def test_delay_nonnegative(self, dl):
        assert (dl.delay >= 0).all()

    def test_delay_upper_triangular(self, dl):
        """BP i → j (i > j) 딜레이는 0 이어야 함 (상류로 거슬러 올라가지 않음)."""
        for j in range(N_BP):
            for i in range(j + 1, N_BP):
                assert dl.delay[j, i] == 0, f"delay[{j},{i}] should be 0"


class TestSubmodel:
    """서브모델 선택 테스트."""

    def test_submodel_below_c0(self, dl):
        """WL < c0 → sm=0"""
        c0 = dl.event_criteria[0, 0]   # Station 1
        assert dl.get_submodel(1, c0 - 1.0) == 0

    def test_submodel_between_c0_c1(self, dl):
        c0, c1 = dl.event_criteria[0, 0], dl.event_criteria[0, 1]
        assert dl.get_submodel(1, (c0 + c1) / 2) == 1

    def test_submodel_between_c1_c2(self, dl):
        c1, c2 = dl.event_criteria[0, 1], dl.event_criteria[0, 2]
        assert dl.get_submodel(1, (c1 + c2) / 2) == 2

    def test_submodel_above_c2(self, dl):
        c2 = dl.event_criteria[0, 2]
        assert dl.get_submodel(1, c2 + 1.0) == 3

    def test_submodel_all_stations(self, dl):
        """모든 스테이션에서 서브모델 반환값이 0~3 범위."""
        for stn in range(1, N_STATION + 1):
            for sm in range(N_SUBMODEL):
                result = dl.get_submodel(stn, dl.event_criteria[stn - 1, 0] - 0.5)
                assert result in (0, 1, 2, 3)


class TestSubmodelParams:
    """서브모델 파라미터 인덱스 테스트."""

    def test_c_sm_in_water_level_range(self, dl):
        """c_sm(기저 수위)이 level_limit 범위 내에 있어야 함."""
        for stn in range(1, N_STATION + 1):
            lo, hi = dl.level_limit[stn - 1, 1], dl.level_limit[stn - 1, 0]
            for sm in range(N_SUBMODEL):
                a, b, c = dl.get_submodel_params(stn, sm)
                assert lo <= c <= hi, \
                    f"St{stn} sm={sm}: c_sm={c:.3f} 범위 밖 [{lo},{hi}]"

    def test_q_coefficients_small(self, dl):
        """a_sm, b_sm은 매우 작아야 함 (|coeff| < 0.05)."""
        for stn in range(1, N_STATION + 1):
            for sm in range(N_SUBMODEL):
                a, b, c = dl.get_submodel_params(stn, sm)
                assert abs(a) < 0.05, f"St{stn} sm={sm}: |a_sm|={abs(a):.6f} 너무 큼"
                assert abs(b) < 0.05, f"St{stn} sm={sm}: |b_sm|={abs(b):.6f} 너무 큼"

    def test_c_sm_increases_downstream(self, dl):
        """상류 스테이션의 c_sm0가 하류보다 커야 함 (수위 감소 방향)."""
        c_sm0_vals = [dl.get_submodel_params(stn, 0)[2] for stn in range(1, N_STATION + 1)]
        # 처음 몇 스테이션은 단조 감소해야 함
        assert c_sm0_vals[0] > c_sm0_vals[2], "상류 c_sm0 > 하류 c_sm0"

    def test_param_index_station1(self, dl):
        """St1 sm=0 파라미터가 정확히 로드됐는지 검증."""
        a, b, c = dl.get_submodel_params(1, 0)
        assert abs(a - 0.002965) < 1e-5, f"a_sm0 mismatch: {a}"
        assert abs(b - 0.004698) < 1e-5, f"b_sm0 mismatch: {b}"
        assert abs(c - 124.504)  < 1e-2, f"c_sm0 mismatch: {c}"


class TestLevelLimit:
    """level_limit 클리핑 테스트."""

    def test_clip_above_upper(self, dl):
        """상한 초과 → 상한으로 클리핑."""
        hi = dl.level_limit[0, 0]
        assert dl.clip_wl(1, hi + 100) == pytest.approx(hi)

    def test_clip_below_lower(self, dl):
        """하한 미만 → 하한으로 클리핑."""
        lo = dl.level_limit[0, 1]
        assert dl.clip_wl(1, lo - 100) == pytest.approx(lo)

    def test_within_range_unchanged(self, dl):
        """범위 내 값은 변경 없음."""
        lo, hi = dl.level_limit[4, 1], dl.level_limit[4, 0]
        mid = (lo + hi) / 2
        assert dl.clip_wl(5, mid) == pytest.approx(mid)
