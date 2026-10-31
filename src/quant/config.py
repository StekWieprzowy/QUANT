"""Project-wide constants. HOLDOUT_START is pre-committed (see research/00_plan.md) - do not change."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
HOLDOUT_DIR = ROOT / "holdout"
HYPOTHESES_LOG = ROOT / "hypotheses_log.csv"

SEED = 20261030
TRADING_DAYS = 252

# --- Pre-committed split (decided before any data was downloaded) ---
RESEARCH_START = pd.Timestamp("2005-01-01")
HOLDOUT_START = pd.Timestamp("2022-07-01")

# phase 1: 200 (128 used); phase 2 (user instruction 2026-10-31): +40 cost attack, +60 events -> 228
HYPOTHESIS_BUDGET = 228


@dataclass(frozen=True)
class FuturesCosts:
    """Per-side cost model for FW20 (conservative base case)."""

    multiplier: float = 20.0  # PLN per index point
    commission_pln: float = 10.0  # per contract per side
    slippage_points: float = 1.5  # half-spread + slippage per side, in index points

    def per_side_points(self) -> float:
        return self.slippage_points + self.commission_pln / self.multiplier

    def scaled(self, k: float) -> "FuturesCosts":
        return FuturesCosts(self.multiplier, self.commission_pln * k, self.slippage_points * k)


@dataclass(frozen=True)
class StockCosts:
    commission_frac: float = 0.0029  # per side
    slippage_frac: float = 0.0010  # per side (half-spread + impact)
    borrow_annual: float = 0.03  # short borrow cost p.a.

    def per_side_frac(self) -> float:
        return self.commission_frac + self.slippage_frac

    def scaled(self, k: float) -> "StockCosts":
        return StockCosts(self.commission_frac * k, self.slippage_frac * k, self.borrow_annual * k)


BASE_FUT_COSTS = FuturesCosts()
BASE_STOCK_COSTS = StockCosts()


# Approx. annual average NBP reference rate (%), public RPP decision history; used as PLN cash/financing
# proxy (+FUNDING_SPREAD) for long stock legs hedged with FW20 (futures embed r - q, so a hedged long stock
# position otherwise books the cash rate as alpha). 2026 is an estimate. NBP site is behind a bot wall,
# hence a hand-entered table (year granularity is sufficient for a carry correction).
NBP_REF_RATE = {2005: 5.3, 2006: 4.1, 2007: 4.6, 2008: 5.8, 2009: 3.7, 2010: 3.5, 2011: 4.3, 2012: 4.6,
                2013: 2.9, 2014: 2.4, 2015: 1.6, 2016: 1.5, 2017: 1.5, 2018: 1.5, 2019: 1.5, 2020: 0.6,
                2021: 0.3, 2022: 5.2, 2023: 6.6, 2024: 5.75, 2025: 5.1, 2026: 4.25}
FUNDING_SPREAD = 0.25


def pln_rate(dates) -> "pd.Series":
    idx = pd.DatetimeIndex(dates)
    return pd.Series([(NBP_REF_RATE.get(y, 4.0) + FUNDING_SPREAD) / 100 for y in idx.year], index=idx)
