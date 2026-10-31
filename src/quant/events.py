"""Event-study toolkit (phase 2 / part 3).

* Day 0 = first session on/after the event date (or the next session if the event is known only after
  the close, `after_close=True`).
* Abnormal returns: market model r_i = a + b r_m estimated on [-250, -21] before day 0 (log returns);
  if no market series is given, raw returns are used (index-level events).
* For every window we report N, mean CAR, median, std, t-stat, two-sided p (t-test), a bootstrap 95% CI
  of the mean and the hit rate (share of events with CAR of the hypothesised sign).
Every tested (event, window) is logged to hypotheses_log.csv (family "event_*", stage "event");
Benjamini-Hochberg is applied across all of them at the end of part 3.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from quant import config, registry


def day0_positions(sessions: pd.DatetimeIndex, dates, after_close: bool = False) -> np.ndarray:
    s = pd.DatetimeIndex(sessions)
    d = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    pos = s.searchsorted(d, side="right" if after_close else "left")
    return pos


def abnormal(ret: pd.Series, market: pd.Series | None, p0: int, est=(-250, -21), min_obs: int = 60) -> pd.Series | None:
    if market is None:
        return ret
    lo, hi = max(p0 + est[0], 0), p0 + est[1]
    y, x = ret.iloc[lo:hi], market.iloc[lo:hi]
    ok = y.notna() & x.notna()
    if ok.sum() < min_obs:
        return None
    b, a = np.polyfit(x[ok], y[ok], 1)
    return ret - (a + b * market)


def car_table(ret: pd.Series, dates, windows: dict[str, tuple[int, int]], market: pd.Series | None = None,
              after_close: bool = False, labels=None) -> pd.DataFrame:
    """ret/market: daily log returns on the same session index. Returns one row per event."""
    idx = ret.index
    if market is not None:
        market = market.reindex(idx)
    rows = []
    for j, p0 in enumerate(day0_positions(idx, dates, after_close)):
        if p0 >= len(idx):
            continue
        ar = abnormal(ret, market, p0)
        if ar is None:
            continue
        row = {"event_date": pd.Timestamp(list(dates)[j]), "day0": idx[p0]}
        if labels is not None:
            row["label"] = list(labels)[j]
        for w, (a, b) in windows.items():
            lo, hi = p0 + a, p0 + b
            row[w] = float(ar.iloc[lo:hi + 1].sum()) if lo >= 0 and hi < len(idx) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


@dataclass
class Summary:
    n: int
    mean: float
    median: float
    std: float
    t: float
    p: float
    ci_lo: float
    ci_hi: float
    hit: float

    def as_dict(self):
        return self.__dict__


def summarize(x: pd.Series, sign: int = 1, n_boot: int = 5000, seed: int = config.SEED) -> Summary:
    v = pd.Series(x).dropna().to_numpy(float)
    n = len(v)
    if n < 2:
        return Summary(n, float(v.mean()) if n else np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)
    t, p = stats.ttest_1samp(v, 0.0)
    rng = np.random.default_rng(seed)
    bs = rng.choice(v, size=(n_boot, n), replace=True).mean(axis=1)
    return Summary(n, float(v.mean()), float(np.median(v)), float(v.std(ddof=1)), float(t), float(p),
                   float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975)), float((np.sign(v) == sign).mean()))


def log_event(family: str, hypothesis: str, window: str, s: Summary, sample: tuple, notes: str = "") -> str:
    stats_ = {"start": str(pd.Timestamp(sample[0]).date()), "end": str(pd.Timestamp(sample[1]).date()),
              "n_days": None, "n_trades": s.n, "sharpe": None, "ann_ret": s.mean, "p_value": s.p}
    return registry.log(family, hypothesis, window, {"window": window}, "event", stats_,
                        verdict="", notes=(f"mean={s.mean:+.4f} CI95=[{s.ci_lo:+.4f},{s.ci_hi:+.4f}] "
                                           f"t={s.t:.2f} hit={s.hit:.2f} | " + notes)[:900])
