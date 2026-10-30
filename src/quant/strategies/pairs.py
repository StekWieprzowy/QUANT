"""Pairs / relative-value on WIG20 stocks (dividend-adjusted Yahoo prices).

A pair instrument = long 1 PLN of A and short 1 PLN of B (dollar neutral, rebalanced daily, approximation).
Per-side cost of a 1-unit spread trade = both legs' costs. Borrow is charged on |position| (one leg is
always short).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config

PAIRS = [("PKO", "PEO"), ("PKO", "MBK"), ("PEO", "MBK"), ("BHW", "ING"), ("MIL", "MBK"),
         ("PGE", "TPE"), ("PGE", "ENA"), ("TPE", "ENA")]


ISIN = {"PKO": "PLPKO0000016", "PEO": "PLPEKAO00016", "KGH": "PLKGHM000017", "PKN": "PLPKN0000018",
        "MBK": "PLBRE0000012", "OPL": "PLTLKPL00017", "PZU": "PLPZU0000011", "PGE": "PLPGER000010",
        "TPE": "PLTAURN00011", "LPP": "PLLPP0000011", "CDR": "PLOPTTC00011", "ACP": "PLSOFTB00016",
        "CPS": "PLCFRPT00013", "JSW": "PLJSW0000015", "BHW": "PLBH00000012", "ALR": "PLALIOR00045",
        "MIL": "PLBIG0000016", "ENA": "PLENEA000013", "ING": "PLBSK0000017"}


def gpw_spot_fix(ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    """Replace Yahoo open/high/low with the official GPW values on the days where some stock gapped >10%
    (data/raw/gpw/t10_spot.parquet, fetched by scripts/fix_stock_gaps.py). Scaled by Yahoo's split factor."""
    path = config.RAW_DIR / "gpw" / "t10_spot.parquet"
    if ticker not in ISIN or not path.exists():
        return df
    spot = pd.read_parquet(path)
    spot = spot[spot["isin"] == ISIN[ticker]].set_index("date")
    df = df.copy()
    for d, row in spot.iterrows():
        if d in df.index and row["close"] > 0 and row["open"] > 0:
            k = df.at[d, "close"] / row["close"]
            for c in ("open", "high", "low"):
                df.at[d, c] = row[c] * k
    return df


def adjusted_stock(ticker: str) -> pd.DataFrame:
    from quant import research  # research-truncated unless the one-shot holdout was unlocked

    df = research.load_yahoo(f"{ticker}.WA")
    df = df[df.index >= config.RESEARCH_START]
    # Yahoo carries GPW holidays as zero-volume rows with bogus prices (e.g. ING 2013-08-15) -> drop
    df = df[df["volume"] > 0]
    df = gpw_spot_fix(ticker, df)
    f = (df["adjclose"] / df["close"]).where(lambda x: x > 0)
    out = pd.DataFrame({"open": df["open"] * f, "close": df["adjclose"]}, index=df.index)
    # Yahoo sometimes carries no-trade days with volume 0 / open 0 -> open missing
    out.loc[~(df["open"] > 0), "open"] = np.nan
    # bad opening ticks: outside [low, high] (ACP 2012-10-18 open=4626) or a >25% spike that fully reverts
    # intraday (CDR 2006-08-29) -> treat open as unknown (engine then uses prev close: zero overnight leg)
    pc = df["close"].shift(1)
    g, i = np.log(df["open"] / pc), np.log(df["close"] / df["open"])
    bad = (df["open"] > df["high"] * 1.001) | (df["open"] < df["low"] * 0.999) | \
          ((g.abs() > 0.25) & (i.abs() > 0.25) & (np.sign(g) != np.sign(i)))
    out.loc[bad, "open"] = np.nan
    return out.dropna(subset=["close"])


def pair_events(a: str, b: str, costs=config.BASE_STOCK_COSTS) -> tuple[pd.DataFrame, pd.DataFrame]:
    A, B = adjusted_stock(a), adjusted_stock(b)
    idx = A.index.intersection(B.index)
    A, B = A.loc[idx], B.loc[idx]
    oA = A["open"].fillna(A["close"].shift(1))
    oB = B["open"].fillna(B["close"].shift(1))
    n = len(idx)
    ret = np.zeros(2 * n)
    ret[0::2] = ((oA / A["close"].shift(1) - 1) - (oB / B["close"].shift(1) - 1)).fillna(0).to_numpy()
    ret[1::2] = ((A["close"] / oA - 1) - (B["close"] / oB - 1)).fillna(0).to_numpy()
    ev = pd.DataFrame({"date": np.repeat(idx.values, 2), "phase": np.tile(["O", "C"], n), "ret": ret,
                       "price": 1.0, "cost_frac": 2 * costs.per_side_frac(), "roll": False})
    spread = np.log(A["close"]) - np.log(B["close"])
    return ev, pd.DataFrame({"spread": spread})


def zscore_positions(spread: pd.Series, lookback: int, z_in: float, z_out: float, max_hold: int) -> pd.Series:
    m = spread.rolling(lookback, min_periods=lookback).mean()
    sd = spread.rolling(lookback, min_periods=lookback).std()
    z = ((spread - m) / sd).to_numpy()
    pos = np.zeros(len(z))
    cur, held = 0.0, 0
    for i, zi in enumerate(z):
        if np.isnan(zi):
            cur, held = 0.0, 0
        elif cur == 0.0:
            if zi > z_in:
                cur, held = -1.0, 0
            elif zi < -z_in:
                cur, held = 1.0, 0
        else:
            held += 1
            if abs(zi) < z_out or held >= max_hold or np.sign(zi) == cur:  # reverted / timeout / crossed
                cur, held = 0.0, 0
        pos[i] = cur
    return pd.Series(pos, index=spread.index)


def build_book(pairs=PAIRS, costs=config.BASE_STOCK_COSTS):
    events, spreads = {}, {}
    for a, b in pairs:
        ev, sp = pair_events(a, b, costs)
        events[f"{a}-{b}"] = ev
        spreads[f"{a}-{b}"] = sp["spread"]
    book = bt.Book(events, borrow_annual=costs.borrow_annual, borrow_on_abs=True)
    return book, spreads


def decision_fn_factory(book: bt.Book, spreads: dict[str, pd.Series]):
    def fn(p: dict) -> dict[str, np.ndarray]:
        out = {}
        for k, ev in book.events.items():
            pos = zscore_positions(spreads[k], p["lookback"], p["z_in"], p.get("z_out", 0.5),
                                   p.get("max_hold", p["lookback"]))
            out[k] = bt.decisions_at_close(ev, pos)
        return out
    return fn
