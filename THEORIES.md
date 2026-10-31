# THEORIES – czego nie dało się w pełni zweryfikować automatycznie

Posortowane od najbardziej obiecujących. Dla każdej teorii: teza, mechanizm, co już sprawdziłem (z ID w
`hypotheses_log.csv`), jakie dane i jakie kroki ręczne, co potwierdzi / obali.
**Ważne:** każda z tych teorii, jeśli ma trafić do holdoutu (2022-07 →), musi najpierw przejść pełną bramkę
na danych treningowych z modelem kosztów ustalonym *przed* obejrzeniem wyników. Holdout jest jednorazowy.

---

## 1. Relatywna mean-reversion przy kosztach „bez prowizji” (pary bankowe / spółka vs FW20)
* **Teza:** pary bankowe (PKO-PEO, PEO-MBK…) i odwrócenie rezydualnego ruchu spółki vs FW20 dają OOS Sharpe
  ~1.0 przy koszcie all-in ~0.10–0.15% na stronę na nogę (dziś osiągalne: broker z zerową prowizją do limitu
  obrotu + poślizg ~0.1%).
* **Mechanizm:** premia za dostarczanie płynności – inwestorzy, którzy muszą szybko sprzedać/kupić jedną spółkę,
  przesuwają ją od sektora; arbitrażysta, który przejmuje ryzyko, dostaje zapłatę, gdy cena wraca.
* **Sprawdzone:** brutto SR 1.3–2.0 (pary) i 0.7–1.0 (spółka vs FW20), permutacje p=0.003 (H006, H115, H120,
  H128); próg kosztów: SR=1.0 przy ~0.12%/stronę (P1) i ~0.17% (E1) – `reports/figures/cost_threshold.png`.
  **Przeciw:** przewaga brutto spada od 2018 r. (P1 brutto 1.98 → 0.99, R2 1.47 → 0.27); dźwignie kosztowe
  (rebalancing tygodniowy, tylko płynne spółki, kontrakty na akcje) niszczą sygnał (H129–H163); DSR wymaga SR ~1.7.
* **Dane / kroki ręczne:**
  1. Zmierzyć *realne* spready w godzinach 9:30–16:30 dla PKO, PEO, MBK, PZU, MIL, BHW, ING, PGE, TPE, ENA
     (np. 2 tyg. zrzutów arkusza zleceń z platformy brokera, co 15 min) → koszt połowy spreadu.
  2. Spisać koszty brokera z zerową prowizją: limit obrotu, prowizja powyżej limitu, koszt krótkiej sprzedaży
     / CFD (finansowanie, opłata za pożyczkę), dostępność shortów na tych spółkach.
  3. Zamrozić model kosztów (z punktów 1–2) i reguły P1/E1 **przed** ponownym uruchomieniem; potraktować to jako
     nową hipotezę w rejestrze (N rośnie).
  4. Jeśli przejdzie bramkę na 2005–2022 – jedyny legalny dalszy krok to jednorazowy holdout lub paper
     trading od dziś (forward test 6–12 mies.).
* **Potwierdzi:** OOS SR ≥ 1 przy zamrożonych realnych kosztach + dodatni Sharpe w 2018–2022 + holdout ≥ 50%.
  **Obali:** realne spready > 0.1% dla połowy nazw albo koszt shortu > 5% p.a.; dalsze wygasanie w 2022+.

## 2. Zmiany składu indeksów (WIG20 / mWIG40 / sWIG80): run-up przed rewizją, oddanie po
* **Teza:** spółki dodawane do indeksów rosną przed dniem rewizji (front-running funduszy indeksowych i OFE/PPK)
  i oddają po; usuwane – odwrotnie.
* **Mechanizm:** popyt funduszy pasywnych w dniu rewizji jest przewidywalny → arbitrażyści kupują wcześniej i
  sprzedają funduszom na zamknięciu rewizji; po rewizji presja znika.
