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
