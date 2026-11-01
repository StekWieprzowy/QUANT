# 09 – Faza 3: pre-rejestracja (spisane PRZED jakimkolwiek wynikiem tej fazy, 2026-11-01)

Commit z tym plikiem poprzedza pierwsze uruchomienie obliczeń fazy 3. Nic z poniższego nie będzie zmieniane
po obejrzeniu wyników; odstępstwa (np. błędy kodu) będą jawnie opisane w notatkach.

## Budżet i rejestr
* Maks. **40 nowych wpisów** (A ≤ 15, B ≤ 25) w tym samym `hypotheses_log.csv` (budżet 194 + 40 = 234).
* DSR liczony od łącznej liczby wpisów; BH łącznie ze wszystkimi dotychczasowymi wpisami z p-value.
* Holdout (≥ 2022-07-01) nietknięty; jednorazowo tylko dla kandydata, który przejdzie całą bramkę.

## Model kosztów (USTALONY, `quant.portfolio.CostModel`)
Dla akcji, na stronę transakcji, jako ułamek wartości transakcji:
1. **Prowizja 0.29%** (jak w fazach 1–2).
2. **Połowa spreadu zależna od płynności** – ADV = mediana dziennego obrotu (PLN) z 60 poprzednich sesji
   (kauzalnie, z oficjalnych danych GPW):
   | ADV | połowa spreadu |
   |---|---|
   | ≥ 50 mln PLN | 0.05% |
   | 10–50 mln | 0.10% |
   | 2–10 mln | 0.20% |
   | 0.5–2 mln | 0.40% |
   | < 0.5 mln | **niehandlowalna** (wykluczona z uniwersum) |
3. **Poślizg / wpływ na cenę:** 0.05% + σ_dzienna × √(wartość transakcji / ADV), kapitał portfela **2 mln PLN**.
4. **Krótka sprzedaż akcji:** tylko dla spółek z ADV ≥ 10 mln PLN (proxy dostępności pożyczki), koszt
   pożyczki 3% p.a. od wartości shortu.
5. **Finansowanie:** stopa referencyjna NBP + 0.25 pp od netto długiej ekspozycji w akcjach (Σ long − Σ short);
   netto krótka ekspozycja zarabia tę samą stopę (symetrycznie).
6. **Hedge FW20:** 1.5 pkt poślizgu + 10 PLN prowizji na stronę (bez zmian), rolowanie 2 strony.
Dla event study (część A) wynik netto = AR − 2 × (prowizja + połowa spreadu + poślizg) przy pozycji
40 tys. PLN (2% kapitału).

## Uniwersum (część B)
Członkowie WIG20 + mWIG40 według ostatniej rewizji obowiązującej w dniu decyzji (portfele z
gpwbenchmark.pl, od 2009-06), ceny i obroty z oficjalnego archiwum GPW (wszystkie spółki, także wycofane) →
brak survivorship bias. Filtr: ADV ≥ 0.5 mln PLN. Okres: 2009-07 – 2022-06 (rozgrzewka sygnałów do 2010-06;
ocena 2010-07 – 2022-06; podokresy 2010–2012, 2013–2017, 2018–2022H1 – 2008–2009 niedostępne bez historii składu).

## Część A – zmiany składu indeksów (≤ 15 wpisów)
* Indeksy: WIG20, mWIG40, sWIG80. Zdarzenia: dodania i usunięcia w rewizjach/korektach kwartalnych, dla których
  kalendarz GPW Benchmark podaje datę ogłoszenia (2012 →). Dzień 0 okna 1 = sesja po ogłoszeniu (ogłoszenie po sesji).
* Okna: **[ogłoszenie+1 → dzień rewizji]** i **[rewizja+1 → rewizja+10]**; AR = zwrot spółki − zwrot WIG
  (szeroki rynek; dla WIG20 również vs WIG20 jako kontrola opisowa).
