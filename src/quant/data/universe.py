"""Symbols downloaded by scripts/refresh_data.py.

stooq/bossa turned out to be unreachable from the research container (stooq resets TLS, bossa requires
login), so the working sources are: GPW archive (PL indices, FW20 contracts, stocks), NBP API (FX fixing)
and the Yahoo chart API (foreign markets). The stooq lists are kept for users running locally.
"""

YAHOO = {
    "^GDAXI": "DAX", "^GSPC": "S&P 500", "ES=F": "E-mini S&P 500 front", "^VIX": "VIX",
    "^STOXX50E": "Euro Stoxx 50", "^IXIC": "Nasdaq Comp.", "HG=F": "Copper", "BZ=F": "Brent",
    "CL=F": "WTI", "GC=F": "Gold", "EURPLN=X": "EUR/PLN", "USDPLN=X": "USD/PLN", "EURUSD=X": "EUR/USD",
    "^TNX": "US 10Y yield", "EEM": "iShares MSCI EM ETF", "EPOL": "iShares MSCI Poland ETF (US-listed)",
    "^N225": "Nikkei 225",
}

# WSE stocks via Yahoo (.WA); adjclose is split+dividend adjusted. Current/long-lived WIG20 names ->
# survivorship bias acknowledged in REPORT.md.
YAHOO_PL_STOCKS = ["PKO", "PEO", "PZU", "KGH", "PKN", "CDR", "LPP", "DNP", "ALE", "SPL", "MBK", "KTY", "CPS",
                   "OPL", "PGE", "JSW", "KRU", "BDX", "CCC", "PCO", "ACP", "ALR", "LTS", "TPE", "ENG", "PGN",
                   "BHW", "ING", "MIL", "EAT", "ENA", "BNP", "ATT", "GTC", "BRS", "LWB", "CIE"]

STOOQ_INDICES = {
    "wig20": "WIG20 price index",
    "wig20tr": "WIG20 total return",
    "wig": "WIG broad index",
    "mwig40": "mWIG40",
    "^dax": "DAX",
    "^spx": "S&P 500",
    "^ndq": "Nasdaq Composite",
    "^vix": "VIX",
}

STOOQ_FUTURES_CONT = {
    "fw20": "WIG20 futures continuous (stooq splice - used only for cross-check)",
    "es.f": "E-mini S&P 500 continuous",
    "fdax.f": "DAX futures continuous",
    "hg.f": "Copper",
    "cb.f": "Brent",
    "cl.f": "WTI",
    "gc.f": "Gold",
}

STOOQ_FX_RATES = {
    "eurpln": "EUR/PLN",
    "usdpln": "USD/PLN",
    "eurusd": "EUR/USD",
    "10plyb.b": "Poland 10Y yield",
    "2plyb.b": "Poland 2Y yield",
    "plopln3m": "WIBOR 3M",
    "10deyb.b": "Germany 10Y yield",
    "10usy.b": "US 10Y yield",
}

# current WIG20 members + long-lived former members (survivorship bias acknowledged in REPORT.md)
STOOQ_STOCKS = {
    "pko": "PKO BP", "peo": "Pekao", "pzu": "PZU", "kgh": "KGHM", "pkn": "Orlen", "cdr": "CD Projekt",
    "lpp": "LPP", "dnp": "Dino", "ale": "Allegro", "spl": "Santander BP", "mbk": "mBank", "kty": "Kety",
    "cps": "Cyfrowy Polsat", "opl": "Orange PL", "pge": "PGE", "jsw": "JSW", "kru": "Kruk", "bdx": "Budimex",
    "ccc": "CCC", "pco": "Pepco", "acp": "Asseco Poland", "alr": "Alior", "lts": "Lotos", "tpe": "Tauron",
    "eng": "Energa", "pgn": "PGNiG", "bhw": "Citi Handlowy", "ing": "ING BSK", "mil": "Millennium",
    "eat": "AmRest", "ena": "Enea", "zab": "Zabka", "tpsa": "TPSA (old Orange)",
}

# FW20 individual contracts on stooq: fw20{m}{yy} e.g. fw20z24 (verified at download time)
FW20_MONTHS = "hmuz"


def fw20_contract_symbols(first_year: int, last_year: int) -> list[str]:
    return [f"fw20{m}{y % 100:02d}" for y in range(first_year, last_year + 1) for m in FW20_MONTHS]
