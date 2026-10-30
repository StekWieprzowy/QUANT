"""Fetch the official GPW stock quotes (type 10) for every day on which a universe stock gaps >10% at the
open in the Yahoo data; quant.strategies.pairs.gpw_spot_fix uses them to replace bad Yahoo opens."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import requests

from quant import config
from quant.data import gpw, sources, store
from quant.strategies import pairs, resid


def main() -> None:
    days = set()
    for t in set(resid.UNIVERSE) | {x for p in pairs.PAIRS for x in p}:
        df = store.load_full("yahoo", f"{t}.WA")
        df = df[(df["volume"] > 0) & (df.index >= config.RESEARCH_START)]
        g = np.log(df["open"] / df["close"].shift(1))
        days |= set(df.index[g.abs() > 0.10])
    s = requests.Session()
    s.headers["User-Agent"] = sources.USER_AGENT
    out = []
    for d in sorted(days):
        df = gpw.fetch_day(s, 10, d)
        time.sleep(gpw.DELAY_S)
        if len(df):
            out.append(df)
    spot = pd.concat(out, ignore_index=True)
    for c in ("isin", "currency", "name"):
        spot[c] = spot[c].astype(str)
    spot.to_parquet(config.RAW_DIR / "gpw" / "t10_spot.parquet")
    print(f"{len(days)} days fetched")


if __name__ == "__main__":
    main()
