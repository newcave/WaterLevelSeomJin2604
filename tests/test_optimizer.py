"""tests/test_optimizer.py — FlowOptimizer 단위 테스트"""
import pytest
import numpy as np
from waterlevel_sim import FlowOptimizer, WaterLevelSimulator
from waterlevel_sim.npz_loader import load_demo


class TestFlowOptimizerGlobal:
    @pytest.fixture
    def opt_global(self, dl, nc_tesr):
        opt = FlowOptimizer(dl, nc_tesr.wl, nc_tesr.q_station)
        return opt.optimize("global", verbose=False)

    def test_rmse_improves(self, opt_global, sim_result):
        assert opt_global.rmse_opt <= sim_result.rmse_mean + 0.01

    def test_scale_uniform(self, opt_global):
        scales = np.atleast_1d(opt_global.scales)
        assert np.allclose(scales, scales[0])

    def test_improvement_nonnegative(self, opt_global):
        assert opt_global.improvement >= -1.0


class TestFlowOptimizerPerStation:
    @pytest.fixture(scope="class")
    def opt_ps(self, dl, nc_tesr):
        opt = FlowOptimizer(dl, nc_tesr.wl, nc_tesr.q_station)
        return opt.optimize("per_station", verbose=False)

    def test_rmse_significantly_improves(self, opt_ps, sim_result):
        improvement_pct = (1 - opt_ps.rmse_opt / sim_result.rmse_mean) * 100
        assert improvement_pct >= 50.0, f"개선율 {improvement_pct:.1f}% < 50%"

    def test_scales_count(self, opt_ps):
        from waterlevel_sim.data_library import N_STATION
        assert len(opt_ps.scales) == N_STATION

    def test_scales_positive(self, opt_ps):
        assert (np.array(opt_ps.scales) > 0).all()

    def test_scales_in_bounds(self, opt_ps):
        scales = np.array(opt_ps.scales)
        assert scales.min() > 0.01
        assert scales.max() < 10.0

    def test_q_optimized_shape(self, opt_ps, nc_tesr):
        assert opt_ps.q_optimized.shape == nc_tesr.q_station.shape

    def test_summary_string(self, opt_ps):
        s = opt_ps.summary()
        assert "per_station" in s
        assert "RMSE" in s

    def test_sim_result_attached(self, opt_ps):
        assert opt_ps.sim_result is not None
        assert hasattr(opt_ps.sim_result, "rmse")


class TestFlowOptimizerMultiEvent:
    @pytest.mark.parametrize("event", ["tesr", "tesr2", "tesr3"])
    def test_per_station_all_events(self, event, dl):
        nc  = load_demo(event)
        r0  = WaterLevelSimulator(dl, nc.wl, nc.q_station).run()
        opt = FlowOptimizer(dl, nc.wl, nc.q_station)
        rp  = opt.optimize("per_station", verbose=False)
        improvement = (1 - rp.rmse_opt / r0.rmse_mean) * 100
        assert improvement >= 40.0, f"{event}: 개선율 {improvement:.1f}% < 40%"

    def test_event3_beats_exe_rmse(self, dl):
        nc  = load_demo("tesr3")
        opt = FlowOptimizer(dl, nc.wl, nc.q_station)
        rp  = opt.optimize("per_station", verbose=False)
        assert rp.rmse_opt < 2.0, f"Event3 RMSE={rp.rmse_opt:.3f}m > 2.0m"


class TestFlowOptimizerInvalidMode:
    def test_invalid_mode_raises(self, dl, nc_tesr):
        opt = FlowOptimizer(dl, nc_tesr.wl, nc_tesr.q_station)
        with pytest.raises(ValueError, match="Unknown mode"):
            opt.optimize("invalid_xyz")
