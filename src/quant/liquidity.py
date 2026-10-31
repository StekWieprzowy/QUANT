"""Liquidity / effective-spread estimates from daily OHLC (no quote data available).

Abdi & Ranaldo (2017): s^2 = 4 * E[(c_t - eta_t) * (c_t - eta_{t+1})], eta = mid-range log price,
c = log close. Estimated over rolling windows; negative moment -> 0. Returns the FULL relative spread
(half-spread = s/2 is the cost of crossing once vs mid).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def abdi_ranaldo(df: pd.DataFrame, window: int = 63, min_periods: int = 40) -> pd.Series:
    c = np.log(df["close"])
    eta = (np.log(df["high"]) + np.log(df["low"])) / 2
    m = (c - eta) * (c - eta.shift(-1))
    # value at t uses eta_{t+1}: shift the product forward one day so the estimate is causal
    m = m.shift(1)
    s2 = 4 * m.rolling(window, min_periods=min_periods).mean()
    return np.sqrt(s2.clip(lower=0))


def turnover_pln(df: pd.DataFrame, window: int = 60) -> pd.Series:
    """Trailing average daily traded value (close * volume), causal (known at close)."""
    return (df["close"] * df["volume"]).rolling(window, min_periods=window // 2).mean()