* Oczekiwane znaki: dodania + / −, usunięcia − / +.
* Wpisy: 3 indeksy × 2 typy × 2 okna = **12**; raportowane N, średnia, 95% CI (bootstrap), p (t), BH łącznie
  z dotychczasowymi wpisami, wynik netto po kosztach z modelu powyżej.
* Kryterium włączenia do części B: okno istotne po BH **i** dodatnie (w oczekiwanym kierunku) w obu połowach
  okresu (2012–2016, 2017–2022).

## Część B – portfel wielu słabych sygnałów (≤ 25 wpisów)
Sygnały (piątek, zamknięcie t, dane ≤ t; transakcja na otwarciu następnej sesji):
| kod | sygnał | definicja |
|---|---|---|
| REV | krótkoterminowy reversal | −Σ reszt (vs WIG, β z 250 dni, opóźniona) z 5 sesji |
| MOM | momentum przekrojowe | log(P[t−21] / P[t−252]) |
| PEAD | dryf po wynikach (proxy) | sign(AR0) przez 10 sesji po dniu z wolumenem > 3× mediany 60d i |AR| > 2σ w sezonie raportów |
| LVOL | niska zmienność | −odch. std. dziennych zwrotów z 60 sesji |
| VAL | value (proxy) | stopa dywidendy z 12 mies. (dywidendy z Yahoo; brak pokrycia → sygnał nieobecny) |
| IDX | zmiany indeksów | +1 ogłoszone dodanie / −1 ogłoszone usunięcie do dnia rewizji – **tylko jeśli część A spełni kryterium** |
| (KGHM–miedź) | — | wykluczony z góry: horyzont 1 sesja niezgodny z tygodniowym rebalancingiem, wersja 20-dniowa nieistotna (H184) |
| (jakość) | — | wykluczony: brak darmowych danych fundamentalnych |

* Każdy sygnał: z-score przekrojowy w uniwersum handlowalnym, winsoryzacja ±3.
* **Łączenie (wagi z góry):** B-EW równe wagi; B-IV wagi ∝ 1/zmienność zwrotów portfela danego sygnału
  (z 252 dni, kauzalnie); B-WF wagi z regresji grzbietowej walk-forward (oznaczony jako estymowany).
* **Konstrukcja L/S:** w_i ∝ z_i, Σ|w| = 1 (brutto 100% kapitału), |w_i| ≤ 5%, ujemne wagi tylko dla
  shortowalnych (ADV ≥ 10 mln), beta-neutralność przez FW20: h = −Σ w_i β_i.
* **Long-only + FW20:** w_i ∝ max(z_i, 0) dla górnej tercyli, Σw = 1, |w_i| ≤ 5%, hedge −Σ w_i β_i.
* **Kontrola obrotu:** handel tylko zmianą pozycji netto (sygnały łączone przed transakcją); no-trade band:
  zlecenie tylko gdy |w_cel − w_obecna| > 0.5% kapitału; rebalancing co tydzień (ostatnia sesja tygodnia).
* Planowane wpisy: 5–6 portfeli jednosygnałowych (te same reguły, do porównania i atrybucji) + B-EW (główny),
  B-IV, B-WF, B-EW long-only, B-EW bez no-trade bandu ⇒ ok. 11 wpisów.
* Brak neutralności sektorowej (brak historycznej klasyfikacji sektorowej w darmowych danych) – ograniczenie.

## Bramka (bez zmian) + stabilność
Sharpe netto > 1.0, DSR > 0.95 (N = łączna liczba wpisów), MDD < 20%, ≥ 100 transakcji, permutacja p < 0.01,
dodatni Sharpe w każdym podokresie i brak zaniku w 2018–2022 (Sharpe ostatniego podokresu ≥ 50% średniej),
2× koszty → Sharpe > 0.5. Dopiero wtedy: jednorazowy holdout (`scripts/run_holdout.py`).
