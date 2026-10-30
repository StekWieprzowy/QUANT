# QUANT – research WIG20 / FW20

Projekt badawczy: szukanie statystycznie istotnej, odpornej i opłacalnej po kosztach zależności na WIG20/FW20.
**Tylko research i backtesty** – brak handlu na żywo i jakichkolwiek połączeń z brokerem.

Plan i pre-commitment podziału danych: [`research/00_plan.md`](research/00_plan.md). Raport końcowy: [`REPORT.md`](REPORT.md).

## Uruchomienie od zera

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # albo: pip install -r requirements.txt
python -m pytest                   # testy backtestera (look-ahead, koszty, rolowanie, holdout lock)
python scripts/refresh_data.py     # pobiera dane EOD do data/raw (stooq / bossa / NBP)
python scripts/check_data.py       # kontrola jakości + budowa ciągłej serii FW20 -> data/processed
```

Każda iteracja researchu to skrypt `scripts/hNN_*.py`, który loguje wszystkie warianty do `hypotheses_log.csv`
i zapisuje notatkę w `research/`. Holdout (od 2022-07-01) jest dostępny wyłącznie przez
`scripts/run_holdout.py` i może być użyty dokładnie raz (`holdout/LOCK`).

## Struktura

| Ścieżka | Zawartość |
|---|---|
| `src/quant/config.py` | stałe: podział research/holdout, model kosztów, seed |
| `src/quant/data/` | pobieranie (stooq, bossa, NBP), magazyn parquet z „firewallem” holdoutu, kalendarz i rolowanie FW20 |
| `src/quant/backtest.py` | wektorowy backtester na siatce zdarzeń open/close (wykonanie zawsze na następnym barze) |
| `src/quant/metrics.py` | Sharpe, MDD, PSR, Deflated Sharpe, BH, White Reality Check |
| `src/quant/validation.py` | walk-forward, purged k-fold, test permutacyjny, sąsiedztwo parametrów |
| `src/quant/registry.py` | rejestr hipotez `hypotheses_log.csv` (budżet 200) |
| `src/quant/holdout.py` | jednorazowa blokada holdoutu |
| `research/` | notatki z iteracji |
| `tests/` | testy jednostkowe |
