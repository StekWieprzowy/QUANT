"""GPW official quotation archive (https://www.gpw.pl/archiwum-notowan).

One XLS per (instrument type, session date) with OHLC, volume, number of trades, turnover and open interest
for every instrument of that type. Types used: 1 = indices, 35 = futures, 10 = stocks.

Raw rows are cached per month in data/raw/gpw/t{type}/{YYYY-MM}.parquet. Requests are sequential with a
delay (~1 req/s) - robots.txt allows the archive.
"""
from __future__ import annotations

import io
import logging
import re
import time

import pandas as pd
import requests

from quant import config

log = logging.getLogger(__name__)

URL = "https://www.gpw.pl/archiwum-notowan?fetch=1&type={type}&instrument=&date={date:%d-%m-%Y}"
COLS = {
    "Data": "date", "Nazwa": "name", "ISIN": "isin", "Waluta": "currency", "Kurs otwarcia": "open",
    "Kurs max": "high", "Kurs min": "low", "Kurs zamknięcia": "close", "Zmiana": "chg_pct",
    "Wolumen": "volume", "Liczba Transakcji": "n_trades", "Obrót": "turnover_k",
    "Liczba otwartych pozycji": "oi", "Wartość otwartych pozycji": "oi_value", "Cena nominalna": "nominal",
}
TYPES = {"indices": 1, "stocks": 10, "futures": 35}
DELAY_S = 0.6


def month_path(type_: int, month: pd.Period):
    return config.RAW_DIR / "gpw" / f"t{type_}" / f"{month}.parquet"


def parse_xls(content: bytes) -> pd.DataFrame:
    # non-session days return an HTML page instead of an OLE2 (.xls) workbook
    if len(content) < 600 or not (content[:4] == b"\xd0\xcf\x11\xe0" or content[:2] == b"PK"):
        return pd.DataFrame()
    df = pd.read_excel(io.BytesIO(content))
    if df.empty:
        return df
    df = df.rename(columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_day(session: requests.Session, type_: int, date: pd.Timestamp, retries: int = 4) -> pd.DataFrame:
    for i in range(retries):
        try:
            r = session.get(URL.format(type=type_, date=date), timeout=60)
            r.raise_for_status()
            return parse_xls(r.content)
        except Exception as e:  # noqa: BLE001
            log.warning("gpw t%s %s attempt %d: %s", type_, date.date(), i + 1, e)
            time.sleep(5 * 2**i)
    raise RuntimeError(f"gpw t{type_} {date.date()} failed")


def download_month(session: requests.Session, type_: int, month: pd.Period, force: bool = False) -> int:
    path = month_path(type_, month)
    today = pd.Timestamp.today().normalize()
    complete = month.end_time.normalize() < today - pd.Timedelta(days=3)
    if path.exists() and complete and not force:
        return 0
    days = pd.bdate_range(month.start_time, min(month.end_time.normalize(), today - pd.Timedelta(days=1)))
    frames = []
    for d in days:
        df = fetch_day(session, type_, d)
        if len(df):
            frames.append(df)
        time.sleep(DELAY_S)
    if frames:
        path.parent.mkdir(parents=True, exist_ok=True)
        out = pd.concat(frames, ignore_index=True)
        for c in ["isin", "currency", "name"]:
            out[c] = out[c].astype(str)
        out.to_parquet(path)
    return len(days)


def load_type(type_: int) -> pd.DataFrame:
    files = sorted((config.RAW_DIR / "gpw" / f"t{type_}").glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no GPW t{type_} data - run scripts/refresh_gpw.py")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


# ------------------------------------------------------------------ FW20 naming
_FW20 = re.compile(r"^FW20([HMUZ])(\d+)$")


def fw20_contract(name: str, trade_date: pd.Timestamp) -> tuple[int, int] | None:
    """GPW names: FW20H5 (2005), FW20H10 (2010), FW20H2220 (2022, multiplier-20 series) ...
    The year is resolved as the first year >= trade year whose last digits match."""
    m = _FW20.match(str(name).strip().upper())
    if not m:
        return None
    month = {"H": 3, "M": 6, "U": 9, "Z": 12}[m.group(1)]
    digits = m.group(2)
    candidates = [digits]
    if len(digits) == 4:
        candidates = [digits[:2]]
    elif len(digits) == 3:
        candidates = [digits[:1], digits[:2]]
    for y in range(trade_date.year, trade_date.year + 4):
        for c in candidates:
            if str(y).endswith(c) and (y > trade_date.year or month >= trade_date.month):
                return y, month
    return None
