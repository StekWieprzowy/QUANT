import numpy as np
import pandas as pd
import pytest

from quant import backtest as bt
from quant import config, holdout, metrics, validation
from quant.data import store


def test_sharpe_and_mdd():
    r = np.array([0.01, -0.02, 0.01, 0.0])
    assert metrics.max_drawdown(r) == pytest.approx(0.02, rel=1e-6)
    assert metrics.sharpe(np.zeros(10)) == 0.0


def test_dsr_penalises_many_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0006, 0.01, 2000)
    one = metrics.deflated_sharpe(r, 1)["dsr"]
    many = metrics.deflated_sharpe(r, 200)["dsr"]
    assert many < one


def test_bh():
    p = np.array([0.001, 0.02, 0.04, 0.5])
    assert list(metrics.benjamini_hochberg(p, 0.05)) == [True, True, False, False]


def test_reality_check_null_not_significant():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, (1000, 5))
    assert metrics.whites_reality_check(x, n_boot=200) > 0.05


def test_purged_kfold_no_overlap():
    t0 = pd.bdate_range("2020-01-01", periods=200)
    t1 = t0 + pd.Timedelta(days=5)
    for train, test in validation.purged_kfold(t0, t1, 5, 0.02):
        ts, te = t0[test[0]], t1[test].max()
        tr0, tr1 = t0[train], t1[train]
        assert not np.any((tr0 <= te) & (tr1 >= ts))


def test_permutation_random_signal_not_significant():
    rng = np.random.default_rng(2)
    dates = pd.bdate_range("2010-01-01", periods=1500)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
    d = pd.DataFrame({"open": c, "close": c}, index=dates)
    ev = bt.events_from_daily(d, cost_frac_per_side=0.0)
    sig = pd.Series(rng.choice([-1.0, 1.0], len(dates)), index=dates)
    out = validation.permutation_test(ev, bt.decisions_at_close(ev, sig), n_perm=100)
    assert out["p_value"] > 0.01


def test_research_loader_never_returns_holdout():
    idx = pd.bdate_range("2021-01-01", "2023-01-01")
    df = pd.DataFrame({"close": 1.0}, index=idx)
    out = store.truncate_research(df)
    assert out.index.max() < config.HOLDOUT_START


def test_holdout_lock_single_use(tmp_path, monkeypatch):
    monkeypatch.setattr(holdout, "LOCK", tmp_path / "LOCK")
    holdout.claim_holdout({"a": 1})
    with pytest.raises(holdout.HoldoutAlreadyUsed):
        holdout.claim_holdout({"a": 2})


def test_neighbours():
    nb = validation.neighbours({"n": 10, "z": 1.5, "flag": True})
    assert {"n": 8, "z": 1.5, "flag": True} in nb and {"n": 12, "z": 1.5, "flag": True} in nb
    assert any(abs(q["z"] - 1.8) < 1e-9 for q in nb)
