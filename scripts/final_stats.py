"""Summary statistics over all valid walk-forward variants (research period only):
White's Reality Check on OOS daily net returns, Benjamini-Hochberg on permutation p-values, correlations.
Writes reports/final_stats.json and reports/oos_returns.parquet. Does NOT log new trials."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from quant import config, metrics, registry, research, validation
from quant.strategies import catalog

VARIANTS = ["P1", "P2", "C1", "C2", "T1", "T2", "M1", "M2", "L1", "L2", "L3", "F1", "O1", "X1", "R1", "R2",
            "G1", "G2", "K1", "E1"]


def main() -> None:
    daily, events = research.fw20_events()
    oos = {}
    for v in VARIANTS:
        sp = catalog.build(v, daily, events)
        wf = validation.walk_forward(sp.events, sp.fn, sp.grid, research.FIRST_TEST_YEAR)
        oos[v] = wf["result"].net[wf["result"].net.index >= wf["oos_start"]]
        print(v, round(metrics.sharpe(oos[v]), 3))
    R = pd.DataFrame(oos).fillna(0.0)
    R = R[R.index >= pd.Timestamp("2008-01-01")]
    R.to_parquet(config.REPORTS_DIR / "oos_returns.parquet")
    rc = metrics.whites_reality_check(R.to_numpy(), n_boot=2000, mean_block=10, seed=config.SEED)
    rc_s = metrics.whites_reality_check(R.to_numpy(), n_boot=2000, mean_block=10, seed=config.SEED,
                                        studentize=True)
    reg = registry.load()
    wf_rows = reg[(reg["stage"] == "wf") & (reg["verdict"] != "INVALID")]
    bh = metrics.benjamini_hochberg(wf_rows["p_value"].to_numpy(), 0.05)
    out = {
        "n_trials_total": int(registry.n_trials()),
        "n_invalid_rows": int((reg["verdict"] == "INVALID").sum()),
        "n_valid_wf": int(len(wf_rows)),
        "whites_reality_check_p": rc,
        "studentized_reality_check_p": rc_s,
        "oos_sharpes": {k: round(metrics.sharpe(R[k]), 3) for k in R},
        "bh_significant_q05": wf_rows.loc[bh, ["id", "hypothesis", "p_value", "sharpe_net"]].to_dict("records"),
        "best_valid_wf": wf_rows.sort_values("sharpe_net").tail(5)[["id", "hypothesis", "sharpe_net", "dsr"]]
        .to_dict("records"),
        "corr_relative_value": R[["P1", "R2", "K1"]].corr().round(2).to_dict(),
    }
    (config.REPORTS_DIR / "final_stats.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
