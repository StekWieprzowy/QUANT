"""Gradient boosting on daily features, strictly walk-forward (yearly refit on an expanding, purged window).

Decision at the close of d (all features known by then; foreign closes of d are known before the next
open) -> position held from O_{d+1} to O_{d+2}. Label = sign of that return.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from quant import config, research
from quant.strategies.fw20 import FW20Signals, rsi_wilder


def build_features(daily: pd.DataFrame) -> pd.DataFrame:
    S = FW20Signals(daily)
    idx = daily.index
    f = pd.DataFrame(index=idx)
    r = S.ret
    for k in (1, 2, 5, 10, 20, 60, 120):
        f[f"ret_{k}"] = r.rolling(k).sum()
    f["gap"] = S.on_ret
    f["intraday"] = S.id_ret
    f["vol20"] = r.rolling(20).std()
    f["vol60"] = r.rolling(60).std()
    f["vol_ratio"] = f["vol20"] / f["vol60"]
    f["z5"] = f["ret_5"] / (f["vol60"] * np.sqrt(5))
    for L in (20, 50, 200):
        f[f"ma_dist_{L}"] = np.log(S.idx / S.idx.rolling(L).mean())
    f["rsi2"] = rsi_wilder(S.idx, 2)
    f["range"] = np.log(daily["high"] / daily["low"])
    f["vol_chg"] = np.log(daily["volume"].replace(0, np.nan)).diff(5)
    f["oi_chg"] = np.log(daily["oi"].replace(0, np.nan)).diff(5)
    cal = S.cal
    f["rank_end"] = cal["rank_end"]
    f["rank_start"] = cal["rank_start"]
    f["dow_next"] = pd.Series(idx.dayofweek, index=idx).shift(-1).fillna(0)  # calendar is known
    f["pre_holiday"] = cal["pre_holiday"].astype(float)
    f["sess_to_expiry"] = cal["sess_to_expiry"]
    for sym, name in [("^GSPC", "spx"), ("^GDAXI", "dax"), ("^VIX", "vix"), ("HG=F", "copper"),
                      ("CL=F", "oil"), ("^TNX", "us10y"), ("EEM", "eem")]:
        a = research.align_foreign(research.load_yahoo(sym), idx, same_day=True)
        f[f"{name}_r1"] = a["ret"]
        f[f"{name}_r5"] = a["ret"].rolling(5).sum()
    vix = research.align_foreign(research.load_yahoo("^VIX"), idx, same_day=True)
    f["vix_level"] = vix["value"]
    for code in ("eur", "usd"):
        fx = np.log(research.load_nbp(code)["close"].reindex(idx, method="ffill"))
        f[f"{code}pln_r1"] = fx.diff()
        f[f"{code}pln_r5"] = fx.diff(5)
        f[f"{code}pln_r20"] = fx.diff(20)
    return f.replace([np.inf, -np.inf], np.nan)


def label_next(events: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    """Return of a +1 position decided at C_d: intervals (O_{d+1},C_{d+1}] and (C_{d+1},O_{d+2}]."""
    ev = events.reset_index(drop=True)
    r = np.log1p(ev["ret"].to_numpy())
    is_c = (ev["phase"] == "C").to_numpy()
    c_idx = np.flatnonzero(is_c)
    out = np.full(len(c_idx), np.nan)
    for j, k in enumerate(c_idx):
        if k + 2 < len(r):
            out[j] = r[k + 2] + (r[k + 3] if k + 3 < len(r) else 0.0)
    # the +2 offset: decision at C_d is executed at O_{d+1}=k+1; held over (k+1,k+2] and (k+2,k+3]
    return pd.Series(out, index=pd.DatetimeIndex(ev.loc[is_c, "date"])).reindex(dates)


PARAMS = dict(objective="binary", learning_rate=0.03, n_estimators=200, num_leaves=7, max_depth=3,
              min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
              reg_lambda=1.0, verbose=-1)


def walk_forward_proba(features: pd.DataFrame, label: pd.Series, first_test_year: int,
                       purge: int = 2, seed: int = config.SEED) -> pd.Series:
    """Yearly expanding refit. Training samples whose label window overlaps the test year are purged
    (last `purge` sessions before the test year)."""
    proba = pd.Series(np.nan, index=features.index)
    y = (label > 0).astype(float).where(label.notna())
    years = sorted(set(features.index.year))
    for yr in years:
        if yr < first_test_year:
            continue
        tr_mask = features.index.year < yr
        tr_idx = np.flatnonzero(tr_mask)[:-purge] if purge else np.flatnonzero(tr_mask)
        Xtr, ytr = features.iloc[tr_idx], y.iloc[tr_idx]
        ok = ytr.notna()
        model = lgb.LGBMClassifier(random_state=seed, **PARAMS)
        model.fit(Xtr[ok], ytr[ok])
        te = features.index.year == yr
        proba[te] = model.predict_proba(features[te])[:, 1]
    return proba
