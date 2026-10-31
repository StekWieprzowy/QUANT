"""Phase 2 / part 3: event studies (research period only, < 2022-07-01).

Every study below is PRE-SPECIFIED: event list, window(s) and hypothesised sign are fixed in code before
the numbers are computed. Each (event, window) is one registry row (family event_*). At the end
Benjamini-Hochberg is applied across all part-3 rows -> reports/phase3/event_summary.csv.

Usage: python scripts/phase3_events.py [study ...]   (default: all)
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy import stats

from quant import config, events, metrics, registry, research
from quant.data import futures, store
from quant.strategies.pairs import adjusted_stock

OUT = config.REPORTS_DIR / "phase3"
EV = config.RAW_DIR / "events"
RESULTS: list[dict] = []

BANKS = ["PKO", "PEO", "MBK", "BHW", "ING", "MIL"]
SOE = ["PKO", "PZU", "PKN", "PGE", "KGH", "TPE", "ENA", "JSW"]  # + PEO from 2017-06-07 (PZU/PFR take-over)
PRIVATE = ["MBK", "BHW", "ING", "MIL", "CPS", "LPP", "ACP", "CDR", "OPL"]


# ------------------------------------------------------------------ data helpers (research-truncated)
def fw20() -> pd.DataFrame:
    d = research.fw20_daily()
    d["r"] = np.log(d["close"] / d["prev_close"])
    d["r_id"] = np.log(d["close"] / d["open"])
    return d


def wig20_ret() -> pd.Series:
    w = store.load_processed_research("wig20")
    return np.log(w["close"]).diff()


def stock_ret(t: str, idx: pd.DatetimeIndex) -> pd.Series:
    s = adjusted_stock(t)
    return np.log(s["close"]).diff().reindex(idx)


DRY = "--dry" in sys.argv


def record(study: str, hypothesis: str, window: str, s: events.Summary, sign: int, sample, notes: str = ""):
    hid = "DRY" if DRY else events.log_event(f"event_{study}", hypothesis, window, s, sample, notes)
    RESULTS.append({"id": hid, "study": study, "hypothesis": hypothesis, "window": window, "sign": sign,
                    **s.as_dict()})
    print(f"{hid} {study:10s} {hypothesis[:60]:60s} {window:10s} N={s.n:4d} mean={s.mean:+.4f} "
          f"CI=[{s.ci_lo:+.4f},{s.ci_hi:+.4f}] p={s.p:.4f} hit={s.hit:.2f}", flush=True)


# ------------------------------------------------------------------ studies
def rpp():
    """RPP rate changes. Decision = session before the effective date. Cuts expected +, hikes - for FW20;
    banks (NIM) expected + on hikes, - on cuts (abnormal vs WIG20)."""
    f = fw20()
    rates = pd.read_csv(EV / "nbp_rates.csv", parse_dates=["effective"])
    rates = rates[(rates["change"].fillna(0) != 0) & (rates["effective"] >= "2005-01-01")]
    sess = f.index
    pos = sess.searchsorted(rates["effective"]) - 1
    ok = (pos >= 0) & (pos < len(sess))
    dec = pd.DataFrame({"date": sess[pos[ok]], "dir": np.sign(rates["change"].to_numpy()[ok])})
    dec = dec[dec["date"] < config.HOLDOUT_START]
    cuts, hikes = dec[dec["dir"] < 0]["date"], dec[dec["dir"] > 0]["date"]
    w = {"d0_1": (0, 1), "post1_5": (1, 5)}
    tc = events.car_table(f["r"], cuts, w)
    th = events.car_table(f["r"], hikes, w)
    record("rpp", "FW20 reaction to RPP cut", "[0,+1]", events.summarize(tc["d0_1"], +1), +1, (cuts.min(), cuts.max()))
    record("rpp", "FW20 reaction to RPP hike", "[0,+1]", events.summarize(th["d0_1"], -1), -1, (hikes.min(), hikes.max()))
    # banks: average abnormal return per event across available banks
    m = wig20_ret()
    br = {b: stock_ret(b, m.index) for b in BANKS}
    for name, dates, sign in [("hike", hikes, +1), ("cut", cuts, -1)]:
        per = [events.car_table(br[b], dates, {"x": (0, 1)}, m).set_index("event_date")["x"] for b in BANKS]
        avg = pd.concat(per, axis=1).mean(axis=1)
        record("rpp", f"Banks abnormal return on RPP {name}", "[0,+1]", events.summarize(avg, sign), sign,
               (dates.min(), dates.max()), notes="avg of 6 banks per event, market model vs WIG20")
    both = pd.concat([tc.assign(s=1), th.assign(s=-1)])
    record("rpp", "FW20 post-decision drift in direction of easing (signed)", "[+1,+5]",
           events.summarize(both["post1_5"] * both["s"], +1), +1, (dec["date"].min(), dec["date"].max()),
           notes="signed: cut=+1, hike=-1; tradable from close of decision day")
    pd.concat([tc.assign(kind="cut"), th.assign(kind="hike")]).to_csv(OUT / "rpp_detail.csv", index=False)


def dividends():
    """Ex-dividend: total-return abnormal return on ex-day (>0 = price falls less than the dividend);
    pre-ex run-up (dividend capture demand) and post-ex reversal."""
    m = wig20_ret()
    div = pd.read_csv(EV / "dividends.csv", parse_dates=["ex_date"])
    div = div[(div["ex_date"] >= "2005-03-01") & (div["ex_date"] < config.HOLDOUT_START)]
    rows = []
    for t, g in div.groupby("ticker"):
        try:
            r = stock_ret(t, m.index)
            raw = store.load_research("yahoo", f"{t}.WA")
        except FileNotFoundError:
            continue
        tab = events.car_table(r, g["ex_date"], {"pre": (-10, -1), "d0": (0, 0), "post": (1, 10)}, m)
        if tab.empty:
            continue
        prev_close = raw["close"].reindex(m.index).ffill().shift(1)
        tab["yield"] = [g.loc[g["ex_date"] == e, "amount"].iloc[0] / prev_close.get(d0, np.nan)
                        for e, d0 in zip(tab["event_date"], tab["day0"])]
        tab["ticker"] = t
        rows.append(tab)
    tab = pd.concat(rows)
    tab.to_csv(OUT / "dividends_detail.csv", index=False)
    rng = (tab["day0"].min(), tab["day0"].max())
    record("dividend", "Ex-day abnormal total return (price drop < dividend)", "[0]", events.summarize(tab["d0"], +1), +1, rng)
    record("dividend", "Pre-ex run-up (dividend capture demand)", "[-10,-1]", events.summarize(tab["pre"], +1), +1, rng)
    record("dividend", "Post-ex reversal", "[+1,+10]", events.summarize(tab["post"], -1), -1, rng)
    hy = tab[tab["yield"] > 0.04]
    record("dividend", "Ex-day abnormal total return, yield > 4%", "[0]", events.summarize(hy["d0"], +1), +1, rng)


def index_changes():
    """WIG20 additions/deletions, day0 = revision Friday (index funds trade at its close).
    Market-adjusted returns (r_i - r_WIG20) from official GPW quotes (no survivorship bias)."""
    port = pd.read_csv(EV / "wig20_portfolios.csv", parse_dates=["revision"])
    revs = sorted(port["revision"].unique())
    q = pd.concat([pd.read_parquet(f) for f in sorted((EV / "gpw_t10").glob("*.parquet"))])
    q["close"] = pd.to_numeric(q["close"], errors="coerce")
    q = q[q["close"] > 0]
    px = q.pivot_table(index="date", columns="isin", values="close", aggfunc="last").sort_index()
    m = wig20_ret()
    rows = []
    for a, r in zip(revs[:-1], revs[1:]):
        if r >= config.HOLDOUT_START:
            break
        old, new = set(port.loc[port.revision == a, "isin"]), set(port.loc[port.revision == r, "isin"])
        for kind, isins in (("add", new - old), ("del", old - new)):
            for isin in isins:
                if isin not in px:
                    continue
                s = px[isin].dropna()
                sess = s.index
                p0 = sess.searchsorted(r)
                if p0 >= len(sess) or abs((sess[p0] - r).days) > 3:
                    continue
                rr = np.log(s).diff()
                ar = rr - m.reindex(sess)
                def w(lo, hi):
                    return float(ar.iloc[p0 + lo:p0 + hi + 1].sum()) if p0 + lo >= 1 and p0 + hi < len(sess) else np.nan
                rows.append({"revision": r, "kind": kind, "isin": isin,
                             "name": port.loc[port["isin"] == isin, "name"].iloc[0],
                             "pre": w(-10, -1), "d0": w(0, 0), "post": w(1, 10)})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "index_changes_detail.csv", index=False)
    rng = (tab["revision"].min(), tab["revision"].max())
    for kind, sgn in (("add", +1), ("del", -1)):
        t = tab[tab["kind"] == kind]
        lab = "addition to" if kind == "add" else "deletion from"
        record("index", f"WIG20 {lab}: pre-revision drift", "[-10,-1]", events.summarize(t["pre"], sgn), sgn, rng)
        record("index", f"WIG20 {lab}: revision-day close", "[0]", events.summarize(t["d0"], sgn), sgn, rng)
        record("index", f"WIG20 {lab}: post-revision reversal", "[+1,+10]", events.summarize(t["post"], -sgn), -sgn, rng)


ELECTIONS = [  # decisive vote, winner camp (PiS / PO); pl.wikipedia (Wybory parlamentarne/prezydenckie w Polsce)
    ("2005-09-25", "PiS"), ("2005-10-23", "PiS"), ("2007-10-21", "PO"), ("2010-07-04", "PO"),
    ("2011-10-09", "PO"), ("2015-05-24", "PiS"), ("2015-10-25", "PiS"), ("2019-10-13", "PiS"), ("2020-07-12", "PiS")]


def elections():
    """SOE minus private basket on the first session after a decisive election.
    H1: larger than normal moves (|z| > E|N(0,1)|). H2: SOE underperform after PiS wins / outperform after PO
    wins (more state interference expected under PiS) -> signed spread > 0."""
    m = wig20_ret()
    idx = m.index
    R = {t: stock_ret(t, idx) for t in set(SOE + PRIVATE + ["PEO"])}
    soe_cols = pd.DataFrame({t: R[t] for t in SOE})
    soe_cols["PEO"] = R["PEO"].where(idx >= "2017-06-07")
    priv = pd.DataFrame({t: R[t] for t in PRIVATE})
    priv["PEO"] = R["PEO"].where(idx < "2017-06-07")
    spread = soe_cols.mean(axis=1) - priv.mean(axis=1)
    rows = []
    for d, camp in ELECTIONS:
        p0 = idx.searchsorted(pd.Timestamp(d))
        sd = spread.iloc[max(p0 - 250, 0):p0].std()
        rows.append({"election": d, "winner": camp, "d0": spread.iloc[p0], "z0": spread.iloc[p0] / sd,
                     "d0_5": spread.iloc[p0:p0 + 6].sum(), "sign": -1 if camp == "PiS" else 1})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "elections_detail.csv", index=False)
    rng = (ELECTIONS[0][0], ELECTIONS[-1][0])
    record("election", "|SOE-private| z-score above normal (E|z|=0.80)", "[0]",
           events.summarize(tab["z0"].abs() - np.sqrt(2 / np.pi), +1), +1, rng, notes="units: z-score excess")
    record("election", "SOE underperform after PiS win / outperform after PO win (signed)", "[0,+5]",
           events.summarize(tab["d0_5"] * tab["sign"], +1), +1, rng)


CHF_EVENTS = ["2015-01-15", "2019-05-14", "2019-10-03", "2021-04-29", "2021-05-07"]
# SNB floor removal; AG Tanchev opinion & CJEU Dziubak C-260/18; CJEU C-19/20; SN resolution III CZP 6/21


def chf():
    m = wig20_ret()
    exposed = ["MBK", "MIL", "PKO"]
    per = [events.car_table(stock_ret(b, m.index), CHF_EVENTS, {"x": (0, 1)}, m).set_index("event_date")["x"]
           for b in exposed]
    avg = pd.concat(per, axis=1).mean(axis=1)
    ctrl = [events.car_table(stock_ret(b, m.index), CHF_EVENTS, {"x": (0, 1)}, m).set_index("event_date")["x"]
            for b in ["BHW", "ING", "PEO"]]
    pd.concat([pd.concat(per, axis=1).set_axis(exposed, axis=1), pd.concat(ctrl, axis=1).set_axis(["BHW", "ING", "PEO"], axis=1)],
              axis=1).to_csv(OUT / "chf_detail.csv")
    record("chf", "CHF-exposed banks (MBK, MIL, PKO) on CHF rulings/shocks", "[0,+1]", events.summarize(avg, -1), -1,
           (CHF_EVENTS[0], CHF_EVENTS[-1]), notes="5 events; controls BHW/ING/PEO in detail file")


def kghm():
    """H19: KGHM session (open->close) on d under-reacts to copper's move on d-1 (COMEX closes after GPW).
    H20: slow diffusion - past 20d copper(PLN) return not yet in KGH predicts next 20d abnormal return."""
    m = wig20_ret()
    idx = m.index
    kgh = adjusted_stock("KGH").reindex(idx)
    cu = research.align_foreign(research.load_yahoo("HG=F"), idx, same_day=False)["ret"]  # known before open d
    kgh_id = np.log(kgh["close"] / kgh["open"])
    df = pd.DataFrame({"y": kgh_id, "x": cu}).dropna()
    df = df[df["x"] != 0]
    sl = stats.linregress(df["x"], df["y"])
    s = events.Summary(len(df), sl.slope, np.nan, sl.stderr, sl.slope / sl.stderr, sl.pvalue,
                       sl.slope - 1.96 * sl.stderr, sl.slope + 1.96 * sl.stderr, float((np.sign(df.x) == np.sign(df.y)).mean()))
    record("kghm", "KGH open->close on d vs copper return d-1 (slope)", "[0] slope", s, +1, (df.index[0], df.index[-1]),
           notes="slope of intraday KGH log-ret on prior-day copper log-ret; >0 = under-reaction at open")
    usd = np.log(research.load_nbp("usd")["close"].reindex(idx, method="ffill"))
    cu_lvl = np.log(research.align_foreign(research.load_yahoo("HG=F"), idx, same_day=True)["value"]) + usd
    kr = np.log(kgh["close"]).diff()
    beta = (kr.rolling(250, min_periods=120).cov(m) / m.rolling(250, min_periods=120).var()).shift(1)
    ar = kr - beta * m
    gap = cu_lvl.diff(20) - ar.rolling(20).sum()  # copper move not reflected in KGH residual
    fwd = ar.rolling(20).sum().shift(-20)
    sub = pd.DataFrame({"g": gap, "f": fwd}).dropna().iloc[::20]  # non-overlapping
    ic = stats.spearmanr(sub["g"], sub["f"])
    n = len(sub)
    se = 1 / np.sqrt(n - 3)
    s = events.Summary(n, ic.statistic, np.nan, se, ic.statistic / se, ic.pvalue, ic.statistic - 1.96 * se,
                       ic.statistic + 1.96 * se, float((np.sign(sub.g) == np.sign(sub.f)).mean()))
    record("kghm", "Copper(PLN) 20d move not in KGH -> KGH next 20d abnormal (rank IC)", "IC 20d", s, +1,
           (sub.index[0], sub.index[-1]), notes="non-overlapping 20d blocks")


def orlen():
    """Refining margin (3-2-1 crack proxy from RBOB, heating oil, Brent) change over 20d -> PKN next 20d
    abnormal return (slow pricing of margin news)."""
    m = wig20_ret()
    idx = m.index
    get = lambda s: research.align_foreign(research.load_yahoo(s), idx, same_day=True)["value"]  # noqa: E731
    crack = (2 * get("RB=F") * 42 + get("HO=F") * 42 - 3 * get("BZ=F")) / 3
    pkn = np.log(adjusted_stock("PKN")["close"].reindex(idx)).diff()
    beta = (pkn.rolling(250, min_periods=120).cov(m) / m.rolling(250, min_periods=120).var()).shift(1)
    ar = pkn - beta * m
    sub = pd.DataFrame({"g": crack.diff(20), "f": ar.rolling(20).sum().shift(-20)}).dropna().iloc[::20]
    ic = stats.spearmanr(sub["g"], sub["f"])
    n = len(sub)
    se = 1 / np.sqrt(n - 3)
    s = events.Summary(n, ic.statistic, np.nan, se, ic.statistic / se, ic.pvalue, ic.statistic - 1.96 * se,
                       ic.statistic + 1.96 * se, float((np.sign(sub.g) == np.sign(sub.f)).mean()))
    record("orlen", "Crack spread 20d change -> PKN next 20d abnormal (rank IC)", "IC 20d", s, +1,
           (sub.index[0], sub.index[-1]), notes="crack proxy (2*RB+HO-3*Brent)/3 $/bbl; Brent from 2007-07")


CDR_RELEASES = ["2015-05-19", "2015-10-13", "2016-05-31", "2018-10-23", "2020-12-10"]  # W3, HoS, B&W, Thronebreaker, CP2077
CDR_DELAYS = ["2020-01-16", "2020-06-18", "2020-10-27"]  # Cyberpunk 2077 postponements


def cdr():
    m = wig20_ret()
    r = stock_ret("CDR", m.index)
    tab = events.car_table(r, CDR_RELEASES, {"pre": (-20, -1), "post": (0, 10)}, m)
    dl = events.car_table(r, CDR_DELAYS, {"d0_1": (0, 1)}, m)
    pd.concat([tab.assign(kind="release"), dl.assign(kind="delay")]).to_csv(OUT / "cdr_detail.csv", index=False)
    rng = (CDR_RELEASES[0], CDR_RELEASES[-1])
    record("cdr", "CD Projekt run-up before game release", "[-20,-1]", events.summarize(tab["pre"], +1), +1, rng)
    record("cdr", "CD Projekt 'sell the news' after release", "[0,+10]", events.summarize(tab["post"], -1), -1, rng)
    record("cdr", "CD Projekt reaction to Cyberpunk delay", "[0,+1]", events.summarize(dl["d0_1"], -1), -1,
           (CDR_DELAYS[0], CDR_DELAYS[-1]))


def expiry():
    """FW20 around quarterly expiry (3rd Friday Mar/Jun/Sep/Dec; also WIG20 options). Welch test of the
    group's daily returns vs all other days (difference in means)."""
    f = fw20()
    sess = f.index
    sched = futures.expiry_schedule(sess, 2005, 2022)
    exp = [e for e in sched["expiry"] if e in sess and e < config.HOLDOUT_START]
    lab = pd.Series("other", index=sess)
    for e in exp:
        p = sess.get_loc(e)
        lab.iloc[max(p - 4, 0):p] = "week_before"
        lab.iloc[p] = "expiry_day"
        lab.iloc[p + 1:p + 6] = "week_after"
    f["lab"] = lab
    f.groupby("lab")["r"].agg(["count", "mean", "std"]).to_csv(OUT / "expiry_detail.csv")
    f = f.dropna(subset=["r"])
    other = f.loc[f["lab"] == "other", "r"]
    for g, name in [("week_before", "Mon-Thu before expiry"), ("expiry_day", "expiry Friday"),
                    ("week_after", "5 sessions after expiry")]:
        x = f.loc[f["lab"] == g, "r"]
        t, p = stats.ttest_ind(x, other, equal_var=False)
        d = x.mean() - other.mean()
        se = d / t if t else np.nan
        s = events.Summary(len(x), d, float(x.median()), float(x.std()), float(t), float(p), d - 1.96 * abs(se),
                           d + 1.96 * abs(se), float((x > 0).mean()))
        record("expiry", f"FW20 daily return {name} vs other days", "diff", s, 0, (sess[0], sess[-1]),
               notes="two-sided; mean is difference of daily means")


