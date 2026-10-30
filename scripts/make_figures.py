"""Figures for REPORT.md: walk-forward OOS equity / drawdown / return distribution of selected registry
entries (research period only) + benchmark, and registry overview.

Usage: python scripts/make_figures.py VARIANT [VARIANT ...]
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from quant import config, metrics, registry, research, validation  # noqa: E402
from quant.strategies import catalog  # noqa: E402

INK, MUTED, GRID = "#1f2328", "#6e7781", "#d0d7de"
SERIES = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2"]
plt.rcParams.update({"axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})


def wf_daily(variant: str, daily, events) -> pd.Series:
    sp = catalog.build(variant, daily, events)
    wf = validation.walk_forward(sp.events, sp.fn, sp.grid, research.FIRST_TEST_YEAR)
    return wf["result"].net[wf["result"].net.index >= wf["oos_start"]].rename(sp.name)


def main(variants: list[str]) -> None:
    config.FIG_DIR.mkdir(parents=True, exist_ok=True)
    daily, events = research.fw20_events()
    curves = {v: wf_daily(v, daily, events) for v in variants}
    start = min(c.index[0] for c in curves.values())
    bh = np.expm1(np.log(daily["close"] / daily["prev_close"]).fillna(0))
    bh = bh[bh.index >= start].rename("Buy & hold FW20")

    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for i, (v, c) in enumerate(list(curves.items()) + [("BH", bh)]):
        col = MUTED if v == "BH" else SERIES[i % len(SERIES)]
        eq = (1 + c).cumprod()
        ax[0].plot(eq.index, eq, color=col, lw=1.6 if v != "BH" else 1.0, label=f"{c.name} (SR {metrics.sharpe(c):.2f})")
        dd = eq / eq.cummax() - 1
        ax[1].plot(dd.index, dd, color=col, lw=1.0)
    ax[0].set_ylabel("equity (log)")
    ax[0].set_yscale("log")
    ax[0].legend(frameon=False, fontsize=8, loc="upper left")
    ax[1].set_ylabel("drawdown")
    ax[0].set_title("Walk-forward OOS (research period, net of costs)", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(config.FIG_DIR / "wf_equity_drawdown.png", dpi=130)

    fig, ax = plt.subplots(figsize=(9, 3))
    for i, (v, c) in enumerate(curves.items()):
        nz = c[c != 0]
        ax.hist(nz, bins=80, alpha=0.55, color=SERIES[i % len(SERIES)], label=c.name)
    ax.set_title("Daily net returns on days with exposure (OOS)", loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(config.FIG_DIR / "wf_return_hist.png", dpi=130)

    reg = registry.load()
    reg = reg[(reg["stage"] != "holdout") & (reg["verdict"].fillna("") != "INVALID")].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 3))
    wf = reg[reg["stage"] == "wf"]
    sc = reg[reg["stage"] == "screen"]
    ax.scatter(sc.index, sc["sharpe_net"], s=10, color=MUTED, label="grid points (in-sample)")
    ax.scatter(wf.index, wf["sharpe_net"], s=22, color=SERIES[0],
               label="walk-forward OOS")
    ax.axhline(1.0, color=SERIES[3], lw=1, ls="--", label="gate SR=1")
    ax.set_xlabel("registry order")
    ax.set_ylabel("net Sharpe")
    ax.set_title(f"All {len(reg)} logged trials", loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(config.FIG_DIR / "registry_sharpes.png", dpi=130)
    print("figures written to", config.FIG_DIR)


if __name__ == "__main__":
    main(sys.argv[1:])
