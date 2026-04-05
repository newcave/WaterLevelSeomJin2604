"""tests/test_routing_metrics.py — FlowRouter·metrics 단위 테스트"""
import pytest
import numpy as np
from waterlevel_sim import FlowRouter
from waterlevel_sim.metrics import compute_metrics
from waterlevel_sim.data_library import N_BP, N_STATION


class TestFlowRouter:
    """FlowRouter 테스트."""

    @pytest.fixture(scope="class")
    def router(self, dl, nc_tesr):
        r = FlowRouter(dl, nc_tesr.q_in, nc_tesr.q_station)
        r.calibrate(t_steady=5)
        return r

    def test_calibrate_sets_flag(self, router):
        assert router.is_calibrated is True

    def test_rmse_finite(self, router):
        assert np.isfinite(router.rmse)

    def test_alpha_in_range(self, router):
        """alpha는 [0, 1) 범위."""
        assert (router.alpha[1:N_STATION+1] >= 0).all()
        assert (router.alpha[1:N_STATION+1] < 1).all()

    def test_ratio_positive(self, router):
        """ratio는 양수여야 함."""
        assert (router.ratio[1:N_STATION+1] > 0).all()

    def test_route_output_shape(self, router, nc_tesr):
        q_routed = router.route(nc_tesr.q_in, n_out=nc_tesr.n_time)
        assert q_routed.shape == (nc_tesr.n_time, N_BP)

    def test_route_nonnegative(self, router, nc_tesr):
        """라우팅 결과 유량은 음수 없음."""
        q_routed = router.route(nc_tesr.q_in, n_out=20)
        assert (q_routed >= 0).all()

    def test_summary_string(self, router):
        s = router.summary()
        assert "FlowRouter" in s
        assert "alpha" in s

    def test_uncalibrated_raises(self, dl, nc_tesr):
        """캘리브레이션 전 route() 호출은 허용 (파라미터 기본값 사용)."""
        r = FlowRouter(dl, nc_tesr.q_in)
        q = r.route(nc_tesr.q_in, n_out=10)
        assert q.shape == (10, N_BP)


class TestMetrics:
    """metrics.compute_metrics 테스트."""

    def test_perfect_prediction(self):
        """완벽 예측 시 RMSE=0, NSE=1."""
        pred = np.random.rand(5, 100)
        true = pred.copy()
        m = compute_metrics(pred, true)
        np.testing.assert_allclose(m["rmse"], 0.0, atol=1e-10)
        np.testing.assert_allclose(m["mae"],  0.0, atol=1e-10)
        np.testing.assert_allclose(m["bias"], 0.0, atol=1e-10)
        np.testing.assert_allclose(m["nse"],  1.0, atol=1e-10)

    def test_constant_bias(self):
        """상수 편향 시 BIAS = 편향 값."""
        true = np.ones((3, 50)) * 10.0
        pred = true + 2.0   # +2m 편향
        m = compute_metrics(pred, true)
        np.testing.assert_allclose(m["bias"], 2.0, atol=1e-10)
        np.testing.assert_allclose(m["rmse"], 2.0, atol=1e-10)
        np.testing.assert_allclose(m["mae"],  2.0, atol=1e-10)

    def test_rmse_nonnegative(self):
        pred = np.random.rand(4, 60)
        true = np.random.rand(4, 60)
        m = compute_metrics(pred, true)
        assert (m["rmse"] >= 0).all()

    def test_output_shapes(self):
        n_stn, n_t = 7, 80
        pred = np.random.rand(n_stn, n_t)
        true = np.random.rand(n_stn, n_t)
        m = compute_metrics(pred, true)
        for key in ("rmse", "mae", "bias", "nse"):
            assert m[key].shape == (n_stn,)

    def test_nse_worst_case(self):
        """예측이 평균과 같을 때 NSE=0."""
        true = np.random.rand(2, 100) + 5.0
        pred = np.tile(true.mean(axis=1, keepdims=True), (1, 100))
        m = compute_metrics(pred, true)
        np.testing.assert_allclose(m["nse"], 0.0, atol=1e-8)

    def test_with_sim_result(self, sim_result):
        """실제 시뮬레이션 결과로 메트릭 계산."""
        m = compute_metrics(sim_result.wl_pred, sim_result.wl_true)
        assert m["rmse"].shape == (N_STATION,)
        assert (m["rmse"] >= 0).all()
        np.testing.assert_allclose(m["rmse"], sim_result.rmse, atol=1e-6)
