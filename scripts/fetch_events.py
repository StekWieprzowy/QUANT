"""Download event data for phase 2 / part 3 into data/raw/events (polite, ~1 req/s).

* NBP interest-rate history (static.nbp.pl XML) -> nbp_rates.csv (effective dates; decision = previous session)
* WIG20 historical portfolios after each quarterly revision (gpwbenchmark.pl PDFs) -> wig20_portfolios.csv
* Dividends (ex-dates, amounts) of the WSE stock universe from the Yahoo chart API -> dividends.csv
* Extra commodity series (silver, heating oil, gasoline) -> data/raw/yahoo
"""
from __future__ import annotations

import io
import json
import re
import time

import pandas as pd
import requests

from quant import config
from quant.data import sources, store, universe

OUT = config.RAW_DIR / "events"
UA = {"User-Agent": "Mozilla/5.0 (research script; low frequency)"}


def nbp_rates() -> None:
    xml = requests.get("https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml", headers=UA, timeout=60)
    s = xml.content.decode("utf-8-sig")
    rows = []
    for m in re.finditer(r'obowiazuje_od="([\d-]+)">(.*?)</pozycje>', s, re.S):
        ref = re.search(r'id="ref"\s+oprocentowanie="([\d,]+)"', m.group(2))
        rows.append({"effective": m.group(1), "ref": float(ref.group(1).replace(",", ".")) if ref else None})
    df = pd.DataFrame(rows)
    df["change"] = df["ref"].diff()
    df.to_csv(OUT / "nbp_rates.csv", index=False)
    print("nbp rates", len(df))


def wig20_portfolios() -> None:
    page = requests.get("https://gpwbenchmark.pl/historyczne-portfele-indeksow", headers=UA, timeout=60).text
    files = sorted(set(re.findall(r'(pub/BENCHMARK/files/PDF/historyczne/(\d{4}_\d{2}_\d{2})_WIG20\.pdf)', page)))
    import pypdf

    cache = OUT / "wig20_pdf"
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, d in files:
        f = cache / f"{d}.pdf"
        if not f.exists():
            time.sleep(1.0)
            r = requests.get("https://gpwbenchmark.pl/" + path, headers=UA, timeout=60)
            if r.status_code != 200:
                print("skip", path, r.status_code)
                continue
            f.write_bytes(r.content)
        text = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(f.read_bytes())).pages)
        text = re.split(r"rezerwow", text, flags=re.I)[0]  # drop the reserve list
        # layout differs across years (with/without price & weight columns): keep rank, ISIN, name
        got = 0
        for m in re.finditer(r"^\s*(\d{1,2})\s+([A-Z]{2}[A-Z0-9]{9}\d)\s+(\S+)", text, re.M):
            if int(m.group(1)) == 1 and got:  # numbering restarts -> reserve list
                break
            got += 1
            rows.append({"revision": pd.Timestamp(d.replace("_", "-")), "rank": int(m.group(1)),
                         "isin": m.group(2), "name": m.group(3)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "wig20_portfolios.csv", index=False)
    print("wig20 portfolios", df["revision"].nunique(), "revisions", len(df), "rows")


def index_portfolios(index: str = "mWIG40") -> None:
    """Historical portfolios after each revision for mWIG40 / sWIG80 (same PDFs source as WIG20)."""
    import pypdf

    page = requests.get("https://gpwbenchmark.pl/historyczne-portfele-indeksow", headers=UA, timeout=60).text
    files = sorted(set(re.findall(rf'(pub/BENCHMARK/files/PDF/historyczne/(\d{{4}}_\d{{2}}_\d{{2}})_{index}(?:_MIS80)?\.pdf)', page)))
    cache = OUT / f"{index.lower()}_pdf"
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, d in files:
        f = cache / f"{d}.pdf"
        if not f.exists():
            time.sleep(1.0)
            r = requests.get("https://gpwbenchmark.pl/" + path, headers=UA, timeout=60)
            if r.status_code != 200:
                print("skip", path, r.status_code)
                continue
            f.write_bytes(r.content)
        text = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(f.read_bytes())).pages)
        got = 0
        for m in re.finditer(r"^\s*(\d{1,2})\s+([A-Z]{2}[A-Z0-9]{9}\d)\s+(\S+)", text, re.M):
            if int(m.group(1)) == 1 and got:  # numbering restarts -> reserve list
                break
            got += 1
            rows.append({"revision": pd.Timestamp(d.replace("_", "-")), "rank": int(m.group(1)),
                         "isin": m.group(2), "name": m.group(3)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"{index.lower()}_portfolios.csv", index=False)
    print(index, df["revision"].nunique(), "revisions", len(df), "rows")


def mwig40_portfolios() -> None:
    index_portfolios("mWIG40")


def swig80_portfolios() -> None:
    index_portfolios("sWIG80")


MONTHS_PL = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
             "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}


def index_calendar() -> None:
    """GPW Benchmark 'Kalendarium indeksów' 2012-2026: announcement and revision dates of WIG20/mWIG40/sWIG80."""
    rows = []
    for y in range(2012, 2027):
        time.sleep(1.0)
        s = requests.get(f"https://gpwbenchmark.pl/kalendarium-indeksow?year={y}", headers=UA, timeout=60).text
        t = re.sub(r"<[^>]+>", "|", re.sub(r"<(script|style).*?</\1>", "", s, flags=re.S))
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"(\|\s*)+", "|", t)
        segs = t.split("|")
        for i, seg in enumerate(segs):
            m = re.fullmatch(r"\s*(\d{2}) ([a-ząćęłńóśźż]+) (\d{4})\s*", seg)
            if not m or m.group(2) not in MONTHS_PL:
                continue
            d = pd.Timestamp(int(m.group(3)), MONTHS_PL[m.group(2)], int(m.group(1)))
            for txt in segs[i + 1:i + 8]:
                txt = txt.strip()
                if re.fullmatch(r"(\d{1,2}(&nbsp;)?|x|Po|Wt|Śr|Cz|Pt|So|N)?", txt) or re.match(r"\d{2} [a-z]", txt):
                    break  # next calendar cell
                if re.search(r"\b(WIG20|mWIG40|sWIG80)\b", txt):
                    kind = ("announcement" if "ogłoszenie zmian" in txt else
                            "revision" if ("rewizja" in txt or "korekta" in txt) else
                            "ranking" if "ranking" in txt else "other")
                    rows.append({"date": d, "kind": kind, "text": txt})
    df = pd.DataFrame(rows).drop_duplicates(["date", "kind"])
    df.to_csv(OUT / "index_calendar.csv", index=False)
    print(df.groupby("kind").size())


