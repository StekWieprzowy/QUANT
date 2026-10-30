"""Empirical look-ahead detector for catalog strategies.

Perturb one piece of information that becomes known at a given event (open of T, close of T, foreign closes
dated T) and recompute the strategy's decisions. Every decision placed at an event BEFORE the perturbed
information became available must be bit-for-bit unchanged. Catches mis-aligned features such as using
today's return to trade today (bug found in L2, see research/03).
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config, research, validation


def _decisions(variant: str, daily: pd.DataFrame, params: dict) -> dict[str, pd.DataFrame]:
    """Per instrument: frame [date, phase, dec] (decisions forward-filled)."""
    from quant.strategies import catalog

    events = bt.events_from_daily(daily, costs=config.BASE_FUT_COSTS)
    sp = catalog.build(variant, daily, events)
    book = validation.as_book(sp.events)
    out = {}
    for k, v in validation.as_dec(sp.fn(params)).items():
        ev = book.events[k]
        out[k] = pd.DataFrame({"date": pd.DatetimeIndex(ev["date"]), "phase": ev["phase"].to_numpy(),
                               "dec": pd.Series(v).ffill().fillna(0.0).to_numpy()})
    return out


@contextmanager
def _patched_foreign(date: pd.Timestamp, factor: float):
    orig_y, orig_n = research.load_yahoo, research.load_nbp

    def bump(df):
        df = df.copy()
        m = df.index == date
        for c in ("open", "high", "low", "close", "adjclose"):
            if c in df:
                df.loc[m, c] = df.loc[m, c] * factor
        return df

    research.load_yahoo = lambda s: bump(orig_y(s))
    research.load_nbp = lambda c: bump(orig_n(c))
    try:
        yield
    finally:
        research.load_yahoo, research.load_nbp = orig_y, orig_n


def _violations(a: dict, b: dict, T: pd.Timestamp, phase: str) -> list[str]:
    """Decisions placed strictly before event (T, phase) must be identical."""
    bad = []
    for k in a:
        ev = a[k]
        before = (ev["date"] < T) | ((ev["date"] == T) & (phase == "C") & (ev["phase"] == "O"))
        diff = ~np.isclose(a[k]["dec"].to_numpy(), b[k]["dec"].to_numpy(), equal_nan=True) & before.to_numpy()
        if diff.any():
            i = np.flatnonzero(diff)[0]
            bad.append(f"{k}@{ev['date'].iloc[i].date()}{ev['phase'].iloc[i]}")
    return bad


def check(variant: str, daily: pd.DataFrame, params: dict, n_points: int = 4, seed: int = 0) -> list[str]:
    """Returns a list of violations (empty = no look-ahead detected)."""
    rng = np.random.default_rng(seed)
    base = _decisions(variant, daily, params)
    n = len(daily)
    problems = []
    for t in rng.integers(n // 3, n - 5, size=n_points):
        T = daily.index[t]
        # 1) close (and volume / OI, known at the close) of T
        d = daily.copy()
        same = d["contract"].iloc[t + 1] == d["contract"].iloc[t]
        d.iloc[t, d.columns.get_loc("close")] *= 1.05
        d.iloc[t, d.columns.get_loc("high")] = max(d["high"].iloc[t], d["close"].iloc[t])
        for c in ("volume", "oi"):
            d.iloc[t, d.columns.get_loc(c)] *= 1.5
        if same:
            d.iloc[t + 1, d.columns.get_loc("prev_close")] = d["close"].iloc[t]
        v = _violations(base, _decisions(variant, d, params), T, "C")
        if v:
            problems.append(f"{variant}: close of {T.date()} changed earlier decisions {v[:3]}")
        # 2) open of T
        d = daily.copy()
        d.iloc[t, d.columns.get_loc("open")] *= 1.03
        d.iloc[t, d.columns.get_loc("high")] = max(d["high"].iloc[t], d["open"].iloc[t])
        v = _violations(base, _decisions(variant, d, params), T, "O")
        if v:
            problems.append(f"{variant}: open of {T.date()} changed earlier decisions {v[:3]}")
        # 3) foreign closes dated T (US close 22:00 CET > PL close) -> may only affect decisions from C_T on
        with _patched_foreign(T, 1.05):
            v = _violations(base, _decisions(variant, daily, params), T, "C")
        if v:
            problems.append(f"{variant}: foreign data of {T.date()} changed earlier decisions {v[:3]}")
    return problems


def check_features(build_fn, daily: pd.DataFrame, n_points: int = 3, seed: int = 1) -> list[str]:
    """Feature row d is used for the decision at C_d. Perturbing data of session T (open/close) or foreign
    closes dated T must leave rows < T unchanged."""
    rng = np.random.default_rng(seed)
    base = build_fn(daily)
    problems = []
    for t in rng.integers(len(daily) // 3, len(daily) - 5, size=n_points):
        T = daily.index[t]
        variants = {}
        d = daily.copy()
        d.iloc[t, d.columns.get_loc("close")] *= 1.05
        variants["close"] = d
        d = daily.copy()
        d.iloc[t, d.columns.get_loc("open")] *= 1.03
        variants["open"] = d
        for name, dd in variants.items():
            f = build_fn(dd)
            diff = ~np.isclose(base.iloc[:t].to_numpy(dtype=float), f.iloc[:t].to_numpy(dtype=float), equal_nan=True)
            if diff.any():
                cols = base.columns[diff.any(axis=0)].tolist()
                problems.append(f"{name} of {T.date()} changed earlier feature rows: {cols}")
        with _patched_foreign(T, 1.05):
            f = build_fn(daily)
        diff = ~np.isclose(base.iloc[:t].to_numpy(dtype=float), f.iloc[:t].to_numpy(dtype=float), equal_nan=True)
        if diff.any():
            problems.append(f"foreign of {T.date()} changed earlier rows: {base.columns[diff.any(axis=0)].tolist()}")
    return problems
