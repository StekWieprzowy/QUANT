"""Phase 2 / part 1: the same residual mean-reversion signal, implemented with lower turnover / cheaper
execution. No new signals - only *when* and *with what* we trade.

Levers:
* trade_days    : entries/exits only on the last session of each week (or every 2nd week)
* hysteresis    : exit only after the residual has fully reverted (z_exit <= 0) -> longer, fewer trades
* liquid_top_n  : causal universe = top-n stocks by trailing 60d PLN turnover (no future knowledge)
* stock futures : GPW single-stock futures instead of shares (no borrow, no cash financing, own cost model)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config, liquidity, research
from quant.data import futures, gpw
from quant.data.build import ROLL_DAYS
from quant.strategies.pairs import adjusted_stock


# ------------------------------------------------------------------ masks (all causal)
def week_end_mask(index: pd.DatetimeIndex, every: int = 1) -> pd.Series:
    """True on the last session of each ISO week (every=2: of every second week)."""
    idx = pd.DatetimeIndex(index)
    wk = pd.Series(idx.isocalendar().week.to_numpy() + 100 * idx.isocalendar().year.to_numpy(), index=idx)
    last = wk != wk.shift(-1)  # calendar known in advance
    if every > 1:
        n = pd.Series(pd.factorize(wk)[0], index=idx)
        last &= (n % every) == 0
    return last


def liquid_masks(tickers: list[str], n: int) -> dict[str, pd.Series]:
    """Per ticker: True when the stock is in the top-n by trailing 60d turnover (known at close d)."""
    tv = {}
    for t in tickers:
        raw = research.load_yahoo(f"{t}.WA")
        raw = raw[raw["volume"] > 0]
        tv[t] = liquidity.turnover_pln(raw)
    tv = pd.DataFrame(tv)
    rank = tv.rank(axis=1, ascending=False)
    return {t: (rank[t] <= n).fillna(False) for t in tickers}


def positions(z: pd.Series, z_in: float, z_exit: float, max_hold: int, entry_ok: pd.Series | None = None,
              trade_days: pd.Series | None = None, side: str = "long") -> pd.Series:
    """Generic state machine on a z-score. side='long': enter long when z < -z_in, exit when z > -z_exit;
    side='both': symmetric (short when z > z_in). Entries require entry_ok & trade_day; exits happen only on
    trade days, except the max_hold timeout (forced exit on the next trade day)."""
    zz = z.to_numpy()
    idx = z.index
    ok = np.ones(len(zz), bool) if entry_ok is None else entry_ok.reindex(idx).fillna(False).to_numpy(bool)
    td = np.ones(len(zz), bool) if trade_days is None else trade_days.reindex(idx).fillna(False).to_numpy(bool)
    pos = np.zeros(len(zz))
    cur, held = 0.0, 0
    for i, x in enumerate(zz):
        if cur != 0.0:
            held += 1
        if np.isnan(x):
            if td[i]:
                cur, held = 0.0, 0
        elif cur == 0.0:
            if td[i] and ok[i]:
                if x < -z_in:
                    cur, held = 1.0, 0
                elif side == "both" and x > z_in:
                    cur, held = -1.0, 0
        elif td[i] and (cur * x > -z_exit or held >= max_hold):
            # long (cur=1): exit when x > -z_exit; short (cur=-1): exit when x < z_exit
            cur, held = 0.0, 0
        pos[i] = cur
    return pd.Series(pos, index=idx)


def resid_z(resid: pd.Series, k: int, vol_lb: int = 60) -> pd.Series:
    sd = resid.rolling(vol_lb, min_periods=vol_lb // 2).std() * np.sqrt(k)
    return resid.rolling(k).sum() / sd


# ------------------------------------------------------------------ single-stock futures
SSF = {"KGH": "FKGH", "PKO": "FPKO", "PKN": "FPKN", "PZU": "FPZU", "JSW": "FJSW", "CDR": "FCDR",
       "PGE": "FPGE", "TPE": "FTPE", "PEO": "FPEO"}


def ssf_continuous(root: str) -> pd.DataFrame:
    """Continuous front stock-future (quarterly, 3rd Friday, roll ROLL_DAYS sessions before expiry).
    Days without trades in the held contract carry no price (missing) and are flagged non-tradable."""
    raw = gpw.load_type(gpw.TYPES["futures"])
    if research._FULL_ACCESS is False:
        raw = raw[raw["date"] < config.HOLDOUT_START]
    m = raw["name"].str.extract(rf"^{root}([HMUZ])(\d+)$")
    raw = raw[m[0].notna()].copy()
    raw["code"] = [f"FW20{c}{gpw.fw20_contract('FW20' + c + d, dt)[0] % 100:02d}" if gpw.fw20_contract(
        'FW20' + c + d, dt) else None for c, d, dt in zip(m.loc[raw.index, 0], m.loc[raw.index, 1], raw["date"])]
    raw = raw[raw["code"].notna()]
    for c in ("open", "high", "low", "close", "volume", "oi", "n_trades"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
        if c in ("open", "high", "low", "close"):
            raw.loc[raw[c] <= 0, c] = np.nan
    # if a contract had parallel series (e.g. multiplier change), keep the most traded name
    tot = raw.groupby(["code", "name"])["volume"].sum().reset_index()
    keep = set(tot.sort_values("volume").groupby("code").tail(1)["name"])
    raw = raw[raw["name"].isin(keep)]
    frames = {code: g.set_index("date")[["open", "high", "low", "close", "volume", "oi", "n_trades"]]
              for code, g in raw.groupby("code")}
    sessions = pd.DatetimeIndex(sorted(raw["date"].unique()))
    cont = futures.build_continuous({k: v.drop(columns="n_trades") for k, v in frames.items()}, sessions,
                                    roll_days=ROLL_DAYS)
    ntr = pd.Series({(d, c): v for c, f in frames.items() for d, v in f["n_trades"].items()})
    cont["n_trades"] = [ntr.get((d, c), 0) for d, c in zip(cont.index, cont["contract"])]
    cont["tradable"] = (cont["n_trades"] >= 5) & cont["close"].notna() & cont["open"].notna()
    return cont


def ssf_hedged_events(root: str, fw: pd.DataFrame, cost_per_side: float, beta_lb: int = 250,
                      fut_costs=config.BASE_FUT_COSTS):
    """Long 1 notional of the stock future, short beta*FW20. Returns are within-contract for both legs."""
    s = ssf_continuous(root)
    idx = s.index.intersection(fw.index)
    s, F = s.loc[idx], fw.loc[idx]
    close = s["close"].ffill()
    opn = s["open"].fillna(close)
    prev = s["prev_close"].fillna(close.shift(1))
    rs = np.log(close / prev)
    rf = np.log(F["close"] / F["prev_close"])
    beta = (rs.rolling(beta_lb, min_periods=120).cov(rf) / rf.rolling(beta_lb, min_periods=120).var())
    beta = beta.clip(0.3, 1.5).shift(1).fillna(1.0)
    n = len(idx)
    ret = np.zeros(2 * n)
    ret[0::2] = ((opn / prev - 1) - beta * (F["open"] / F["prev_close"] - 1)).fillna(0).to_numpy()
    ret[1::2] = ((close / opn - 1) - beta * (F["close"] / F["open"] - 1)).fillna(0).to_numpy()
    f_side = fut_costs.per_side_points() / F["close"]
    cost = np.repeat((cost_per_side + beta * f_side).to_numpy(), 2)
    roll = np.zeros(2 * n, dtype=bool)
    # both legs roll; stock future rolls at its own roll dates, FW20 at its own -> charge each leg separately
    roll_s = s["roll_at_close"].fillna(False).to_numpy(bool)
    roll_f = F["roll_at_close"].fillna(False).to_numpy(bool)
    roll[1::2] = roll_s | roll_f
    cost[1::2] = np.where(roll_s & roll_f, cost[1::2], np.where(roll_s, cost_per_side, np.where(roll_f, (beta * f_side).to_numpy(), cost[1::2])))
    ev = pd.DataFrame({"date": np.repeat(idx.values, 2), "phase": np.tile(["O", "C"], n), "ret": ret,
                       "price": 1.0, "cost_frac": cost, "roll": roll})
    resid = (rs - beta * rf).fillna(0.0)
    return ev, resid, s["tradable"]
