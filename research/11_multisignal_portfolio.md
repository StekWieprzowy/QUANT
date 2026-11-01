# 11 – Faza 3, część B: portfel wielu słabych sygnałów

**Rejestr:** H207–H224 (18 z limitu 25; H213/H214 INVALID – błąd wyrównania wag zmiennych w czasie, poprawione
i powtórzone jako H222/H223). Skrypt: `scripts/phase4_portfolio.py`; wyniki: `reports/phase4/`
(`results.json`, `portfolio_table.csv`, `signal_corr_*.csv`, `daily_*.parquet`), wykres
`reports/figures/phase4_portfolios.png`. Pre-rejestracja: `research/09_phase3_preregistration.md`.

## Ustawienia (z pre-rejestracji, bez zmian)
Uniwersum: WIG20 + mWIG40 wg historycznego składu (ok. 60 spółek, oficjalne kursy GPW, bez survivorship bias),
ADV ≥ 0.5 mln PLN. Rebalancing tygodniowy (decyzja na zamknięciu ostatniej sesji tygodnia, wykonanie na otwarciu
następnej), no-trade band 0.5% kapitału, |w| ≤ 5%, brutto 100% (L/S), shorty tylko ADV ≥ 10 mln, hedge bety FW20.
Koszty: prowizja 0.29% + połowa spreadu wg ADV (0.05–0.40%) + 0.05% + σ·√(transakcja/ADV) przy kapitale 2 mln PLN,
pożyczka 3% p.a., finansowanie NBP+0.25 pp. Ocena 2010-07 – 2022-06. IDX wykluczony (część A nie spełniła kryterium).

## Błędy wykryte po drodze
1. **Test permutacyjny** – pierwsza wersja tasowała sygnały między spółkami niezależnie co tydzień, co dawało
   nullowi prawie pełny obrót; trwały sygnał „wygrywał” kosztami, nie informacją (REV z SR netto −3.96 miał p=0.016),
   a 60 permutacji nie pozwalało zejść poniżej p=0.016. Poprawka: stabilne losowe przypisanie sygnałów do spółek
   (zachowuje trwałość i obrót), 200 permutacji; p dla H207–H211 przeliczone i poprawione w rejestrze z adnotacją.
2. **Wagi zmienne w czasie** (B-IV, B-WF) – inf w okresie rozgrzewki i daty 1 stycznia bez forward-fill → B-IV bez
   pozycji, B-WF identyczny z B-EW. H213/H214 → INVALID, poprawka + asercja pokrycia sygnału, powtórka H222/H223.
3. Wydajność: budowa wag w pandas (34 s/wywołanie) → numpy (test zgodności); przerwane przed pierwszym wpisem.

## Korelacje sygnałów
* Przekrojowa korelacja Spearmana z-score'ów (średnia po datach): |ρ| ≤ 0.24 (najwyższa LVOL–VAL 0.24, MOM–LVOL 0.16).
* Korelacja dziennych zwrotów brutto portfeli jednosygnałowych: 0.08–0.41 (REV–LVOL 0.40, MOM–LVOL 0.41) – wyższa
  niż korelacja samych sygnałów: wspólna ekspozycja czynnikowa (prawdopodobnie wielkość/płynność), której hedge betą
  FW20 nie usuwa. Dywersyfikacja jest więc umiarkowana.

## Wyniki (2010-07 – 2022-06)