def fx_shock():
    """PLN shock days: NBP EUR/PLN fixing change beyond 2 sigma (trailing 250d) -> FW20 next 5 sessions.
    Two-sided (continuation via foreign outflows vs reversal). Events de-clustered (>=5 sessions apart)."""
    f = fw20()
    eur = np.log(research.load_nbp("eur")["close"]).diff()
    z = eur / eur.rolling(250, min_periods=120).std().shift(1)
    z = z.reindex(f.index)
    for name, mask in (("PLN depreciation shock (EURPLN +2sd)", z > 2), ("PLN appreciation shock (EURPLN -2sd)", z < -2)):
        dates, last = [], None
        for d in z.index[mask.fillna(False)]:
            if last is None or f.index.get_loc(d) - f.index.get_loc(last) >= 5:
                dates.append(d)
                last = d
        tab = events.car_table(f["r"], dates, {"post": (1, 5)})
        record("fx", f"FW20 after {name}", "[+1,+5]", events.summarize(tab["post"], +1), 0,
               (dates[0], dates[-1]), notes="two-sided; fixing 11:45 known before close of day 0")


def kghm_bigcopper():
    """Actionable version of H183 for a discretionary trader: only sessions after a large copper move
    (|copper d-1| > 2 sd, trailing 250d). Abnormal KGH open->close (minus WIG20 open->close) signed by the
    copper move. Tradable only if the mean exceeds a round trip (~0.5-0.8%)."""
    w = store.load_processed_research("wig20")
    idx = w.index
    kgh = adjusted_stock("KGH").reindex(idx)
    cu = research.align_foreign(research.load_yahoo("HG=F"), idx, same_day=False)["ret"]
    sd = cu.rolling(250, min_periods=120).std().shift(1)
    big = cu.abs() > 2 * sd
    y = (np.log(kgh["close"] / kgh["open"]) - np.log(w["close"] / w["open"])) * np.sign(cu)
    x = y[big].dropna()
    x.to_csv(OUT / "kghm_bigcopper_detail.csv")
    record("kghm", "KGH session vs WIG20 after |copper d-1| > 2sd, signed by copper", "[0] O->C",
           events.summarize(x, +1), +1, (x.index[0], x.index[-1]))


