"""Family R: short-term reversal of a stock's residual (idiosyncratic) move vs the index.

Instrument per stock = long 1 PLN of the stock, short beta PLN of FW20 (hedge rebalanced daily with the
lagged rolling beta). Long-only on the stock (no borrow), hedge in the cheap future.
Costs per side: stock 0.29%+0.10% + beta * FW20 per-side cost; FW20 roll charged on the hedge leg only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config
from quant.strategies.pairs import adjusted_stock

UNIVERSE = ["PKO", "PEO", "KGH", "PKN", "MBK", "OPL", "PZU", "PGE", "TPE", "LPP", "CDR", "ACP", "CPS", "JSW",
            "BHW", "ALR", "MIL", "ENA"]


def stock_hedged_events(ticker: str, fw: pd.DataFrame, beta_lb: int = 250,
                        stock_costs=config.BASE_STOCK_COSTS, fut_costs=config.BASE_FUT_COSTS):
    S = adjusted_stock(ticker)
    idx = S.index.intersection(fw.index)
    S, F = S.loc[idx], fw.loc[idx]
    rs = np.log(S["close"]).diff()
    # FW20 close-to-close within the held contract
    rf = np.log(F["close"] / F["prev_close"])
    # FW20 prev_close is only valid if the previous session in this (intersected) index is the previous
    # FW20 session; Yahoo gaps are rare - treat returns spanning a gap as missing
    full_prev = fw.index.to_series().shift(1).reindex(idx)
    gap = full_prev != idx.to_series().shift(1)
    rf[gap] = np.nan
    rs[gap] = np.nan
    beta = (rs.rolling(beta_lb, min_periods=120).cov(rf) / rf.rolling(beta_lb, min_periods=120).var())
    beta = beta.clip(0.3, 1.5).shift(1).fillna(1.0)  # known before the day starts
    oS = S["open"].fillna(S["close"].shift(1))
    n = len(idx)
    ret = np.zeros(2 * n)
    # cash financing of the long stock notional, charged on the overnight leg (futures leg embeds r - q,
    # so without this the hedged position would book the PLN cash rate as alpha)
    fin = config.pln_rate(idx) / 252
    ret[0::2] = ((oS / S["close"].shift(1) - 1) - beta * (F["open"] / F["prev_close"] - 1) - fin).fillna(0).to_numpy()
    ret[1::2] = ((S["close"] / oS - 1) - beta * (F["close"] / F["open"] - 1)).fillna(0).to_numpy()
    fut_side = fut_costs.per_side_points() / F["close"]
    cost = np.empty(2 * n)
    cost[0::2] = (stock_costs.per_side_frac() + beta * fut_side).to_numpy()
    cost[1::2] = cost[0::2]
    roll = np.zeros(2 * n, dtype=bool)
    roll[1::2] = F["roll_at_close"].to_numpy(dtype=bool)
    # on roll events the engine charges (|before|+|after|) * cost_frac; only the hedge leg rolls
    cost[1::2] = np.where(roll[1::2], (beta * fut_side).to_numpy(), cost[1::2])
    ev = pd.DataFrame({"date": np.repeat(idx.values, 2), "phase": np.tile(["O", "C"], n), "ret": ret,
                       "price": 1.0, "cost_frac": cost, "roll": roll})
    resid = (rs - beta * rf).fillna(0.0)
    return ev, resid


def reversal_positions(resid: pd.Series, k: int, z_in: float, z_exit: float = 0.5, max_hold: int = 10,
                       vol_lb: int = 60, allow_entry: pd.Series | None = None) -> pd.Series:
    cum = resid.rolling(k).sum()
    sd = resid.rolling(vol_lb, min_periods=vol_lb // 2).std() * np.sqrt(k)
    z = (cum / sd).to_numpy()
    ok = np.ones(len(z), dtype=bool) if allow_entry is None else \
        allow_entry.reindex(resid.index).ffill().fillna(False).to_numpy(dtype=bool)
    pos = np.zeros(len(z))
    cur, held = 0.0, 0
    for i, zi in enumerate(z):
        if np.isnan(zi):
            cur, held = 0.0, 0
        elif cur == 0.0:
            if zi < -z_in and ok[i]:
                cur, held = 1.0, 0
        else:
            held += 1
            if zi > -z_exit or held >= max_hold:
                cur, held = 0.0, 0
        pos[i] = cur
    return pd.Series(pos, index=resid.index)


def build_book(fw: pd.DataFrame, universe=UNIVERSE):
    events, resids = {}, {}
    for t in universe:
        ev, r = stock_hedged_events(t, fw)
        events[t], resids[t] = ev, r
    return bt.Book(events), resids


def decision_fn_factory(book: bt.Book, resids: dict[str, pd.Series], allow_entry: pd.Series | None = None):
    def fn(p: dict) -> dict[str, np.ndarray]:
        return {k: bt.decisions_at_close(ev, reversal_positions(resids[k], p["k"], p["z_in"],
                                                                  max_hold=p.get("max_hold", 10),
                                                                  allow_entry=allow_entry))
                for k, ev in book.events.items()}
    return fn
