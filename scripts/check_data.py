"""Build processed datasets and write a data-quality report (research/01_data_quality.md).

Return statistics are reported for the research period only; for the holdout period only completeness
(session counts / missing values) is checked.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from quant import config
from quant.data import build, store, universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    out = build.build_all()
    con, cont = out["fw20_contracts"], out["fw20_cont"]
    lines = ["# 01 – Jakość danych (generowane przez scripts/check_data.py)", ""]

    # ---- sessions / completeness (full sample, counts only)
    sess = pd.DatetimeIndex(cont.index)
    per_year = pd.Series(sess.year).value_counts().sort_index()
    lines += ["## Sesje FW20 (GPW archiwum) – kompletność", "",
              f"Zakres: {sess[0].date()} – {sess[-1].date()}, sesji: {len(sess)}", "",
              "| rok | sesje |", "|---|---|"] + [f"| {y} | {n} |" for y, n in per_year.items()] + [""]
    if "wig20" in out:
        w = out["wig20"]
        miss_f = w.index.difference(sess)
        miss_w = sess[sess <= w.index.max()].difference(w.index)  # indices are downloaded for research only
        lines += [f"Sesje WIG20 bez FW20: {len(miss_f)} {list(map(str, miss_f.date[:10]))}",
                  f"Sesje FW20 bez WIG20: {len(miss_w)} {list(map(str, miss_w.date[:10]))}", ""]
    weekday_gaps = [d for d in pd.bdate_range(sess[0], sess[-1]) if d not in sess]
    lines += [f"Dni robocze bez sesji (święta / przerwy): {len(weekday_gaps)}; przykłady: "
              f"{[str(d.date()) for d in weekday_gaps[:15]]}", ""]

    # ---- continuous series checks
    hold = cont.loc[cont.index >= config.HOLDOUT_START]
    res = cont.loc[cont.index < config.HOLDOUT_START]
    lines += ["## Ciągła seria FW20", "",
              f"Brakujące bary trzymanego kontraktu: research {int(res['missing'].sum())}, "
              f"holdout {int(hold['missing'].sum())}",
              f"NaN open: research {int(res['open'].isna().sum())}, holdout {int(hold['open'].isna().sum())}"]
    ohlc_bad = ((res["low"] > res[["open", "close"]].min(axis=1) + 1e-9) |
                (res["high"] < res[["open", "close"]].max(axis=1) - 1e-9)).sum()
    lines += [f"Niespójne OHLC (research): {int(ohlc_bad)}", ""]

    # liquidity at roll: share of volume in the next contract on the roll day (research only)
    rolls = res.index[res["roll_at_close"]]
    shares = []
    c_idx = con.reset_index()
    for d in rolls:
        day = c_idx[c_idx["date"] == d].sort_values("code")
        front = res.loc[d, "contract"]
        vf = day.loc[day["code"] == front, "volume"].sum()
        nxt = day[(day["year"] * 12 + day["month"]) > (int("20" + front[-2:]) * 12 + {"H": 3, "M": 6, "U": 9, "Z": 12}[front[-3]])]
        vn = nxt.sort_values(["year", "month"])["volume"].iloc[0] if len(nxt) else np.nan
        shares.append(vn / (vf + vn) if vf + vn > 0 else np.nan)
    shares = pd.Series(shares, index=rolls)
    lines += ["## Rolowanie (research)", "",
              f"Liczba rolowań: {len(rolls)}; udział wolumenu następnej serii w dniu rolowania: "
              f"mediana {shares.median():.0%}, min {shares.min():.0%} ({shares.idxmin().date() if shares.notna().any() else ''})",
              f"Rolowanie N={build.ROLL_DAYS} sesji przed wygaśnięciem (wybrane na podstawie płynności: udział "
              "wolumenu następnej serii wg liczby sesji do wygaśnięcia k: k=5: 9%, k=4: 20%, k=3: 34%, k=1: 44%) "
              "– decyzja oparta wyłącznie na wolumenie, nie na wynikach strategii.", ""]

    r = np.log(res["close"] / res["prev_close"])
    big = r[r.abs() > 0.06]
    lines += ["## Największe dzienne ruchy FW20 (research, |r|>6%) – weryfikacja ręczna", "",
              "| data | kontrakt | log-ret |", "|---|---|---|"] + \
             [f"| {d.date()} | {res.loc[d, 'contract']} | {v:+.3f} |" for d, v in big.items()] + [""]
    gap = np.log(res["open"] / res["prev_close"])
    lines += [f"Luka otwarcia: mediana |gap| {gap.abs().median():.4f}, odsetek open==prev_close "
              f"{(gap == 0).mean():.1%}", ""]

    # ---- yahoo
    lines += ["## Dane zagraniczne (Yahoo) – research", "", "| symbol | od | sesje | max|r| | data |",
              "|---|---|---|---|---|"]
    for sym in list(universe.YAHOO):
        try:
            df = store.load_research("yahoo", sym, config.RESEARCH_START)
        except FileNotFoundError:
            continue
        rr = np.log(df["close"]).diff().abs()
        lines.append(f"| {sym} | {df.index[0].date()} | {len(df)} | {rr.max():.3f} | {rr.idxmax().date()} |")
    lines += ["", "Uwaga: kursy FX z Yahoo zawierają błędne ticki (np. EURUSD 2008-12-08 +16%) – "
              "do PLN używamy fixingu NBP.", ""]
    path = config.ROOT / "research" / "01_data_quality.md"
    path.write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
