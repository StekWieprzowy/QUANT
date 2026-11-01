"""Phase 3 / part B: multi-signal, market-neutral WIG20+mWIG40 portfolio (pre-registered in
research/09_phase3_preregistration.md). Weekly rebalancing, fixed signal weights, FW20 beta hedge,
liquidity-dependent cost model from quant.portfolio.

Usage: python scripts/phase4_portfolio.py [--dry] [--with-idx] [variants...]
  variants: singles (REV MOM PEAD LVOL VAL [IDX]), EW, IV, WF, LO, NOBAND, LOO
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from quant import config, metrics, registry, research
from quant import portfolio as pf
from quant.data import stocks, store

OUT = config.REPORTS_DIR / "phase4"
EV = config.RAW_DIR / "events"
DRY = "--dry" in sys.argv
WITH_IDX = "--with-idx" in sys.argv
EVAL_START = pd.Timestamp("2010-07-01")
PERIODS = {"2010-2012": ("2010-07-01", "2012-12-31"), "2013-2017": ("2013-01-01", "2017-12-31"),
           "2018-2022H1": ("2018-01-01", "2022-06-30")}
REPORT_WINDOWS = [((2, 15), (4, 30)), ((4, 25), (5, 31)), ((7, 25), (9, 10)), ((10, 20), (11, 30))]
YAHOO_TO_GPW = {"PKO": "PKOBP", "PEO": "PEKAO", "PZU": "PZU", "KGH": "KGHM", "PKN": "PKNORLEN", "CDR": "CDPROJEKT",
                "LPP": "LPP", "DNP": "DINOPL", "ALE": "ALLEGRO", "MBK": "MBANK", "KTY": "KETY", "CPS": "CYFRPLSAT",
                "OPL": "ORANGEPL", "PGE": "PGE", "JSW": "JSW", "KRU": "KRUK", "BDX": "BUDIMEX", "PCO": "PEPCO",
                "ACP": "ASSECOPOL", "ALR": "ALIOR", "TPE": "TAURONPE", "ENG": "ENERGA", "BHW": "HANDLOWY",
                "ING": "INGBSK", "MIL": "MILLENNIUM", "EAT": "AMREST", "ENA": "ENEA", "BNP": "BNPPPL",
                "ATT": "GRUPAAZOTY", "GTC": "GTC", "BRS": "BORYSZEW", "LWB": "BOGDANKA"}


# ------------------------------------------------------------------ data
def load():
    P = stocks.load_panel()
    sess = P["ret"].index
    sess = sess[sess >= pd.Timestamp("2009-01-01")]
    P = {k: v.reindex(sess) for k, v in P.items()}
    m20, m40 = stocks.membership("WIG20", sess), stocks.membership("mWIG40", sess)
    cols = m20.columns.union(m40.columns)
    member = m20.reindex(columns=cols, fill_value=False) | m40.reindex(columns=cols, fill_value=False)
    cols = [c for c in cols if c in P["ret"]]
    P = {k: v.reindex(columns=cols) for k, v in P.items()}
    member = member[cols]
    tradable = member & (P["adv"] >= pf.CostModel().min_adv) & P["close"].notna()
    fw = research.fw20_daily()
    fw_r = np.log(fw["close"] / fw["prev_close"]).reindex(sess)
    wig = np.log(store.load_processed_research("wig")["close"]).diff().reindex(sess)
    r = np.log1p(P["ret"])
    def beta_vs(x):
        cov = r.rolling(250, min_periods=120).cov(x)
        return (cov.div(x.rolling(250, min_periods=120).var(), axis=0)).shift(1)
    beta_fw = beta_vs(fw_r).clip(0.2, 2.0)
    beta_wig = beta_vs(wig).clip(0.2, 2.0)
    return P, member, tradable, fw, wig, beta_fw, beta_wig


def zscore(df: pd.DataFrame, mask: pd.DataFrame) -> pd.DataFrame:
    x = df.where(mask)
    z = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    return z.clip(-3, 3)


def build_signals(P, tradable, wig, beta_wig, idx_signal=None) -> dict[str, pd.DataFrame]:
    r = np.log1p(P["ret"])
    resid = r - beta_wig.mul(wig, axis=0)
    sig = {}
    sig["REV"] = -resid.rolling(5, min_periods=4).sum()
    tri = r.fillna(0).cumsum()
    sig["MOM"] = (tri.shift(21) - tri.shift(252)).where(r.notna().rolling(252, min_periods=200).sum() >= 200)
    # PEAD proxy: first volume+return shock in a reporting season, sign held for 10 sessions
    sd = resid.rolling(120, min_periods=60).std().shift(1)
    shock = (P["turnover"] > 3 * P["turnover"].rolling(60, min_periods=30).median().shift(1)) & (resid.abs() > 2 * sd)
    idx = r.index
    md = idx.month * 100 + idx.day
    season = pd.Series(-1, index=idx)
    for k, ((m1, d1), (m2, d2)) in enumerate(REPORT_WINDOWS):
        season[(md >= m1 * 100 + d1) & (md <= m2 * 100 + d2)] = k
    key = pd.Series(idx.year * 10 + season.to_numpy(), index=idx)
    shock = shock & (season >= 0).to_numpy()[:, None]
    first = shock & (shock.astype(int).groupby(key).cumsum() == 1)
    ev_sign = np.sign(resid).where(first)
    sig["PEAD"] = ev_sign.ffill(limit=9).fillna(0.0)
    sig["LVOL"] = -P["vol"]
    # value proxy: trailing 12m dividend yield (Yahoo dividends, mapped to ISIN via GPW names)
    nm = stocks.names()
    name_to_isin = {v: k for k, v in nm.items()}
    div = pd.read_csv(EV / "dividends.csv", parse_dates=["ex_date"])
    dps = pd.DataFrame(0.0, index=idx, columns=P["close"].columns)
    for t, g in div.groupby("ticker"):
        isin = name_to_isin.get(YAHOO_TO_GPW.get(t, ""), None)
        if isin is None or isin not in dps:
            continue
        s = g.groupby("ex_date")["amount"].sum()
        s = s[(s.index >= idx[0]) & (s.index <= idx[-1])]
        dps.loc[dps.index[dps.index.searchsorted(s.index)], isin] += s.to_numpy()
    covered = [name_to_isin[YAHOO_TO_GPW[t]] for t in div["ticker"].unique()
               if YAHOO_TO_GPW.get(t) in name_to_isin and name_to_isin[YAHOO_TO_GPW[t]] in dps]
    ttm = dps.rolling(252, min_periods=1).sum()
    cov_mask = pd.DataFrame(False, index=idx, columns=dps.columns)
    cov_mask[covered] = True
    sig["VAL"] = (ttm / P["close"]).where(cov_mask)
    if idx_signal is not None:
        sig["IDX"] = idx_signal
    return {k: zscore(v, tradable) for k, v in sig.items()}


# ------------------------------------------------------------------ portfolio runs
def targets_from_score(score: pd.DataFrame, rebal: pd.DatetimeIndex, shortable: pd.DataFrame,
                       long_only: bool = False) -> pd.DataFrame:
    rows = {}
    for d in rebal:
        rows[d] = pf.build_weights(score.loc[d], shortable.loc[d], long_only=long_only)
    return pd.DataFrame(rows).T.reindex(columns=score.columns).fillna(0.0)


def evaluate(name: str, res: pf.PortfolioResult, perm_p: float | None, log: bool, notes: str = "",
             res2x: pf.PortfolioResult | None = None) -> dict:
    d = res.daily[res.daily.index >= EVAL_START]
    net, gross = d["net"], d["gross"]
    s = metrics.summary(net, None, gross, d["turnover"])
    s["n_trades"] = int(d["n_orders"].sum())
    s["cost_share_of_gross"] = float(d["cost"].sum() / gross.sum()) if gross.sum() > 0 else float("inf")
    s["subperiods"] = {k: round(metrics.sharpe(net[a:b]), 2) for k, (a, b) in PERIODS.items()}
    s["subperiods_gross"] = {k: round(metrics.sharpe(gross[a:b]), 2) for k, (a, b) in PERIODS.items()}
    n_tr = registry.n_trials() + 1
    dsr = metrics.deflated_sharpe(net.to_numpy(), n_tr, registry.trial_sharpes())
    s["dsr"], s["sr0_ann"] = dsr["dsr"], dsr["sr0_ann"]
    s["p_value"] = perm_p
    if res2x is not None:
        s["sharpe_2x"] = metrics.sharpe(res2x.daily.loc[res2x.daily.index >= EVAL_START, "net"])
    sub = list(s["subperiods"].values())
    gate = {"sharpe": s["sharpe"] > 1.0, "dsr": s["dsr"] > 0.95, "mdd": s["mdd"] < 0.20, "n_trades": s["n_trades"] >= 100,
            "perm": (perm_p is not None and perm_p < 0.01), "subperiods_pos": all(x > 0 for x in sub),
            "no_decay": sub[-1] >= 0.5 * np.mean(sub) if np.mean(sub) > 0 else False,
            "costs_2x": s.get("sharpe_2x", 0) > 0.5}
    s["gate"] = gate
    s["passed"] = all(gate.values())
    if log and not DRY:
        s["id"] = registry.log("multisignal", name, "portfolio", {"band": 0.005, "rebal": "weekly"}, "wf", s,
                               verdict="CANDIDATE" if s["passed"] else "reject", notes=notes[:900])
    print(f"{s.get('id', 'DRY')} {name:34s} SR net {s['sharpe']:+.2f} gross {s['sharpe_gross']:+.2f} "
          f"vol {s['ann_vol']:.1%} mdd {s['mdd']:.1%} turn/yr {s['turnover_ann']:.1f} orders {s['n_trades']} "
          f"cost/gross {s['cost_share_of_gross']:.0%} sub {s['subperiods']} perm p {perm_p} DSR {s['dsr']:.2f}", flush=True)
    return s


def permutation_p(score, rebal, shortable, P, fw, beta_fw, actual_sr, n=None, seed=config.SEED) -> float:
    """Null: at each rebalance the scores are randomly re-assigned among the tradable stocks (same
    constraints, same turnover regime). p = P(null net Sharpe >= actual)."""
    n = n or (3 if "--fast" in sys.argv else 60)
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n):
        sh = score.copy()
        for d in rebal:
            row = sh.loc[d]
            ok = row.notna().to_numpy()
            vals = row.to_numpy()[ok]
            rng.shuffle(vals)
            arr = row.to_numpy().copy()
            arr[ok] = vals
            sh.loc[d] = arr
        tg = targets_from_score(sh, rebal, shortable)
        rr = pf.run(tg, P, fw, beta_fw)
        null.append(metrics.sharpe(rr.daily.loc[rr.daily.index >= EVAL_START, "net"]))
    return float((1 + np.sum(np.array(null) >= actual_sr)) / (1 + n))


def main(variants: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    P, member, tradable, fw, wig, beta_fw, beta_wig = load()
    idx_sig = None
    if WITH_IDX:
        idx_sig = pd.read_parquet(OUT / "idx_signal.parquet").reindex(index=P["ret"].index, columns=P["ret"].columns)
    Z = build_signals(P, tradable, wig, beta_wig, idx_sig)
    shortable = tradable & (P["adv"] >= pf.CostModel().short_min_adv)
    rebal = pf.rebalance_days(P["ret"].index)
    rebal = rebal[rebal >= pd.Timestamp("2010-06-01")]
    names = list(Z)
    # correlations: mean cross-sectional Spearman of z-scores on rebalance days
    corr = pd.DataFrame(0.0, index=names, columns=names)
    for d in rebal:
        corr += pd.DataFrame({k: Z[k].loc[d] for k in names}).corr(method="spearman").fillna(0)
    corr /= len(rebal)
    corr.round(3).to_csv(OUT / "signal_corr_xs.csv")
    print("mean cross-sectional correlation of signals:\n", corr.round(2))
    results, single_daily = {}, {}

    def composite(weights: dict[str, float] | pd.DataFrame) -> pd.DataFrame:
        num = sum((Z[k].fillna(0) * (weights[k] if isinstance(weights, dict) else weights[k].reindex(Z[k].index).ffill().fillna(1.0).to_numpy()[:, None]))
                  for k in names)
        den = sum((Z[k].notna() * (weights[k] if isinstance(weights, dict) else weights[k].reindex(Z[k].index).ffill().fillna(1.0).to_numpy()[:, None]))
                  for k in names)
        return (num / den.replace(0, np.nan)).where(tradable)

    def run_and_eval(label, score, long_only=False, band=0.005, perm=True, notes=""):
        tg = targets_from_score(score, rebal, shortable, long_only)
        res = pf.run(tg, P, fw, beta_fw, band=band)
        res2 = pf.run(tg, P, fw, beta_fw, band=band, cost_mult=2.0)
        sr = metrics.sharpe(res.daily.loc[res.daily.index >= EVAL_START, "net"])
        p = permutation_p(score, rebal, shortable, P, fw, beta_fw, sr) if (perm and not long_only) else None
        s = evaluate(label, res, p, log=True, notes=notes, res2x=res2)
        results[label] = s
        res.daily.to_parquet(OUT / f"daily_{label.split()[0]}.parquet")
        return res

    if "singles" in variants:
        for k in names:
            res = run_and_eval(f"S-{k} single-signal L/S", Z[k].where(tradable), perm=True)
            single_daily[k] = res.daily
    if "EW" in variants:
        run_and_eval("B-EW equal-weight composite L/S", composite({k: 1.0 for k in names}),
                     notes="primary pre-registered portfolio")
    if "IV" in variants:
        g = pd.DataFrame({k: pd.read_parquet(OUT / f"daily_S-{k}.parquet")["gross"] for k in names})
        ivw = (1 / g.rolling(252, min_periods=126).std().shift(1)).reindex(P["ret"].index)
        run_and_eval("B-IV inverse-vol composite L/S", composite({k: ivw[k] for k in names}))
    if "WF" in variants:
        run_and_eval("B-WF ridge walk-forward weights (ESTIMATED)", composite(ridge_weights(Z, P, beta_wig, wig, rebal, names)),
                     notes="weights estimated walk-forward (yearly, pooled ridge, clipped >=0)")
    if "LO" in variants:
        run_and_eval("B-LO equal-weight long-only + FW20", composite({k: 1.0 for k in names}), long_only=True)
    if "NOBAND" in variants:
        run_and_eval("B-EW-noband equal-weight, no trade band", composite({k: 1.0 for k in names}), band=0.0, perm=False)
    if "LOO" in variants:
        for k in names:
            run_and_eval(f"B-EW-minus-{k} leave-one-out", composite({j: (0.0 if j == k else 1.0) for j in names}),
                         perm=False, notes="attribution diagnostic")
    prev = OUT / "results.json"
    allres = json.loads(prev.read_text()) if prev.exists() else {}
    allres.update(results)
    if not DRY:
        prev.write_text(json.dumps(allres, indent=2, default=str))


def ridge_weights(Z, P, beta_wig, wig, rebal, names) -> pd.DataFrame:
    """Yearly walk-forward: pooled ridge of next-5-session residual return on signal z-scores, trained on
    data whose labels end before Jan 1 of the year; coefficients clipped at 0 and normalised."""
    r = np.log1p(P["ret"])
    resid = r - beta_wig.mul(wig, axis=0)
    fwd = resid.rolling(5).sum().shift(-5)
    rows = []
    for d in rebal:
        X = pd.DataFrame({k: Z[k].loc[d] for k in names})
        X["y"] = fwd.loc[d]
        X["date"] = d
        rows.append(X.dropna(subset=["y"]))
    panel = pd.concat(rows)
    out = {}
    for y in range(2011, 2023):
        cut = pd.Timestamp(year=y, month=1, day=1) - pd.Timedelta(days=10)  # label (5 sessions) ends before Jan 1
        tr = panel[panel["date"] < cut]
        if len(tr) < 500:
            continue
        m = Ridge(alpha=100.0).fit(tr[names].fillna(0), tr["y"])
        w = np.clip(m.coef_, 0, None)
        w = w / w.sum() if w.sum() > 0 else np.ones(len(names)) / len(names)
        out[pd.Timestamp(year=y, month=1, day=1)] = dict(zip(names, w))
        print("WF ridge weights", y, {k: round(v, 2) for k, v in out[pd.Timestamp(year=y, month=1, day=1)].items()})
    return pd.DataFrame(out).T


if __name__ == "__main__":
    v = [a for a in sys.argv[1:] if not a.startswith("--")] or ["singles", "EW", "IV", "WF", "LO", "NOBAND", "LOO"]
    main(v)
