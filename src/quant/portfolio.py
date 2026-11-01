"""Phase 3: weekly multi-stock portfolio backtester with the pre-registered liquidity-dependent cost model
(research/09_phase3_preregistration.md).

Timing: target weights are decided with data up to the CLOSE of the decision session (last session of the
week) and executed at the OPEN of the next session. Between rebalances weights drift with prices.
The engine is long/short in stocks plus an FW20 beta hedge; all quantities are fractions of equity.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant import config

CAPITAL_PLN = 2_000_000.0


@dataclass(frozen=True)
class CostModel:
    commission: float = 0.0029
    slippage_fixed: float = 0.0005
    borrow_annual: float = 0.03
    min_adv: float = 0.5e6
    short_min_adv: float = 10e6
    capital: float = CAPITAL_PLN
    # (ADV lower bound in PLN, half-spread)
    spread_tiers: tuple = ((50e6, 0.0005), (10e6, 0.0010), (2e6, 0.0020), (0.5e6, 0.0040))

    def half_spread(self, adv: np.ndarray) -> np.ndarray:
        out = np.full(np.shape(adv), np.nan)
        for lo, hs in reversed(self.spread_tiers):  # ascending lower bounds; higher tiers overwrite
            out = np.where(adv >= lo, hs, out)
        return out

    def per_side(self, trade_frac: np.ndarray, adv: np.ndarray, vol: np.ndarray, equity_mult: float = 1.0) -> np.ndarray:
        """Cost as fraction of traded value. trade_frac = |dw| (fraction of equity)."""
        value = np.abs(trade_frac) * self.capital * equity_mult
        impact = np.nan_to_num(vol) * np.sqrt(value / np.maximum(adv, 1.0))
        return self.commission + np.nan_to_num(self.half_spread(adv), nan=0.01) + self.slippage_fixed + impact


@dataclass
class PortfolioResult:
    daily: pd.DataFrame  # gross, cost, net, turnover, n_orders, long, short, hedge
    weights: pd.DataFrame  # post-trade weights on execution days


def rebalance_days(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last session of each ISO week (calendar known in advance)."""
    s = pd.DatetimeIndex(sessions)
    iso = s.isocalendar()
    key = (iso["year"] * 100 + iso["week"]).to_numpy()
    last = np.r_[key[1:] != key[:-1], True]
    return s[last]


