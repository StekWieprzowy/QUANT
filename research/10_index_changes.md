# 10 – Faza 3, część A: zmiany składu WIG20 / mWIG40 / sWIG80

**Rejestr:** H195–H206 (12 z limitu 15). Skrypt: `scripts/phase4_index.py`; dane: `reports/phase4/index_events.csv`,
`index_summary.csv`. Pre-rejestracja: `research/09_phase3_preregistration.md`.

## Dane
* Składy po każdej rewizji (PDF gpwbenchmark.pl, 70 rewizji 2009–2026 × WIG20/mWIG40/sWIG80) – `fetch_events.py`.
* **Daty ogłoszeń** z „Kalendarium indeksów” GPW Benchmark 2012–2026 (60 par ogłoszenie → rewizja; wszystkie 60
  dat rewizji zgodne z datami PDF; ogłoszenie 14–38 dni przed rewizją, od 2018 r. stale 15 dni).
  Pierwsza wersja parsera myliła komórki kalendarza (odstępy 63–169 dni) – poprawiona przed obliczeniem wyników.
* Ceny: pełne archiwum GPW (akcje, 2009–2022H1, 661 ISIN-ów, także wycofane); zwrot = GPW „Zmiana”
  (korygowana o dywidendy/splity/prawa poboru). Rynek = WIG.
* **Weryfikacja ręczna:** Mercator → WIG20 (2021-03), mBank powrót do WIG20 (2022-03), Pepco → WIG20 (2022-03),
  CD Projekt (2018-03), Dino i Play (2019-03), Allegro (2020-12) – zgodne z faktami; PDF 2022-03-18 zawiera PEPCO.

## Wyniki (AR vs WIG, N, 95% CI bootstrap, p t-test; BH łącznie z 70 p-value w rejestrze)

| ID | indeks / typ / okno | N | średnia AR | 95% CI | p | netto w oczek. kierunku (N handl.) | 2012–16 / 2017–22 (ze znakiem) | BH |
|---|---|---|---|---|---|---|---|---|
| H195 | WIG20 dodanie [ogł+1, rew] | 20 | +1.7% | [−1.4, +4.7] | 0.30 | +0.4% (20) | +1.7% / +1.7% | ✗ |
| H196 | WIG20 dodanie [rew+1, +10] | 20 | −1.6% | [−4.2, +1.0] | 0.26 | +0.2% (20) | +0.9% / +2.4% | ✗ |
| H197 | WIG20 usunięcie [ogł+1, rew] | 20 | −3.0% | [−10.8, +2.6] | 0.39 | +1.3% (20) | +6.6% / −1.3% | ✗ |
| H198 | WIG20 usunięcie [rew+1, +10] | 20 | −0.1% | [−2.8, +2.7] | 0.93 | −1.7% (20) | +1.1% / −1.7% | ✗ |
| H199 | mWIG40 dodanie [ogł+1, rew] | 97 | +2.6% | [−0.1, +5.0] | 0.048 | +0.4% (65) | +0.6% / +4.5% | ✗ |
| H200 | mWIG40 dodanie [rew+1, +10] | 97 | −0.6% | [−2.6, +1.4] | 0.56 | −1.2% (65) | +0.1% / +1.1% | ✗ |
| H201 | mWIG40 usunięcie [ogł+1, rew] | 91 | **−3.4%** | [−5.9, −1.0] | **0.009** | −0.9% (35) | +3.7% / +3.1% | ✗ |
| H202 | mWIG40 usunięcie [rew+1, +10] | 91 | +1.9% | [+0.1, +3.6] | 0.039 | −1.4% (35) | +0.4% / +3.2% | ✗ |
| H203 | sWIG80 dodanie [ogł+1, rew] | 282 | −1.1% | [−2.3, +0.1] | 0.077 | −4.7% (54) | −1.6% / −0.7% | ✗ |
| H204 | sWIG80 dodanie [rew+1, +10] | 282 | +0.9% | [−0.1, +1.9] | 0.074 | −3.2% (54) | −0.7% / −1.1% | ✗ |
| H205 | sWIG80 usunięcie [ogł+1, rew] | 275 | −1.6% | [−3.5, +0.1] | 0.085 | −2.9% (40) | +2.9% / +0.6% | ✗ |
| H206 | sWIG80 usunięcie [rew+1, +10] | 275 | −0.9% | [−2.3, +0.5] | 0.20 | −4.7% (40) | −0.5% / −1.3% | ✗ |

## Interpretacja
* **Nic nie przeżywa korekty BH** (70 p-value). Najmocniejszy wynik – spadek usuwanych z mWIG40 między ogłoszeniem a
  rewizją (−3.4%, p=0.009) i odbicie po (+1.9%) – **siedzi w spółkach niehandlowalnych**: dla ADV < 0.5 mln PLN
  −4.5% (N=56, p=0.007) i odbicie +2.5% (p=0.003); dla handlowalnych (ADV ≥ 0.5 mln) −1.6% (N=35, p=0.44).
  Skrajne przypadki to spółki w kryzysie (New World Resources −44%, IDM −42%, Bioton −39%) – usunięcie z indeksu
  jest skutkiem załamania, nie przyczyną spadku. (Podział wg płynności – opis już zalogowanych wyników, nie nowy test.)
* sWIG80: znak „odwrotny” wynika z mechaniki – dodania do sWIG80 to w dużej mierze spółki zdegradowane z mWIG40,
  a usunięcia – awanse do mWIG40.
* WIG20 (N=20 z datami ogłoszeń): run-up przed rewizją +1.7%, oddanie −1.6% – kierunek jak w fazie 2 (H174/H176),
  ale nieistotne.
* **Netto przy kosztach zależnych od płynności: żadne okno nie daje sensownego zysku** (najlepsze +0.4% przed rewizją
  dla dodań, przy dużym rozrzucie).

## Decyzja (wg pre-rejestracji)
Kryterium włączenia do części B (istotność po BH + dodatnie w obu połowach) – **niespełnione**. Sygnał IDX
nie wchodzi do portfela. Do playbooka: tylko jako kontekst (ostrożność wobec spółek usuwanych z mWIG40 – zwykle
w kryzysie i niepłynne).