def stability_confirmed():
    """Descriptive (not logged): sub-period means for the findings that survived BH."""
    rows = []
    d = pd.read_csv(OUT / "dividends_detail.csv", parse_dates=["day0"])
    for a, b in [("2005", "2012"), ("2013", "2017"), ("2018", "2022")]:
        s = d[(d.day0 >= a) & (d.day0 <= b + "-12-31")]["d0"]
        rows.append({"finding": "ex-div AR d0", "period": f"{a}-{b}", "n": len(s), "mean": s.mean(), "p": stats.ttest_1samp(s, 0).pvalue})
    w = store.load_processed_research("wig20")
    idx = w.index
    kgh = adjusted_stock("KGH").reindex(idx)
    cu = research.align_foreign(research.load_yahoo("HG=F"), idx, same_day=False)["ret"]
    y = np.log(kgh["close"] / kgh["open"])
    for a, b in [("2005", "2012"), ("2013", "2017"), ("2018", "2022")]:
        df = pd.DataFrame({"y": y, "x": cu})[a:b].dropna()
        df = df[df.x != 0]
        sl = stats.linregress(df.x, df.y)
        rows.append({"finding": "KGH O->C on copper d-1 slope", "period": f"{a}-{b}", "n": len(df), "mean": sl.slope, "p": sl.pvalue})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "stability_confirmed.csv", index=False)
    print(out.round(4).to_string())


