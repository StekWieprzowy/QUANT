"""X2: LightGBM selection of stock residual-reversal trades (panel of stock-days, yearly walk-forward refit).

Decision at the close of d -> long stock / short beta*FW20 from O_{d+1} for H sessions.
Label = net-of-nothing (gross) hedged return of that holding, computed from the instrument's event grid.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from quant import config, research
from quant.strategies.pairs import adjusted_stock

H = 5
PARAMS = dict(objective="regression", learning_rate=0.03, n_estimators=300, num_leaves=15, max_depth=4,
              min_child_samples=200, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0,
              verbose=-1)


def forward_label(ev: pd.DataFrame, hold: int = H) -> pd.Series:
    r = np.log1p(ev["ret"].to_numpy())
    c = np.cumsum(np.concatenate([[0.0], r]))  # c[j] = sum r[:j]
    is_c = (ev["phase"] == "C").to_numpy()
    k = np.flatnonzero(is_c)
    lo, hi = k + 2, k + 2 * hold + 2
    out = np.where(hi <= len(r), c[np.minimum(hi, len(r))] - c[np.minimum(lo, len(r))], np.nan)
    return pd.Series(out, index=pd.DatetimeIndex(ev.loc[is_c, "date"]))


def panel(book_events: dict, resids: dict, daily: pd.DataFrame) -> pd.DataFrame:
    mret = np.log(daily["close"] / daily["prev_close"]).fillna(0.0)
    mvol = mret.rolling(20).std()
    vix = research.align_foreign(research.load_yahoo("^VIX"), daily.index, same_day=True)
    frames = []
    for t, ev in book_events.items():
        e = resids[t]
        st = adjusted_stock(t).reindex(e.index)
        raw = research.load_yahoo(f"{t}.WA").reindex(e.index)
        f = pd.DataFrame(index=e.index)
        sd = e.rolling(60, min_periods=30).std()
        for k in (1, 3, 5, 10, 20):
            f[f"rz{k}"] = e.rolling(k).sum() / (sd * np.sqrt(k))
        f["svol20"] = np.log(st["close"]).diff().rolling(20).std()
        f["svol_ratio"] = f["svol20"] / np.log(st["close"]).diff().rolling(120).std()
        f["volu_ratio"] = np.log(raw["volume"].rolling(5).mean() / raw["volume"].rolling(60).mean())
        f["dist_high"] = np.log(st["close"] / st["close"].rolling(250, min_periods=60).max())
        f["gap_today"] = np.log(st["open"] / st["close"].shift(1))
        f["intraday_today"] = np.log(st["close"] / st["open"])
        f["m_r1"] = mret.reindex(e.index)
        f["m_r5"] = mret.rolling(5).sum().reindex(e.index)
        f["m_r20"] = mret.rolling(20).sum().reindex(e.index)
        f["m_vol20"] = mvol.reindex(e.index)
        f["vix"] = vix["value"].reindex(e.index)
        f["dow"] = e.index.dayofweek
        f["label"] = forward_label(ev).reindex(e.index)
        f["ticker"] = t
        frames.append(f)
    p = pd.concat(frames)
    p["xs_rank_rz5"] = p.groupby(level=0)["rz5"].rank(pct=True)
    return p.replace([np.inf, -np.inf], np.nan)


def walk_forward_pred(p: pd.DataFrame, first_test_year: int, seed: int = config.SEED) -> pd.Series:
    feats = [c for c in p.columns if c not in ("label", "ticker")]
    pred = pd.Series(np.nan, index=range(len(p)))
    dates = pd.DatetimeIndex(p.index)
    years = sorted(set(dates.year))
    sess = pd.DatetimeIndex(sorted(set(dates)))
    for yr in years:
        if yr < first_test_year:
            continue
        test_start = pd.Timestamp(year=yr, month=1, day=1)
        # purge: labels of training rows must end before the test year (H+1 sessions ahead)
        cut = sess[sess < test_start]
        cut = cut[-(H + 2)] if len(cut) > H + 2 else cut[0]
        tr = (dates < cut) & p["label"].notna().to_numpy()
        te = dates.year == yr
        m = lgb.LGBMRegressor(random_state=seed, **PARAMS)
        m.fit(p.loc[tr, feats], p.loc[tr, "label"])
        pred[np.flatnonzero(te)] = m.predict(p.loc[te, feats])
    return pd.Series(pred.to_numpy(), index=p.index)
