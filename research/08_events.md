# 08 – Faza 2, część 3: event studies i nietypowe źródła

**Rejestr:** H164–H194 (31 hipotez z limitu 60). Skrypt: `scripts/phase3_events.py` (każde badanie
pre-specyfikowane w kodzie: lista zdarzeń, okno, oczekiwany znak; dry-run bez logowania do wyłapania błędów
kodu – wykrył 3: NaN w teście wygasania, `port.isin` jako metoda, indeksowanie klucza sezonu).
Dane: `scripts/fetch_events.py` (stopy NBP z static.nbp.pl, historyczne portfele WIG20 z gpwbenchmark.pl –
70 rewizji 2009–2026, dywidendy z Yahoo, oficjalne kursy GPW ±15 sesji wokół 19 rewizji ze zmianą składu).
Metodologia: AR z modelu rynkowego vs WIG20 (estymacja [−250, −21]); zmiany indeksu – zwroty skorygowane o rynek
(kursy GPW, bez survivorship bias); test t + bootstrap 95% CI; BH (q=5%) i Bonferroni po wszystkich 31.

## Wyniki

| ID | badanie | okno | N | średnia | 95% CI | p | BH |
|---|---|---|---|---|---|---|---|
| H170 | Dywidenda: AR dnia odcięcia (total return) | [0] | 237 | **+0.77%** | [+0.49, +1.04] | <0.001 | ✔ |
| H173 | j.w., stopa dywidendy > 4% | [0] | 111 | **+0.79%** | [+0.45, +1.15] | <0.001 | ✔ |
| H183 | KGH sesja (O→C) d vs miedź d−1 (nachylenie) | [0] | 4219 | **0.084** | [0.045, 0.122] | <0.001 | ✔ |
| H194 | KGH − WIG20 w sesji po |Δmiedź| > 2σ (ze znakiem miedzi) | [0] | 235 | +0.34% | [+0.06, +0.61] | 0.017 | ✗ |
| H169 | Proxy wyników kw.: dryf po dniu szoku wolumenu (PEAD) | [+1,+10] | 324 | +0.79% | [−0.03, +1.65] | 0.063 | ✗ |
| H174 | Dodanie do WIG20: dryf przed rewizją | [−10,−1] | 27 | +2.11% | [0.00, +4.34] | 0.073 | ✗ |
| H176 | Dodanie do WIG20: odwrócenie po rewizji | [+1,+10] | 27 | −2.45% | [−4.62, −0.33] | 0.038 | ✗ |
| H187 | CD Projekt po premierze („sell the news”) | [0,+10] | 5 | −10.5% (mediana −2.4%) | [−25.6, −1.5] | 0.23 | ✗ |
| H188 | CD Projekt na opóźnienie Cyberpunka | [0,+1] | 3 | −3.9% | [−6.9, −0.5] | 0.17 | ✗ |
| H164–168 | RPP: FW20 i banki na obniżki/podwyżki, dryf po decyzji | różne | 22–48 | −0.5…+0.5% | obejmują 0 | ≥0.30 | ✗ |
| H171–172 | Dywidenda: run-up przed / odwrócenie po | ±10 | 235–237 | +0.45% / 0.00% | obejmują 0 | ≥0.16 | ✗ |
| H175, H177–179 | Indeks: dzień rewizji, usunięcia | różne | 27 | −0.8…+1.2% | obejmują 0 | ≥0.16 | ✗ |
| H180–181 | Wybory: spółki SP vs prywatne | [0], [0,+5] | 9 | ~0 | szerokie | ≥0.76 | ✗ |
| H182 | CHF: banki z portfelem frankowym na wyroki/szoki | [0,+1] | 5 | −0.35% | [−3.9, +3.3] | 0.88 | ✗ |
| H184 | KGH: ruch miedzi (PLN) nieodzwierciedlony → 20 dni | IC | 196 | −0.01 | [−0.15, +0.13] | 0.88 | ✗ |
| H185 | Crack spread 20d → PKN 20 dni | IC | 179 | +0.07 | [−0.08, +0.21] | 0.38 | ✗ |
| H186 | CD Projekt run-up przed premierą | [−20,−1] | 5 | −1.1% | szeroki | 0.84 | ✗ |
| H189–191 | FW20 w tygodniu wygasania / dzień / tydzień po | różnica | 70–350 | ±0.04 pp/dzień | obejmują 0 | ≥0.74 | ✗ |
| H192–193 | FW20 po szoku EUR/PLN ±2σ | [+1,+5] | 86–114 | −0.03 / +0.19% | obejmują 0 | ≥0.70 | ✗ |

