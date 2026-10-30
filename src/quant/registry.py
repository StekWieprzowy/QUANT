"""Append-only registry of every tested hypothesis / parameter variant (hypotheses_log.csv)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from quant import config

COLUMNS = ["id", "timestamp", "family", "hypothesis", "variant", "params", "stage", "sample_start",
           "sample_end", "n_days", "n_trades", "sharpe_net", "sharpe_gross", "ann_ret", "mdd", "p_value",
           "dsr", "n_trials_at_test", "verdict", "notes"]


def load() -> pd.DataFrame:
    if config.HYPOTHESES_LOG.exists():
        return pd.read_csv(config.HYPOTHESES_LOG)
    return pd.DataFrame(columns=COLUMNS)


def n_trials() -> int:
    df = load()
    return int((df["stage"] != "holdout").sum()) if len(df) else 0


def trial_sharpes() -> np.ndarray:
    df = load()
    if not len(df):
        return np.array([])
    return df.loc[df["stage"] != "holdout", "sharpe_net"].dropna().to_numpy(dtype=float)


def log(family: str, hypothesis: str, variant: str, params: dict, stage: str, stats: dict,
        verdict: str = "", notes: str = "") -> str:
    df = load()
    hid = f"H{len(df) + 1:03d}"
    if stage != "holdout" and n_trials() >= config.HYPOTHESIS_BUDGET:
        raise RuntimeError("hypothesis budget exhausted - write the final report")
    row = {
        "id": hid,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "family": family, "hypothesis": hypothesis, "variant": variant,
        "params": json.dumps(params, default=str, sort_keys=True), "stage": stage,
        "sample_start": stats.get("start"), "sample_end": stats.get("end"),
        "n_days": stats.get("n_days"), "n_trades": stats.get("n_trades"),
        "sharpe_net": _r(stats.get("sharpe")), "sharpe_gross": _r(stats.get("sharpe_gross")),
        "ann_ret": _r(stats.get("ann_ret")), "mdd": _r(stats.get("mdd")),
        "p_value": _r(stats.get("p_value"), 5), "dsr": _r(stats.get("dsr")),
        "n_trials_at_test": n_trials() + 1, "verdict": verdict, "notes": notes,
    }
    out = pd.concat([df, pd.DataFrame([row], columns=COLUMNS)], ignore_index=True)
    out.to_csv(config.HYPOTHESES_LOG, index=False)
    return hid


def _r(x, nd: int = 4):
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None
