"""ONE-SHOT holdout evaluation of the frozen candidate in holdout/candidate.json.

The candidate file is written when (and only when) a strategy passes the full research gate. This script
claims holdout/LOCK first (raises if the holdout was already used), then evaluates the frozen rule on
data >= HOLDOUT_START. No parameter is changed here. Success criteria (all, net of costs):
  Sharpe > 1.0, DSR > 0.95 (N = all registry trials), MDD < 20%, Sharpe_holdout >= 0.5 * Sharpe_validation.
"""
from __future__ import annotations

import json

import numpy as np

from quant import backtest as bt
from quant import config, holdout, metrics, registry, research, validation
from quant.strategies import catalog


def main() -> None:
    cand = json.loads((config.HOLDOUT_DIR / "candidate.json").read_text())
    research.unlock_holdout(cand)  # writes LOCK; raises HoldoutAlreadyUsed on a second call
    daily, events = research.fw20_events()
    sp = catalog.build(cand["variant"], daily, events)
    dec = validation.as_dec(sp.fn(cand["params"]))
    res = bt.run_book(validation.as_book(sp.events), dec)
    start = config.HOLDOUT_START
    daily_h, trades_h = validation.oos_slice(res, start)
    s = metrics.summary(daily_h["net"], trades_h, daily_h["gross"], daily_h["turnover"])
    n = registry.n_trials()
    d = metrics.deflated_sharpe(daily_h["net"].to_numpy(), n, registry.trial_sharpes())
    s["dsr"], s["sr0_ann"] = d["dsr"], d["sr0_ann"]
    perm = validation.permutation_test(validation.as_book(sp.events), dec, start=start, n_perm=1000)
    s["p_value"] = perm["p_value"]
    res2 = bt.run_book(validation.as_book(sp.events), dec, cost_mult=2.0)
    s["sharpe_2x_costs"] = metrics.sharpe(res2.net[res2.net.index >= start])
    bh = daily.loc[daily.index >= start]
    bh_ret = np.log(bh["close"] / bh["prev_close"]).fillna(0)
    s["benchmark_fw20_bh_sharpe"] = metrics.sharpe(np.expm1(bh_ret))
    s["benchmark_fw20_bh_mdd"] = metrics.max_drawdown(np.expm1(bh_ret))
    crit = {
        "sharpe>1": s["sharpe"] > 1.0,
        "dsr>0.95": s["dsr"] > 0.95,
        "mdd<20%": s["mdd"] < 0.20,
        "sharpe>=0.5*validation": s["sharpe"] >= 0.5 * cand["validation_sharpe"],
    }
    s["criteria"] = crit
    s["success"] = all(crit.values())
    s["candidate"] = cand
    holdout.write_result(s)
    registry.log(sp.family, sp.name, "HOLDOUT", cand["params"], "holdout", s,
                 verdict="SUCCESS" if s["success"] else "FAILED_HOLDOUT", notes="one-shot holdout")
    res.daily.to_parquet(config.HOLDOUT_DIR / "holdout_daily.parquet")
    print(json.dumps(s, indent=2, default=str))


if __name__ == "__main__":
    main()
