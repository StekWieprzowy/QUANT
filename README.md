# QUANT – research WIG20 / FW20

Projekt badawczy: szukanie statystycznie istotnej, odpornej i opłacalnej po kosztach zależności na WIG20/FW20.
**Tylko research i backtesty** – brak handlu na żywo i jakichkolwiek połączeń z brokerem.

* Plan i pre-commitment podziału danych: [`research/00_plan.md`](research/00_plan.md)
* **Raport końcowy:** [`REPORT.md`](REPORT.md) – wynik negatywny: żaden z wariantów nie przeszedł walidacji, holdout nieużyty
* Rejestr wszystkich testów: [`hypotheses_log.csv`](hypotheses_log.csv)
* Notatki z iteracji: [`research/`](research/)
* Faza 2: [`DISCRETIONARY_PLAYBOOK.md`](DISCRETIONARY_PLAYBOOK.md) (ściąga eventów) i [`THEORIES.md`](THEORIES.md) (teorie do ręcznej weryfikacji)

## Uruchomienie od zera

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest                          # testy: look-ahead, koszty, rolowanie, wyrównanie danych, holdout lock
python scripts/refresh_gpw.py --types futures indices   # archiwum GPW od 2005 (~2-3 h, ~1 zapyt./s, przyrostowo)
python scripts/refresh_data.py            # Yahoo (rynki zagraniczne, akcje .WA) + NBP (fixing FX)
python scripts/fix_stock_gaps.py          # oficjalne kursy GPW dla dni z luką >10% (naprawa ticków Yahoo)
python scripts/check_data.py              # ciągła seria FW20 -> data/processed + research/01_data_quality.md
```

Research (każde uruchomienie dopisuje wiersze do `hypotheses_log.csv` – nie powtarzaj bez potrzeby):

```bash
python scripts/check_lookahead.py R2 K1   # empiryczny detektor look-ahead dla wariantów z katalogu
python scripts/h_fw20.py R2               # walk-forward + rejestr + DSR + permutacje + bramka
python scripts/h_pairs.py P1
python scripts/final_stats.py             # Reality Check / BH na wszystkich wariantach (bez logowania)
python scripts/make_figures.py E1 R2 K1   # wykresy do REPORT.md
```

Faza 2 (koszty, stabilność, eventy):

```bash
python scripts/h_fw20.py CA1 CA2 CA3 CA4 CA5 CA6 CA7   # atak na koszty (loguje do rejestru)
python scripts/phase2_costs.py            # próg kosztów (walk-forward przy skalowanych kosztach) + zwroty OOS
python scripts/phase2_stability.py        # podokresy, rolling Sharpe 2y
python scripts/fetch_events.py            # stopy NBP, dywidendy, portfele WIG20, surowce
python scripts/fetch_events.py index_change_quotes   # kursy GPW wokół zmian składu WIG20 (~600 zapytań)
python scripts/phase3_events.py --dry     # event studies bez logowania (kontrola błędów)
python scripts/phase3_events.py           # event studies -> rejestr + reports/phase3/event_summary.csv (BH)
```

Holdout (od 2022-07-01) jest dostępny wyłącznie przez `scripts/run_holdout.py`, czyta zamrożonego kandydata z
`holdout/candidate.json` (zapisywanego tylko po przejściu pełnej bramki) i może być użyty dokładnie raz
(`holdout/LOCK`). W tym projekcie nie został użyty.

## Struktura

| Ścieżka | Zawartość |
|---|---|
| `src/quant/config.py` | podział research/holdout, modele kosztów, seed, stopy NBP (finansowanie) |
| `src/quant/data/` | GPW archiwum, Yahoo, NBP (+ stooq/bossa dla uruchomień lokalnych), magazyn parquet z „firewallem” holdoutu, kalendarz wygasania i rolowanie FW20 |
| `src/quant/backtest.py` | wektorowy backtester na siatce zdarzeń open/close (wykonanie zawsze na następnym zdarzeniu), portfele wieloinstrumentowe |
| `src/quant/metrics.py` | Sharpe, MDD, PSR, Deflated Sharpe, BH, White Reality Check (klasyczny i studentyzowany) |
| `src/quant/validation.py` | walk-forward, purged k-fold, test permutacyjny, sąsiedztwo parametrów |
| `src/quant/research.py` | wspólny pipeline oceny + bramka kandydata |
| `src/quant/lookahead.py` | detektor look-ahead (zaburzanie przyszłych danych) |
| `src/quant/strategies/` | katalog hipotez (`catalog.py`) i implementacje rodzin |
| `src/quant/registry.py`, `holdout.py` | rejestr hipotez (budżet 228 po fazie 2), jednorazowa blokada holdoutu |
| `src/quant/events.py`, `liquidity.py` | event studies (CAR, bootstrap CI, BH), estymatory płynności |
| `scripts/` | pobieranie danych, testy hipotez, statystyki końcowe, wykresy, holdout |
| `reports/` | wykresy i statystyki końcowe |

Dane rynkowe (`data/`) nie są w repozytorium (regulaminy źródeł) – odtwarza je `scripts/refresh_*.py`.
