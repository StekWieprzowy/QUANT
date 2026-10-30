# 01 – Jakość danych (generowane przez scripts/check_data.py)

## Sesje FW20 (GPW archiwum) – kompletność

Zakres: 2005-01-03 – 2026-10-29, sesji: 5462

| rok | sesje |
|---|---|
| 2005 | 251 |
| 2006 | 251 |
| 2007 | 249 |
| 2008 | 251 |
| 2009 | 252 |
| 2010 | 253 |
| 2011 | 251 |
| 2012 | 249 |
| 2013 | 247 |
| 2014 | 249 |
| 2015 | 251 |
| 2016 | 251 |
| 2017 | 250 |
| 2018 | 247 |
| 2019 | 248 |
| 2020 | 252 |
| 2021 | 251 |
| 2022 | 251 |
| 2023 | 250 |
| 2024 | 249 |
| 2025 | 249 |
| 2026 | 210 |

Sesje WIG20 bez FW20: 0 []
Sesje FW20 bez WIG20: 0 []

Dni robocze bez sesji (święta / przerwy): 232; przykłady: ['2005-03-25', '2005-03-28', '2005-04-08', '2005-05-03', '2005-05-26', '2005-08-15', '2005-11-01', '2005-11-11', '2005-12-26', '2006-04-14', '2006-04-17', '2006-05-01', '2006-05-03', '2006-06-15', '2006-08-15']

## Ciągła seria FW20

Brakujące bary trzymanego kontraktu: research 0, holdout 0
NaN open: research 0, holdout 0
Niespójne OHLC (research): 0

## Rolowanie (research)

Liczba rolowań: 70; udział wolumenu następnej serii w dniu rolowania: mediana 34%, min 6% (2006-06-12)
Rolowanie N=3 sesji przed wygaśnięciem (wybrane na podstawie płynności: udział wolumenu następnej serii wg liczby sesji do wygaśnięcia k: k=5: 9%, k=4: 20%, k=3: 34%, k=1: 44%) – decyzja oparta wyłącznie na wolumenie, nie na wynikach strategii.

## Największe dzienne ruchy FW20 (research, |r|>6%) – weryfikacja ręczna

| data | kontrakt | log-ret |
|---|---|---|
| 2006-05-22 | FW20M06 | -0.061 |
| 2008-01-21 | FW20H08 | -0.063 |
| 2008-10-06 | FW20Z08 | -0.070 |
| 2008-10-10 | FW20Z08 | -0.088 |
| 2008-10-15 | FW20Z08 | -0.062 |
| 2008-10-17 | FW20Z08 | -0.063 |
| 2008-10-22 | FW20Z08 | -0.084 |
| 2008-10-29 | FW20Z08 | +0.078 |
| 2008-11-12 | FW20Z08 | -0.108 |
| 2008-11-24 | FW20Z08 | +0.107 |
| 2009-01-14 | FW20H09 | -0.064 |
| 2009-02-17 | FW20H09 | -0.094 |
| 2009-04-02 | FW20M09 | +0.069 |
| 2009-06-01 | FW20M09 | +0.065 |
| 2009-06-22 | FW20U09 | -0.065 |
| 2011-08-10 | FW20U11 | -0.072 |
| 2011-08-18 | FW20U11 | -0.065 |
| 2011-09-22 | FW20Z11 | -0.082 |
| 2013-06-20 | FW20U13 | -0.066 |
| 2020-03-09 | FW20H20 | -0.085 |
| 2020-03-11 | FW20H20 | -0.062 |
| 2020-03-12 | FW20H20 | -0.127 |
| 2020-03-17 | FW20H20 | +0.075 |
| 2020-03-19 | FW20M20 | +0.063 |
| 2020-03-23 | FW20M20 | -0.064 |
| 2022-02-24 | FW20H22 | -0.122 |
| 2022-02-25 | FW20H22 | +0.090 |

Luka otwarcia: mediana |gap| 0.0031, odsetek open==prev_close 5.6%

## Dane zagraniczne (Yahoo) – research

| symbol | od | sesje | max|r| | data |
|---|---|---|---|---|
| ^GDAXI | 2005-01-03 | 4439 | 0.131 | 2020-03-12 |
| ^GSPC | 2005-01-03 | 4404 | 0.128 | 2020-03-16 |
| ES=F | 2005-01-03 | 4409 | 0.132 | 2008-10-13 |
| ^VIX | 2005-01-03 | 4404 | 0.768 | 2018-02-05 |
| ^STOXX50E | 2007-03-30 | 3822 | 0.132 | 2020-03-12 |
| ^IXIC | 2005-01-03 | 4404 | 0.131 | 2020-03-16 |
| HG=F | 2005-01-03 | 4400 | 0.118 | 2008-10-29 |
| BZ=F | 2007-07-30 | 3703 | 0.280 | 2020-04-21 |
| CL=F | 2005-01-03 | 4401 | 0.320 | 2020-04-22 |
| GC=F | 2005-01-03 | 4397 | 0.098 | 2013-04-15 |
| EURPLN=X | 2005-01-03 | 4536 | 0.048 | 2008-10-28 |
| USDPLN=X | 2005-01-03 | 4535 | 0.097 | 2008-08-26 |
| EURUSD=X | 2005-01-03 | 4536 | 0.160 | 2008-12-08 |
| ^TNX | 2005-01-03 | 4399 | 0.405 | 2020-03-10 |
| EEM | 2005-01-03 | 4404 | 0.205 | 2008-10-13 |
| EPOL | 2010-05-26 | 3046 | 0.148 | 2020-03-12 |
| ^N225 | 2005-01-04 | 4280 | 0.132 | 2008-10-14 |

Uwaga: kursy FX z Yahoo zawierają błędne ticki (np. EURUSD 2008-12-08 +16%) – do PLN używamy fixingu NBP.