REPORT_WINDOWS =[((2, 15), (4, 30)), ((4, 25), (5, 31)), ((7, 25), (9, 10)), ((10, 20), (11, 30))]


def earnings_proxy():
    """No free source of report dates (ESPI/PAP not accessible). Causal proxy: within statutory reporting
    seasons, the FIRST session where volume > 3x its trailing 60d median AND |abnormal return| > 2 sd
    (all known at the close of that day). H: post-announcement drift continues the day-0 move (PEAD),
    tested on [+1,+10] signed by sign(AR0)."""
    from quant.strategies.resid import UNIVERSE
    m = wig20_ret()
    idx = m.index
    rows = []
    for t in UNIVERSE:
        raw = research.load_yahoo(f"{t}.WA")
        raw = raw[raw["volume"] > 0].reindex(idx)
        r = stock_ret(t, idx)
        beta = (r.rolling(250, min_periods=120).cov(m) / m.rolling(250, min_periods=120).var()).shift(1)
        ar = r - beta * m
        sd = ar.rolling(120, min_periods=60).std().shift(1)
        vol_ok = raw["volume"] > 3 * raw["volume"].rolling(60, min_periods=30).median().shift(1)
        trig = vol_ok & (ar.abs() > 2 * sd)
        season = pd.Series(-1, index=idx)
        for k, ((m1, d1), (m2, d2)) in enumerate(REPORT_WINDOWS):
            md = idx.month * 100 + idx.day
            season[(md >= m1 * 100 + d1) & (md <= m2 * 100 + d2)] = k
        key = (idx.year * 10 + season).to_numpy()
        seen = set()
        for i in np.flatnonzero(trig.fillna(False).to_numpy() & (season.to_numpy() >= 0)):
            if key[i] in seen or i + 10 >= len(idx):
                continue
            seen.add(key[i])
            rows.append({"ticker": t, "day0": idx[i], "ar0": ar.iloc[i], "post": ar.iloc[i + 1:i + 11].sum()})
    tab = pd.DataFrame(rows).dropna()
    tab.to_csv(OUT / "earnings_proxy_detail.csv", index=False)
    record("earnings", "Post-earnings-proxy drift continues day-0 move (PEAD)", "[+1,+10]",
           events.summarize(tab["post"] * np.sign(tab["ar0"]), +1), +1, (tab["day0"].min(), tab["day0"].max()),
           notes="event = first volume>3x & |AR|>2sd day in reporting season (proxy for report dates)")


