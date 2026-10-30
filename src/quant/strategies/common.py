"""Helpers that turn daily target series into event-grid decisions + calendar features."""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant.data import futures


def hold_sessions(events: pd.DataFrame, in_set: pd.Series, side: float = 1.0) -> np.ndarray:
    """Be positioned (`side`) from the OPEN of every session in `in_set` to the OPEN of the first
    session after it that is not in the set. Uses only the (deterministic) session calendar."""
    sess = in_set.index
    nxt = pd.Series(in_set.shift(-1).fillna(False).astype(bool).to_numpy(), index=sess)
    return bt.decisions_at_close(events, nxt.astype(float) * side)


def calendar_frame(sessions: pd.DatetimeIndex) -> pd.DataFrame:
    s = pd.DatetimeIndex(sessions)
    df = pd.DataFrame(index=s)
    ym = s.year * 100 + s.month
    df["ym"] = ym
    df["rank_start"] = df.groupby("ym").cumcount() + 1
    df["rank_end"] = df.groupby("ym").cumcount(ascending=False) + 1
    df["dow"] = s.dayofweek
    gaps = pd.Series(s[1:] - s[:-1], index=s[:-1]).dt.days
    # pre-holiday: next session is more than 1 calendar day away and not just a weekend
    nxt_gap = gaps.reindex(s)
    df["pre_holiday"] = ((nxt_gap > 1) & ~((df["dow"] == 4) & (nxt_gap == 3))).fillna(False)
    sched = futures.expiry_schedule(s, s.year.min(), s.year.max())
    exp = pd.DatetimeIndex(sched["expiry"])
    df["is_expiry"] = s.isin(exp)
    # sessions until the next expiry (0 on expiry day)
    pos = np.searchsorted(exp.values, s.values)
    nxt_exp = exp[np.minimum(pos, len(exp) - 1)]
    idx = pd.Series(np.arange(len(s)), index=s)
    df["sess_to_expiry"] = [idx.get(e, np.nan) - i if e in idx.index else np.nan
                            for i, e in zip(range(len(s)), nxt_exp)]
    return df


def vol_scale(ret: pd.Series, target_ann: float, lookback: int = 20, cap: float = 1.0) -> pd.Series:
    """Position multiplier min(cap, target / realised vol) using returns up to and including d."""
    rv = ret.rolling(lookback, min_periods=lookback // 2).std() * np.sqrt(252)
    return (target_ann / rv).clip(upper=cap).fillna(0.0)