## Weryfikacja wyników „za dobrych”
* **Dywidendy:** zanim zaakceptowałem, sprawdziłem, czy Yahoo nie przesuwa dat: mediana „drop ratio” (spadek
  ceny / dywidenda, skorygowany o rynek) = **0.79**, ruch dnia następnego ≈ 0 → daty poprawne (~8% podejrzanych).
  0.79 ≈ 1 − 19% podatku Belki: kurs spada o dywidendę *netto*. To nie arbitraż dla podatnika – zysk
  znika po podatku; dla rachunku zwolnionego (IKE/IKZE) zysk +0.77% ≈ koszt round-trip akcji (~0.78%). Stabilne:
  2005–12 +0.64%, 2013–17 +0.91%, 2018–22 +0.77%.
* **KGHM–miedź:** sprawdzone placebo (PKN, PKO: nachylenie ≈ 0), kontrola S&P (bez znaczenia), efekt
  względem WIG20 (t=3.3), luka otwarcia KGH wyjaśnia tylko część ruchu miedzi. Słabnie w czasie:
  nachylenie 0.08 (2005–12) → 0.15 (2013–17) → 0.04 (2018–22, p=0.37).

## Studia przypadków (N za małe na statystykę)
* **CHF:** szok SNB 2015-01-15 → banki frankowe AR −6% do −9% w 2 dni (kontrole BHW/ING/PEO +1%); wyroki
  TSUE 2019 – mieszane, 2021 (TSUE C-19/20, uchwała SN) – **dodatnie** (+3–6%, „koniec niepewności”). Kurs CHF
  ważniejszy niż orzeczenia; orzeczenia w dużej mierze zdyskontowane.
* **CD Projekt:** po wszystkich 5 premierach AR[0,+10] < 0 (W3 −8%, CP2077 −40%); run-up przed premierą
  niejednoznaczny (Thronebreaker −19%). Opóźnienia Cyberpunka: wszystkie 3 ujemne.
* **Wybory:** brak systematycznej reakcji SP vs prywatne; największy ruch 2019-10-13 (z = −2.8, mimo
  przewidywalnego wyniku).
* **Dodania do WIG20:** część to szybkie wejścia po IPO (PGE, PZU, Tauron 2010; Allegro 2020), które zaburzają
  obraz. Mediana: przed +0.9%, po −2.6%.
* **Wygasanie FW20:** brak efektu w średniej, ale **zmienność w dzień wygasania niższa** (odch. std. 1.08% vs
  1.54% w zwykłe dni) – możliwy „pinning” (nie testowany formalnie).

## Źródła niedostępne / niezweryfikowane (→ THEORIES.md)
KNF rejestr krótkich pozycji (brak eksportu historycznego), insiderzy MAR / ESPI (PAP zablokowany),
IZFiA→izfa.pl (domena zablokowana), rekomendacje DM, Google Trends/fora, typy komunikatów ESPI,
GUS CPI/PKB (stat.gov.pl wciąż 403), rentowności obligacji PL (brak źródła), posiedzenia RPP bez zmiany stóp
(terminarz na www.nbp.pl za ścianą anty-botową – testowane tylko decyzje ze zmianą stóp).
