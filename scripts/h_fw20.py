"""FW20 hypothesis families. Usage: python scripts/h_fw20.py <VARIANT> [--no-screen]

Each variant is pre-specified here (grid and rationale) BEFORE it is run; every run is logged in
hypotheses_log.csv by quant.research.evaluate.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from quant import backtest as bt
from quant import research
from quant.strategies.common import hold_sessions
from quant.strategies.fw20 import FW20Signals, hold_signal
from quant.validation import param_grid

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LOG_SCREEN = "--no-screen" not in sys.argv


def run(family, name, events, fn, grid, notes=""):
    ev = research.evaluate(family, name, events, fn, grid, notes=notes, log_screen=LOG_SCREEN)
    print(ev.line())
    print(research.fmt_eval_md(ev))
    return ev


def main(variant: str):
    daily, events = research.fw20_events()
    S = FW20Signals(daily)
    close = lambda tgt: bt.decisions_at_close(events, tgt)  # noqa: E731
    intraday = lambda tgt: bt.decisions_intraday(events, tgt)  # noqa: E731

    # ------------------------------------------------------------ C: calendar
    if variant == "C1":  # turn-of-month: pension/salary inflows (OFE contributions historically ~ month start)
        run("calendar", "C1 turn-of-month long", events,
            lambda p: hold_sessions(events, S.tom_set(p["k_end"], p["n_start"])),
            param_grid({"k_end": [1, 2, 3], "n_start": [2, 3]}))
    elif variant == "C2":  # pre-holiday effect (documented internationally)
        run("calendar", "C2 pre-holiday long", events,
            lambda p: hold_sessions(events, S.pre_holiday_set()), [{}])

    # ------------------------------------------------------------ T: trend
    elif variant == "T1":  # time-series momentum, long/short
        run("trend", "T1 TSMOM sign(L-day return) L/S", events,
            lambda p: close(S.tsmom_close(p["lookback"])),
            param_grid({"lookback": [20, 60, 120, 250]}))
    elif variant == "T2":  # long-only MA filter (avoid bear markets)
        run("trend", "T2 long-only above MA(L)", events,
            lambda p: close(S.ma_filter_close(p["lookback"], long_only=True)),
            param_grid({"lookback": [50, 100, 200]}))

    # ------------------------------------------------------------ M: short-term mean reversion
    elif variant == "M1":
        run("meanrev", "M1 k-day z-move reversal, hold h", events,
            lambda p: close(S.reversal_close(p["k"], p["z"], p["hold"])),
            param_grid({"k": [1, 3, 5], "z": [1.5, 2.0], "hold": [3]}))
    elif variant == "M2":
        run("meanrev", "M2 RSI2 dip-buy in uptrend (long only)", events,
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
            run("leadlag", "L1 S&P(d-1) -> FW20 intraday d, thresholded", events,
                lambda p: intraday(p["dir"] * np.sign(x).where(x.abs() > p["z"] * sd, 0.0)),
                param_grid({"dir": [1, -1], "z": [0.5, 1.0]}))
        else:
            # gap surprise proxy: S&P move vs what FW20 already did in the overlapping US-open hour is
            # unknown, so use the residual of S&P(d-1) on FW20 close-to-close(d-1) (rolling beta, causal)
            y = S.ret.reindex(daily.index)
            beta = (x.rolling(250, min_periods=120).cov(y) / y.rolling(250, min_periods=120).var()).shift(1)
            resid = x - beta * y
            rsd = resid.rolling(60, min_periods=30).std()
            run("leadlag", "L2 S&P residual after PL close -> FW20 intraday d", events,
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
        run("leadlag", "L3 (DAX+S&P)(d) -> FW20 intraday d+1", events,
            lambda p: intraday(sig(p).fillna(0.0)), param_grid({"dir": [1, -1], "z": [0.5, 1.0]}))

    # ------------------------------------------------------------ F: FX / flows
    elif variant == "F1":
        # PLN appreciation over k days (foreign inflows) -> long FW20; NBP fixing 11:45 known at close d
        eur = research.load_nbp("eur")["close"]
        fx = np.log(eur.reindex(daily.index, method="ffill"))
        run("fx", "F1 -sign(EURPLN k-day change) -> FW20", events,
            lambda p: close(-np.sign(fx.diff(p["k"])).fillna(0.0)),
            param_grid({"k": [5, 20, 60]}))
    # ------------------------------------------------------------ X: machine learning
    elif variant == "X1":
        from quant.strategies import ml
        feats = ml.build_features(daily)
        lab = ml.label_next(events, daily.index)
        proba = ml.walk_forward_proba(feats, lab, research.FIRST_TEST_YEAR)
        edge = (proba - 0.5).fillna(0.0)
        run("ml", "X1 LightGBM next-day direction (yearly WF refit)", events,
            lambda p: close(np.sign(edge).where(edge.abs() > p["th"], 0.0)),
            param_grid({"th": [0.0, 0.02, 0.05]}),
            notes="49 features (FW20 price/vol/calendar, foreign closes, NBP FX); fixed hyperparams")
    else:
        raise SystemExit(f"unknown variant {variant}")


if __name__ == "__main__":
    for v in ARGS:
        main(v)
