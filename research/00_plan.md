# 00 – Plan badawczy (spisany PRZED pobraniem jakichkolwiek danych)

Data: 2026-10-30

## 1. Pre-commitment: podział danych

Decyzje podjęte zanim zobaczyłem jakiekolwiek ceny (zapisane w `src/quant/config.py`, pierwszy commit repo):

| Okres | Zakres | Uwagi |
|---|---|---|
| Research (trening + walidacja walk-forward) | 2005-01-01 – 2022-06-30 | ~17.5 roku |
| **HOLDOUT** | **2022-07-01 – koniec danych (~2026-10)** | ~4.3 roku ≈ 20% okresu 2005–2026 |

* Start 2005: po wejściu PL do UE (stabilniejszy reżim EUR/PLN), FW20 już płynny, dostępne dane DAX/S&P/FX.
* Wszystkie loadery researchowe (`quant.data.store.load_research`) obcinają dane do `< HOLDOUT_START`.
  Test jednostkowy pilnuje, że żaden loader researchowy nie zwraca dat z holdoutu.
* Holdout odpalany jest wyłącznie przez `scripts/run_holdout.py`, który zapisuje `holdout/holdout_result.json`
  i blokuje ponowne uruchomienie (plik-zamek). Każda próba dostrojenia po porażce = złamanie reguł.
* Kontrola jakości danych w holdoucie ogranicza się do kompletności (brakujące sesje, NaN) – bez statystyk zwrotów.

## 2. Instrument i koszty (bazowe, konserwatywne)

* Instrument główny: ciągła seria FW20 (front-month, rolowanie N=5 sesji przed wygaśnięciem, wygasanie
  w 3. piątek III/VI/IX/XII, a jeśli to nie sesja – poprzedni dzień sesyjny).
* Mnożnik: 20 PLN/pkt (koszty liczone tak, jakby obecny mnożnik obowiązywał cały czas – konserwatywnie
  dla prowizji stałej w PLN przy starym mnożniku 10 PLN jest to nawet zaniżenie, więc dodatkowo test 2× kosztów).
* Koszt jednej strony transakcji: **prowizja 10 PLN/kontrakt + 1.5 pkt (spread + poślizg)**
  ≈ 2.0 pkt ≈ 8–9 bps notionalu przy WIG20≈2300. Round-trip ≈ 17 bps. Stress test: 2× koszty.
* Rolowanie = zamknięcie starej + otwarcie nowej serii = 2 strony kosztu.
* Akcje (pary): 0.29% prowizji/stronę (min. 5 PLN pomijam przy dużym kapitale) + 0.10% spread/poślizg,
  krótka sprzedaż +3% p.a. kosztu pożyczki. Akcje z WIG20 mają survivorship bias (dzisiejszy skład) – opisane jako ograniczenie.

## 3. Model wykonania (anty look-ahead)

Siatka zdarzeń dziennych: `O_d` (otwarcie), `C_d` (zamknięcie). Decyzja podjęta „w zdarzeniu k” może używać
tylko informacji dostępnych przed zdarzeniem k+1 i jest realizowana po cenie zdarzenia k+1 (następny bar).
* Decyzja po sesji d (dane WIG20/FW20 do C_d, DAX C_d 17:30, US C_d 22:00, FX z dnia d) → wykonanie na O_{d+1}.
* Decyzja w trakcie sesji d (dane do O_d, rynki zagraniczne tylko z d-1) → wykonanie na C_d.
* Dane zagraniczne łączone `merge_asof` ściśle wcześniejszą datą (różne kalendarze świąt).

## 4. Walidacja

1. Research okres: walk-forward (rozszerzane okno, re-fit raz na rok, test na kolejnym roku) – łączone OOS = „wynik walidacji”.
   Dla ML: purged k-fold CV z embargo (López de Prado) wewnątrz okien treningowych.
2. Każdy wariant -> wiersz w `hypotheses_log.csv` (również porażki, również warianty parametrów).
3. Korekta na wielokrotne testowanie: Deflated Sharpe Ratio z N = liczba wszystkich wariantów w rejestrze
   (wariancja SR z rejestru), dodatkowo BH-FDR na p-value i White Reality Check (stationary bootstrap) w obrębie rodzin.
4. Odporność: siatka ±20% parametrów (bez ostrych szczytów), podokresy (min. 3 rozłączne), koncentracja PnL
   (udział top-5 transakcji), ≥100 transakcji w OOS.
5. Sanity: buy&hold WIG20 + test permutacyjny (losowe przesunięcia/przetasowania sygnału).

## 5. Kryterium wyboru kandydata do holdoutu (wszystkie na OOS walk-forward, po kosztach)

* Sharpe ≥ 1.0, DSR > 0.95 (przy N z rejestru), MDD < 20%, ≥100 transakcji,
* sąsiedztwo ±20% parametrów: Sharpe ≥ 0.7 dla wszystkich sąsiadów,
* dodatni Sharpe w każdym z ≥3 podokresów, p-value permutacji < 0.01, przeżywa 2× koszty (Sharpe > 0.5).

Kryteria sukcesu na holdoucie (jednorazowo): Sharpe > 1.0 po kosztach, DSR istotny, MDD < 20%,
Sharpe_holdout ≥ 0.5 × Sharpe_walidacja.

## 6. Kolejność hipotez (priorytet wg ekonomicznego uzasadnienia, budżet ≤ 200 wariantów)

1. Efekty kalendarzowe na FW20 (turn-of-month, dzień tygodnia, tydzień wygasania) – mało parametrów.
2. Lead-lag: S&P/ES, DAX z poprzedniego dnia → sesja WIG20 (open→close), luka otwarcia.
3. Momentum / mean-reversion w horyzontach 1–60 dni, filtry reżimu zmienności.
4. FX (EUR/PLN, USD/PLN) jako proxy przepływów zagranicznych.
5. Pary / kointegracja (banki, KGHM–miedź, Orlen–ropa) – z realnymi kosztami akcji.
6. ML (LightGBM) na zbiorze cech z 1–5 – na końcu, z purged CV i liczeniem każdej konfiguracji w rejestrze.

Reguła stopu: ~200 wariantów w rejestrze bez kandydata spełniającego p.5 → raport negatywny.
