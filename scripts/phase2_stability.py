"""Phase 2 / part 2: stability over time of the base-cost walk-forward OOS returns.

* net Sharpe in 2008-2012, 2013-2017, 2018-2022H1
* rolling 2-year (504 sessions) Sharpe + chart
* decay test: OLS slope of yearly Sharpe on year (and its p-value)
Rule (pre-stated): a variant is rejected as "decaying" if its last sub-period Sharpe is < 0, or the yearly
slope is negative with p < 0.10 - even if the overall result looks fine.
Uses reports/phase2/oos_returns.parquet (written by phase2_costs.py) + adds CA7.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from quant import config, metrics, research, validation  # noqa: E402
from quant.strategies import catalog  # noqa: E402

OUT = config.REPORTS_DIR / "phase2"
PERIODS = {"2008-2012": ("2008", "2012"), "2013-2017": ("2013", "2017"), "2018-2022H1": ("2018", "2022")}


def main() -> None:
    R = pd.read_parquet(OUT / "oos_returns.parquet")
    if "CA7" not in R:
        daily, events = research.fw20_events()
        sp = catalog.build("CA7", daily, events)
        wf = validation.walk_forward(sp.events, sp.fn, sp.grid, research.FIRST_TEST_YEAR)
        R["CA7"] = wf["result"].net[wf["result"].net.index >= wf["oos_start"]]
        R.to_parquet(OUT / "oos_returns.parquet")
    R = R[R.index >= "2008-01-01"].fillna(0.0)
    res = {}
    for v in R:
        r = R[v]
        sub = {k: metrics.sharpe(r[a:b]) for k, (a, b) in PERIODS.items()}
        yearly = r.groupby(r.index.year).apply(metrics.sharpe)
        sl = stats.linregress(yearly.index.to_numpy(float), yearly.to_numpy())
        decaying = bool(list(sub.values())[-1] < 0 or (sl.slope < 0 and sl.pvalue < 0.10))
        res[v] = {"total": metrics.sharpe(r), **{k: round(x, 2) for k, x in sub.items()},
                  "yearly_slope": round(sl.slope, 3), "slope_p": round(sl.pvalue, 3), "decaying": decaying,
                  "yearly": {int(k): round(x, 2) for k, x in yearly.items()}}
        print(v, {k: res[v][k] for k in ["total", *PERIODS, "yearly_slope", "slope_p", "decaying"]})
    (OUT / "stability.json").write_text(json.dumps(res, indent=2))

    roll = R.rolling(504, min_periods=400).apply(lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0,
                                                 raw=True)
    cols = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2", "#6e7781", "#111827"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for i, v in enumerate(R):
        ax.plot(roll.index, roll[v], lw=1.3, color=cols[i % len(cols)], label=v)
    ax.axhline(0, color="#6e7781", lw=0.8)
    ax.axhline(1, color="#db2777", lw=1, ls="--")
    ax.set_title("Rolling 2-year net Sharpe (walk-forward OOS, base costs)", loc="left")
    ax.legend(frameon=False, fontsize=8, ncol=4)
    fig.tight_layout()
    fig.savefig(config.FIG_DIR / "rolling_sharpe_2y.png", dpi=130)


if __name__ == "__main__":
    main()
