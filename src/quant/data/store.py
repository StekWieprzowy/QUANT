"""Local parquet storage + the research/holdout firewall.

Every research script must load data through `load_research` / `load_processed_research`, which truncate
at HOLDOUT_START. Full-sample access (`load_full`) is reserved for data refresh, completeness checks and
the one-shot holdout evaluation.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant import config

OHLCV = ["open", "high", "low", "close", "volume"]


def raw_path(source: str, symbol: str) -> Path:
    return config.RAW_DIR / source / f"{symbol.lower().replace('^', 'idx_').replace('.', '_')}.parquet"


def processed_path(name: str) -> Path:
    return config.PROCESSED_DIR / f"{name}.parquet"


def save(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return path


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run scripts/refresh_data.py first")
    df = pd.read_parquet(path)
    df.index = pd.DatetimeIndex(df.index, name="date")
    return df.sort_index()


def truncate_research(df: pd.DataFrame, start: pd.Timestamp | None = None) -> pd.DataFrame:
    """Cut everything on/after HOLDOUT_START. `start` optionally trims the beginning."""
    out = df.loc[df.index < config.HOLDOUT_START]
    if start is not None:
        out = out.loc[out.index >= start]
    return out


def load_research(source: str, symbol: str, start: pd.Timestamp | None = None) -> pd.DataFrame:
    return truncate_research(_read(raw_path(source, symbol)), start)


def load_processed_research(name: str, start: pd.Timestamp | None = None) -> pd.DataFrame:
    return truncate_research(_read(processed_path(name)), start)


def load_full(source: str, symbol: str) -> pd.DataFrame:
    """FULL sample incl. holdout. Only for refresh/completeness checks/holdout runner."""
    return _read(raw_path(source, symbol))


def load_processed_full(name: str) -> pd.DataFrame:
    return _read(processed_path(name))
