"""nc_reader.py — NetCDF I/O (K-Water HEC-RAS 형식)"""

from __future__ import annotations
import json
import numpy as np
from netCDF4 import Dataset


# 섬진강 BP별 단면(station) 인덱스 매핑 (0-based)
BP_KM = [136.0, 130.4, 128.0, 126.6, 109.2, 108.4, 104.4, 97.8,
         93.2,  89.2,  79.88, 77.8,  74.8,  61.8,  54.6,  53.8,
         47.6,  40.2,  33.5,  24.5,  15.0,  -2.0]

INDEX_STATION = [0, 29, 45, 54, 154, 159, 183, 223, 251, 273,
                 325, 337, 356, 426, 467, 471, 506, 546, 581, 601, 622, 664]


class NCReader:
    """K-Water HEC-RAS NetCDF 파일 리더.

    Parameters
    ----------
    nc_path : str
        .nc 파일 경로

    Attributes
    ----------
    wl : ndarray, shape (n_time, n_bp)
        수위 시계열 [m]  — n_bp = 22
    q_station : ndarray, shape (n_time, n_bp)
        단면 유량 시계열 [m³/s]
    q_in : ndarray, shape (n_time_bc, n_bp)
        경계 유입 유량 [m³/s]
    dt_sec : int
        타임스텝 [초]
    n_time : int
        총 출력 타임스텝 수
    """

    def __init__(self, nc_path: str) -> None:
        self.nc_path = nc_path
        self._load(nc_path)

    # ------------------------------------------------------------------ #
    def _load(self, path: str) -> None:
        nc  = Dataset(path)
        kr  = nc.groups["K-RIVER"]
        pi  = kr.groups["ProjectInfo"]
        out = kr.groups["Output"].groups["Station"]

        # --- 프로젝트 정보 ---
        self.dt_sec     = int(pi.variables["TimeStep"][0])
        self.sim_period = int(pi.variables["SimulationPeriod"][0])
        self.start_date = str(pi.variables["StartDate"][0])

        # --- 출력 수위 / 유량 (전체 단면) ---
        wl_all = np.array(out.variables["WL"][:], dtype=np.float64)   # (n_time, 665)
        q_all  = np.array(out.variables["Q"][:],  dtype=np.float64)

        # BP 22개 지점만 추출
        idx = INDEX_STATION
        self.wl        = wl_all[:, idx]   # (n_time, 22)
        self.q_station = q_all[:, idx]
        self.n_time    = wl_all.shape[0]

        # --- 경계 유입 유량 ---
        self.q_in = self._parse_boundary(kr)

        nc.close()

    def _parse_boundary(self, kr) -> np.ndarray:
        """경계 조건(Boundary) → Q_in 배열 (n_time_bc, 22)."""
        B = kr.groups["Input"].groups["Geo"].variables["Boundary"][:]
        bc: dict[float, list[float]] = {}
        for row in B:
            btype = str(row[2])
            km    = float(str(row[0]).split(";")[2])
            data  = json.loads(str(row[3]))
            keys  = [k for k in data[0] if "Flow" in k or "Stage" in k]
            if keys:
                bc[km] = [d[keys[0]] for d in data]

        n_bc = max(len(v) for v in bc.values())
        q_in = np.zeros((n_bc, 22), dtype=np.float64)
        for i, km in enumerate(BP_KM):
            if km in bc:
                vals = bc[km]
                q_in[:len(vals), i] = vals
        return q_in

    # ------------------------------------------------------------------ #
    def summary(self) -> str:
        lines = [
            f"NetCDF: {self.nc_path}",
            f"  StartDate  : {self.start_date}",
            f"  TimeStep   : {self.dt_sec} s  ({self.dt_sec/60:.0f} min)",
            f"  SimPeriod  : {self.sim_period} s  ({self.sim_period/3600:.1f} h)",
            f"  n_time     : {self.n_time} steps",
            f"  WL shape   : {self.wl.shape}  (time × 22 BP)",
            f"  Q_station  : {self.q_station.shape}",
            f"  Q_in       : {self.q_in.shape}  (boundary conditions)",
        ]
        return "\n".join(lines)