| ID | portfel | SR brutto | SR netto | obrót/rok | koszty %/rok | zwrot brutto %/rok | MDD netto | perm. p |
|---|---|---|---|---|---|---|---|---|
| H207 | S-REV | 0.39 | −3.96 | 67× | 62.4 | 4.8 | 100% | 0.005 |
| H208 | S-MOM | **1.18** | 0.27 | 8.6× | 9.9 | 12.9 | 31% | 0.005 |
| H209 | S-PEAD | −0.21 | −2.73 | 23× | 23.2 | −1.6 | 95% | 0.32 |
| H210 | S-LVOL | 0.85 | −0.24 | 7.6× | 9.3 | 7.2 | 33% | 0.005 |
| H211 | S-VAL | 0.14 | −0.63 | 6.0× | 6.5 | 1.2 | 52% | 0.76 |
| H212 | **B-EW** (główny) | 1.23 | −2.01 | 36× | 32.6 | 11.8 | 92% | 0.005 |
| H222 | B-IV | 1.35 | −1.61 | 30× | 28.1 | 12.4 | 86% | 0.005 |
| H223 | B-WF (wagi estymowane) | **1.43** | −1.30 | 30× | 27.1 | 13.8 | 81% | 0.005 |
| H215 | B-LO long-only + FW20 | 1.04 | −2.43 | 43× | – | – | 98% | – |
| H216 | B-EW bez no-trade bandu | 1.23 | −2.06 | 37× | – | – | 93% | – |
| H224 | B-SLOW (**post-hoc**): bez REV, miesięcznie, band 1% | 1.16 | 0.31 | 5.3× | 8.0 | 11.0 | 26% | 0.005 |

Wagi ridge walk-forward (B-WF) stabilne: MOM ~0.35, LVOL ~0.30, REV ~0.2, PEAD ~0.15, VAL ~0.

### Atrybucja (leave-one-out B-EW, H217–H221)
| bez sygnału | SR brutto | SR netto | obrót/rok |
|---|---|---|---|
| (pełny B-EW) | 1.23 | −2.01 | 36× |
| −REV | 1.27 | **−0.10** | 11× |
| −MOM | 0.87 | −2.89 | 42× |
| −PEAD | 1.23 | −2.02 | 36× |
| −LVOL | 1.21 | −2.22 | 42× |
| −VAL | 1.43 | −2.08 | 40× |
MOM wnosi najwięcej przewagi brutto (−0.36 SR po usunięciu); REV wnosi niemal zero brutto, a ~2/3 obrotu;
PEAD i VAL nic nie wnoszą (VAL wręcz szkodzi brutto).

### Stabilność
Brutto: B-EW 0.81 / 2.00 / 0.76, B-SLOW 0.93 / 1.58 / 0.91, MOM 0.76 / 1.65 / 1.02 (2010–12 / 2013–17 / 2018–22H1) –
przewaga brutto **nie zanika** (inaczej niż relatywna mean-reversion z fazy 2), szczyt 2013–17, potem ~0.8–1.0.
Netto: B-SLOW −0.15 / 0.68 / 0.20 – ujemny pierwszy podokres, słaby ostatni; rolling 2-letni Sharpe netto < 0
w 2012 i 2018–2019.

## Wnioski
* **Łączenie sygnałów działa brutto**: B-WF 1.43 i B-IV 1.35 vs najlepszy pojedynczy (MOM) 1.18 – zysk z
  dywersyfikacji ~+0.2 SR, istotny w permutacjach (p=0.005, null z dopasowanym obrotem).
* **Netto przegrywa z kosztami**: przy kapitale 2 mln PLN średni koszt to ~1.1% na jednostkę obrotu (mWIG40:
  spread 0.2–0.4% + wpływ na cenę σ√(Q/ADV) ~0.3–0.6% + prowizja 0.29%). Każde 1×/rok obrotu kosztuje ~1.1% rocznie,
  a zwrot brutto całego portfela to ~11–14% rocznie przy zmienności ~10%.
* Najlepszy możliwy kierunek – wolne sygnały, rzadki rebalancing (B-SLOW) – daje SR netto 0.31 ≈ samo momentum;
  nawet przy zerowych kosztach (SR brutto 1.16) nie przeszedłby progu DSR (~1.7 przy N ≈ 220).
* Żaden wariant nie przechodzi bramki (SR netto > 1, DSR, MDD < 20%, stabilność) → **holdout nietknięty**.
