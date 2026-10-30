# 02 – Rodzina P: pairs trading na spółkach WIG20

**Rejestr:** H001–H011 (H005 = INVALID, błąd stitchingu walk-forward – wykryty, naprawiony, test regresyjny dodany).

## Hipoteza
Spółki z tego samego sektora (banki: PKO, PEO, MBK, BHW, ING, MIL; energetyka: PGE, TPE, ENA) mają wspólne
czynniki ryzyka, więc odchylenia ich względnej wyceny (log-spread, 1:1 dolarowo neutralny) powinny wracać do średniej.
Pary wybrane **ex ante** z uzasadnienia sektorowego (bez skanowania wszystkich par – to oszczędza budżet testów).

## Implementacja
* Ceny Yahoo `.WA` skorygowane o dywidendy i splity (`adjclose`), usunięte wiersze z wolumenem 0
  (Yahoo zawiera dni świąteczne GPW z fałszywymi cenami, np. ING 2013-08-15).
* z-score log-spreadu z okna L; wejście przy |z|>z_in (decyzja po zamknięciu d, wykonanie na otwarciu d+1),
  wyjście przy |z|<0.5, przecięciu zera lub po L sesjach.
* Koszty: 0.29% prowizji + 0.10% poślizgu na stronę **na każdą nogę** (spread = 2 nogi), pożyczka akcji 3% p.a.
* Portfel 8 par, równe wagi kapitału (para bez danych = gotówka).

## Wyniki (walk-forward OOS 2008-01 – 2022-06, po kosztach)

| ID | wariant | SR netto | SR brutto | ann. ret | MDD | transakcje | p perm. |
|---|---|---|---|---|---|---|---|
| H006 | P1: L∈{20,60}, z_in∈{1.5,2.0} | 0.31 | 1.34 | 2.7% | 21.1% | 586 | 0.003 |
| H011 | P2: L∈{60,120}, z_in∈{2.5,3.0} | 0.21 | 0.63 | 1.4% | 12.1% | 158 | 0.003 |

In-sample (cały okres research) brutto SR 1.3–1.95 dla krótkich okien – **mean-reversion w spreadach bankowych
istnieje**, ale przy kosztach akcji (~1.6% round-trip na spread) netto jest bliskie zera. Szersze progi
zmniejszają obrót, ale proporcjonalnie zmniejszają też brutto przewagę.

## Wniosek
Odrzucone. Efekt jest prawdziwy brutto (permutacja p=0.003), ale nie przeżywa realnych kosztów detalicznych.
Dalsze dłubanie (inne progi, inne pary) to klasyczne przeuczanie – zamykam rodzinę. Ewentualna przewaga
istniałaby tylko przy kosztach instytucjonalnych (<0.1%/stronę), co jest poza założeniami projektu.
