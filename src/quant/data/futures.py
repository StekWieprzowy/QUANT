"""FW20 contract calendar and continuous-series construction.

Rules (GPW): WIG20 futures expire in March/June/September/December on the 3rd Friday of the month;
if that is not a session day, on the preceding session day. Contract codes: FW20{H,M,U,Z}{YY}.

The continuous series holds the front contract and rolls at the CLOSE of the session that is `roll_days`
sessions before expiry. Returns are always computed inside a single contract, so the roll never creates
an artificial jump; the roll itself is flagged so the backtester charges two sides of costs.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

MONTH_CODES = {3: "H", 6: "M", 9: "U", 12: "Z"}
CODE_MONTHS = {v: k for k, v in MONTH_CODES.items()}


def third_friday(year: int, month: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (4 - first.weekday()) % 7  # Friday = 4
    return first + pd.Timedelta(days=offset + 14)


def expiry_date(year: int, month: int, sessions: pd.DatetimeIndex) -> pd.Timestamp:
    """Last session on/before the 3rd Friday (handles holidays such as Good Friday)."""
    tf = third_friday(year, month)
    prior = sessions[sessions <= tf]
    if len(prior) == 0:
        return tf
    return prior[-1]


def contract_code(year: int, month: int, root: str = "FW20") -> str:
    return f"{root}{MONTH_CODES[month]}{year % 100:02d}"


def parse_contract_code(code: str) -> tuple[int, int]:
    """'FW20Z24' / 'FW20Z2024' / 'fw20z24' -> (2024, 12)."""
    m = re.search(r"([HMUZ])(\d{2}|\d{4})$", code.upper())
    if not m:
        raise ValueError(f"cannot parse contract code {code}")
    month = CODE_MONTHS[m.group(1)]
    yy = int(m.group(2))
    year = yy if yy > 1900 else (2000 + yy if yy < 80 else 1900 + yy)
    return year, month


def expiry_schedule(sessions: pd.DatetimeIndex, start_year: int, end_year: int) -> pd.DataFrame:
    rows = []
    for y in range(start_year, end_year + 1):
        for m in (3, 6, 9, 12):
            rows.append({"contract": contract_code(y, m), "year": y, "month": m,
                         "expiry": expiry_date(y, m, sessions)})
    return pd.DataFrame(rows).sort_values("expiry").reset_index(drop=True)


def roll_dates(sessions: pd.DatetimeIndex, schedule: pd.DataFrame, roll_days: int) -> pd.Series:
    """Map contract -> session at whose close we roll OUT of that contract."""
    sess = pd.DatetimeIndex(sessions).sort_values()
    out = {}
    for _, r in schedule.iterrows():
        pos = sess.searchsorted(r["expiry"])
        if pos >= len(sess) or sess[pos] != r["expiry"]:
            pos = min(pos, len(sess) - 1)
        out[r["contract"]] = sess[max(pos - roll_days, 0)]
    return pd.Series(out)


def build_continuous(contracts: dict[str, pd.DataFrame], sessions: pd.DatetimeIndex,
                     roll_days: int = 5) -> pd.DataFrame:
    """Build a daily continuous front-month frame.

    contracts: {code: DataFrame[open, high, low, close, volume, (oi)]} indexed by date.
    Output columns: contract, open, high, low, close, prev_close (same contract, previous session),
    roll_at_close (bool), volume, oi.
    """
    sessions = pd.DatetimeIndex(sessions).sort_values()
    norm = {}
    for code, df in contracts.items():
        y, m = parse_contract_code(code)
        norm[contract_code(y, m)] = df.sort_index()
    years = sorted({parse_contract_code(c)[0] for c in norm})
    sched = expiry_schedule(sessions, years[0], years[-1])
    sched = sched[sched["contract"].isin(norm)].reset_index(drop=True)
    rolls = roll_dates(sessions, sched, roll_days)

    # contract held during each session = first contract whose roll date >= session
    held = pd.Series(index=sessions, dtype=object)
    prev_roll = pd.Timestamp.min
    for _, r in sched.iterrows():
        rd = rolls[r["contract"]]
        mask = (sessions > prev_roll) & (sessions <= rd)
        held[mask] = r["contract"]
        prev_roll = rd
    held = held.dropna()

    rows = []
    for d, code in held.items():
        df = norm[code]
        if d not in df.index:
            rows.append({"date": d, "contract": code, "missing": True})
            continue
        bar = df.loc[d]
        prev = df.loc[df.index < d]
        prev_close = prev["close"].iloc[-1] if len(prev) else np.nan
        rows.append({"date": d, "contract": code, "open": bar["open"], "high": bar.get("high", np.nan),
                     "low": bar.get("low", np.nan), "close": bar["close"], "prev_close": prev_close,
                     "volume": bar.get("volume", np.nan), "oi": bar.get("oi", np.nan),
                     "roll_at_close": d == rolls[code], "missing": False})
    out = pd.DataFrame(rows).set_index("date")
    out["roll_at_close"] = out["roll_at_close"].fillna(False).astype(bool)
    return out


def continuous_excess_index(cont: pd.DataFrame) -> pd.Series:
    """Ratio-chained price index of the continuous futures (no roll jumps); for signal computation."""
    r = cont["close"] / cont["prev_close"] - 1.0
    return (1.0 + r.fillna(0.0)).cumprod() * 1000.0
