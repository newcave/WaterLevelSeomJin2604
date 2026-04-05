"""npz_loader.py — NPZ 형식 데이터 로더 (GitHub 경량 배포용)

NC 파일 없이도 동작하는 데모 데이터 로더.
NPZ: NC 파일 20MB → 45KB 압축 (GitHub 친화)
"""
from __future__ import annotations
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# tesr_demo.npz에 저장된 배열 구조
# wl        : (241, 22) float32 — BP 22개 수위
# q_station : (241, 22) float32 — BP 22개 단면 유량
# q_in      : (121, 22) float32 — 경계 유입 유량
# dt_sec    : scalar          — 타임스텝 [초]
# start_date: str             — 시작일


class NPZData:
    """NPZ 데이터 컨테이너 — NCReader 호환 인터페이스."""

    def __init__(self, npz_path: str | Path) -> None:
        d = np.load(npz_path, allow_pickle=True)
        self.wl         = d["wl"].astype(np.float64)
        self.q_station  = d["q_station"].astype(np.float64)
        self.q_in       = d["q_in"].astype(np.float64)
        self.dt_sec     = int(d["dt_sec"][0])
        self.start_date = str(d["start_date"][0])
        self.n_time     = self.wl.shape[0]
        self.source     = str(npz_path)

    def summary(self) -> str:
        return (
            f"NPZ 데이터: {Path(self.source).name}\n"
            f"  StartDate  : {self.start_date}\n"
            f"  TimeStep   : {self.dt_sec} s  ({self.dt_sec/60:.0f} min)\n"
            f"  n_time     : {self.n_time} steps\n"
            f"  WL shape   : {self.wl.shape}\n"
            f"  Q_station  : {self.q_station.shape}\n"
            f"  Q_in       : {self.q_in.shape}"
        )


def load_demo(event: str = "tesr") -> NPZData:
    """내장 데모 데이터 로드.

    Parameters
    ----------
    event : str — 'tesr' | 'tesr2' | 'tesr3'
    """
    path = DATA_DIR / f"{event}_demo.npz"
    if not path.exists():
        raise FileNotFoundError(f"데모 데이터 없음: {path}")
    return NPZData(path)


def available_demos() -> list[str]:
    """사용 가능한 데모 이벤트 목록."""
    return sorted(p.stem.replace("_demo", "")
                  for p in DATA_DIR.glob("*_demo.npz"))


def load_uploaded_nc(uploaded_file) -> "NCData":
    """Streamlit 업로드 파일(NC) 로드."""
    import tempfile, os
    from waterlevel_sim.nc_reader import NCReader
    with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    try:
        nc = NCReader(tmp_path)
    finally:
        os.unlink(tmp_path)
    return nc
