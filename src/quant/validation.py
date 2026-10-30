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


def as_book(events) -> bt.Book:
    return events if isinstance(events, bt.Book) else bt.Book({"main": events})


def as_dec(d) -> dict[str, np.ndarray]:
    return d if isinstance(d, dict) else {"main": np.asarray(d, dtype=float)}


def walk_forward(events, decision_fn: DecisionFn, grid: list[dict], first_test_year: int,
                 min_train_years: int = 3, cost_mult: float = 1.0, select: str = "sharpe") -> dict:
    """Expanding-window walk-forward: for each test year choose params by net Sharpe on all prior data,
    stitch the chosen decisions for that year (per instrument), then run ONE backtest over the stitched
    decisions (so position transitions at year boundaries are charged correctly).

    `events` is an event grid (single instrument) or a backtest.Book; decision_fn returns an array or a
    dict of arrays respectively."""
    book = as_book(events)
    # forward-fill "hold" NaNs per param BEFORE stitching, otherwise NaN->0 would flatten every open
    cache = {i: {k: pd.Series(v).ffill().fillna(0.0).to_numpy() for k, v in as_dec(decision_fn(p)).items()}
             for i, p in enumerate(grid)}
    full_runs = {i: bt.run_book(book, d, cost_mult=cost_mult) for i, d in cache.items()}
    all_dates = book.all_dates()
    years = year_slices(all_dates, first_test_year)
    first_year = all_dates.year.min()
    stitched = {k: np.full(len(ev), np.nan) for k, ev in book.events.items()}
    chosen = {}
    for y in years:
        if y - first_year < min_train_years:
            continue
        scores = {}
        for i, res in full_runs.items():
            tr = res.net[res.net.index.year < y]
            scores[i] = sharpe(tr) if select == "sharpe" else tr.mean()
        best = max(scores, key=scores.get)
        chosen[y] = (grid[best], scores[best])
        for k, ev in book.events.items():
            mask = pd.DatetimeIndex(ev["date"]).year == y
            stitched[k][mask] = cache[best][k][mask]
    if not chosen:
        raise ValueError("no OOS years")
    oos_start = pd.Timestamp(year=min(chosen), month=1, day=1)
    dec = {k: np.where(np.isnan(v), 0.0, v) for k, v in stitched.items()}
    res = bt.run_book(book, dec, cost_mult=cost_mult)
    oos_start = res.daily.index[res.daily.index >= oos_start][0]
    return {"result": res, "oos_start": oos_start, "chosen": chosen, "decisions": dec,
            "full_runs": full_runs, "grid": grid, "book": book}


def oos_slice(res, start: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = res.daily.loc[res.daily.index >= start]
    tr = res.trades()
    tr = tr.loc[tr["entry"] >= start] if len(tr) else tr
    return daily, tr


def permutation_test(events, decision, start: pd.Timestamp | None = None, n_perm: int = 500,
                     min_shift: int = 120, cost_mult: float = 1.0, seed: int = SEED) -> dict:
    """Circular-shift test: shifts each instrument's decision series (same shift for all instruments)
    relative to returns, keeping autocorrelation and exposure profile; only the OOS part (>= start) is
    shifted and scored. p = P(shuffled net Sharpe >= actual)."""
    rng = np.random.default_rng(seed)
    book = as_book(events)
    dec = as_dec(decision)
    sub_events, sub_dec = {}, {}
    for k, ev in book.events.items():
        m = np.ones(len(ev), dtype=bool) if start is None else (pd.DatetimeIndex(ev["date"]) >= start)
        sub_events[k] = ev.loc[m].reset_index(drop=True)
        sub_dec[k] = dec[k][m]
    sbook = bt.Book(sub_events, book.weights, book.borrow_annual, book.borrow_on_abs)
    actual = sharpe(bt.run_book(sbook, sub_dec, cost_mult).net)
    n = min(len(v) for v in sub_dec.values())
    hi = max(n // 2 - min_shift // 2, min_shift // 2 + 1)
    shifts = rng.integers(min_shift // 2, hi, size=n_perm) * 2  # even -> keep open/close phase
    null = np.array([sharpe(bt.run_book(sbook, {k: np.roll(v, s) for k, v in sub_dec.items()}, cost_mult).net)
                     for s in shifts])
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
