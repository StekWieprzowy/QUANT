"""Catalog of pre-specified FW20 hypotheses (signal definitions + parameter grids).

Shared by the research scripts (research-period data) and the one-shot holdout runner (full data), so
the holdout evaluates exactly the code that was validated.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import research
from quant.strategies.common import hold_sessions
from quant.strategies.fw20 import FW20Signals
from quant.validation import param_grid


@dataclass
class Spec:
    family: str
    name: str
    events: pd.DataFrame
    fn: Callable[[dict], np.ndarray]
    grid: list[dict]
    notes: str = ""
    extra: dict = field(default_factory=dict)


def build(variant: str, daily: pd.DataFrame, events: pd.DataFrame) -> Spec:
    S = FW20Signals(daily)
    close = lambda tgt: bt.decisions_at_close(events, tgt)  # noqa: E731
    intraday = lambda tgt: bt.decisions_intraday(events, tgt)  # noqa: E731

    # ------------------------------------------------------------ C: calendar
    if variant == "C1":  # turn-of-month: pension/salary inflows (OFE contributions historically ~ month start)
        return Spec("calendar", "C1 turn-of-month long", events,
            lambda p: hold_sessions(events, S.tom_set(p["k_end"], p["n_start"])),
            param_grid({"k_end": [1, 2, 3], "n_start": [2, 3]}))
    elif variant == "C2":  # pre-holiday effect (documented internationally)
        return Spec("calendar", "C2 pre-holiday long", events,
            lambda p: hold_sessions(events, S.pre_holiday_set()), [{}])

    # ------------------------------------------------------------ T: trend
    elif variant == "T1":  # time-series momentum, long/short
        return Spec("trend", "T1 TSMOM sign(L-day return) L/S", events,
            lambda p: close(S.tsmom_close(p["lookback"])),
            param_grid({"lookback": [20, 60, 120, 250]}))
    elif variant == "T2":  # long-only MA filter (avoid bear markets)
        return Spec("trend", "T2 long-only above MA(L)", events,
            lambda p: close(S.ma_filter_close(p["lookback"], long_only=True)),
            param_grid({"lookback": [50, 100, 200]}))

    # ------------------------------------------------------------ M: short-term mean reversion
    elif variant == "M1":
        return Spec("meanrev", "M1 k-day z-move reversal, hold h", events,
            lambda p: close(S.reversal_close(p["k"], p["z"], p["hold"])),
            param_grid({"k": [1, 3, 5], "z": [1.5, 2.0], "hold": [3]}))
    elif variant == "M2":
        return Spec("meanrev", "M2 RSI2 dip-buy in uptrend (long only)", events,
            lambda p: close(S.rsi2_dip_close(p["rsi_th"])),
            param_grid({"rsi_th": [5, 10, 20]}))
    # ------------------------------------------------------------ L: lead-lag from foreign markets
    elif variant in ("L1", "L2"):
        # US session (S&P 500, close d-1, 22:00 CET) -> FW20 intraday on d. The overnight part is priced
        # in the open; question is whether the open under/over-reacts. dir=+1 continuation, -1 reversal.
        spx = research.align_foreign(research.load_yahoo("^GSPC"), daily.index, same_day=False)
        x = spx["ret"]
        sd = x.rolling(60, min_periods=30).std()
        if variant == "L1":
            return Spec("leadlag", "L1 S&P(d-1) -> FW20 intraday d, thresholded", events,
                lambda p: intraday(p["dir"] * np.sign(x).where(x.abs() > p["z"] * sd, 0.0)),
                param_grid({"dir": [1, -1], "z": [0.5, 1.0]}))
        else:
            # gap surprise proxy: S&P move vs what FW20 already did in the overlapping US-open hour is
            # unknown, so use the residual of S&P(d-1) on FW20 close-to-close(d-1) (rolling beta, causal)
            # FW20 close-to-close of d-1 (overlaps the US session d-1 until 17:00); NOT of the traded day d
            # (bug in H045-H049: y of day d leaked the traded session -> caught by quant.lookahead)
            y = S.ret.reindex(daily.index).shift(1)
            beta = (x.rolling(250, min_periods=120).cov(y) / y.rolling(250, min_periods=120).var()).shift(1)
            resid = x - beta * y
            rsd = resid.rolling(60, min_periods=30).std()
            return Spec("leadlag", "L2 S&P residual after PL close -> FW20 intraday d", events,
                lambda p: intraday(p["dir"] * np.sign(resid).where(resid.abs() > p["z"] * rsd, 0.0)),
                param_grid({"dir": [1, -1], "z": [0.5, 1.0]}))
    elif variant == "L3":
        # DAX/S&P close d (after FW20 close) -> FW20 from open d+1 held to close d+1 (intraday next day)
        # vs close-to-close: the gap is unavoidable; tests whether foreign momentum persists into the session
        dax = research.align_foreign(research.load_yahoo("^GDAXI"), daily.index, same_day=True)["ret"]
        spx = research.align_foreign(research.load_yahoo("^GSPC"), daily.index, same_day=True)["ret"]
        comb = (dax + spx) / 2
        sd = comb.rolling(60, min_periods=30).std()
        sig = lambda p: (p["dir"] * np.sign(comb).where(comb.abs() > p["z"] * sd, 0.0)).shift(1)  # noqa: E731
        return Spec("leadlag", "L3 (DAX+S&P)(d) -> FW20 intraday d+1", events,
            lambda p: intraday(sig(p).fillna(0.0)), param_grid({"dir": [1, -1], "z": [0.5, 1.0]}))

    # ------------------------------------------------------------ F: FX / flows
    elif variant == "F1":
        # PLN appreciation over k days (foreign inflows) -> long FW20; NBP fixing 11:45 known at close d
        eur = research.load_nbp("eur")["close"]
        fx = np.log(eur.reindex(daily.index, method="ffill"))
        return Spec("fx", "F1 -sign(EURPLN k-day change) -> FW20", events,
            lambda p: close(-np.sign(fx.diff(p["k"])).fillna(0.0)),
            param_grid({"k": [5, 20, 60]}))
    # ------------------------------------------------------------ O: open-interest positioning
    elif variant == "O1":
        # price and open interest rising together = new longs (trend-confirming); price up with OI falling =
        # short covering (weak). Long/short only when OI confirms the k-day move.
        oi = np.log(daily["oi"].replace(0, np.nan)).ffill()
        # OI resets at each roll (new contract) -> measure OI change within the held contract only
        def sig(p):
            k = p["k"]
            doi = oi.diff(k).where(daily["contract"].eq(daily["contract"].shift(k)))
            dp = S.ret.rolling(k).sum()
            return (np.sign(dp) * (doi > 0)).fillna(0.0)
        return Spec("positioning", "O1 OI-confirmed k-day trend", events,
                    lambda p: close(sig(p)), param_grid({"k": [5, 10, 20]}))

    # ------------------------------------------------------------ R: residual reversal, stock long / FW20 hedge
    elif variant == "R1":
        from quant.strategies import resid
        book, res = resid.build_book(daily)
        return Spec("resid", "R1 stock residual reversal, long stock / short beta*FW20", book,
                    resid.decision_fn_factory(book, res), param_grid({"k": [3, 5], "z_in": [1.5, 2.0]}),
                    notes="18 long-lived WIG20 names (survivorship bias); long-only stock leg, no borrow")

    elif variant == "R2":  # longer residual horizon: fewer, larger dislocations vs the same ~1% round trip
        from quant.strategies import resid
        book, res = resid.build_book(daily)
        return Spec("resid", "R2 stock residual reversal, 10-20d horizon", book,
                    resid.decision_fn_factory(book, res),
                    param_grid({"k": [10, 20], "z_in": [1.5, 2.0], "max_hold": [20]}),
                    notes="as R1, longer horizon")

    elif variant == "R3":  # Nagel (2012): reversal = liquidity provision premium, larger when vol is high
        from quant.strategies import resid
        book, res = resid.build_book(daily)
        vol = S.ret.rolling(20).std()
        high_vol = vol > vol.rolling(250, min_periods=120).median()
        return Spec("resid", "R3 residual reversal, entries only in high market-vol regime", book,
                    resid.decision_fn_factory(book, res, allow_entry=high_vol),
                    param_grid({"k": [5, 10], "z_in": [1.5, 2.0], "max_hold": [15]}),
                    notes="regime: FW20 20d vol > trailing 250d median (known at close d)")

    elif variant == "X2":  # ML trade selection for the residual-reversal instrument
        from quant.strategies import ml_resid, resid
        from quant.strategies.fw20 import hold_signal
        book, res = resid.build_book(daily)
        pan = ml_resid.panel(book.events, res, daily)
        pred = ml_resid.walk_forward_pred(pan, research.FIRST_TEST_YEAR)
        per = {t: pred[pan["ticker"].to_numpy() == t] for t in book.events}

        def fn(p):
            return {t: bt.decisions_at_close(ev, hold_signal((per[t] > p["theta"]).astype(float), ml_resid.H))
                    for t, ev in book.events.items()}
        return Spec("ml", "X2 LightGBM panel: select residual-reversal longs (5d hold)", book, fn,
                    param_grid({"theta": [0.010, 0.015]}),
                    notes="pred = 5d hedged gross return; enter only if pred > theta (~round-trip cost)")

    elif variant in ("P1", "P2"):  # same definitions as scripts/h_pairs.py (kept for the summary stats)
        from quant.strategies import pairs
        pbook, spreads = pairs.build_book(pairs.PAIRS)
        grid = param_grid({"lookback": [20, 60], "z_in": [1.5, 2.0]}) if variant == "P1" else \
            param_grid({"lookback": [60, 120], "z_in": [2.5, 3.0]})
        return Spec("pairs", f"{variant} z-score pairs book", pbook, pairs.decision_fn_factory(pbook, spreads), grid)

    elif variant == "E1":  # ensemble of the two permutation-significant relative-value edges (P1 + R2)
        from quant.strategies import pairs, resid
        pbook, spreads = pairs.build_book(pairs.PAIRS)
        rbook, res = resid.build_book(daily)
        pfn, rfn = pairs.decision_fn_factory(pbook, spreads), resid.decision_fn_factory(rbook, res)
        book = bt.Book({**pbook.events, **rbook.events},
                       borrow_annual={k: pbook.borrow_annual for k in pbook.events},
                       borrow_on_abs={k: True for k in pbook.events})
        return Spec("ensemble", "E1 P1 bank pairs + R2 residual reversal, equal capital slots", book,
                    lambda p: {**pfn({"lookback": 60, "z_in": p["pz"]}),
                               **rfn({"k": 20, "z_in": p["rz"], "max_hold": 20})},
                    param_grid({"pz": [1.5, 2.0], "rz": [1.5, 2.0]}))

    # ------------------------------------------------------------ CA: phase 2 part 1 - cost attack (same signal)
    elif variant in ("CA1", "CA2", "CA3", "CA6"):
        from quant.strategies import costattack as ca
        from quant.strategies import resid
        book, res = resid.build_book(daily)
        tick = list(book.events)
        liq = ca.liquid_masks(tick, 8) if variant in ("CA3", "CA6") else {t: None for t in tick}
        every = {"CA1": 1, "CA6": 2}.get(variant)
        days = {t: (ca.week_end_mask(res[t].index, every) if every else None) for t in tick}

        def fn(p):
            out = {}
            for t, ev in book.events.items():
                z = ca.resid_z(res[t], p["k"])
                pos = ca.positions(z, p["z_in"], p.get("z_exit", 0.5), p.get("max_hold", 20),
                                   entry_ok=liq[t], trade_days=days[t])
                out[t] = bt.decisions_at_close(ev, pos)
            return out
        spec = {
            "CA1": ("CA1 R weekly rebalance (entries/exits only on week-end)",
                    {"k": [10, 20], "z_in": [1.5, 2.0], "z_exit": [0.5], "max_hold": [20]}),
            "CA2": ("CA2 R hysteresis: exit only after full reversion/overshoot",
                    {"k": [10, 20], "z_in": [2.0], "z_exit": [0.0, -0.5], "max_hold": [40]}),
            "CA3": ("CA3 R liquid top-8 by trailing turnover",
                    {"k": [10, 20], "z_in": [1.5, 2.0], "z_exit": [0.5], "max_hold": [20]}),
            "CA6": ("CA6 R liquid top-8 + biweekly + hysteresis",
                    {"k": [10, 20], "z_in": [1.5, 2.0], "z_exit": [0.0], "max_hold": [40]}),
        }[variant]
        return Spec("costattack", spec[0], book, fn, param_grid(spec[1]),
                    notes="phase2 part1; stocks 0.39%/side + financing; same residual signal as R2")
    elif variant == "CA4":  # single-stock futures instead of shares (no borrow, no financing)
        from quant.strategies import costattack as ca
        evs, res, trad = {}, {}, {}
        for t, root in ca.SSF.items():
            evs[t], res[t], trad[t] = ca.ssf_hedged_events(root, daily, cost_per_side=0.0025)
        book = bt.Book(evs)

        def fn(p):
            return {t: bt.decisions_at_close(ev, ca.positions(
                ca.resid_z(res[t], p["k"]), p["z_in"], 0.5, 20, entry_ok=trad[t], trade_days=trad[t]))
                for t, ev in book.events.items()}
        return Spec("costattack", "CA4 R via GPW single-stock futures (0.25%/side assumed) + FW20 hedge", book, fn,
                    param_grid({"k": [10, 20], "z_in": [1.5, 2.0]}),
                    notes="9 SSF roots; cost scenario 0.10% comm + 0.15% slippage (thin books, unverified)")
    elif variant == "CA7":  # pairs restricted to the three most liquid WIG20 financials (tightest spreads)
        from quant.strategies import pairs
        pbook, spreads = pairs.build_book([("PKO", "PEO"), ("PKO", "PZU"), ("PEO", "PZU")])
        return Spec("costattack", "CA7 pairs, only most liquid names (PKO/PEO/PZU)", pbook,
                    pairs.decision_fn_factory(pbook, spreads), param_grid({"lookback": [20, 60], "z_in": [1.5, 2.0]}),
                    notes="same signal as P1; liquidity lever")
    elif variant == "CA5":  # pairs (L/S shares) with weekly rebalancing + hysteresis
        from quant.strategies import costattack as ca
        from quant.strategies import pairs
        pbook, spreads = pairs.build_book(pairs.PAIRS)

        def fn(p):
            out = {}
            for k, ev in pbook.events.items():
                sp = spreads[k]
                z = (sp - sp.rolling(p["lookback"]).mean()) / sp.rolling(p["lookback"]).std()
                # pairs: long spread when z < -z_in, short when z > z_in (positions() uses -z convention)
                pos = ca.positions(z, p["z_in"], 0.0, p["lookback"], trade_days=ca.week_end_mask(sp.index, 1),
                                   side="both")
                out[k] = bt.decisions_at_close(ev, pos)
            return out
        return Spec("costattack", "CA5 pairs weekly + exit at full reversion", pbook, fn,
                    param_grid({"lookback": [60, 120], "z_in": [1.5, 2.0]}))

    # ------------------------------------------------------------ K: monthly cross-sectional factors (hedged)
    elif variant in ("K1", "K2"):
        from quant.strategies import resid
        from quant.strategies.pairs import adjusted_stock
        book, res = resid.build_book(daily)
        closes = pd.DataFrame({t: adjusted_stock(t)["close"] for t in book.events}).reindex(daily.index)
        lr = np.log(closes).diff()
        month_end = S.cal["rank_end"] == 1

        def fn(p):
            if variant == "K1":  # 12-1 (or 6-1) month momentum: winners keep winning (Jegadeesh-Titman)
                score = np.log(closes.shift(21) / closes.shift(p["lookback"]))
            else:  # low volatility anomaly: low-vol stocks earn more per unit risk
                score = -lr.rolling(p["lookback"], min_periods=p["lookback"] // 2).std()
            score = score.where(closes.notna())
            rank = score.rank(axis=1, ascending=False)
            pick = (rank <= p["n"]).astype(float).where(month_end).ffill().fillna(0.0)
            return {t: bt.decisions_at_close(ev, pick[t].reindex(pd.DatetimeIndex(ev["date"].unique())).fillna(0.0))
                    for t, ev in book.events.items()}
        if variant == "K1":
            return Spec("factor", "K1 XS momentum top-n WIG20 names, hedged, monthly", book, fn,
                        param_grid({"lookback": [126, 252], "n": [4]}))
        return Spec("factor", "K2 low-volatility top-n WIG20 names, hedged, monthly", book, fn,
                    param_grid({"lookback": [60, 250], "n": [4]}))

    # ------------------------------------------------------------ G: FW20 vs DAX relative value
    elif variant in ("G1", "G2"):
        from quant.strategies import glob
        a = glob.aligned(daily)
        sev, res = glob.spread_events(a)
        if variant == "G1":  # hedged spread, both cheap futures
            return Spec("global_rv", "G1 FW20-beta*DAX spread reversion (hedged)", sev,
                        lambda p: bt.decisions_at_close(sev, glob.reversion_positions(
                            glob.residual_z(res, p["k"]), p["z_in"], 0.5, p["max_hold"])),
                        param_grid({"k": [5, 10], "z_in": [1.5, 2.0], "max_hold": [10]}),
                        notes="FDAX 3bps/side; DAX index as FDAX proxy")
        # G2: unhedged FW20 after PL under/over-performance vs DAX (one cheap leg, keeps market beta)
        z_pl = lambda p: glob.residual_z(res, p["k"]).reindex(daily.index).ffill()  # noqa: E731
        return Spec("global_rv", "G2 FW20 alone, reversal of residual vs DAX", events,
                    lambda p: close(glob.reversion_positions(z_pl(p).fillna(0.0), p["z_in"], 0.5, p["max_hold"])),
                    param_grid({"k": [5, 10], "z_in": [1.5, 2.0], "max_hold": [10]}))

    # ------------------------------------------------------------ X: machine learning
    elif variant == "X1":
        from quant.strategies import ml
        feats = ml.build_features(daily)
        lab = ml.label_next(events, daily.index)
        proba = ml.walk_forward_proba(feats, lab, research.FIRST_TEST_YEAR)
        edge = (proba - 0.5).fillna(0.0)
        return Spec("ml", "X1 LightGBM next-day direction (yearly WF refit)", events,
            lambda p: close(np.sign(edge).where(edge.abs() > p["th"], 0.0)),
            param_grid({"th": [0.0, 0.02, 0.05]}),
            notes="49 features (FW20 price/vol/calendar, foreign closes, NBP FX); fixed hyperparams")
    else:
        raise SystemExit(f"unknown variant {variant}")
