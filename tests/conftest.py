"""conftest.py — pytest 공용 픽스처"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import numpy as np
from waterlevel_sim import DataLibrary, WaterLevelSimulator
from waterlevel_sim.npz_loader import load_demo

DATA_DIR  = ROOT / "data"
PARAM_CSV = DATA_DIR / "ParamSetforcxx.csv"


@pytest.fixture(scope="session")
def dl():
    """DataLibrary 픽스처 (세션 범위 — 전체 테스트 한 번만 로드)."""
    return DataLibrary(str(PARAM_CSV))


@pytest.fixture(scope="session")
def nc_tesr():
    """tesr 데모 데이터 픽스처."""
    return load_demo("tesr")


@pytest.fixture(scope="session")
def sim_result(dl, nc_tesr):
    """베이스라인 시뮬레이션 결과 픽스처."""
    sim = WaterLevelSimulator(dl, nc_tesr.wl, nc_tesr.q_station)
    return sim.run()
