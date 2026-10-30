import numpy as np
import pandas as pd
import pytest

from quant import backtest as bt
from quant.config import FuturesCosts


def make_daily(n=300, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2010-01-04", periods=n)
    c = 2000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.concatenate([[2000], c[:-1]]) * np.exp(rng.normal(0, 0.003, n))
    return pd.DataFrame({"open": o, "close": c}, index=dates)


def test_event_grid_returns_compound_to_close_to_close():
    d = make_daily()
    ev = bt.events_from_daily(d)
    grid = (1 + ev["ret"]).groupby(ev["date"]).prod() - 1
    cc = d["close"].pct_change().fillna(0)
    # first day: prev_close missing -> zero
    np.testing.assert_allclose(grid.iloc[1:].to_numpy(), cc.iloc[1:].to_numpy(), rtol=1e-9)


def test_decision_executed_on_next_event_only():
    d = make_daily(50)
    ev = bt.events_from_daily(d)
    dec = np.zeros(len(ev))
    k = 20  # decide at event 20 -> trade at event 21 -> first pnl at event 22
    dec[k:] = 1.0
    res = bt.run(ev, dec)
    assert np.all(res.events["gross"].to_numpy()[: k + 2] == 0)
    assert res.events["gross"].iloc[k + 2] == pytest.approx(ev["ret"].iloc[k + 2])
    assert res.events["turnover"].iloc[k + 1] == 1.0
    assert res.events["turnover"].sum() == 1.0


def test_no_lookahead_future_perturbation_does_not_change_past():
    """Changing returns after event T must not change PnL up to T for a causal signal."""
    d = make_daily(400, seed=3)

    def signal(daily):  # causal: momentum on closes up to d
        return np.sign(daily["close"].pct_change(10)).fillna(0)

    ev = bt.events_from_daily(d)
    r1 = bt.run(ev, bt.decisions_at_close(ev, signal(d)))
    d2 = d.copy()
    cut = 250
    d2.iloc[cut:, :] *= np.linspace(0.5, 2.0, len(d2) - cut)[:, None]
    ev2 = bt.events_from_daily(d2)
    r2 = bt.run(ev2, bt.decisions_at_close(ev2, signal(d2)))
    # pnl up to (and including) the close of day cut-1 must be identical
    np.testing.assert_allclose(r1.net.iloc[:cut].to_numpy(), r2.net.iloc[:cut].to_numpy())


def test_lookahead_signal_is_not_rewarded_by_engine():
    """A signal that 'peeks' at today's close-to-close return is shifted by the engine, so a perfect
    same-day oracle earns roughly nothing - demonstrating the engine forbids same-bar execution."""
    d = make_daily(2000, seed=5)
    ev = bt.events_from_daily(d)
    oracle = np.sign(d["close"].pct_change()).fillna(0)
    res = bt.run(ev, bt.decisions_at_close(ev, oracle))
    same_bar = (oracle * d["close"].pct_change().fillna(0))  # what a look-ahead engine would book
    from quant.metrics import sharpe
    assert sharpe(same_bar) > 10
    assert abs(sharpe(res.gross)) < 1.0


def test_costs_per_side_points():
    d = pd.DataFrame({"open": [2000.0] * 6, "close": [2000.0] * 6}, index=pd.bdate_range("2020-01-01", periods=6))
    costs = FuturesCosts(multiplier=20, commission_pln=10, slippage_points=1.5)
    ev = bt.events_from_daily(d, costs=costs)
    dec = np.zeros(len(ev))
    dec[2:6] = 1.0  # enter at event 3, exit at event 7
    res = bt.run(ev, dec)
    per_side = (1.5 + 10 / 20) / 2000
    assert res.events["cost"].sum() == pytest.approx(2 * per_side)
    assert res.net.sum() == pytest.approx(-2 * per_side)
    # cost multiplier scales linearly
    assert bt.run(ev, dec, cost_mult=2).net.sum() == pytest.approx(-4 * per_side)


def test_flip_costs_two_units():
    d = pd.DataFrame({"open": [100.0] * 4, "close": [100.0] * 4}, index=pd.bdate_range("2020-01-01", periods=4))
    ev = bt.events_from_daily(d, cost_frac_per_side=0.001)
    dec = np.array([1, 1, -1, -1, -1, -1, -1, -1], dtype=float)
    res = bt.run(ev, dec)
    assert res.events["turnover"].sum() == pytest.approx(1 + 2)


def test_roll_charges_two_sides_and_no_price_jump():
    dates = pd.bdate_range("2020-01-01", periods=4)
    daily = pd.DataFrame({
        "open": [100, 101, 151, 152.0], "close": [101, 102, 152, 153.0],
        "prev_close": [np.nan, 101, 150, 152.0],  # day 3 is in the new contract (prev close 150 in new)
        "roll_at_close": [False, True, False, False]}, index=dates)
    ev = bt.events_from_daily(daily, cost_frac_per_side=0.001)
    dec = np.ones(len(ev))
    res = bt.run(ev, dec)
    # no artificial +48% jump from the contract switch
    assert res.events["gross"].max() < 0.02
    roll_ev = res.events.index[res.events["roll"]][0]
    assert res.events.loc[roll_ev, "turnover"] == pytest.approx(2.0)


def test_intraday_decisions_flat_overnight():
    d = make_daily(30)
    ev = bt.events_from_daily(d)
    tgt = pd.Series(1.0, index=d.index)
    res = bt.run(ev, bt.decisions_intraday(ev, tgt))
    held = res.events["pos_held"].to_numpy()
    is_o = (ev["phase"] == "O").to_numpy()
    assert np.all(held[is_o] == 0)  # overnight interval ends at O -> flat
    assert np.all(held[~is_o][1:] == 1)  # intraday interval ends at C -> long


def test_extract_trades_counts_round_trips():
    d = make_daily(20)
    ev = bt.events_from_daily(d, cost_frac_per_side=0.0005)
    dec = np.zeros(len(ev))
    dec[2:6] = 1
    dec[10:14] = -1
    dec[14:18] = 1  # flip
    res = bt.run(ev, dec)
    tr = res.trades()
    assert len(tr) == 3
    assert list(tr["side"]) == [1, -1, 1]
    assert tr["pnl"].sum() == pytest.approx(res.events["net"].sum())
