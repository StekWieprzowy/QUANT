"""Download / refresh all raw data into data/raw/<source>/*.parquet.

Usage: python scripts/refresh_data.py [--only stooq|bossa|nbp] [--skip-existing]

Sources are tried in order of preference and failures are logged (not fatal), so a partial network
policy still yields whatever is reachable. Completeness of the result is checked by scripts/check_data.py.
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from quant.data import sources, store, universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("refresh")


def stooq_all(skip_existing: bool) -> list[str]:
    failed = []
    groups = [universe.STOOQ_INDICES, universe.STOOQ_FUTURES_CONT, universe.STOOQ_FX_RATES, universe.STOOQ_STOCKS]
    symbols = [s for g in groups for s in g]
    symbols += universe.fw20_contract_symbols(1999, pd.Timestamp.today().year + 1)
    for sym in symbols:
        path = store.raw_path("stooq", sym)
        if skip_existing and path.exists():
            continue
        try:
            df = sources.fetch_stooq(sym)
            store.save(df, path)
            log.info("stooq %-10s %5d rows %s..%s", sym, len(df), df.index[0].date(), df.index[-1].date())
        except Exception as e:  # noqa: BLE001
            failed.append(sym)
            log.warning("stooq %s failed: %s", sym, e)
    return failed


BOSSA_FUT = "https://info.bossa.pl/pub/futures/mstock/mstfut.zip"


def bossa_futures() -> list[str]:
    try:
        frames = sources.fetch_bossa_zip(BOSSA_FUT, name_filter="FW20")
    except Exception as e:  # noqa: BLE001
        log.warning("bossa futures failed: %s", e)
        return ["bossa_fut"]
    for stem, df in frames.items():
        store.save(df.drop(columns=["ticker"], errors="ignore"), store.raw_path("bossa", stem))
    log.info("bossa: %d FW20 files", len(frames))
    return []


def nbp_fx() -> list[str]:
    failed = []
    for code in ["eur", "usd", "chf"]:
        try:
            df = sources.fetch_nbp_fx(code, pd.Timestamp("2002-01-02"), pd.Timestamp.today())
            store.save(df, store.raw_path("nbp", code))
        except Exception as e:  # noqa: BLE001
            failed.append(code)
            log.warning("nbp %s failed: %s", code, e)
    return failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["stooq", "bossa", "nbp"])
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()
    failed = []
    if a.only in (None, "stooq"):
        failed += stooq_all(a.skip_existing)
    if a.only in (None, "bossa"):
        failed += bossa_futures()
    if a.only in (None, "nbp"):
        failed += nbp_fx()
    log.info("done; %d failures: %s", len(failed), failed[:30])
    return 0


if __name__ == "__main__":
    sys.exit(main())
