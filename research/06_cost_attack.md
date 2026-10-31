# 06 – Faza 2, część 1: atak na koszty relatywnej mean-reversion

**Rejestr:** H129–H163 (35 wariantów z limitu 40). Ten sam sygnał (rezydualne odwrócenie / pary), zmieniane
tylko *kiedy* i *czym* handlujemy. Koszty bazowe bez zmian (akcje 0.39%/stronę + finansowanie NBP, FW20 2 pkt).

## Płynność i spready (opis, nie test)
* Spready szacowane z dziennych OHLC (Abdi-Ranaldo 2017, `quant/liquidity.py`) okazały się **niewiarygodne**
  dla dużych spółek (dużo zer, PKO 65 bps – niemożliwe przy 1 ticku). Do selekcji płynności użyty obrót
  (`reports/stock_liquidity.csv`).
* **Kontrakty na akcje GPW** (`reports/stock_futures_liquidity.csv`, 2018–22): mediana dziennego obrotu FKGH
  ~0.9 mln PLN, FCDR ~0.9 mln, FPKN ~0.4 mln, FPKO/FPEO ~0.16 mln, FPGE/FTPE ~10–20 tys. PLN; 14–18% dni bez
  transakcji w FCDR/FTPE. Pojemność rzędu dziesiątek–setek tys. PLN na transakcję. Prowizje maklerskie dla
  kontraktów na akcje niezweryfikowane → scenariusz 0.10% + 0.15% poślizgu.

## Wyniki (walk-forward OOS 2008-01 – 2022-06, netto)

| ID | dźwignia kosztowa | SR netto | SR brutto | trans. | MDD | p perm. |
|---|---|---|---|---|---|---|
| (H120) | R2 bazowe – punkt odniesienia | 0.45 | 0.74 | 172 | 5.5% | 0.003 |
| H133 | CA1 rebalancing tygodniowy | −0.10 | 0.14 | 130 | 9.5% | 0.40 |
| H138 | CA2 histereza (wyjście dopiero po pełnym powrocie) | 0.31 | 0.53 | 161 | 8.9% | 0.07 |
| H143 | CA3 tylko top-8 najpłynniejszych (kauzalny ranking obrotu) | 0.07 | 0.32 | 89 | 4.0% | 0.11 |
| H148 | CA4 kontrakty na akcje zamiast akcji | −0.13 | 0.27 | 174 | 11.2% | 0.34 |
| H153 | CA5 pary: tygodniowo + wyjście przy pełnym powrocie | 0.28 | 0.85 | 306 | 14.6% | 0.003 |
| H158 | CA6 top-8 + co 2 tygodnie + histereza | −0.10 | 0.03 | 37 | 5.0% | 0.74 |
| H163 | CA7 pary tylko PKO/PEO/PZU | −0.16 | 0.67 | 248 | 45.4% | 0.003 |

## Kluczowy wniosek
**Dźwignie obniżające koszty niszczą przewagę brutto szybciej, niż oszczędzają koszty.**
* Przewaga wygasa w ciągu kilku dni – czekanie do piątku (CA1) obcina brutto SR z 0.74 do 0.14.
* Przewaga siedzi w mniej płynnych nazwach – top-8 (CA3) i trójka PKO/PEO/PZU (CA7) mają najsłabsze brutto.
  To zgodne z interpretacją odwrócenia jako **premii za dostarczanie płynności**: płacą tam, gdzie płynność
  jest droga – czyli dokładnie tam, gdzie koszty są wysokie.
* Kontrakty na akcje: tańsze w teorii, ale cienkie, a rezydua kontraktów dają słabszy sygnał brutto.
* Hedge betą FW20 (R) vs pełne L/S na akcjach (P): P ma wyższe brutto (1.3–2.0), ale płaci koszty dwóch nóg
  akcyjnych + pożyczkę; R ma niższe brutto, ale tańszą drugą nogę. Po kosztach oba ~0.3–0.45.

## Próg kosztów (`scripts/phase2_costs.py`, `reports/phase2/cost_curve.csv`, `reports/figures/cost_threshold.png`)
Pełny walk-forward (z ponownym wyborem parametrów) przy przeskalowanych kosztach. Analiza wrażliwości,
nie selekcja – nie logowana jako testy.

| koszt akcji / stronę | P1 | E1 | R1 | R2 | CA5 | CA2 | K1 |
|---|---|---|---|---|---|---|---|
| 0.00% | 1.99 | 1.46 | 1.31 | 0.46 | 0.78 | 0.47 | 0.74 |
| 0.06% | 1.58 | 1.28 | 0.86 | 0.69 | 0.73 | 0.43 | – |
| 0.12% | 1.07 | 1.06 | 0.62 | 0.65 | 0.64 | 0.40 | – |
| 0.18% | 0.79 | 0.99 | 0.43 | 0.61 | 0.62 | 0.43 | – |
| 0.23% | 0.63 | 0.84 | 0.49 | 0.57 | 0.49 | 0.40 | – |
| 0.31% | 0.51 | 0.65 | 0.33 | 0.51 | 0.38 | 0.35 | – |
| **0.39% (baza)** | 0.31 | 0.46 | 0.16 | 0.45 | 0.28 | 0.31 | 0.53 |
| 0.59% | −0.20 | −0.01 | −0.25 | 0.31 | 0.01 | 0.20 | – |

**Próg kosztów:** SR OOS = 1.0 osiąga P1 przy ~**0.12%/stronę/nogę**, E1 przy ~**0.17%**, R1 przy ~0.04%;
R2/CA2/K1 nie osiągają 1.0 nawet przy zerowych kosztach. Uwaga: to nadal nie przechodzi DSR (próg ~1.7).
Koszt ~0.10–0.12% all-in jest dziś osiągalny detalicznie (broker 0% prowizji do limitu obrotu + poślizg
~0.1%), ale dobór modelu kosztów *po* zobaczeniu wyników byłby oszustwem – to materiał do THEORIES.md, nie kandydat.