def run(targets: pd.DataFrame, px: dict[str, pd.DataFrame], fw: pd.DataFrame, beta: pd.DataFrame,
        costs: CostModel = CostModel(), band: float = 0.005, cost_mult: float = 1.0,
        hedge: bool = True) -> PortfolioResult:
    """targets: index = decision dates, columns = tickers, target weights (NaN = 0).
    px: {'open','close','ret','adv','vol'} DataFrames (dates x tickers); ret = adjusted close-to-close.
    fw: FW20 continuous frame (open, close, prev_close, roll_at_close). beta: dates x tickers (lagged)."""
    sess = px["close"].index
    cols = px["close"].columns
    targets = targets.reindex(columns=cols).fillna(0.0)
    o, c, r = px["open"].to_numpy(), px["close"].to_numpy(), px["ret"].to_numpy()
    pc_adj = c / (1 + np.nan_to_num(r))
    r_on = np.nan_to_num(o / pc_adj - 1)
    r_id = np.nan_to_num(c / o - 1)
    has_open = np.isfinite(o) & np.isfinite(c)
    r_on = np.where(has_open, r_on, np.nan_to_num(r))
    r_id = np.where(has_open, r_id, 0.0)
    adv, vol = px["adv"].to_numpy(), px["vol"].to_numpy()
    F = fw.reindex(sess)
    f_on = np.nan_to_num((F["open"] / F["prev_close"] - 1).to_numpy())
    f_id = np.nan_to_num((F["close"] / F["open"] - 1).to_numpy())
    f_cost = (config.BASE_FUT_COSTS.per_side_points() / F["close"]).ffill().to_numpy()
    f_roll = F["roll_at_close"].fillna(False).to_numpy(bool)
    rate = config.pln_rate(sess).to_numpy() / 252
    B = beta.reindex(index=sess, columns=cols).ffill().fillna(1.0).to_numpy()
    exec_map = {}
    for d in targets.index:
        p = sess.searchsorted(d, side="right")  # next session after the decision close
        if p < len(sess):
            exec_map[p] = targets.loc[d].to_numpy()
    n, m = len(sess), len(cols)
    w = np.zeros(m)
    h = 0.0
    rows, wrec = [], {}
    for t in range(n):
        # overnight leg with pre-trade weights
        g_on = w @ r_on[t] + h * f_on[t]
        w = w * (1 + r_on[t])
        h = h * (1 + f_on[t])
        eq = 1 + g_on
        w, h = w / eq, h / eq
        cost = 0.0
        turn, n_orders = 0.0, 0
        if t in exec_map:
            tgt = exec_map[t]
            tradable = np.isfinite(o[t]) & (np.nan_to_num(adv[t]) >= costs.min_adv)
            dw = np.where(tradable, tgt - w, 0.0)
            trade = np.abs(dw) > band
            dw = np.where(trade, dw, 0.0)
            per = costs.per_side(dw, adv[t], vol[t]) * cost_mult
            cost += float(np.nansum(np.abs(dw) * per))
            turn += float(np.abs(dw).sum())
            n_orders += int(trade.sum())
            w = w + dw
            new_h = -float(w @ B[t]) if hedge else 0.0
            cost += abs(new_h - h) * f_cost[t] * cost_mult
            h = new_h
            wrec[sess[t]] = w.copy()
        # intraday leg
        g_id = w @ r_id[t] + h * f_id[t]
        w = w * (1 + r_id[t])
        h = h * (1 + f_id[t])
        eq = 1 + g_id
        w, h = w / eq, h / eq
        if f_roll[t]:
            cost += 2 * abs(h) * f_cost[t] * cost_mult
        short = float(-w[w < 0].sum())
        carry = short * costs.borrow_annual / 252 * cost_mult + float(w.sum()) * rate[t]
        gross = (1 + g_on) * (1 + g_id) - 1
        rows.append((sess[t], gross, cost + carry, gross - cost - carry, turn, n_orders, float(w[w > 0].sum()), short, h))
    daily = pd.DataFrame(rows, columns=["date", "gross", "cost", "net", "turnover", "n_orders", "long", "short", "hedge"])
    return PortfolioResult(daily.set_index("date"), pd.DataFrame(wrec, index=cols).T)


def build_weights(score: pd.Series, shortable: pd.Series, cap: float = 0.05, long_only: bool = False) -> pd.Series:
    """Cross-sectional score -> target weights. L/S: w ∝ score, sum|w| = 1, negatives only if shortable.
    Long-only: top tercile, w ∝ score, sum w = 1. Cap |w| <= cap (iterative)."""
    s = score.dropna()
    if s.empty:
        return pd.Series(dtype=float)
    if long_only:
        s = s[s >= s.quantile(2 / 3)]
        s = s - s.min() + 1e-6
    else:
        s = s - s.mean()
        s = s.where((s > 0) | shortable.reindex(s.index).fillna(False), 0.0)
    w = s / s.abs().sum() if s.abs().sum() > 0 else s * 0
    for _ in range(20):
        over = w.abs() > cap
        if not over.any():
            break
        w[over] = np.sign(w[over]) * cap
        free = ~over
        rest = 1.0 - w[over].abs().sum()
        if w[free].abs().sum() > 0:
            w[free] = w[free] / w[free].abs().sum() * rest
    return w


def build_weights_np(score: np.ndarray, shortable: np.ndarray, cap: float = 0.05, long_only: bool = False) -> np.ndarray:
    """numpy version of build_weights (identical logic; NaN score = not held)."""
    w = np.zeros(len(score))
    ok = np.isfinite(score)
    if not ok.any():
        return w
    s = score[ok].astype(float)
    if long_only:
        keep = s >= np.quantile(s, 2 / 3)
        s = np.where(keep, s - s[keep].min() + 1e-6, 0.0)
    else:
        s = s - s.mean()
        s = np.where((s > 0) | shortable[ok], s, 0.0)
    tot = np.abs(s).sum()
    if tot <= 0:
        return w
    x = s / tot
    for _ in range(20):
        over = np.abs(x) > cap
        if not over.any():
            break
        x[over] = np.sign(x[over]) * cap
        free = ~over
        rest = 1.0 - np.abs(x[over]).sum()
        if np.abs(x[free]).sum() > 0:
            x[free] = x[free] / np.abs(x[free]).sum() * rest
    w[ok] = x
    return w
