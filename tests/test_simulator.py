"""tests/test_simulator.py — WaterLevelSimulator 단위 테스트"""
import pytest
import numpy as np
from waterlevel_sim import DataLibrary, WaterLevelSimulator
from waterlevel_sim.npz_loader import load_demo
from waterlevel_sim.data_library import N_STATION


class TestSimulatorOutput:
    """시뮬레이션 출력 형상·범위 테스트."""

    def test_wl_pred_shape(self, sim_result):
        assert sim_result.wl_pred.shape[0] == N_STATION
        assert sim_result.wl_pred.shape[1] == sim_result.n_valid

    def test_wl_true_shape_matches_pred(self, sim_result):
        assert sim_result.wl_true.shape == sim_result.wl_pred.shape

    def test_n_valid_positive(self, sim_result):
        assert sim_result.n_valid > 0

    def test_rmse_shape(self, sim_result):
        assert sim_result.rmse.shape == (N_STATION,)

    def test_rmse_nonnegative(self, sim_result):
        assert (sim_result.rmse >= 0).all()

    def test_rmse_mean_positive(self, sim_result):
        assert sim_result.rmse_mean > 0

    def test_wl_pred_in_physical_range(self, sim_result, dl):
        """예측 수위가 level_limit 범위 내에 있어야 함."""
        for p in range(N_STATION):
            lo = dl.level_limit[p, 1]
            hi = dl.level_limit[p, 0]
            assert sim_result.wl_pred[p].min() >= lo - 1e-6, \
                f"St{p+1}: 예측 수위 하한 미만"
            assert sim_result.wl_pred[p].max() <= hi + 1e-6, \
                f"St{p+1}: 예측 수위 상한 초과"

    def test_time_hours_monotone(self, sim_result):
        """시간축이 단조 증가해야 함."""
        assert (np.diff(sim_result.time_hours) > 0).all()

    def test_stats_table_string(self, sim_result):
        s = sim_result.stats_table()
        assert "RMSE" in s
        assert "Station" in s


class TestSimulatorRMSEBaseline:
    """베이스라인 RMSE 범위 검증."""

    def test_rmse_below_threshold(self, sim_result):
        """베이스라인 평균 RMSE < 10m (극단적 오류 방지)."""
        assert sim_result.rmse_mean < 10.0

    def test_best_station_rmse(self, sim_result):
        """최소 RMSE < 2m."""
        assert sim_result.rmse.min() < 2.0

    @pytest.mark.parametrize("event", ["tesr", "tesr2", "tesr3"])
    def test_rmse_per_event(self, event, dl):
        """각 이벤트 베이스라인 RMSE < 8m."""
        nc  = load_demo(event)
        sim = WaterLevelSimulator(dl, nc.wl, nc.q_station)
        res = sim.run()
        assert res.rmse_mean < 8.0, f"{event}: RMSE={res.rmse_mean:.3f}m 너무 큼"


class TestPredictStep:
    """단일 스텝 예측 테스트."""

    def test_predict_step_returns_scalar(self, dl, nc_tesr):
        sim = WaterLevelSimulator(dl, nc_tesr.wl, nc_tesr.q_station)
        q0  = float(nc_tesr.q_station[10, 1])
        q1  = float(nc_tesr.q_station[9,  1])
        wl  = float(nc_tesr.wl[10, 1])
        out = sim.predict_step(1, q0, q1, wl)
        assert isinstance(out, float)

    def test_predict_step_clipped(self, dl, nc_tesr):
        """극단적 Q 입력에도 level_limit 범위 내 유지."""
        sim = WaterLevelSimulator(dl, nc_tesr.wl, nc_tesr.q_station)
        for stn in range(1, N_STATION + 1):
            out = sim.predict_step(stn, 1e6, 1e6, 50.0)   # 극단적 Q
            lo  = dl.level_limit[stn - 1, 1]
            hi  = dl.level_limit[stn - 1, 0]
            assert lo <= out <= hi, f"St{stn}: 클리핑 실패 {out:.2f}"

    def test_predict_step_zero_q(self, dl, nc_tesr):
        """Q=0 일 때 c_sm 근처 수위 반환."""
        wl_init = float(nc_tesr.wl[5, 1])
        sim = WaterLevelSimulator(dl, nc_tesr.wl, nc_tesr.q_station)
        sm  = dl.get_submodel(1, wl_init)
        _, _, c_sm = dl.get_submodel_params(1, sm)
        out = sim.predict_step(1, 0.0, 0.0, wl_init)
        assert abs(out - c_sm) < 5.0, "Q=0 시 예측값이 c_sm과 너무 다름"
