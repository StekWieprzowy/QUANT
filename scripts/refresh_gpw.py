"""Download GPW daily archive (indices + futures [+ stocks]) month by month.

Usage: python scripts/refresh_gpw.py [--types indices futures stocks] [--start 2005-01] [--force]
Already-complete months are skipped, so the script is incremental (re-run to refresh).
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd
import requests

from quant.data import gpw, sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("refresh_gpw")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", nargs="+", default=["indices", "futures"], choices=list(gpw.TYPES))
    ap.add_argument("--start", default="2005-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = requests.Session()
    s.headers["User-Agent"] = sources.USER_AGENT
    end = pd.Period(a.end or pd.Timestamp.today(), "M")
    for month in pd.period_range(pd.Period(a.start, "M"), end, freq="M"):
        for t in a.types:
            n = gpw.download_month(s, gpw.TYPES[t], month, force=a.force)
            if n:
                log.info("%s %s: %d days requested", t, month, n)


if __name__ == "__main__":
    main()
