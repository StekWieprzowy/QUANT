"""Symbols downloaded by scripts/refresh_data.py (stooq naming)."""

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
