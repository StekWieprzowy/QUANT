"""Shared research harness: research-period data loading, feature alignment and the standard evaluation
pipeline (walk-forward OOS + registry logging + DSR + permutation + robustness gate).

Everything here only ever sees data before HOLDOUT_START (via quant.data.store.load_*_research).
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import config, metrics, registry, validation
from quant.data import store

FIRST_TEST_YEAR = 2008  # walk-forward OOS = 2008-01 .. 2022-06 (train starts 2005)

GATE = {  # pre-committed in research/00_plan.md section 5
    "sharpe": 1.0, "dsr": 0.95, "mdd": 0.20, "n_trades": 100, "neighbour_sharpe": 0.7,
    "subperiods_positive": 3, "perm_p": 0.01, "sharpe_2x_costs": 0.5,
}


# ------------------------------------------------------------------ data
def fw20_daily(start: pd.Timestamp = config.RESEARCH_START) -> pd.DataFrame:
    d = store.load_processed_research("fw20_cont", start)
    d = d[~d["missing"].astype(bool)]
    return d


def fw20_events(costs=config.BASE_FUT_COSTS, start: pd.Timestamp = config.RESEARCH_START):
    d = fw20_daily(start)
    return d, bt.events_from_daily(d, costs=costs)


def align_foreign(foreign: pd.DataFrame, sessions: pd.DatetimeIndex, col: str = "close",
                  same_day: bool = True) -> pd.DataFrame:
    """For each PL session d: the foreign value of the last foreign date <= d (same_day=True; usable for
    decisions executed at the NEXT PL open, e.g. US close 22:00 CET) or < d (same_day=False; usable
    intraday on d). Also returns the foreign log-return accrued since the previous PL session's
    information set (0 when the foreign market was closed - no stale double counting)."""
    f = foreign[[col]].dropna().sort_index()
    f = f[f[col] > 0]
    f.index = pd.DatetimeIndex(f.index).astype("datetime64[ns]")
    s = pd.DataFrame(index=pd.DatetimeIndex(sessions, name="date").astype("datetime64[ns]"))
    key = s.index if same_day else s.index - pd.Timedelta(days=1)
    m = pd.merge_asof(pd.DataFrame({"k": key}, index=s.index).sort_values("k"),
                      f.rename(columns={col: "v"}).assign(fdate=f.index),
                      left_on="k", right_index=True, direction="backward")
    m.index = s.index
    out = pd.DataFrame(index=s.index)
    out["value"] = m["v"]
    out["fdate"] = m["fdate"]
    lv = np.log(out["value"])
    out["ret"] = lv.diff().where(out["fdate"] != out["fdate"].shift(1), 0.0)
    return out


def load_yahoo(sym: str) -> pd.DataFrame:
    return store.load_research("yahoo", sym)


def load_nbp(code: str) -> pd.DataFrame:
    return store.load_research("nbp", code)


# ------------------------------------------------------------------ evaluation
@dataclass
class Evaluation:
    name: str
    params: dict
    oos: dict
    gate: dict
    passed: bool
    wf: dict
    hid: str

    def line(self) -> str:
        o = self.oos
        return (f"{self.hid} {self.name:38s} SR={o['sharpe']:+.2f} (gross {o.get('sharpe_gross', 0):+.2f}) "
                f"ret={o['ann_ret']:+.1%} mdd={o['mdd']:.1%} trades={o.get('n_trades', 0)} "
                f"p_perm={o.get('p_value', float('nan')):.3f} DSR={o.get('dsr', float('nan')):.2f} "
                f"{'PASS' if self.passed else 'fail'}")


def _oos_stats(res, start) -> dict:
    daily, tr = validation.oos_slice(res, start)
    return metrics.summary(daily["net"], tr, daily["gross"], daily["turnover"])


def evaluate(family: str, hypothesis: str, events: pd.DataFrame,
             decision_fn: Callable[[dict], np.ndarray], grid: list[dict], notes: str = "",
             robustness: bool = True, n_perm: int = 300, log_screen: bool = True) -> Evaluation:
    """Standard pipeline. Every grid point is logged as a 'screen' trial (in-sample stats on the whole
    research period), the walk-forward result as a 'wf' trial. Full gate is computed only if the OOS
    Sharpe is promising (>0.7), otherwise cheap diagnostics only."""
    wf = validation.walk_forward(events, decision_fn, grid, FIRST_TEST_YEAR)
    if log_screen and len(grid) > 1:
        for p, (i, run) in zip(grid, wf["full_runs"].items()):
            s = metrics.summary(run.net, run.trades(), run.gross)
            registry.log(family, hypothesis, "screen", p, "screen", s, notes="in-sample grid point")
    res = wf["result"]
    start = wf["oos_start"]
    oos = _oos_stats(res, start)
    perm = validation.permutation_test(events, wf["decisions"], start=start, n_perm=n_perm)
    oos["p_value"] = perm["p_value"]
    net = res.daily.loc[res.daily.index >= start, "net"]
    n_trials = registry.n_trials() + 1
    d = metrics.deflated_sharpe(net.to_numpy(), n_trials, registry.trial_sharpes())
    oos["dsr"] = d["dsr"]
    oos["sr0_ann"] = d["sr0_ann"]
    chosen = {str(y): p for y, (p, _) in wf["chosen"].items()}
    last_params = list(wf["chosen"].values())[-1][0] if wf["chosen"] else grid[0]

    gate = {"sharpe": oos["sharpe"] >= GATE["sharpe"], "dsr": oos["dsr"] >= GATE["dsr"],
            "mdd": oos["mdd"] < GATE["mdd"], "n_trades": oos.get("n_trades", 0) >= GATE["n_trades"],
            "perm_p": perm["p_value"] < GATE["perm_p"]}
    sub = validation.subperiod_sharpes(net, 3)
    oos["subperiod_sharpes"] = [round(x, 2) for x in sub]
    gate["subperiods"] = sum(x > 0 for x in sub) >= GATE["subperiods_positive"]
    if robustness and oos["sharpe"] > 0.7:
        book = wf["book"]
        res2 = bt.run_book(book, wf["decisions"], cost_mult=2.0)
        oos["sharpe_2x"] = metrics.sharpe(res2.daily.loc[res2.daily.index >= start, "net"])
        gate["costs_2x"] = oos["sharpe_2x"] > GATE["sharpe_2x_costs"]
        nb = []
        for q in validation.neighbours(last_params):
            r = bt.run_book(book, validation.as_dec(decision_fn(q)))
            nb.append(metrics.sharpe(r.net[r.net.index >= start]))
        oos["neighbour_min_sharpe"] = float(min(nb)) if nb else float("nan")
        gate["neighbours"] = (min(nb) >= GATE["neighbour_sharpe"]) if nb else True
    else:
        gate["costs_2x"] = False
        gate["neighbours"] = False
    passed = all(gate.values())
    hid = registry.log(family, hypothesis, "walk-forward", {"grid": grid, "chosen_last": last_params},
                       "wf", oos, verdict="CANDIDATE" if passed else "reject",
                       notes=(notes + " | chosen=" + json.dumps(chosen, default=str))[:900])
    return Evaluation(hypothesis, last_params, oos, gate, passed, wf, hid)


def fmt_eval_md(ev: Evaluation) -> str:
    o = ev.oos
    keys = ["sharpe", "sharpe_gross", "ann_ret", "ann_vol", "mdd", "n_trades", "hit_rate", "turnover_ann",
            "p_value", "dsr", "sr0_ann", "subperiod_sharpes", "sharpe_2x", "neighbour_min_sharpe"]
    cells = []
    for k in keys:
        if k in o:
            v = o[k]
            cells.append(f"{k}={v:.3f}" if isinstance(v, float) and not math.isnan(v) else f"{k}={v}")
    failed = [k for k, v in ev.gate.items() if not v]
    return f"- **{ev.hid} {ev.name}** – " + ", ".join(cells) + f"; gate failed: {failed or 'none'}"
