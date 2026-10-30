import numpy as np
import pandas as pd

from quant.data import futures as fu


def test_third_friday():
    assert fu.third_friday(2024, 3) == pd.Timestamp("2024-03-15")
    assert fu.third_friday(2024, 12) == pd.Timestamp("2024-12-20")
    assert fu.third_friday(2021, 1) == pd.Timestamp("2021-01-15")


def test_expiry_moves_to_previous_session_on_holiday():
    # 2016-03-25 was Good Friday (also 3rd Friday? no: 3rd Friday of Mar 2016 is 18th) - use synthetic holiday
    sessions = pd.bdate_range("2016-03-01", "2016-03-31").drop(pd.Timestamp("2016-03-18"))
    assert fu.expiry_date(2016, 3, sessions) == pd.Timestamp("2016-03-17")


def test_contract_code_roundtrip():
    assert fu.contract_code(2024, 12) == "FW20Z24"
    assert fu.parse_contract_code("FW20Z24") == (2024, 12)
    assert fu.parse_contract_code("fw20h2005") == (2005, 3)
    assert fu.parse_contract_code("FW20U99") == (1999, 9)


def _contract(sessions, start, end, level, drift):
    idx = sessions[(sessions >= start) & (sessions <= end)]
    c = level + drift * np.arange(len(idx))
    return pd.DataFrame({"open": c - 0.5, "high": c + 1, "low": c - 1, "close": c, "volume": 100}, index=idx)


def test_build_continuous_rolls_before_expiry_and_has_no_jump():
    sessions = pd.bdate_range("2024-01-02", "2024-07-31")
    h = _contract(sessions, "2024-01-02", fu.third_friday(2024, 3), 2000, 1.0)
    m = _contract(sessions, "2024-01-02", fu.third_friday(2024, 6), 2050, 1.0)  # contango +50
    u = _contract(sessions, "2024-03-01", "2024-07-31", 2100, 1.0)
    cont = fu.build_continuous({"FW20H24": h, "FW20M24": m, "FW20U24": u}, sessions, roll_days=5)
    exp_h = fu.expiry_date(2024, 3, sessions)
    roll = sessions[sessions.get_loc(exp_h) - 5]
    assert cont.loc[roll, "roll_at_close"]
    assert cont.loc[roll, "contract"] == "FW20H24"
    nxt = sessions[sessions.get_loc(roll) + 1]
    assert cont.loc[nxt, "contract"] == "FW20M24"
    # returns inside each contract only: close-prev_close is always the drift (1 pt)
    diff = (cont["close"] - cont["prev_close"]).dropna()
    assert np.allclose(diff, 1.0)
    idx = fu.continuous_excess_index(cont)
    assert idx.pct_change().abs().max() < 0.01