STUDIES = {"rpp": rpp, "earnings": earnings_proxy, "kghm_big": kghm_bigcopper, "stability": stability_confirmed, "dividends": dividends, "index": index_changes, "elections": elections, "chf": chf,
           "kghm": kghm, "orlen": orlen, "cdr": cdr, "expiry": expiry, "fx": fx_shock}


def summarize_all():
    reg = registry.load()
    ev = reg[reg["stage"] == "event"].copy()
    ev["p_value"] = ev["p_value"].astype(float)
    ev["bh_q05"] = metrics.benjamini_hochberg(ev["p_value"].fillna(1).to_numpy(), 0.05)
    n = len(ev)
    ev["bonferroni_sig"] = ev["p_value"] < 0.05 / max(n, 1)
    ev.to_csv(OUT / "event_summary.csv", index=False)
    print(ev[["id", "family", "hypothesis", "variant", "n_trades", "p_value", "bh_q05"]].to_string())


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [a for a in sys.argv[1:] if not a.startswith("--")] or \
        [k for k in STUDIES if k not in ("kghm_big", "stability")]
    for name in todo:
        if name == "summary":
            continue
        STUDIES[name]()
    if DRY:
        sys.exit(0)
    if RESULTS and not DRY:
        prev = OUT / "event_results.csv"
        old = pd.read_csv(prev) if prev.exists() else pd.DataFrame()
        pd.concat([old, pd.DataFrame(RESULTS)]).to_csv(prev, index=False)
    summarize_all()
