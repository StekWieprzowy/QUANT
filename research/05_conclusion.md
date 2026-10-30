# 05 – Korekta finansowania, ostatnie rodziny, decyzja o zakończeniu

**Rejestr:** H097–H128.

## Iteracje
* **R3** (H101): rezydualne odwrócenie tylko w reżimie wysokiej zmienności (Nagel 2012) → SR 0.06 (gorzej niż bez filtra).
* **X2** (H104): LightGBM na panelu spółka×dzień do selekcji transakcji R → SR −0.22 (gorzej niż prosty z-score).
* **K1/K2** (H107/H110): momentum przekrojowe i low-vol, miesięcznie, hedge FW20 → 0.68 / 0.25, ale K1 p perm. 0.17.

## Odkryty błąd księgowy: carry w hedgu
Pozycja „długa akcja, krótki FW20” zarabia stopę bez ryzyka (kontrakt wyceniany z r − q), jeśli nie obciąży się
finansowania nogi akcyjnej. Test permutacyjny był na to odporny (przesunięty sygnał ma tę samą ekspozycję i ten sam
carry – stąd K1 nieistotne), ale Sharpe/zwroty były zawyżone. Wiersze R1/R2/R3/X2/K1/K2 oznaczone INVALID,
dodane finansowanie (stopa referencyjna NBP + 0.25 pp), powtórzone R1/R2/K1:
H115 R1 0.16, H120 R2 0.45, H123 K1 0.53 (p 0.18).

## E1 – portfel słabych, ale istotnych przewag
H128: P1 (pary) + R2, wspólny walk-forward po siatce 2×2: SR netto 0.46, brutto 1.42, MDD 9.5%, 758 transakcji,
p perm. 0.003, podokresy 0.51 / 1.06 / 0.05; odpada na Sharpe, DSR, 2× kosztach i sąsiadach.

## Statystyki końcowe (scripts/final_stats.py)
White RC p = 0.94, studentyzowany p = 0.28, SR₀ (DSR) ≈ 1.4. Szczegóły i wrażliwość na koszty w REPORT.md.

## Decyzja
Stop przy 128/200. Rodziny z przestrzeni startowej i trzy dodatkowe są pokryte; dalsze warianty to byłoby
mielenie parametrów rodzin, które już zawiodły, przy rosnącym progu DSR. Holdout pozostaje nieużyty.
