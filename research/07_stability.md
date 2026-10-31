# 07 – Faza 2, część 2: stabilność w czasie

Skrypt: `scripts/phase2_stability.py` → `reports/phase2/stability.json`, `reports/figures/rolling_sharpe_2y.png`.
Dane: dzienne zwroty netto walk-forward OOS przy kosztach bazowych (te same co w rejestrze).
Reguła (ustalona przed obliczeniem): wariant „zanika”, jeśli Sharpe ostatniego podokresu < 0 albo nachylenie
rocznych Sharpe'ów jest ujemne z p < 0.10; dodatkowo odrzucam warianty, których ostatni podokres jest ≈ 0
przy wyraźnie dodatnich wcześniejszych (przewaga praktycznie zniknęła).

## Sharpe netto w podokresach

| wariant | całość | 2008–2012 | 2013–2017 | 2018–2022H1 | nachylenie/rok (p) | werdykt |
|---|---|---|---|---|---|---|
| R1 | 0.16 | −0.03 | 0.87 | −0.19 | −0.015 (0.81) | zanika → odrzucony |
| R2 | 0.45 | 0.73 | 1.05 | 0.00 | −0.039 (0.57) | zanika → odrzucony |
| P1 | 0.31 | 0.20 | 0.71 | 0.07 | −0.006 (0.87) | ostatni okres ≈ 0 → odrzucony |
| E1 | 0.46 | 0.51 | 1.02 | 0.05 | −0.030 (0.50) | ostatni okres ≈ 0 → odrzucony |
| CA2 | 0.31 | 0.60 | 0.80 | −0.21 | −0.042 (0.54) | zanika → odrzucony |
| CA5 | 0.28 | 0.33 | 0.55 | 0.02 | −0.059 (0.23) | ostatni okres ≈ 0 → odrzucony |
| CA7 | −0.16 | 0.19 | −0.37 | −0.27 | −0.052 (0.21) | zanika → odrzucony |
| K1 | 0.53 | 0.27 | 1.02 | 0.38 | −0.018 (0.82) | stabilny, ale nieistotny (perm. p=0.18) |

## Czy zanika przewaga brutto, czy tylko netto?

| | brutto 2008–12 | brutto 2013–17 | brutto 2018–22H1 | obrót/rok (bez zmian) |
|---|---|---|---|---|
| P1 | 1.14 | 1.98 | 0.99 | 8.8 → 11.3 → 10.2 |
| R2 | 0.96 | 1.47 | 0.27 | 1.2 → 1.4 → 2.2 |
| E1 | 1.38 | 2.33 | 0.86 | 3.6 → 4.5 → 4.7 |
| K1 | 0.47 | 1.30 | 0.59 | ~3.4 |

Zanika **sama przewaga brutto** przy stałym obrocie – to nie efekt kosztów, tylko zmiana rynku. Możliwe
przyczyny (hipotezy, niezweryfikowane): więcej algorytmicznych dostawców płynności / animatorów na GPW po 2017,
szoki sektorowe łamiące relacje par (podatek bankowy, wyroki CHF, COVID, wojna, polityka wobec spółek SP),
większy udział ETF/PPK.

Rolling 2-letni Sharpe: wszystkie warianty relative value mają szczyt 2016–2017 (R2 ~2.6) i spadają poniżej
zera w 2019–2021. Nie ma podstaw, by oczekiwać, że holdout (2022-07 →) odwróci ten trend.

## Wniosek
Żaden kandydat z części 1 ani z poprzednich faz nie przechodzi testu stabilności w połączeniu z pozostałymi
kryteriami. Rodzinę relatywnej mean-reversion zamykam dla automatycznego tradingu przy kosztach detalicznych.