def index_change_quotes() -> None:
    """Official GPW stock quotes (type 10) for +-15 sessions around every WIG20 revision (research period)
    that changed the composition -> no survivorship bias for added/removed names."""
    from quant.data import gpw, store

    port = pd.read_csv(OUT / "wig20_portfolios.csv", parse_dates=["revision"])
    revs = sorted(port["revision"].unique())
    changed = [r for a, r in zip(revs[:-1], revs[1:])
               if set(port.loc[port.revision == a, "isin"]) != set(port.loc[port.revision == r, "isin"])
               and r < config.HOLDOUT_START]
    sess = pd.DatetimeIndex(store.load_processed_research("fw20_cont").index)
    days = set()
    for r in changed:
        p = sess.searchsorted(r)
        days |= set(sess[max(p - 15, 0): p + 16])
    cache = OUT / "gpw_t10"
    cache.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    for d in sorted(days):
        f = cache / f"{d:%Y-%m-%d}.parquet"
        if f.exists():
            continue
        df = gpw.fetch_day(s, 10, d)
        time.sleep(gpw.DELAY_S)
        if len(df):
            for c in ("isin", "currency", "name"):
                df[c] = df[c].astype(str)
            df.to_parquet(f)
    print("index changes", len(changed), "revisions;", len(days), "sessions")


def dividends() -> None:
    rows = []
    for t in universe.YAHOO_PL_STOCKS:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{t}.WA?period1=0&period2={int(time.time())}"
               "&interval=1d&events=div")
        try:
            js = json.loads(sources.http_get(url))
        except RuntimeError as e:
            print("div fail", t, e)
            continue
        ev = js["chart"]["result"][0].get("events", {}).get("dividends", {})
        tz = js["chart"]["result"][0]["meta"].get("exchangeTimezoneName", "Europe/Warsaw")
        for v in ev.values():
            d = pd.to_datetime(v["date"], unit="s", utc=True).tz_convert(tz).date()
            rows.append({"ticker": t, "ex_date": pd.Timestamp(d), "amount": v["amount"]})
    df = pd.DataFrame(rows).sort_values(["ticker", "ex_date"])
    df.to_csv(OUT / "dividends.csv", index=False)
    print("dividends", len(df))


def extra_commodities() -> None:
    for sym in ["SI=F", "HO=F", "RB=F"]:
        df = sources.fetch_yahoo(sym)
        store.save(df, store.raw_path("yahoo", sym))
        print(sym, len(df), df.index[0].date())


if __name__ == "__main__":
    import sys

    OUT.mkdir(parents=True, exist_ok=True)
    steps = sys.argv[1:] or ["nbp_rates", "dividends", "extra_commodities", "wig20_portfolios"]
    for step in steps:
        globals()[step]()
