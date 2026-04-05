"""metrics.py — 수위 예측 정확도 지표."""

from __future__ import annotations
import numpy as np


def compute_metrics(
    pred: np.ndarray,
    true: np.ndarray,
) -> dict[str, np.ndarray]:
    """RMSE / MAE / BIAS / NSE 계산.

    Parameters
    ----------
    pred : ndarray, shape (n_station, n_time)
    true : ndarray, shape (n_station, n_time)

    Returns
    -------
    dict with keys: rmse, mae, bias, nse
    """
    err = pred - true
    rmse = np.sqrt(np.mean(err ** 2, axis=-1))
    mae  = np.mean(np.abs(err),       axis=-1)
    bias = np.mean(err,               axis=-1)

    # Nash-Sutcliffe Efficiency
    denom = np.var(true, axis=-1)
    nse   = np.where(denom > 1e-10, 1 - np.mean(err**2, axis=-1) / denom, np.nan)

    return {"rmse": rmse, "mae": mae, "bias": bias, "nse": nse}
