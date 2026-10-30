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

HYPOTHESIS_BUDGET = 200


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
