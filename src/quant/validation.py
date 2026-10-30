"""Walk-forward selection, purged CV, permutation tests and robustness checks."""
from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant.config import SEED
from quant.metrics import sharpe

# A strategy maps (params, context) -> decision array on the event grid (see quant.backtest)
DecisionFn = Callable[[dict], np.ndarray]


def param_grid(grid: dict[str, Iterable]) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*[list(grid[k]) for k in keys])]


def year_slices(dates: pd.DatetimeIndex, first_test_year: int) -> list[int]:
    return [y for y in sorted(set(dates.year)) if y >= first_test_year]


def walk_forward(events: pd.DataFrame, decision_fn: DecisionFn, grid: list[dict], first_test_year: int,
                 min_train_years: int = 3, cost_mult: float = 1.0, select: str = "sharpe") -> dict:
    """Expanding-window walk-forward: for each test year choose params by net Sharpe on all prior data,
    stitch the chosen decisions for that year, then run ONE backtest over the stitched decisions.

    Returns dict with result (BacktestResult restricted to OOS years), chosen params per year and the
    full per-param decisions (cached for neighbourhood analysis)."""
    dates = pd.DatetimeIndex(events["date"])
    cache = {i: decision_fn(p) for i, p in enumerate(grid)}
    full_runs = {i: bt.run(events, d, cost_mult=cost_mult) for i, d in cache.items()}
    years = year_slices(dates, first_test_year)
    stitched = np.full(len(events), np.nan)
    chosen = {}
    first_year = dates.year.min()
    for y in years:
        if y - first_year < min_train_years:
            continue
        scores = {}
        for i, res in full_runs.items():
            tr = res.net[res.net.index.year < y]
            scores[i] = sharpe(tr) if select == "sharpe" else tr.mean()
        best = max(scores, key=scores.get)
        chosen[y] = (grid[best], scores[best])
        mask = dates.year == y
        stitched[mask] = cache[best][mask]
    oos_mask = ~np.isnan(stitched)
    if not oos_mask.any():
        raise ValueError("no OOS years")
    first_oos = np.flatnonzero(oos_mask)[0]
    dec = np.where(oos_mask, stitched, 0.0)
    res = bt.run(events, dec, cost_mult=cost_mult)
    oos_dates = pd.DatetimeIndex(events["date"].iloc[first_oos:].unique())
    return {"result": res, "oos_start": oos_dates[0], "chosen": chosen, "decisions": dec,
            "full_runs": full_runs, "grid": grid}


def oos_slice(res: bt.BacktestResult, start: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = res.daily.loc[res.daily.index >= start]
    tr = res.trades()
    tr = tr.loc[tr["entry"] >= start] if len(tr) else tr
    return daily, tr


def permutation_test(events: pd.DataFrame, decision: np.ndarray, start_idx: int = 0, n_perm: int = 500,
                     min_shift: int = 120, cost_mult: float = 1.0, seed: int = SEED) -> dict:
    """Circular-shift test: shifts the decision series relative to returns, keeping its autocorrelation
    and exposure profile. p = P(shuffled net Sharpe >= actual)."""
    rng = np.random.default_rng(seed)
    dec = np.asarray(decision, dtype=float)
    ev = events.iloc[start_idx:].reset_index(drop=True)
    d = dec[start_idx:]
    actual = sharpe(bt.run(ev, d, cost_mult=cost_mult).net)
    n = len(d)
    # shift by an even number of events so decisions keep their open/close phase
    shifts = rng.integers(min_shift // 2, max(n // 2 - min_shift // 2, min_shift // 2 + 1), size=n_perm) * 2
    null = np.array([sharpe(bt.run(ev, np.roll(d, s), cost_mult=cost_mult).net) for s in shifts])
    p = (1 + np.sum(null >= actual)) / (1 + n_perm)
    return {"actual": actual, "p_value": float(p), "null_mean": float(null.mean()),
            "null_p95": float(np.quantile(null, 0.95))}


def subperiod_sharpes(net: pd.Series, k: int = 3) -> list[float]:
    chunks = np.array_split(net.to_numpy(), k)
    return [sharpe(c) for c in chunks]


def neighbours(params: dict, rel: float = 0.2, keys: Iterable[str] | None = None) -> list[dict]:
    """Each numeric param moved by -rel and +rel (one at a time), ints rounded and kept >=1 and != orig."""
    keys = list(keys) if keys is not None else [k for k, v in params.items()
                                                  if isinstance(v, (int, float)) and not isinstance(v, bool)]
    out = []
    for k in keys:
        v = params[k]
        for f in (1 - rel, 1 + rel):
            nv = v * f
            if isinstance(v, int):
                nv = int(round(nv))
                if nv == v:
                    nv = v + (1 if f > 1 else -1)
                nv = max(nv, 1)
            q = dict(params)
            q[k] = nv
            out.append(q)
    return out


# ------------------------------------------------------------------ purged CV (for ML)
def purged_kfold(t0: pd.DatetimeIndex, t1: pd.DatetimeIndex, n_splits: int = 5,
                 embargo_frac: float = 0.01) -> list[tuple[np.ndarray, np.ndarray]]:
    """Lopez de Prado purged k-fold. t0 = sample (decision) time, t1 = label end time.
    Training samples whose [t0,t1] overlaps the test fold's span are purged; an embargo after the
    test fold removes `embargo_frac` of samples."""
    n = len(t0)
    t0 = pd.DatetimeIndex(t0)
    t1 = pd.DatetimeIndex(t1)
    folds = np.array_split(np.arange(n), n_splits)
    emb = int(np.ceil(n * embargo_frac))
    out = []
    for f in folds:
        test_start, test_end = t0[f[0]], t1[f].max()
        train = np.ones(n, dtype=bool)
        train[f] = False
        overlap = (t0 <= test_end) & (t1 >= test_start)
        train &= ~np.asarray(overlap)
        if emb:
            after = np.arange(f[-1] + 1, min(f[-1] + 1 + emb, n))
            train[after] = False
        out.append((np.flatnonzero(train), f))
    return out
