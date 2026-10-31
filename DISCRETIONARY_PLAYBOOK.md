# DISCRETIONARY PLAYBOOK – WIG20 / FW20

Ściąga dla tradera ręcznego: co ma **mierzalną, powtarzalną** reakcję cenową, jak dużą, jak długo trwa, jak
pewną i kiedy nie działa. Wszystkie liczby z okresu **2005 – czerwiec 2022** (dane po 2022-07 to nietknięty
holdout – nic tu nie jest zweryfikowane na latach 2022–2026). Źródła liczb: `reports/phase3/`,
`hypotheses_log.csv` (ID w nawiasach). Koszt round-trip akcji ≈ 0.6–0.8%, FW20 ≈ 0.17% – większość efektów
poniżej jest **mniejsza niż koszt** i nadaje się jako *filtr / kontekst*, nie samodzielny sygnał.

Skala pewności: ★★★ potwierdzone (przeżywa korektę na wielokrotne testowanie) · ★★ obiecujące
(p < 0.10, nie przeżywa korekty) · ★ anegdota / studium przypadku (N < 10) · ✗ brak efektu (nie trać czasu).

---

## ★★★ 1. Dzień odcięcia dywidendy – kurs spada o ~80% dywidendy, nie o 100%
* **Co:** w dniu odcięcia cena spada średnio o **0.79 × dywidenda brutto** (mediana), czyli mniej więcej o
  dywidendę *netto* po 19% podatku. Total return (cena + dywidenda) w dniu odcięcia: **+0.77% ponad rynek**.
* **Pewność:** N=237 (spółki WIG20 2005–2022), 95% CI [+0.49%, +1.04%], 70% przypadków dodatnich; stabilne:
  2005–12 +0.64%, 2013–17 +0.91%, 2018–22 +0.77%. Przy stopie > 4%: +0.79% (N=111). (H170, H173)
* **Jak długo:** tylko dzień 0. Brak run-upu przed (+0.45%, nieistotne) i brak odbicia po (0.00%).
* **Jak używać:** *nie* jako „dividend capture” na zwykłym rachunku – po 19% podatku zysk znika. Na rachunku
  zwolnionym z podatku (IKE/IKZE) zysk ~0.77% jest zjadany przez koszt round-trip (~0.78%) – opłacalne tylko
  przy bardzo niskich prowizjach i dużych dywidendach. Praktyczny wniosek: **jeśli i tak chcesz kupić spółkę
  przed dywidendą, dla podatnika obojętne jest, czy kupisz przed czy po dniu odcięcia**; wycena „po odcięciu”
  jest na ogół wyższa o ~20% dywidendy, niż sugeruje naiwny rachunek.
* **Kiedy nie działa:** dywidendy niespodziewane/nadzwyczajne, akcje mało płynne, dni z dużym ruchem rynku.

## ★★★ (słabnie) 2. KGHM dogania nocny ruch miedzi w trakcie sesji
* **Co:** miedź (COMEX) zamyka się po sesji GPW. Otwarcie KGH dyskontuje tylko część nocnego ruchu miedzi;
  reszta „dociąga” w sesji: **open→close KGH ≈ 0.084 × zwrot miedzi z poprzedniego dnia** (H183, N=4219,
  CI [0.045, 0.122]). Placebo: PKN, PKO – zero; efekt istnieje także względem WIG20.
* **Praktycznie:** po dniach z dużym ruchem miedzi (|Δ| > 2σ, ok. 3–4% ruchu, ~14 razy w roku) KGH
  wypracowuje w sesji **+0.34% ponad WIG20 w kierunku miedzi** (H194, N=235, CI [+0.06%, +0.61%], trafność 55%).
* **Jak długo:** jedna sesja (od otwarcia do zamknięcia); brak efektu w horyzoncie 20 dni (H184).
* **Kiedy nie działa / uwaga:** efekt **słabnie** – nachylenie 0.08 (2005–12), 0.15 (2013–17), 0.04 (2018–22,
  nieistotne). Mniejszy niż koszt round-trip na akcjach; jako filtr: *nie graj przeciw miedzi w pierwszych
  godzinach po dużym nocnym ruchu*. Kontrakt FKGH tańszy, ale płytki (~0.9 mln PLN/dzień).

## ★★ 3. Dodanie do WIG20: run-up przed rewizją, oddanie po
* **Co:** spółki wchodzące do WIG20 zyskują ~**+2.1%** ponad rynek w 10 sesjach przed 3. piątkiem miesiąca
  rewizji (CI [0.0%, +4.3%], p=0.07) i oddają ~**−2.5%** w 10 sesjach po (CI [−4.6%, −0.3%], p=0.04,
  67% przypadków ujemnych). N=27 dodań (2010–2022), dane GPW bez survivorship bias. (H174, H176)
