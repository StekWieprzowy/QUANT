"""Performance metrics and multiple-testing statistics."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from quant.config import TRADING_DAYS

EULER_GAMMA = 0.5772156649015329


def sharpe(r: pd.Series | np.ndarray, periods: int = TRADING_DAYS) -> float:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods))


def max_drawdown(r: pd.Series | np.ndarray) -> float:
    eq = np.cumprod(1.0 + np.nan_to_num(np.asarray(r, dtype=float)))
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    return float(np.max(1.0 - eq / peak)) if len(eq) else 0.0


def cagr(r: pd.Series | np.ndarray, periods: int = TRADING_DAYS) -> float:
    r = np.nan_to_num(np.asarray(r, dtype=float))
    if len(r) == 0:
        return 0.0
    total = float(np.prod(1.0 + r))
    return total ** (periods / len(r)) - 1.0 if total > 0 else -1.0


def summary(net: pd.Series, trades: pd.DataFrame | None = None, gross: pd.Series | None = None,
            turnover: pd.Series | None = None) -> dict:
    out = {
        "start": str(net.index[0].date()) if len(net) else None,
        "end": str(net.index[-1].date()) if len(net) else None,
        "n_days": int(len(net)),
        "sharpe": sharpe(net),
        "ann_ret": float(np.mean(net) * TRADING_DAYS),
        "ann_vol": float(np.std(net, ddof=1) * math.sqrt(TRADING_DAYS)) if len(net) > 1 else 0.0,
        "cagr": cagr(net),
        "mdd": max_drawdown(net),
        "skew": float(stats.skew(net)) if len(net) > 2 else 0.0,
        "kurt": float(stats.kurtosis(net, fisher=False)) if len(net) > 3 else 3.0,
    }
    if gross is not None:
        out["sharpe_gross"] = sharpe(gross)
    if turnover is not None:
        out["turnover_ann"] = float(turnover.sum() / max(len(net), 1) * TRADING_DAYS)
    if trades is not None:
        n = len(trades)
        out["n_trades"] = int(n)
        if n:
            pnl = trades["pnl"].to_numpy()
            out["hit_rate"] = float((pnl > 0).mean())
            out["avg_trade"] = float(pnl.mean())
            pos, neg = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
            out["profit_factor"] = float(pos / neg) if neg > 0 else float("inf")
            tot = pnl.sum()
            top5 = np.sort(pnl)[::-1][:5].sum()
            out["top5_share"] = float(top5 / tot) if tot > 0 else float("nan")
    return out


# ------------------------------------------------------------------ Sharpe inference
def probabilistic_sharpe(r: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """PSR (Bailey & Lopez de Prado 2012). sr_benchmark in per-period (non-annualised) units."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    t = len(r)
    if t < 3 or r.std(ddof=1) == 0:
        return 0.0
    sr = r.mean() / r.std(ddof=1)
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)
    denom = math.sqrt(max(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr**2, 1e-12))
    return float(stats.norm.cdf((sr - sr_benchmark) * math.sqrt(t - 1) / denom))


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """E[max SR] across n_trials iid null strategies with SR-estimate variance var_sr (per-period units)."""
    if n_trials <= 1:
        return 0.0
    n = n_trials
    return math.sqrt(var_sr) * ((1 - EULER_GAMMA) * stats.norm.ppf(1 - 1.0 / n)
                                + EULER_GAMMA * stats.norm.ppf(1 - 1.0 / (n * math.e)))


def deflated_sharpe(r: np.ndarray, n_trials: int, trial_sharpes_ann: np.ndarray | None = None,
                    periods: int = TRADING_DAYS) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014).

    The variance of SR across trials is estimated from the registry (annualised SRs converted to
    per-period). We use the larger of that estimate and the null estimator variance 1/T, which is the
    conservative choice when few trials are logged.
    """
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    t = len(r)
    var_null = 1.0 / max(t, 1)
    var_emp = 0.0
    if trial_sharpes_ann is not None and len(trial_sharpes_ann) > 1:
        var_emp = float(np.var(np.asarray(trial_sharpes_ann) / math.sqrt(periods), ddof=1))
    var_sr = max(var_emp, var_null)
    sr0 = expected_max_sharpe(n_trials, var_sr)
    return {"dsr": probabilistic_sharpe(r, sr0), "sr0_ann": sr0 * math.sqrt(periods),
            "var_sr_source": "registry" if var_emp > var_null else "null_1/T", "n_trials": n_trials}


def sharpe_pvalue(r: np.ndarray) -> float:
    """One-sided p-value for SR>0 using the PSR (non-normality adjusted) statistic."""
    return 1.0 - probabilistic_sharpe(r, 0.0)


def benjamini_hochberg(pvals: np.ndarray, q: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    thresh = q * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    k = np.max(np.nonzero(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(n, dtype=bool)
    out[order[:k]] = True
    return out


# ------------------------------------------------------------------ bootstrap
def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    jumps = rng.random(n) < p
    starts = rng.integers(n, size=n)
    for i in range(1, n):
        idx[i] = starts[i] if jumps[i] else (idx[i - 1] + 1) % n
    return idx


def whites_reality_check(returns: np.ndarray, n_boot: int = 1000, mean_block: float = 10.0,
                         seed: int = 0) -> float:
    """White (2000) RC p-value for H0: no strategy (columns) beats zero. returns: T x K daily net returns."""
    x = np.asarray(returns, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    t = x.shape[0]
    mu = x.mean(axis=0)
    stat = math.sqrt(t) * mu.max()
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_boot):
        idx = stationary_bootstrap_indices(t, mean_block, rng)
        mb = x[idx].mean(axis=0)
        if math.sqrt(t) * (mb - mu).max() >= stat:
            cnt += 1
    return (cnt + 1) / (n_boot + 1)
