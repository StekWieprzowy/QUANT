"""FW20 single-instrument strategy signals.

Conventions:
* `daily` = continuous FW20 frame (quant.data.futures.build_continuous) restricted to the research period.
* functions return a DAILY target series; `*_close` targets are computed with info up to the close of d
  (+ foreign closes of d) and executed at O_{d+1} via backtest.decisions_at_close; `*_intraday` targets use
  info available before the open of d and are held O_d -> C_d via backtest.decisions_intraday.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant.data.futures import continuous_excess_index
from quant.strategies.common import calendar_frame


class FW20Signals:
    def __init__(self, daily: pd.DataFrame):
        self.d = daily
        self.idx = continuous_excess_index(daily)  # close-based, roll-free
        self.ret = np.log(self.idx).diff().fillna(0.0)
        self.cal = calendar_frame(daily.index)
        self.on_ret = np.log(daily["open"] / daily["prev_close"]).fillna(0.0)  # overnight (gap)
        self.id_ret = np.log(daily["close"] / daily["open"]).fillna(0.0)  # intraday

    # ---------------- calendar
    def tom_set(self, k_end: int, n_start: int) -> pd.Series:
        return (self.cal["rank_end"] <= k_end) | (self.cal["rank_start"] <= n_start)

    def pre_holiday_set(self) -> pd.Series:
        return self.cal["pre_holiday"].astype(bool)

    # ---------------- trend / momentum (close-based, executed next open)
    def tsmom_close(self, lookback: int, long_only: bool = False) -> pd.Series:
        s = np.sign(self.ret.rolling(lookback, min_periods=lookback).sum()).fillna(0.0)
        return s.clip(lower=0) if long_only else s

    def ma_filter_close(self, lookback: int, long_only: bool = True) -> pd.Series:
        ma = self.idx.rolling(lookback, min_periods=lookback).mean()
        s = pd.Series(np.where(self.idx > ma, 1.0, -1.0), index=self.idx.index).where(ma.notna(), 0.0)
        return s.clip(lower=0) if long_only else s

    # ---------------- short-term mean reversion
    def reversal_close(self, k: int, z: float, hold: int, vol_lb: int = 60) -> pd.Series:
        """After a k-day move larger than z sigma, bet on reversal for `hold` sessions."""
        rk = self.ret.rolling(k).sum()
        sd = self.ret.rolling(vol_lb, min_periods=vol_lb // 2).std() * np.sqrt(k)
        trig = pd.Series(np.where(rk > z * sd, -1.0, np.where(rk < -z * sd, 1.0, 0.0)), index=rk.index)
        return hold_signal(trig, hold)

    def rsi2_dip_close(self, rsi_th: float, trend_lb: int = 200, exit_ma: int = 5) -> pd.Series:
        """Long-only: buy when RSI(2) < rsi_th and above the trend MA; exit when close > MA(exit_ma)."""
        rsi = rsi_wilder(self.idx, 2)
        trend = self.idx > self.idx.rolling(trend_lb, min_periods=trend_lb).mean()
        exit_ok = self.idx > self.idx.rolling(exit_ma).mean()
        pos = np.zeros(len(rsi))
        cur = 0.0
        for i in range(len(rsi)):
            if cur == 0 and rsi.iloc[i] < rsi_th and trend.iloc[i]:
                cur = 1.0
            elif cur == 1 and exit_ok.iloc[i]:
                cur = 0.0
            pos[i] = cur
        return pd.Series(pos, index=rsi.index)


def hold_signal(trigger: pd.Series, hold: int) -> pd.Series:
    """Turn sparse triggers (+1/-1/0) into positions held for `hold` sessions (new trigger resets)."""
    t = trigger.to_numpy()
    pos = np.zeros(len(t))
    cur, left = 0.0, 0
    for i, x in enumerate(t):
        if x != 0:
            cur, left = x, hold
        if left > 0:
            pos[i] = cur
            left -= 1
        else:
            cur = 0.0
    return pd.Series(pos, index=trigger.index)


def rsi_wilder(px: pd.Series, n: int) -> pd.Series:
    d = px.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)