* **Dzień rewizji (zamknięcie funduszy indeksowych):** brak efektu (−0.8%, nieistotne).
* **Kiedy nie działa:** szybkie wejścia po IPO (PGE, PZU, Tauron, Allegro) zachowują się inaczej; usunięcia
  z indeksu nie mają powtarzalnej reakcji (N=27, wszystko nieistotne). Po korekcie na liczbę testów –
  tylko wskazówka. Daty rewizji i lista zmian: gpwbenchmark.pl (ogłaszane ~2 tygodnie wcześniej).

## ★★ 4. Dryf po wynikach (proxy) – reakcja na szok w sezonie raportów kontynuuje się
* **Co:** pierwszy dzień w sezonie raportów z wolumenem > 3× normy i ruchem > 2σ (proxy publikacji wyników):
  w kolejnych 10 sesjach kurs dryfuje dalej w kierunku dnia 0 o średnio **+0.79%** (N=324, CI [−0.03%, +1.65%],
  p=0.06). Trafność tylko 50% – średnią robią duże przypadki (prawy ogon).
* **Uwaga:** to proxy (brak dat publikacji raportów w danych). Do sprawdzenia na prawdziwych datach (THEORIES #3).

## ★ 5. CD Projekt – „sell the news” po premierach, kara za opóźnienia
* Po wszystkich 5 premierach (Wiedźmin 3, 2 dodatki, Thronebreaker, Cyberpunk 2077) AR [0,+10] < 0; mediana
  −2.4%, średnia −10.5% (Cyberpunk −40%). Run-up przed premierą niejednoznaczny. Opóźnienia Cyberpunka (3×):
  −0.5% do −6.9% w 2 dni. N za małe na statystykę – traktuj jako regułę kciuka: *nie trzymaj spekulacyjnie
  przez dzień premiery*.

## ★ 6. Banki frankowe – kurs CHF ważniejszy niż wyroki
* Szok SNB 15.01.2015: mBank, Millennium, PKO −6% do −9% w 2 dni (BHW/ING/PEO +1%). Wyroki TSUE 2019 –
  reakcje mieszane; TSUE/SN 2021 – **dodatnie** (+3–6%, ulga po „końcu niepewności”). N=5 – brak statystyki.
  Wniosek: rynek dyskontuje orzeczenia z wyprzedzeniem; reaguje na *zaskoczenie* (kurs CHF, skala rezerw).

---

## ✗ Nie trać czasu (brak mierzalnego efektu w 2005–2022)
| zdarzenie | wynik | ID |
|---|---|---|
| Decyzje RPP (obniżki/podwyżki) – FW20 i banki, reakcja i dryf 5 dni | wszystko w granicach szumu (N=22–48) | H164–168 |
| Tydzień wygasania FW20 / dzień wygasania / tydzień po | brak różnicy w średnim zwrocie; **ale zmienność w dniu wygasania ~30% niższa** | H189–191 |
| Szoki EUR/PLN (±2σ) → WIG20 w kolejnych 5 dniach | zero (N=86–114) | H192–193 |
| Wybory (spółki SP vs prywatne) | brak systematycznej reakcji (N=9) | H180–181 |
| Crack spread → Orlen (20 dni) | IC 0.07, nieistotne | H185 |
| Run-up przed dywidendą, odbicie po | brak | H171–172 |
| Kalendarz (koniec miesiąca, przed świętami), trend, mean-reversion FW20, sesja USA → FW20 | brak (faza 1) | H012–H071 |

## Zasady ogólne z całego projektu
1. **Kierunku FW20 nie da się przewidzieć z danych dziennych** – informacja z USA/DAX jest w cenie otwarcia.
2. **Relatywne ruchy spółek wracają do średniej** (pary bankowe, ruch spółki vs indeks) – ale w ciągu dni,
   głównie w mniej płynnych nazwach, i słabiej od 2018 r. Dla tradera ręcznego: *po gwałtownym, niewyjaśnionym
   newsami odjeździe spółki od sektora częściej opłaca się czekać na powrót niż gonić ruch* – ale koszt wejścia
   i wyjścia (~0.8%) zjada większość przewagi.
3. Zanim zagrasz „event”, sprawdź N i przedział ufności – większość popularnych opowieści rynkowych
   (RPP, wygasanie, wybory) nie zostawia śladu w cenach.
