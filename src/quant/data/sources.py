"""Free EOD data downloaders (stooq CSV, bossa.pl metastock zips, NBP API).

All downloads are polite (delay between requests, small retry count) and cached as parquet under data/raw.
Parsers are pure functions so they are unit-testable offline.
"""
from __future__ import annotations

import io
import logging
import time
import zipfile

import pandas as pd
import requests

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (research script; EOD data, low frequency)"
DELAY_S = 2.0


def http_get(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            r.raise_for_status()
            time.sleep(DELAY_S)
            return r.content
        except Exception as e:  # noqa: BLE001 - network errors of any kind are retried
            last = e
            time.sleep(DELAY_S * 2**i)
    raise RuntimeError(f"GET {url} failed: {last}")


# ---------------------------------------------------------------- stooq
STOOQ_COLS = {
    "Date": "date", "Data": "date",
    "Open": "open", "Otwarcie": "open",
    "High": "high", "Najwyzszy": "high",
    "Low": "low", "Najnizszy": "low",
    "Close": "close", "Zamkniecie": "close",
    "Volume": "volume", "Wolumen": "volume",
    "OpenInt": "oi", "LOP": "oi",
}


def parse_stooq_csv(content: bytes) -> pd.DataFrame:
    text = content.decode("utf-8", errors="replace").strip()
    if not text or not (text.startswith("Date") or text.startswith("Data")):
        raise ValueError(f"stooq returned non-CSV payload: {text[:120]!r}")
    df = pd.read_csv(io.StringIO(text)).rename(columns=STOOQ_COLS)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    for c in ["open", "high", "low", "close", "volume", "oi"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df:
        df["volume"] = float("nan")
    return df[[c for c in ["open", "high", "low", "close", "volume", "oi"] if c in df]]


def fetch_stooq(symbol: str, base: str = "https://stooq.pl") -> pd.DataFrame:
    url = f"{base}/q/d/l/?s={symbol}&i=d"
    return parse_stooq_csv(http_get(url))


# ---------------------------------------------------------------- bossa.pl metastock ASCII
def parse_metastock_txt(text: str) -> pd.DataFrame:
    """bossa format: <TICKER>,<DTYYYYMMDD>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>[,<OPENINT>]"""
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df = df.rename(columns={"dtyyyymmdd": "date", "vol": "volume", "openint": "oi"})
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df = df.set_index("date").sort_index()
    keep = [c for c in ["ticker", "open", "high", "low", "close", "volume", "oi"] if c in df]
    return df[keep]


def fetch_bossa_zip(url: str, name_filter: str | None = None) -> dict[str, pd.DataFrame]:
    """Download a bossa metastock zip; returns {file_stem: frame} for members matching name_filter."""
    blob = http_get(url, timeout=300)
    out: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if name_filter and name_filter.upper() not in stem.upper():
                continue
            try:
                out[stem] = parse_metastock_txt(zf.read(name).decode("latin-1"))
            except Exception as e:  # noqa: BLE001
                log.warning("skip %s: %s", name, e)
    return out


# ---------------------------------------------------------------- NBP (official FX fixing ~11:45 CET)
def fetch_nbp_fx(code: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frames = []
    s = pd.Timestamp(start)
    while s <= end:
        e = min(s + pd.Timedelta(days=360), pd.Timestamp(end))
        url = (f"https://api.nbp.pl/api/exchangerates/rates/a/{code}/"
               f"{s:%Y-%m-%d}/{e:%Y-%m-%d}/?format=json")
        try:
            js = pd.read_json(io.BytesIO(http_get(url)))
            rates = pd.DataFrame(list(js["rates"]))
            frames.append(rates.rename(columns={"effectiveDate": "date", "mid": "close"})[["date", "close"]])
        except RuntimeError as err:
            log.warning("NBP %s %s-%s: %s", code, s.date(), e.date(), err)
        s = e + pd.Timedelta(days=1)
    df = pd.concat(frames)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()
