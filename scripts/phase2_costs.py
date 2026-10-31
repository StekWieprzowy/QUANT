"""Phase 2 / part 1: cost threshold. For each strategy, re-run the FULL walk-forward (parameter choice
redone) at scaled cost levels and record the OOS net Sharpe. Costs are exogenous, so this is a sensitivity
analysis, not a selection step - nothing is logged to the registry.

Also stores the base-cost (1x) OOS daily returns for part 2 (stability).
Outputs: reports/phase2/cost_curve.csv, reports/phase2/oos_returns.parquet, reports/figures/cost_threshold.png
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from quant import config, metrics, research, validation  # noqa: E402
from quant.strategies import catalog  # noqa: E402

STRATS = ["R1", "R2", "P1", "E1", "CA2", "CA5", "K1"]
MULTS = [0.0, 0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.5]
BASE_STOCK_SIDE = config.BASE_STOCK_COSTS.per_side_frac()  # 0.39%
OUT = config.REPORTS_DIR / "phase2"


def main(strats: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily, events = research.fw20_events()
    rows, oos = [], {}
    for v in strats:
        sp = catalog.build(v, daily, events)
        for m in MULTS:
            if v == "K1" and m not in (0.0, 0.5, 1.0):
                continue
            wf = validation.walk_forward(sp.events, sp.fn, sp.grid, research.FIRST_TEST_YEAR, cost_mult=m)
            net = wf["result"].net[wf["result"].net.index >= wf["oos_start"]]
            rows.append({"strategy": v, "cost_mult": m, "stock_cost_per_side_pct": round(100 * m * BASE_STOCK_SIDE, 3),
                         "oos_sharpe": metrics.sharpe(net), "ann_ret": float(net.mean() * 252)})
            if m == 1.0:
                oos[v] = net
            print(rows[-1], flush=True)
        pd.DataFrame(rows).to_csv(OUT / "cost_curve.csv", index=False)
    pd.DataFrame(oos).to_parquet(OUT / "oos_returns.parquet")
    plot()


def plot() -> None:
    cc = pd.read_csv(OUT / "cost_curve.csv")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    cols = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2", "#6e7781"]
    for i, (v, g) in enumerate(cc.groupby("strategy", sort=False)):
        ax.plot(g["stock_cost_per_side_pct"], g["oos_sharpe"], marker="o", ms=3, lw=1.5, color=cols[i % 7], label=v)
    ax.axhline(1.0, color="#db2777", ls="--", lw=1)
    ax.axhline(0.0, color="#6e7781", lw=0.8)
    ax.axvline(100 * BASE_STOCK_SIDE, color="#6e7781", ls=":", lw=1)
    ax.text(100 * BASE_STOCK_SIDE, ax.get_ylim()[1] * 0.95, " base 0.39%/side", color="#6e7781", fontsize=8, va="top")
    ax.set_xlabel("stock cost per side (commission + slippage), % of notional  [FW20/borrow scaled alike]")
    ax.set_ylabel("walk-forward OOS net Sharpe")
    ax.set_title("Cost threshold: OOS Sharpe 2008-2022 vs transaction cost", loc="left")
    ax.legend(frameon=False, fontsize=8, ncol=4)
    fig.tight_layout()
    fig.savefig(config.FIG_DIR / "cost_threshold.png", dpi=130)


if __name__ == "__main__":
    if sys.argv[1:] == ["--plot"]:
        plot()
    else:
        main(sys.argv[1:] or STRATS)
