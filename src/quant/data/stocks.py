"""Official GPW stock panel (all listed shares incl. later delisted ones) from the daily archive (type 10).

* ret      : GPW 'Zmiana' (% vs the reference price) / 100 -> adjusted for dividends, splits and rights issues
             (verified: Handlowy ex-div 2016-07-01 raw -4.95% vs 'Zmiana' +1.69%; CI Games 10:1 split
             2017-02-23 raw -90% vs -0.71%).
* turnover : PLN value traded (turnover_k * 1000)
* adv      : median turnover over the previous 60 sessions (known before the session)
* vol      : std of ret over the previous 60 sessions
Indexed by ISIN (stable across name changes); `names` maps ISIN -> last GPW short name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant import config
from quant.data import gpw, store

FIELDS = ("open", "close", "ret", "turnover", "adv", "vol")


def build_panel() -> dict[str, pd.DataFrame]:
    raw = gpw.load_type(gpw.TYPES["stocks"])
    raw = raw[raw["currency"].isin(["PLN", "nan"])]
    for c in ("open", "close", "chg_pct", "volume", "turnover_k"):
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    raw = raw.drop_duplicates(["date", "isin"], keep="last")
    piv = {k: raw.pivot(index="date", columns="isin", values=v).sort_index()
           for k, v in [("open", "open"), ("close", "close"), ("chg", "chg_pct"), ("turnover", "turnover_k")]}
    close = piv["close"].where(piv["close"] > 0)
    opn = piv["open"].where(piv["open"] > 0)
    ret = piv["chg"] / 100.0
    ret = ret.where(close.notna())
    # GPW reports 0 change for days without trades; extreme values (>+-60%) are almost always reference
    # resets after suspensions -> treat as missing rather than as a return
    ret = ret.where(ret.abs() <= 0.6)
    turnover = piv["turnover"] * 1000.0
    adv = turnover.rolling(60, min_periods=20).median().shift(1)
    vol = ret.rolling(60, min_periods=20).std().shift(1)
    out = {"open": opn, "close": close, "ret": ret, "turnover": turnover, "adv": adv, "vol": vol}
    names = raw.sort_values("date").groupby("isin")["name"].last()
    for k, v in out.items():
        store.save(v, store.processed_path(f"stocks_{k}"))
    store.save(names.to_frame("name"), store.processed_path("stocks_names"))
    return out


def load_panel(research_only: bool = True) -> dict[str, pd.DataFrame]:
    from quant import research

    full = research._FULL_ACCESS or not research_only
    load = store.load_processed_full if full else store.load_processed_research
    return {k: load(f"stocks_{k}") for k in FIELDS}


def names() -> pd.Series:
    return pd.read_parquet(store.processed_path("stocks_names"))["name"]


def membership(index: str, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Boolean (sessions x ISIN): member of `index` after the latest revision effective BEFORE the session
    (a revision on Friday r applies from the next session)."""
    port = pd.read_csv(config.RAW_DIR / "events" / f"{index.lower()}_portfolios.csv", parse_dates=["revision"])
    revs = sorted(port["revision"].unique())
    sess = pd.DatetimeIndex(sessions)
    m = pd.DataFrame(False, index=sess, columns=sorted(port["isin"].unique()))
    for i, r in enumerate(revs):
        nxt = revs[i + 1] if i + 1 < len(revs) else pd.Timestamp("2100-01-01")
        rows = (sess > r) & (sess <= nxt)
        m.loc[rows, list(port.loc[port["revision"] == r, "isin"])] = True
    return m