* **Sprawdzone:** WIG20, N=27 dodań: +2.1% w [−10,−1] (p=0.07), −2.5% w [+1,+10] (p=0.04) (H174, H176);
  usunięcia – brak efektu; nie przeżywa korekty BH.
* **Dane / kroki:** (1) gpwbenchmark.pl → „Historyczne portfele indeksów” zawiera też **mWIG40 i sWIG80**
  (PDF co kwartał od 2009) – N wzrośnie kilkukrotnie, a efekt powinien być silniejszy w mniejszych spółkach;
  (2) **daty ogłoszenia** zmian: komunikaty GPW Benchmark („Komunikaty i uchwały”) – potrzebne, by oddzielić
  efekt ogłoszenia od efektu wejścia; (3) kursy z archiwum GPW (`scripts/fetch_events.py index_change_quotes`
  – rozszerzyć o mWIG40/sWIG80); (4) wykluczyć szybkie wejścia po IPO.
* **Potwierdzi:** AR [ogłoszenie, rewizja] > 0 i [+1,+10] < 0 przy N ≥ 100, po BH. **Obali:** efekt tylko
  w WIG20 i tylko przed 2015 (rynek nauczył się front-runningu).

## 3. Dryf po wynikach kwartalnych (PEAD) na prawdziwych datach publikacji
* **Teza:** po zaskoczeniu wynikami kurs dryfuje w tym samym kierunku przez 1–2 tygodnie.
* **Mechanizm:** niedoreakcja – inwestorzy powoli aktualizują oczekiwania; na GPW mało analityków na spółkę.
* **Sprawdzone:** proxy (pierwszy szok wolumenu w sezonie raportów): +0.79% w [+1,+10], N=324, p=0.06 (H169).
* **Dane / kroki:** (1) daty i godziny publikacji raportów okresowych z ESPI (raporty kwartalne / półroczne /
  roczne; godzina ważna – zwykle przed sesją lub po zamknięciu); (2) zaskoczenie: wynik vs konsensus (PAP
  Biznes / Parkiet publikują konsensusy dla dużych spółek) albo SUE z sezonowej zmiany EPS; (3) AR [+1,+10] i
  [+1,+40], kwintyle zaskoczenia.
* **Potwierdzi:** monotoniczny dryf w kwintylach zaskoczenia, po BH. **Obali:** dryf znika po kontroli momentum.

## 4. Krótkie pozycje netto (rejestr KNF)
* **Teza:** wzrost ujawnionych krótkich pozycji netto (≥ 0.5% kapitału) przewiduje słabsze stopy zwrotu
  w kolejnych tygodniach; zamykanie shortów – wzrosty.
* **Mechanizm:** shortujący to zwykle poinformowani gracze instytucjonalni; short na GPW jest drogi
  i ryzykowny, więc pozycja jest sygnałem przekonania (Boehmer, Jones, Zhang 2008; Jank & Smajlbegovic dla UE).
* **Sprawdzone:** strona KNF działa, ale nie znalazłem eksportu historii (dawne adresy rejestru nie istnieją).
* **Kroki:** (1) knf.gov.pl → Dla rynku → krótka sprzedaż → „pozycje krótkie netto” – pobrać listę
  publikacji (data, posiadacz, emitent, % kapitału); jeśli dostępne tylko bieżące – zbierać co tydzień albo
  wnioskować o archiwum (informacja publiczna); (2) zdarzenia: nowa pozycja / zwiększenie ≥ 0.1 pp /
  zamknięcie; (3) AR [+1,+20] vs WIG20.
* **Potwierdzi:** AR [+1,+20] < 0 po nowych/zwiększonych shortach, N ≥ 50, po BH. **Obali:** AR ≈ 0 lub efekt
  tylko poza WIG20.

## 5. Zakupy insiderów (art. 19 MAR, ESPI)
* **Teza:** zakupy członków zarządu/RN (szczególnie kilku osób w krótkim czasie) przewidują dodatnie AR w 1–3
  mies.; sprzedaże są mało informatywne.
