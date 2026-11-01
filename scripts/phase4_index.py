"""Phase 3 / part A: index composition changes (WIG20, mWIG40, sWIG80), 2012-03 .. 2022-06.

Pre-registered in research/09_phase3_preregistration.md:
* events: additions / deletions at each revision whose announcement date is in the GPW Benchmark calendar
* windows: W1 = [announcement+1 .. revision day], W2 = [revision+1 .. revision+10]
* AR = stock total return (GPW 'Zmiana') - WIG return; expected signs: additions +/-, deletions -/+
* net = |AR in the expected direction| - 2 x per-side cost (commission + liquidity half-spread + slippage +
  impact at 40k PLN), deletions in W1 need a short (allowed only if ADV >= 10m PLN, + borrow)
12 registry entries (3 indices x 2 kinds x 2 windows). Usage: python scripts/phase4_index.py [--dry]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from quant import config, events, metrics, registry
from quant.data import stocks, store
from quant.portfolio import CostModel

OUT = config.REPORTS_DIR / "phase4"
EV = config.RAW_DIR / "events"
DRY = "--dry" in sys.argv
POS_PLN = 40_000.0


def per_side_cost(cm: CostModel, adv: float, vol: float) -> float:
    if not np.isfinite(adv) or adv < cm.min_adv:
        return np.nan
    hs = float(cm.half_spread(np.array([adv]))[0])
    return cm.commission + hs + cm.slippage_fixed + np.nan_to_num(vol) * np.sqrt(POS_PLN / adv)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    P = stocks.load_panel()
    ret, adv, vol = P["ret"], P["adv"], P["vol"]
    sess = ret.index
    wig = np.log(store.load_processed_research("wig")["close"]).diff()
    mkt = np.expm1(wig).reindex(sess)
    cal = pd.read_csv(EV / "index_calendar.csv", parse_dates=["date"])
    ann = cal[cal.kind == "announcement"]["date"].sort_values()
    rev = cal[cal.kind == "revision"]["date"].sort_values()
    pairs = pd.merge_asof(rev.to_frame("rev"), ann.to_frame("ann"), left_on="rev", right_on="ann")
    pairs = pairs[(pairs.rev < config.HOLDOUT_START) & pairs.ann.notna()]
    cm = CostModel()
    nm = stocks.names()
    rows = []
    for index in ("WIG20", "mWIG40", "sWIG80"):
        port = pd.read_csv(EV / f"{index.lower()}_portfolios.csv", parse_dates=["revision"])
        revs = sorted(port["revision"].unique())
        for _, pr in pairs.iterrows():
            r, a = pr.rev, pr.ann
            if r not in revs or revs.index(r) == 0:
                continue
            prev = revs[revs.index(r) - 1]
            old = set(port.loc[port.revision == prev, "isin"])
            new = set(port.loc[port.revision == r, "isin"])
            pa = sess.searchsorted(a, side="right")  # first session after the announcement
            prv = sess.searchsorted(r)
            if prv >= len(sess) or sess[prv] != r:
                continue
            for kind, isins in (("add", new - old), ("del", old - new)):
                for isin in isins:
                    if isin not in ret:
                        continue
                    ar = (ret[isin] - mkt)
                    w1 = ar.iloc[pa:prv + 1]
                    w2 = ar.iloc[prv + 1:prv + 11]
                    if w1.notna().sum() < 3 or w2.notna().sum() < 5:
                        continue
                    c = per_side_cost(cm, adv[isin].iloc[pa], vol[isin].iloc[pa])
                    rows.append({"index": index, "kind": kind, "isin": isin, "name": nm.get(isin, isin),
                                 "ann": a, "rev": r, "w1": float(np.log1p(w1.dropna()).sum()),
                                 "w2": float(np.log1p(w2.dropna()).sum()), "cost_side": c,
                                 "adv": adv[isin].iloc[pa], "n_w1": int(w1.notna().sum())})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "index_events.csv", index=False)
    out = []
    for index in ("WIG20", "mWIG40", "sWIG80"):
        for kind in ("add", "del"):
            t = tab[(tab["index"] == index) & (tab["kind"] == kind)]
            for win, sign in (("w1", +1 if kind == "add" else -1), ("w2", -1 if kind == "add" else +1)):
                s = events.summarize(t[win], sign)
                # net per event when trading in the expected direction: sign*AR - round trip - borrow if short
                short_needed = sign < 0
                ok = t["cost_side"].notna() & (~short_needed | (t["adv"] >= cm.short_min_adv))
                days = t["n_w1"] if win == "w1" else 10
                borrow = (cm.borrow_annual * days / 252) if short_needed else 0.0
                net = (sign * t[win] - 2 * t["cost_side"] - borrow)[ok]
                half = t.assign(y=t["rev"].dt.year)
                h1 = (sign * half.loc[half.y <= 2016, win]).mean()
                h2 = (sign * half.loc[half.y >= 2017, win]).mean()
                label = f"{index} {'addition' if kind == 'add' else 'deletion'} {'[ann+1, rev]' if win == 'w1' else '[rev+1, rev+10]'}"
                rec = {"index": index, "kind": kind, "window": win, "sign": sign, **s.as_dict(),
                       "net_mean": float(net.mean()) if len(net) else np.nan, "n_tradable": int(ok.sum()),
                       "signed_mean_2012_16": h1, "signed_mean_2017_22": h2}
                if not DRY:
                    rec["id"] = events.log_event("event_idx", label, win, s, (t["ann"].min(), t["rev"].max()),
                                                 notes=f"net(trade in expected dir)={rec['net_mean']:+.4f} "
                                                       f"N_tradable={rec['n_tradable']} halves={h1:+.4f}/{h2:+.4f}")
                out.append(rec)
                print(f"{rec.get('id', 'DRY')} {label:42s} N={s.n:3d} mean={s.mean:+.4f} CI=[{s.ci_lo:+.4f},{s.ci_hi:+.4f}] "
                      f"p={s.p:.4f} net={rec['net_mean']:+.4f} (n={rec['n_tradable']}) halves {h1:+.4f}/{h2:+.4f}")
    res = pd.DataFrame(out)
    if not DRY:
        reg = registry.load()
        allp = reg[reg["p_value"].notna() & (reg["stage"] != "holdout") & (reg["verdict"] != "INVALID")].copy()
        allp["bh_q05_all"] = metrics.benjamini_hochberg(allp["p_value"].astype(float).to_numpy(), 0.05)
        res = res.merge(allp[["id", "bh_q05_all"]], on="id", how="left")
        print(f"BH over {len(allp)} registry p-values:", res[["id", "bh_q05_all"]].to_dict("records"))
        res.to_csv(OUT / "index_summary.csv", index=False)




def build_idx_signal() -> None:
    """Signal for part B (only used if part A meets the pre-registered criterion): +1 for announced
    additions to WIG20/mWIG40, -1 for announced deletions, from the session after the announcement to the
    revision day inclusive (the position is decided at the close of each of these days)."""
    P = stocks.load_panel()
    sess = P["ret"].index
    cal = pd.read_csv(EV / "index_calendar.csv", parse_dates=["date"])
    ann = cal[cal.kind == "announcement"]["date"].sort_values()
    rev = cal[cal.kind == "revision"]["date"].sort_values()
    pairs = pd.merge_asof(rev.to_frame("rev"), ann.to_frame("ann"), left_on="rev", right_on="ann").dropna()
    sig = pd.DataFrame(0.0, index=sess, columns=P["ret"].columns)
    for index in ("WIG20", "mWIG40"):
        port = pd.read_csv(EV / f"{index.lower()}_portfolios.csv", parse_dates=["revision"])
        revs = sorted(port["revision"].unique())
        for _, pr in pairs.iterrows():
            if pr.rev not in revs or revs.index(pr.rev) == 0:
                continue
            prev = revs[revs.index(pr.rev) - 1]
            old, new = set(port.loc[port.revision == prev, "isin"]), set(port.loc[port.revision == pr.rev, "isin"])
            rows = (sess > pr.ann) & (sess < pr.rev)  # decided at close; revision-day close is too late
            for isin in new - old:
                if isin in sig:
                    sig.loc[rows, isin] = 1.0
            for isin in old - new:
                if isin in sig:
                    sig.loc[rows, isin] = -1.0
    sig.to_parquet(OUT / "idx_signal.parquet")
    print("idx signal non-zero days:", int((sig != 0).sum().sum()))


if __name__ == "__main__":
    if "--idx-signal" in sys.argv:
        build_idx_signal()
    else:
        main()
