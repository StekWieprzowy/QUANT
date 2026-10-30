"""Family G: relative value FW20 vs DAX (both cheap futures).

Spread instrument = long 1 PLN-notional FW20, short beta notional of DAX futures (FDAX/FDXM; the DAX
index from Yahoo is used as price proxy - DAX is a total-return index, so the dividend part of FDAX
carry is ignored; Euro funding drift is small vs the 1-3 week holding periods tested).
Calendar = sessions where both GPW and Xetra traded; FW20 returns over skipped PL sessions are compounded
in, so nothing is lost.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config, research
from quant.data.futures import continuous_excess_index

FDAX_COST_PER_SIDE = 0.0003  # 3 bps: 1 pt on ~15k + commission, conservative for FDXM


def aligned(daily: pd.DataFrame) -> pd.DataFrame:
    dax = research.load_yahoo("^GDAXI")
    dax = dax[(dax["close"] > 0) & (dax["open"] > 0)]
    xi = continuous_excess_index(daily)  # close index of FW20, roll-free
    f_open = xi.shift(1) * daily["open"] / daily["prev_close"]  # open level on the same chained scale
    f_open.iloc[0] = xi.iloc[0] * daily["open"].iloc[0] / daily["close"].iloc[0]
    idx = daily.index.intersection(pd.DatetimeIndex(dax.index))
    rolls = daily["roll_at_close"].astype(int).cumsum()
    out = pd.DataFrame({"f_close": xi.reindex(idx), "f_open": f_open.reindex(idx),
                        "d_close": dax["close"].reindex(idx), "d_open": dax["open"].reindex(idx),
                        "f_price": daily["close"].reindex(idx)}, index=idx)
    r = rolls.reindex(idx)
    out["roll_at_close"] = r.diff().fillna(0) > 0  # roll at or since previous common session
    return out


def spread_events(a: pd.DataFrame, beta_lb: int = 250, fut_costs=config.BASE_FUT_COSTS):
    rf = np.log(a["f_close"]).diff()
    rd = np.log(a["d_close"]).diff()
    beta = (rf.rolling(beta_lb, min_periods=120).cov(rd) / rd.rolling(beta_lb, min_periods=120).var())
    beta = beta.clip(0.3, 1.5).shift(1).fillna(0.8)
    n = len(a)
    ret = np.zeros(2 * n)
    ret[0::2] = ((a["f_open"] / a["f_close"].shift(1) - 1) - beta * (a["d_open"] / a["d_close"].shift(1) - 1)).fillna(0)
    ret[1::2] = ((a["f_close"] / a["f_open"] - 1) - beta * (a["d_close"] / a["d_open"] - 1)).fillna(0)
    f_side = (fut_costs.per_side_points() / a["f_price"]).to_numpy()
    cost = np.repeat(f_side + beta.to_numpy() * FDAX_COST_PER_SIDE, 2)
    roll = np.zeros(2 * n, dtype=bool)
    roll[1::2] = a["roll_at_close"].to_numpy(dtype=bool)
    cost[1::2] = np.where(roll[1::2], f_side, cost[1::2])  # only the FW20 leg rolls (FDAX roll ignored: ~1bp)
    ev = pd.DataFrame({"date": np.repeat(a.index.values, 2), "phase": np.tile(["O", "C"], n), "ret": ret,
                       "price": 1.0, "cost_frac": cost, "roll": roll})
    resid = (rf - beta * rd).fillna(0.0)
    return ev, resid


def residual_z(resid: pd.Series, k: int, vol_lb: int = 60) -> pd.Series:
    sd = resid.rolling(vol_lb, min_periods=vol_lb // 2).std() * np.sqrt(k)
    return resid.rolling(k).sum() / sd


def reversion_positions(z: pd.Series, z_in: float, z_exit: float, max_hold: int) -> pd.Series:
    """Symmetric: short the spread when z > z_in, long when z < -z_in; exit at |z|<z_exit, cross or timeout."""
    zz = z.to_numpy()
    pos = np.zeros(len(zz))
    cur, held = 0.0, 0
    for i, x in enumerate(zz):
        if np.isnan(x):
            cur, held = 0.0, 0
        elif cur == 0.0:
            if x > z_in:
                cur, held = -1.0, 0
            elif x < -z_in:
                cur, held = 1.0, 0
        else:
            held += 1
            if abs(x) < z_exit or np.sign(x) == cur or held >= max_hold:
                cur, held = 0.0, 0
        pos[i] = cur
    return pd.Series(pos, index=z.index)
