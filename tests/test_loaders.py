"""tests/test_loaders.py — NCReader / NPZLoader 단위 테스트"""
import pytest
import numpy as np
from pathlib import Path
from waterlevel_sim.npz_loader import NPZData, load_demo, available_demos
from waterlevel_sim.data_library import N_BP

DATA_DIR = Path(__file__).parent.parent / "data"


class TestNPZLoader:
    """NPZData 및 load_demo 테스트."""

    def test_available_demos(self):
        demos = available_demos()
        assert len(demos) >= 1
        assert "tesr" in demos

    def test_load_demo_tesr(self):
        nc = load_demo("tesr")
        assert isinstance(nc, NPZData)

    def test_wl_shape(self, nc_tesr):
        """WL 배열: (n_time, 22)"""
        assert nc_tesr.wl.ndim == 2
        assert nc_tesr.wl.shape[1] == N_BP

    def test_q_station_shape(self, nc_tesr):
        """Q_station 배열: WL과 동일 형상"""
        assert nc_tesr.q_station.shape == nc_tesr.wl.shape

    def test_q_in_shape(self, nc_tesr):
        """Q_in 배열: (n_bc, 22)"""
        assert nc_tesr.q_in.ndim == 2
        assert nc_tesr.q_in.shape[1] == N_BP

    def test_q_in_timesteps_leq_wl(self, nc_tesr):
        """경계 유량 타임스텝 ≤ 출력 타임스텝."""
        assert nc_tesr.q_in.shape[0] <= nc_tesr.n_time

    def test_dt_sec_positive(self, nc_tesr):
        assert nc_tesr.dt_sec > 0

    def test_wl_dtype_float64(self, nc_tesr):
        """수치 연산용 float64 타입."""
        assert nc_tesr.wl.dtype == np.float64

    def test_q_mostly_nonnegative(self, nc_tesr):
        """Q_station 대부분 양수 (HEC-RAS 역방향 흐름 허용 — 최하류 소수)."""
        neg_ratio = (nc_tesr.q_station < 0).mean()
        assert neg_ratio < 0.05, f"음수 유량 비율 {neg_ratio:.1%} > 5%"

    def test_wl_physically_reasonable(self, nc_tesr):
        """수위가 물리적 범위 내 (−50m ~ 500m)."""
        assert nc_tesr.wl.min() > -50
        assert nc_tesr.wl.max() < 500

    def test_start_date_format(self, nc_tesr):
        """시작일 형식: YYYY-MM-DD"""
        assert len(nc_tesr.start_date) >= 10
        assert nc_tesr.start_date[4] == "-"

    def test_summary_string(self, nc_tesr):
        s = nc_tesr.summary()
        assert "NPZ" in s
        assert "WL" in s

    def test_load_missing_event(self):
        with pytest.raises(FileNotFoundError):
            load_demo("nonexistent_event_xyz")

    @pytest.mark.parametrize("event", ["tesr", "tesr2", "tesr3"])
    def test_all_events_loadable(self, event):
        """모든 데모 이벤트가 로드 가능."""
        nc = load_demo(event)
        assert nc.n_time > 0
        assert nc.wl.shape[1] == N_BP
