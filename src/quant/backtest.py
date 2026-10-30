"""Vectorised event-grid backtester.

Each session d contributes two events: O_d (open) and C_d (close). Event k carries
  ret[k]       return of a +1 notional position over the interval (k-1, k] in the instrument held then
  cost_frac[k] per-side cost (fraction of notional) of trading at event k
  roll[k]      True if a futures roll happens at event k (forced close+reopen = 2 sides on |position|)

A strategy supplies `decision[k]`: target position (notional units, e.g. -1..1) computed with information
available BEFORE event k+1. It is executed at event k+1's price (never at the price it observed), so:

  position held over (k, k+1]  = decision[k-1]   ->  pnl[k+1] = decision[k-1] * ret[k+1]

i.e. the engine shifts decisions by one event. This is the single place where timing is handled; tests in
tests/test_backtest.py check that perturbing future data never changes past PnL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quant.config import FuturesCosts


def events_from_daily(daily: pd.DataFrame, costs: FuturesCosts | None = None,
                      cost_frac_per_side: float | None = None) -> pd.DataFrame:
    """Convert a daily frame [open, close, prev_close, (roll_at_close)] into the event grid.

    prev_close must be the previous close of the SAME instrument/contract held on that day.
    Missing opens are replaced by prev_close (zero overnight return, all of the day in the intraday leg).
    """
    d = daily.copy()
    if "prev_close" not in d:
        d["prev_close"] = d["close"].shift(1)
    if "roll_at_close" not in d:
        d["roll_at_close"] = False
    op = d["open"].where(d["open"] > 0).fillna(d["prev_close"])
    n = len(d)
    dates = np.repeat(d.index.values, 2)
    phase = np.tile(np.array(["O", "C"]), n)
    ret = np.empty(2 * n)
    ret[0::2] = (op / d["prev_close"] - 1.0).to_numpy()
    ret[1::2] = (d["close"] / op - 1.0).to_numpy()
    price = np.empty(2 * n)
    price[0::2] = op.to_numpy()
    price[1::2] = d["close"].to_numpy()
    roll = np.zeros(2 * n, dtype=bool)
    roll[1::2] = d["roll_at_close"].fillna(False).to_numpy(dtype=bool)
    if costs is not None:
        cost = costs.per_side_points() / price
    elif cost_frac_per_side is not None:
        cost = np.full(2 * n, cost_frac_per_side)
    else:
        cost = np.zeros(2 * n)
    ev = pd.DataFrame({"date": dates, "phase": phase, "ret": np.nan_to_num(ret), "price": price,
                       "cost_frac": cost, "roll": roll})
    return ev


@dataclass
class BacktestResult:
    events: pd.DataFrame  # per-event detail
    daily: pd.DataFrame = field(init=False)  # per-session net/gross returns, position, turnover

    def __post_init__(self):
        g = self.events.groupby("date", sort=True)
        self.daily = pd.DataFrame({
            "gross": g["gross"].sum(),
            "cost": g["cost"].sum(),
            "net": g["net"].sum(),
            "turnover": g["turnover"].sum(),
            "pos_close": g["pos"].last(),
        })

    @property
    def net(self) -> pd.Series:
        return self.daily["net"]

    @property
    def gross(self) -> pd.Series:
        return self.daily["gross"]

    def trades(self) -> pd.DataFrame:
        return extract_trades(self.events)


def run(events: pd.DataFrame, decision: pd.Series | np.ndarray, cost_mult: float = 1.0,
        borrow_annual: float = 0.0, borrow_on_abs: bool = False) -> BacktestResult:
    """decision aligned to events (same length / positional). NaN decisions = hold previous decision.
    borrow_on_abs: charge borrow on |position| (spread trades always have a short leg)."""
    dec = pd.Series(np.asarray(decision, dtype=float)).ffill().fillna(0.0).to_numpy()
    pos = np.concatenate([[0.0, 0.0], dec[:-2]]) if len(dec) >= 2 else np.zeros(len(dec))
    # pos[k] = position held over interval (k-1, k]  == decision[k-2]
    # pos_after[k] = position after trading at event k == decision[k-1]
    pos_after = np.concatenate([[0.0], dec[:-1]])
    pos_before = pos  # position going into event k
    ret = events["ret"].to_numpy()
    gross = pos_before * ret
    # Normal event: trade the difference. Roll event: close everything in the old contract and open the
    # new target in the next contract -> |before| + |after|.
    turnover = np.where(events["roll"].to_numpy(),
                        np.abs(pos_before) + np.abs(pos_after),
                        np.abs(pos_after - pos_before))
    cost = turnover * events["cost_frac"].to_numpy() * cost_mult
    if borrow_annual:
        # charge borrow on short exposure for each overnight interval (O events start a new day)
        is_open = (events["phase"].to_numpy() == "O")
        short = np.abs(pos_before) if borrow_on_abs else np.clip(-pos_before, 0, None)
        cost = cost + np.where(is_open, short * borrow_annual / 252.0 * cost_mult, 0.0)
    ev = events.copy()
    ev["pos"] = pos_after
    ev["pos_held"] = pos_before
    ev["gross"] = gross
    ev["turnover"] = turnover
    ev["cost"] = cost
    ev["net"] = gross - cost
    return BacktestResult(ev)


def extract_trades(ev: pd.DataFrame) -> pd.DataFrame:
    """Round trips: a trade starts when position leaves 0 (or flips sign) and ends when it returns to 0/flips.
    PnL is the sum of net event PnL while the trade is open (incl. exit costs)."""
    pos = ev["pos"].to_numpy()
    net = ev["net"].to_numpy()
    sign = np.sign(pos)
    trades = []
    cur = None
    for k in range(len(pos)):
        if cur is not None:
            cur["pnl"] += net[k]
            cur["n_events"] += 1
        prev_sign = sign[k - 1] if k > 0 else 0.0
        if sign[k] != prev_sign:
            if cur is not None:
                cur["exit"] = ev["date"].iloc[k]
                trades.append(cur)
                cur = None
            if sign[k] != 0:
                # on a flip the event's costs were already booked to the closed trade
                cur = {"entry": ev["date"].iloc[k], "side": sign[k],
                       "pnl": net[k] if prev_sign == 0 else 0.0, "n_events": 0}
    if cur is not None:
        cur["exit"] = ev["date"].iloc[-1]
        trades.append(cur)
    return pd.DataFrame(trades, columns=["entry", "exit", "side", "pnl", "n_events"])


# ------------------------------------------------------------------ multi-instrument book
@dataclass
class Book:
    """Several instruments, each with its own event grid, combined with fixed capital weights.
    Portfolio daily return = sum_i w_i * net_i (missing days of an instrument contribute 0)."""

    events: dict[str, pd.DataFrame]
    weights: dict[str, float] | None = None
    borrow_annual: float | dict = 0.0  # scalar or per-instrument dict
    borrow_on_abs: bool | dict = False

    def w(self, name: str) -> float:
        return self.weights[name] if self.weights else 1.0 / len(self.events)

    def all_dates(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(sorted(set().union(*[set(e["date"]) for e in self.events.values()])))


@dataclass
class BookResult:
    parts: dict[str, BacktestResult]
    daily: pd.DataFrame
    weights: dict[str, float]

    @property
    def net(self) -> pd.Series:
        return self.daily["net"]

    @property
    def gross(self) -> pd.Series:
        return self.daily["gross"]

    def trades(self) -> pd.DataFrame:
        frames = []
        for k, r in self.parts.items():
            t = r.trades()
            t["pnl"] = t["pnl"] * self.weights[k]
            t["instrument"] = k
            frames.append(t)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run_book(book: Book, decisions: dict[str, np.ndarray], cost_mult: float = 1.0) -> BookResult:
    def per(attr, k):
        v = getattr(book, attr)
        return v.get(k, 0.0 if attr == "borrow_annual" else False) if isinstance(v, dict) else v

    parts = {k: run(ev, decisions[k], cost_mult, per("borrow_annual", k), per("borrow_on_abs", k))
             for k, ev in book.events.items()}
    idx = book.all_dates()
    cols = ["gross", "cost", "net", "turnover"]
    daily = pd.DataFrame(0.0, index=idx, columns=cols)
    weights = {k: book.w(k) for k in parts}
    for k, r in parts.items():
        daily = daily.add(r.daily[cols].reindex(idx).fillna(0.0) * weights[k])
    daily.index.name = "date"
    return BookResult(parts, daily, weights)


# ------------------------------------------------------------------ helpers to place decisions on the grid
def decisions_at_close(events: pd.DataFrame, daily_target: pd.Series) -> np.ndarray:
    """daily_target[d] computed with info up to close of d (+ anything before next open) -> executed at O_{d+1}.
    Decision is placed on event C_d; the O events carry NaN (=hold)."""
    out = np.full(len(events), np.nan)
    is_c = events["phase"].to_numpy() == "C"
    tgt = daily_target.reindex(pd.DatetimeIndex(events.loc[is_c, "date"])).to_numpy()
    out[is_c] = tgt
    return out


def decisions_intraday(events: pd.DataFrame, daily_target: pd.Series) -> np.ndarray:
    """Hold daily_target[d] only during session d (O_d -> C_d), flat overnight.

    daily_target[d] must use only info available before the open of d. The decision is placed on event
    C_{d-1} (executed at O_d) and a flat decision on O_d (executed at C_d)."""
    out = np.zeros(len(events))
    dates = pd.DatetimeIndex(events["date"])
    tgt = daily_target.reindex(dates).fillna(0.0).to_numpy()
    is_o = events["phase"].to_numpy() == "O"
    # event index of C_{d-1} is (index of O_d) - 1
    idx_o = np.flatnonzero(is_o)
    for i in idx_o:
        if i - 1 >= 0:
            out[i - 1] = tgt[i]
    out[is_o] = 0.0
    return out
