# 04 – Relative value: rezydualne odwrócenie spółek (R) i FW20 vs DAX (G)

**Rejestr:** H072–H096 (H072–H076 = INVALID: błędne ticki Yahoo).

## Motywacja (z 02 i 03)
Jedyny powtarzalny sygnał brutto: relatywna mean-reversion (pary bankowe brutto SR 1.3). Cel: ta sama idea
taniej. (R) noga długa w akcji + krótki FW20 w wysokości bety (FW20 ~0.09%/stronę, bez pożyczki akcji);
(G) dwa tanie kontrakty: FW20 vs DAX.

## Problem z danymi wykryty po drodze (H072–H076 → INVALID)
Pierwszy przebieg R1 miał ann_vol 166% przy MDD 6% – sprzeczność. Przyczyna: błędne ticki otwarcia w Yahoo
(ACP 2012-10-18 open=4626 przy close 40.24; CDR/Optimus 2006-08-29). Naprawa: `scripts/fix_stock_gaps.py`
pobiera **oficjalne notowania GPW** dla wszystkich 50 dni, w których którakolwiek spółka z uniwersum miała lukę
>10%, i podmienia open/high/low (ISIN-y zweryfikowane). GPW potwierdził m.in., że PKN 2016-06-24 (Brexit)
naprawdę otworzył się na 59.00 – to nie błąd.

## Wyniki walk-forward (OOS 2008-01 – 2022-06, netto)

| ID | wariant | SR netto | SR brutto | ann. ret | MDD | trans. | p perm. |
|---|---|---|---|---|---|---|---|
| H081 | R1 rezydualne odwrócenie k∈{3,5}, z∈{1.5,2} | 0.21 | 1.03 | 0.5% | 5.8% | 492 | 0.003 |
| H086 | R2 to samo, k∈{10,20}, max 20 sesji | **0.50** | 0.78 | 1.2% | 5.4% | 172 | 0.003 |
| H091 | G1 spread FW20 − β·DAX (oba kontrakty) | 0.12 | 0.24 | 0.9% | 27.4% | 55 | 0.11 |
| H096 | G2 sam FW20 po odchyleniu od DAX | −0.34 | −0.26 | −3.5% | 54.2% | 56 | 0.84 |

(Niska zmienność R1/R2 wynika z kapitału dzielonego na 18 „slotów”; Sharpe jest od tego niezależny.)

## Wnioski
* Odwrócenie idiosynkratycznych ruchów spółek WIG20 jest **statystycznie realne** (permutacja p=0.003 w
  R1 i R2, brutto SR 0.8–1.0), ale koszt ~0.95% na round-trip zjada 50–80% przewagi. Dłuższy horyzont (R2)
  pomaga – większy ruch na transakcję przy tym samym koszcie.
* FW20 vs DAX nie wykazuje mean-reversion (dywergencje PL vs DE są trwałe – waluta, sektory, przepływy).
* Kolejne kroki z uzasadnieniem ekonomicznym (nie mielenie parametrów):
  1. R3 – odwrócenie jako zapłata za dostarczanie płynności powinno być silniejsze w okresach wysokiej
     zmienności rynku (Nagel 2012, „Evaporating liquidity”). Warunkowanie na reżim zmienności.
  2. X2 – model ML do selekcji transakcji rezydualnych (więcej informacji niż sam z-score).
