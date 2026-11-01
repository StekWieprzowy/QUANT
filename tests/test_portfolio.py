import numpy as np
import pandas as pd
import pytest

from quant import portfolio as pf


def _setup(n=30):
    idx = pd.bdate_range("2015-01-05", periods=n)
    cols = ["A", "B"]
    close = pd.DataFrame(100.0, index=idx, columns=cols)
    px = {"close": close, "open": close.copy(), "ret": close.pct_change().fillna(0.0),
          "adv": pd.DataFrame(100e6, index=idx, columns=cols), "vol": pd.DataFrame(0.0, index=idx, columns=cols)}
    fw = pd.DataFrame({"open": 2000.0, "close": 2000.0, "prev_close": 2000.0, "roll_at_close": False}, index=idx)
    beta = pd.DataFrame(0.0, index=idx, columns=cols)
    return idx, px, fw, beta


def test_cost_tiers():
    cm = pf.CostModel()
    hs = cm.half_spread(np.array([60e6, 20e6, 5e6, 1e6, 0.1e6]))
    assert list(hs[:4]) == [0.0005, 0.0010, 0.0020, 0.0040] and np.isnan(hs[4])


def test_execution_next_open_no_lookahead():
    idx, px, fw, beta = _setup()
    d = idx[10]
    # a jump on the decision day (close d) and on the overnight into d+1 must NOT be captured
    for k in ("close",):
        px[k].loc[d:, "A"] = 110.0
    px["open"].loc[d:, "A"] = 110.0
    px["open"].loc[idx[11]:, "A"] = 121.0  # overnight +10% into execution day
    px["close"].loc[idx[11]:, "A"] = 121.0
    px["ret"] = px["close"].pct_change().fillna(0.0)
    tgt = pd.DataFrame({"A": [0.05]}, index=[d])
    res = pf.run(tgt, px, fw, beta, band=0.0, hedge=False)
    assert res.daily["gross"].loc[:idx[11]].abs().sum() == pytest.approx(0.0)


def test_costs_and_band():
    idx, px, fw, beta = _setup()
    cm = pf.CostModel(borrow_annual=0.0)
    tgt = pd.DataFrame({"A": [0.04, 0.042]}, index=[idx[5], idx[10]])
    res = pf.run(tgt, px, fw, beta, costs=cm, band=0.005, hedge=False)
    # first rebalance trades 4%, second (0.2% change) is inside the no-trade band
    assert res.daily["n_orders"].sum() == 1
    exp = 0.04 * (0.0029 + 0.0005 + 0.0005)
    trade_cost = res.daily["cost"].iloc[6] - 0.04 * pf.config.pln_rate(idx[6:7]).iloc[0] / 252
    assert trade_cost == pytest.approx(exp, rel=1e-6)


def test_build_weights_caps_and_shorts():
    s = pd.Series({"A": 3.0, "B": 1.0, "C": -1.0, "D": -3.0})
    w = pf.build_weights(s, pd.Series({"A": True, "B": True, "C": True, "D": False}), cap=0.4)
    assert w["D"] == 0 and w.abs().max() <= 0.4 + 1e-12 and abs(w.abs().sum() - 1) < 1e-9


def test_rebalance_days_last_of_week():
    s = pd.bdate_range("2021-01-04", periods=10).drop(pd.Timestamp("2021-01-08"))
    assert list(pf.rebalance_days(s)) == [pd.Timestamp("2021-01-07"), pd.Timestamp("2021-01-15")]