* **Mechanizm:** asymetria informacji; zakup ma jeden motyw, sprzedaż wiele (płynność, podatki) – Lakonishok &
  Lee (2001).
* **Sprawdzone:** brak dostępu do ESPI (PAP zablokowany w środowisku).
* **Kroki:** komunikaty „transakcje osób pełniących obowiązki zarządcze” dla WIG20/mWIG40 → data PUBLIKACJI,
  osoba, K/S, wartość; AR [+1,+20], [+1,+60] osobno dla zakupów > 100 tys. PLN i klastrów.
* **Potwierdzi:** AR [+1,+60] > 0 dla zakupów, stabilne w podokresach. **Obali:** efekt znika po kontroli
  momentum/wielkości spółki.

## 6. KGHM – nocny ruch miedzi na danych intraday i kontrakcie FKGH
* **Teza:** otwarcie KGH niedoreaguje na nocny ruch miedzi, dociągając w pierwszych godzinach sesji.
* **Sprawdzone:** dziennie potwierdzone (H183, nachylenie 0.084, BH ✔), ale słabnie (2018–22 nieistotne);
  na dużych ruchach +0.34% (H194) < koszt round-trip akcji.
* **Kroki:** (1) dane minutowe KGH i FKGH (np. archiwum intraday brokera) + miedź LME/COMEX o 8:55; (2) zmierzyć
  dociąganie w pierwszych 30/60/120 min; (3) koszt FKGH (prowizja + spread w pierwszej godzinie).
* **Potwierdzi:** efekt w pierwszej godzinie > koszt FKGH, stabilny po 2018. **Obali:** dociąganie rozłożone
  na cały dzień lub zanikłe.

## 7. Przepływy do funduszy (IZFA), PPK, OFE
* **Teza:** miesięczne napływy do funduszy akcji polskich i wpłaty PPK tworzą presję popytową na WIG20 /
  mWIG40; odpływy (np. 2018, afera GetBack/Altus) – podażową.
* **Mechanizm:** price pressure (Coval & Stafford 2007) na płytkim rynku.
* **Sprawdzone:** izfia.pl przekierowuje na izfa.pl (domena niedostępna w środowisku).
* **Kroki:** izfa.pl → raporty miesięczne (saldo wpłat/umorzeń, kategoria „akcji polskich”) od 2005; regresja
  zwrotu WIG20/mWIG40 w miesiącu m+1 na saldo z m (z uwzględnieniem dnia publikacji – ~2 tyg. opóźnienia);
  PPK: statystyki PFR.
* **Potwierdzi:** istotny współczynnik *przewidujący*. **Obali:** zależność tylko równoczesna (fundusze gonią wyniki).

## 8. Kompresja zmienności w dzień wygasania FW20 / opcji (pinning)
* **Teza:** w dniu wygasania zmienność FW20 jest wyraźnie niższa (odch. std. 1.08% vs 1.54%, N=70 – opis,
  nie test), bo hedging opcji „przypina” indeks do popularnych strike'ów.
* **Kroki:** dane intraday WIG20 w ostatniej godzinie (rozliczenie = średnia z ostatniej godziny), otwarte
  pozycje na opcjach per strike (archiwum GPW, typ 66) → czy kurs rozliczenia zbliża się do strike'u z max OI.
* **Potwierdzi:** odległość rozliczenia od max-OI strike'u mniejsza niż losowa. Użycie: sprzedaż zmienności
  krótkoterminowej przed wygasaniem.

## 9. Dividend capture na rachunku bez podatku (IKE/IKZE)
* **Teza:** kurs spada średnio o ~79% dywidendy (efekt podatkowy) → inwestor zwolniony z podatku zarabia
  +0.77% na zdarzeniu (H170, BH ✔, stabilne).
* **Przeciw:** koszt round-trip ~0.78% zjada całość przy prowizji 0.29%; ryzyko rynkowe dnia 0.
* **Kroki:** sprawdzić prowizje na IKE (niektóre biura mają niższe), ograniczyć do dywidend > 5% i spółek
  o najwęższym spreadzie; zasymulować z realnym kosztem.
