import numpy as np
import pandas as pd

from quant import events


def test_day0_and_car_windows():
    idx = pd.bdate_range("2020-01-01", periods=400)
    rng = np.random.default_rng(0)
    m = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    r = 0.5 * m + pd.Series(rng.normal(0, 0.002, len(idx)), index=idx)
    ev_date = idx[300]
    r.iloc[300] += 0.05  # abnormal jump on day 0 only
    weekend = idx[idx.dayofweek == 0][-1] - pd.Timedelta(days=2)  # a Saturday -> next session (Monday)
    assert events.day0_positions(idx, [weekend])[0] == idx.get_loc(weekend + pd.Timedelta(days=2))
    tab = events.car_table(r, [ev_date], {"d0": (0, 0), "post": (1, 5), "pre": (-5, -1)}, m)
    assert tab["day0"].iloc[0] == ev_date
    assert abs(tab["d0"].iloc[0] - 0.05) < 0.01
    assert abs(tab["post"].iloc[0]) < 0.02
    # after_close: day 0 is the NEXT session
    tab2 = events.car_table(r, [ev_date], {"d0": (0, 0)}, m, after_close=True)
    assert tab2["day0"].iloc[0] == idx[301]


def test_summarize_ci_contains_mean():
    s = events.summarize(pd.Series(np.random.default_rng(1).normal(0.01, 0.02, 50)))
    assert s.ci_lo < s.mean < s.ci_hi and s.n == 50
