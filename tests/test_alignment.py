import numpy as np
import pandas as pd

from quant import research


def test_align_foreign_timing_and_stale_days():
    sessions = pd.DatetimeIndex(["2024-07-03", "2024-07-04", "2024-07-05", "2024-07-08"])
    # US closed on 07-04
    us = pd.DataFrame({"close": [100.0, 101.0, 103.0, 102.0]},
                      index=pd.DatetimeIndex(["2024-07-02", "2024-07-03", "2024-07-05", "2024-07-08"]))
    same = research.align_foreign(us, sessions, same_day=True)
    prev = research.align_foreign(us, sessions, same_day=False)
    # same_day: session d sees US close of d (for decisions executed at next open)
    assert same.loc["2024-07-03", "value"] == 101.0
    assert same.loc["2024-07-04", "ret"] == 0.0  # US holiday: no new information
    assert np.isclose(same.loc["2024-07-05", "ret"], np.log(103 / 101))
    # strictly before d: usable intraday on d
    assert prev.loc["2024-07-03", "value"] == 100.0
    assert prev.loc["2024-07-08", "value"] == 103.0
    assert (prev["fdate"] < prev.index).all()