* **Potwierdzi:** średni zysk netto > 0 po realnym koszcie IKE w 2018–2022.

## 10. Premiery/zapowiedzi gier („sell the news”)
* **Teza:** spółki gamingowe (CD Projekt i szerzej: 11 bit, PlayWay, Ten Square Games) tracą po premierach
  dużych tytułów i na opóźnieniach.
* **Sprawdzone:** CDR – 5/5 premier z AR [0,+10] < 0 (mediana −2.4%), 3/3 opóźnienia ujemne (H187, H188); N za małe.
* **Kroki:** lista premier i opóźnień (strony spółek, komunikaty ESPI) dla 5–10 spółek gamingowych od 2015 →
  N ≈ 50–100; AR [−20,−1], [0,+10].

## 11. Sentyment – Google Trends, fora
* **Teza:** skok zainteresowania spółką poprzedza krótkoterminowy wzrost i późniejsze odwrócenie (attention-
  induced buying, Da, Engelberg, Gao 2011) – najsilniej w spółkach z dużym udziałem inwestorów indywidualnych.
* **Sprawdzone:** brak dostępu (trends.google.com, fora); ToS ogranicza automatyczne pobieranie.
* **Kroki:** ręcznie pobrać tygodniowe Google Trends (PL) dla nazw spółek WIG20 od 2010 (CSV z interfejsu);
  abnormal search volume = log SVI − mediana 8 tyg.; zwroty w tyg. +1 i +2..+5.
* **Potwierdzi:** dodatni zwrot w tyg. +1 i odwrócenie później. **Obali:** zależność tylko równoczesna.

## 12. Rekomendacje domów maklerskich
* **Teza:** podwyższenia/obniżenia rekomendacji wywołują reakcję i krótki dryf.
* **Problem:** klienci DM dostają rekomendację wcześniej niż rynek → reakcja przed publikacją publiczną.
* **Kroki:** archiwum rekomendacji z datą udostępnienia klientom *i* publicznie; AR [0,+1] i [+2,+20].

## 13. Typy komunikatów ESPI
* **Teza:** duże umowy (+), emisje akcji (−), zmiany zarządu w spółkach SP (−), skup akcji (+) mają
  systematyczne reakcje.
* **Kroki:** archiwum komunikatów z godziną publikacji → klasyfikacja tytułów słownikiem → event study
  (wiele kategorii = wiele testów, korekta BH obowiązkowa).

## 14. Makro: zaskoczenia CPI/PKB, oczekiwania stóp, rentowności obligacji
* **Teza:** *zaskoczenia* (nie same decyzje) przesuwają banki i WIG20; wzrost spreadu PL10Y–Bund sygnalizuje
  odpływ kapitału zagranicznego.
* **Sprawdzone:** decyzje RPP (tylko zmiany stóp – posiedzenia bez zmiany za ścianą anty-botową NBP): brak
  efektu (H164–H168); szoki EUR/PLN: brak efektu (H192–H193); stat.gov.pl niedostępny.
* **Kroki:** kalendarz GUS (godzina 10:00) + konsensus PAP; oczekiwania stóp z FRA/OIS (zaskoczenie RPP =
  decyzja − wycena FRA dzień wcześniej); rentowności z BondSpot/NBP.
* **Potwierdzi:** reakcja banków proporcjonalna do zaskoczenia (nie do decyzji).

## 15. Strategie intraday na FW20 (luka otwarcia, pierwsze minuty)
* **Teza:** luka otwarcia FW20 (wycena nocnej sesji USA) przereagowuje/niedoreagowuje w pierwszych minutach.
* **Problem:** reguła „wejście na następnym barze” przy danych dziennych uniemożliwiła test (sygnał z otwarcia
  realizowany dopiero na zamknięciu). Brutto dzienne lead-lag USA→FW20 było słabe (SR 0.2–0.35, H044–H067).
* **Kroki:** dane minutowe FW20 (np. archiwum brokera po zalogowaniu – poza zakresem tego projektu).
