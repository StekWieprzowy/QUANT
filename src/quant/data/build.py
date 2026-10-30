"""Build processed datasets from raw downloads.

fw20_contracts : long table of every FW20 series (GPW archive)
fw20_cont      : continuous front-month FW20 (roll N sessions before expiry), see quant.data.futures
wig20 / wig20tr: index levels (GPW archive)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from quant.data import futures, gpw, store

log = logging.getLogger(__name__)

ROLL_DAYS = 5


def fw20_contracts() -> pd.DataFrame:
    raw = gpw.load_type(gpw.TYPES["futures"])
    raw = raw[raw["name"].str.upper().str.match(r"^FW20[HMUZ]\d+$")].copy()
    ym = [gpw.fw20_contract(n, d) for n, d in zip(raw["name"], raw["date"])]
    raw["year"] = [x[0] if x else np.nan for x in ym]
    raw["month"] = [x[1] if x else np.nan for x in ym]
    bad = raw["year"].isna()
    if bad.any():
        log.warning("unparsed FW20 names: %s", raw.loc[bad, "name"].unique()[:10])
    raw = raw[~bad]
    raw["code"] = [futures.contract_code(int(y), int(m)) for y, m in zip(raw["year"], raw["month"])]
    for c in ["open", "high", "low", "close", "volume", "oi", "n_trades"]:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    # GPW reports 0 for "no trade" OHLC on illiquid back months
    for c in ["open", "high", "low", "close"]:
        raw.loc[raw[c] <= 0, c] = np.nan
    # 2014: GPW listed multiplier-20 series (e.g. FW20H1420) in parallel with the old multiplier-10 ones
    # (FW20H14). Per contract keep the single series with the larger total volume (never mix series).
    tot = raw.groupby(["code", "name"])["volume"].sum().reset_index()
    keep = tot.sort_values("volume").groupby("code").tail(1)["name"]
    dropped = sorted(set(raw["name"]) - set(keep))
    if dropped:
        log.info("dropping parallel FW20 series: %s", dropped)
    raw = raw[raw["name"].isin(set(keep))]
    return raw[["date", "name", "code", "year", "month", "open", "high", "low", "close", "volume", "oi",
                "n_trades"]].sort_values(["date", "code"]).reset_index(drop=True)


def sessions_from(df: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(df["date"].unique()))


def build_fw20(roll_days: int = ROLL_DAYS) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = fw20_contracts()
    sessions = sessions_from(con)
    frames = {code: g.set_index("date")[["open", "high", "low", "close", "volume", "oi"]]
              for code, g in con.groupby("code")}
    cont = futures.build_continuous(frames, sessions, roll_days=roll_days)
    return con, cont


def gpw_index(name: str) -> pd.DataFrame:
    raw = gpw.load_type(gpw.TYPES["indices"])
    df = raw[raw["name"].str.strip() == name].copy()
    df = df.set_index("date").sort_index()[["open", "high", "low", "close", "turnover_k"]]
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df[c] <= 0, c] = np.nan
    df.index.name = "date"
    return df


def build_all() -> dict[str, pd.DataFrame]:
    out = {}
    con, cont = build_fw20()
    out["fw20_contracts"] = con.set_index("date")
    out["fw20_cont"] = cont
    for name, key in [("WIG20", "wig20"), ("WIG20TR", "wig20tr"), ("WIG", "wig"), ("mWIG40", "mwig40")]:
        try:
            out[key] = gpw_index(name)
        except FileNotFoundError:
            log.warning("GPW indices not downloaded yet")
            break
    for k, v in out.items():
        store.save(v, store.processed_path(k))
    return out
