# 03 – FW20, iteracja 1: kalendarz, trend, mean-reversion, lead-lag, FX, OI, ML

**Rejestr:** H012–H071. Instrument: ciągły FW20 (rolowanie 3 sesje przed wygaśnięciem), koszty bazowe
2 pkt/stronę (~8–9 bps), walk-forward OOS 2008-01 – 2022-06 (rozszerzane okno, wybór parametru po
in-sample Sharpe netto z lat poprzednich).

**Benchmark (nie test):** buy & hold FW20 2008–2022-06, netto z rolowaniem: SR −0.10, MDD 64%, CAGR −5.3%
(WIG20 jako indeks cenowy stał w miejscu, a kontrakt traci dodatkowo na dyskoncie dywidendowym).

## Wyniki walk-forward (OOS, po kosztach)

| ID | hipoteza | uzasadnienie | SR netto | SR brutto | trans. | p perm. |
|---|---|---|---|---|---|---|
| H018 | C1 turn-of-month (k_end∈1..3, n_start∈2..3) | napływy OFE/pensje na początku miesiąca | −0.02 | 0.18 | 175 | 0.19 |
| H019 | C2 sesja przed świętem | efekt przedświąteczny (lit. międzynarodowa) | −0.63 | −0.25 | 110 | 0.86 |
| H024 | T1 TSMOM L/S (L∈20..250) | time-series momentum | −0.11 | 0.01 | 176 | 0.42 |
| H028 | T2 long-only nad MA(L) | unikanie bessy | 0.07 | 0.19 | 89 | 0.11 |
| H035 | M1 odwrócenie po ruchu >zσ (k∈1,3,5) | przereagowanie | −0.19 | −0.04 | 126 | 0.57 |
| H039 | M2 RSI(2) dip w trendzie | popularna reguła detaliczna | −0.18 | −0.04 | 54 | 0.57 |
| H044 | L1 S&P(d−1) → FW20 sesja d (kontynuacja/odwrócenie) | niedoreakcja otwarcia | −0.90 | 0.18 | 1220 | 0.12 |
| H062 | L2 rezydualny ruch S&P po zamknięciu GPW → sesja d | j.w., czystszy sygnał | −1.06 | 0.29 | 1770 | 0.07 |
| H067 | L3 (DAX+S&P)(d) → FW20 sesja d+1 | j.w. | −0.70 | 0.35 | 1005 | 0.10 |
| H053 | F1 −sign(ΔEURPLN k dni) (NBP fixing) | napływ kapitału zagr. | −0.18 | 0.05 | 388 | 0.40 |
| H057 | O1 trend potwierdzony przyrostem OI | pozycjonowanie | −0.25 | 0.02 | 361 | 0.38 |
| H071 | X1 LightGBM, 46 cech, coroczny refit | nieliniowe interakcje | −0.57 | 0.16 | 1141 | 0.30 |

## Błąd wykryty po drodze (H045–H049 → INVALID)
Pierwsza wersja L2 dała brutto SR 2.26 / netto 0.79 przy p=0.003 – „za dobrze”. Przyczyna: reszta
S&P liczona była względem zwrotu FW20 **z dnia handlu d** (zamiast d−1), czyli sygnał widział wynik
sesji, którą handlował. Wiersze oznaczone INVALID (wciąż liczą się do N w DSR – konserwatywnie).
Dodałem `quant/lookahead.py` + `scripts/check_lookahead.py`: empiryczny detektor, który zaburza
open/close sesji T i notowania zagraniczne z dnia T i sprawdza, że żadna wcześniejsza decyzja się nie zmienia.
Wykrywa ten błąd i przepuszcza wszystkie pozostałe warianty; cechy ML przechodzą analogiczny test.

## Wnioski
* Dzienny szereg FW20 nie ma w latach 2008–2022 użytecznej przewidywalności kierunku: brutto SR OOS ≤ 0.35 we
  wszystkich rodzinach, permutacje nieistotne. Model ML z 46 cechami nie robi nic lepszego niż proste reguły.
* Strategie „sesyjne” (O→C) płacą round-trip ~17 bps dziennie; brutto przewaga lead-lag (SR 0.2–0.35) jest
  o rząd wielkości za mała. Informacja z USA/DAX jest wyceniana na otwarciu FW20 (brak sesji wieczornej).
* Jedyny realny sygnał w projekcie do tej pory: mean-reversion relatywna między spółkami (rodzina P, brutto
  SR 1.3+), zabijana przez koszty akcji na obu nogach. Kolejny krok: tańsza realizacja tej samej idei –
  odwrócenie **rezydualnego** ruchu spółki względem indeksu, noga długa w akcji, zabezpieczenie krótkim FW20
  (koszt FW20 ~0.09% vs 0.39% akcji, brak kosztu pożyczki).
