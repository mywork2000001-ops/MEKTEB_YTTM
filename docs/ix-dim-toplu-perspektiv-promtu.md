# IX sinif DİM – «Test toplusu 2025» əsasında perspektiv plan proqramı və P007 testləri ilə əlaqə (06.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən (IX sinif buraxılış imtahanı üzrə).
**Məqsəd.** DİM «Riyaziyyat. Test toplusu 2025» (IX sinif, 9 illik buraxılış) kitabından **ayrıca perspektiv plan proqramı**
qurmaq: hər dərsə toplunun konkret səhifələri və tapşırıq nömrələri (sinifdə / ev / müstəqil) yazılsın; hər dərsin və hər fəslin
onlayn testi **P007 «9-cu sinif dim»** bankından – **eyni kitabın eyni nömrəli tapşırıqlarından** – qurulsun; il ərzində sınaqlar və
2025-ci ilin real imtahan tapşırıqları ilə yekun olsun. Proqram kitabxanada görünür, müəllim onu IX sinfinə (adətən **əlavə
proqram** kimi, səviyyə qrupu üçün) və ya fərdi hazırlıq qrupuna (**əsas proqram** kimi) qoşur.

Əlaqəli sənədlər (oxu, qaydalarını pozma): `perspektiv-proqramlar-promtu.md` (kitabxana, proqramlar qarışdırılmır),
`repetitor-proqramlar-promtu.md` (kurs formatı, məqsəd `buraxilis9`, bölmə seçimi), `plan-test-uygunlugu-promtu.md`
(mövzu testi A-bloku, sınaq C-bloku, səviyyə qrupları D-bloku), `gundelik-plan-promtu.md` (S/E/M aralıqları gündəlik plana düşür).

**Məlumat faylı (hazırdır):** `backend/app/program_data/dim_toplu_9_2025.json` – 22 fəsil (səhifələr, tapşırıq sayı, qapalı/açıq
sərhədi, P007 faylı və bazada olub-olmaması), 2025 imtahan tapşırıqları, göstərici bölgü. Cavab açarı yoxdur.

---

## 0. Sabit qaydalar (pozulmur)
- **Proqramlar qarışdırılmır**: bu proqram yalnız öz JSON şablonundan açılır; IX sinfin rəsmi planından və «Sinif testləri»
  proqramından heç nə köçürülmür. Bölmə seçimi – yalnız bu proqramın daxilində süzgəc.
- **Cavab açarları repoya yazılmır**: JSON-da yalnız struktur. Cavablar P007-dədir (test bazası viktorina-dan avtomatik gəlir).
  PDF (`Dim 2025 Toplu 9-cu sinif.pdf`, 94 MB, skan) repoya getmir – `.gitignore`-da `*.pdf` var, `git add` edərkən yoxla.
- Rəsmi plan formatı dəyişmir: Sıra № | Məzmun standartları | Mövzu | İnteqrasiya | Resurslar | Qiymətləndirmə | Saat | Tarix.
  Resurs sətri mövcud parserin başa düşdüyü formatdadır: `TT 2025 (IX), s.4–8; S 1–9; E 10–15; M 16–17`
  (`importers/plans.py::parse_resources` → `tt_pages` + `tasks[{kind: sinif|ev|mustaqil, start, end}]`).
- `working_plan`, «Mövzunu saxla», jurnalda yazılmış mövzunun dondurulması, kurs müddəti (`ta_range`), fərdi vaxtlar – dəyişmir.
- Summativ yoxdur: proqram kurs formatındadır (KSQ/BSQ yaratmır); məktəb sinfində rəsmi KSQ/BSQ əsas proqramda qalır.
- Hər mərhələ: (lazımsa miqrasiya) → backend → pytest → frontend → `tsc` → ayrıca commit (repo üslubunda, Azərbaycan dilində).

## 1. Mənbənin təhlili (kitabdan yoxlanılıb)
DİM «Test toplusu 2025», IX sinif: 22 fəsil, **2836 tapşırıq**; hər fəsildə əvvəl qapalı (A–E), sonra açıq tapşırıqlar;
səh. 154–155 – «2025-ci ildə buraxılış imtahanında (9 illik) istifadə olunmuş test tapşırıqları» (25: 15 qapalı + 10 açıq);
səh. 156–165 – cavablar. Fəsillərin daxilində yarımbaşlıq yoxdur – dərs bölgüsü **tapşırıq aralıqları** ilə aparılır.

| № | Fəsil | Hissə | Səh. | Tapş. | Qapalı | P007 faylı | Bazada | Dərs (5/4/3 saat) |
|---|---|---|---|---|---|---|---|---|
| 1 | Natural ədədlər | Cəbr | 4–8 | 113 | 1–75 | natural-numbers | ✓ | 7 / 5 / 4 |
| 2 | Adi və onluq kəsrlər | Cəbr | 9–14 | 126 | 1–104 | fractions-decimals | ✓ | 7 / 6 / 4 |
| 3 | Faiz. Nisbət. Tənasüb | Cəbr | 15–23 | 177 | 1–104 | percent-ratio-proportion | ✓ | 9 / 7 / 5 |
| 4 | Həqiqi ədədlər | Cəbr | 24–27 | 87 | 1–80 | real-numbers | ✓ | 5 / 5 / 4 |
| 5 | Tam cəbri ifadələr | Cəbr | 28–31 | 94 | 1–65 | algebraic-expressions | ✓ | 6 / 5 / 4 |
| 6 | Çoxhədlinin vuruqlara ayrılması | Cəbr | 32–37 | 112 | 1–92 | factoring-polynomials | ✓ | 7 / 5 / 4 |
| 7 | Rasional kəsrlər | Cəbr | 38–44 | 116 | 1–90 | rational-fractions | ✓ | 7 / 5 / 4 |
| 8 | Kvadrat köklər. Həqiqi üstlü qüvvət | Cəbr | 45–52 | 176 | 1–145 | square-roots-powers | ✓ | 9 / 7 / 5 |
| 9 | Birməchullu tənliklər və məsələlər | Cəbr | 53–60 | 190 | 1–130 | linear-equations | ✓ | 10 / 8 / 5 |
| 10 | Tənliklər sistemi | Cəbr | 61–65 | 109 | 1–50 | systems-equations | ✓ | 6 / 5 / 4 |
| 11 | Bərabərsizliklər və bərabərsizliklər sistemi | Cəbr | 66–73 | 177 | 1–140 | inequalities | ✓ | 9 / 7 / 5 |
| 12 | Funksiyalar və qrafiklər | Cəbr | 74–84 | 169 | 1–145 | functions-graphs | ✓ | 9 / 7 / 5 |
| 13 | Çoxluqlar | Cəbr | 85–88 | 81 | 1–60 | sets | ✓ | 5 / 4 / 3 |
| 14 | Ehtimal nəzəriyyəsi və statistika | Cəbr | 89–97 | 118 | 1–80 | probability-statistics | ✓ | 7 / 6 / 4 |
| 15 | Həndəsənin əsas anlayışları | Həndəsə | 98–104 | 118 | 1–70 | geometry-basics | ✓ | 7 / 5 / 4 |
| 16 | Üçbucaqlar | Həndəsə | 105–110 | 112 | 1–72 | triangles | ✓ | 7 / 5 / 4 |
| 17 | Çoxbucaqlılar. Dördbucaqlılar | Həndəsə | 111–116 | 120 | 1–70 | polygons-quadrilaterals | ✓ | 7 / 6 / 4 |
| 18 | Çevrə və dairə | Həndəsə | 117–124 | 121 | 1–52 | circle-disk | ✓ | 7 / 6 / 4 |
| 19 | Fiqurların sahəsi | Həndəsə | 125–134 | 206 | 1–145 | area-of-figures | ✓ | 10 / 8 / 6 |
| 20 | Hərəkət. Oxşarlıq | Həndəsə | 135–141 | 98 | 1–50 | motion-similarity | ✓ | 6 / 5 / 4 |
| 21 | Koordinatlar metodu | Həndəsə | 142–150 | 150 | 1–120 | coordinates | ✓ | 8 / 6 / 5 |
| 22 | Çoxüzlülər, onların səthi və həcmi | Həndəsə | 151–153 | 66 | 1–47 | polyhedra | ✓ | 5 / 4 / 3 |
| – | 2025 buraxılış tapşırıqları | – | 154–155 | 25 | 1–15 | exam-2025 | ✓ | ehtiyat |
| | **Cəmi** | | | **2836** | | | 22/22 | **160 / 127 / 94** + ehtiyat 10 / 9 / 8 |

Dərs sayı – göstəricidir (170 / 136 / 102 yuva: həftədə 5 / 4 / 3 saat × 34 həftə); tətbiqdə sinfin cədvəlindən hesablanır.

## 2. P007 ilə əlaqə – nə var və nəyi nəzərə almaq lazımdır
- P007 «9-cu sinif dim» = **bu kitabın rəqəmsal variantı**: 22 mövzu + `exam-2025`, AZ/RU/EN, izahlı həll. Fayl: `…/P007_9-cu_sinif_dim/9-cu sinif dim/<mövzu>/<mövzu>.html`.
- **Nömrələmə üst-üstə düşür:** P007 sualının `id`-si = toplu-dakı tapşırıq nömrəsi (hər fəsildə 1..tasks; hər fayldakı ən böyük id
  kitabın cavab cədvəlindəki say ilə yoxlanılıb – 113, 126, 177, …). Viktorina çıxarıcısı bunu `_qid` kimi ötürür →
  tətbiqdə `BankQuestion.qid` = tapşırıq nömrəsi. Deməli, **dərsin S/E/M aralığı üçün test birbaşa `qid` aralığı ilə seçilir**:
  şagird sinifdə 17–25-i həll edib, evdə 26–31-i – onlayn test məhz həmin tapşırıqlardır (və ya müəllimin seçdiyi hissəsi).
- Bazada: `BankSource 'p007'`, `BankFile.lesson = '<mövzu>/<mövzu>.html'`, `grades = [9]` (`bank/classify.py`). Həm qapalı, həm açıq
  suallar idxal olunur (açıq – `kind = 'open'`, `answer`).
- **Fəsil 17–18 və qid (həll olunub, 06.10.2026):** viktorina `539c74bc` – `extractP007BuiltData` (`polygons-quadrilaterals` 120,
  `circle-disk` 121 sual) və bütün P007 mövzularında `_qid` (əvvəl 9 mövzuda və triangles 21–112-də yox idi). Yoxlama: hər faylda
  `qid = 1..N`, N = kitabdakı tapşırıq sayı. Tətbiq: `bank/sync.py` qid dəyişəndə də sualı yeniləyir; köhnə sualların nömrəsi
  üçün **bir dəfə məcburi sinxronizasiya** (Tənzimləmələr → Admin → «Hamısını yenidən oxu», `POST /api/bank/sync?force=true`). UI-də
  «Bazada yoxdur – P007-də aç» linki yalnız faktiki baza boş olanda (endpoint `in_bank=false`) göstərilir.

## 3. Mərhələ 1 – Daxili proqram (backend)
1. `programs.py`: `ensure_builtin` `dim_toplu_9_2025.json`-dan **bir** ümumi proqram yaradır (idempotent, `key = 'dim-toplu-9-2025'`):
   `kind = 'adaptive'`, `grade = 9`, `subject = 'Riyaziyyat'`, `data = {'template': {...format: 'toplu'}, 'purposes': ['buraxilis9', 'sinif'],
   'source_short': 'TT 2025 (IX)'}`. Təsvir: «22 fəsil, 2836 tapşırıq; hər dərsə toplu səhifələri və S/E/M tapşırıqları, eyni
   tapşırıqlardan onlayn test (P007); fəsil testi, sınaqlar, 2025 imtahan tapşırıqları ilə yekun».
2. Yeni şablon formatı `format: 'toplu'` (köhnə `school` / `course` toxunulmur). `tpl_sections` – fəsillər bölmə kimi
   (`section = '1. Natural ədədlər'`, `part = Cəbr|Həndəsə` → mövcud «Cəbr / Həndəsə» bölmə seçimi işləyir);
   `program_detail` bölmələrdə tapşırıq sayı, səhifələr və P007 (bazada/yox) göstərir.
3. `expand_toplu(tpl, dates, sem1_end, sections=None) -> (lessons, warnings)`:
   - **Ehtiyat dərslər** (yuva azdırsa əvvəl bunlar çıxır): ① ilk dərs – «Diaqnostik test» (hər fəsildən 1 sual, P007);
     ② Cəbr bitəndə – «Sınaq: Cəbr» (fəsil 1–14-dən qarışıq, P007); ③ Həndəsə bitəndə – «Sınaq: Həndəsə» (15–22);
     ④ sonda 2 dərs – «2025 buraxılış imtahanı tapşırıqları (səh. 154–155): icra» (P007 `exam-2025`) və «… təhlil»;
     ⑤ qalan ehtiyat – fəsillər arası «Ümumi təkrar». Çıxma ardıcıllığı: ⑤ → ② ③ → ① → ④-ün təhlil dərsi; sonra fəsillər minimuma
     enir (fəsil başına 1 dərs); yenə sığmırsa – xəbərdarlıq (mövcud mətn üslubunda).
   - **Fəsillərə bölgü:** hər fəslə ən azı 2 dərs, qalanı tapşırıq sayına mütənasib (ən böyük qalıq – mövcud `_share`).
   - **Fəsil daxilində:** 1..tasks tapşırıqları dərslərə ardıcıl, bərabər bölünür (qapalılar əvvəl, açıqlar sonra – çətinlik artır);
     hər dərsin hissəsi S : E : M ≈ 50 : 35 : 15 (yuvarlaqlaşdırma – S-ə; hissə boşdursa yazılmır). Aralıqlar fəsil üzrə **boşluqsuz və
     üst-üstə düşmədən** 1..tasks-ı əhatə edir.
   - Mövzu: `«Natural ədədlər (2/7): tapşırıqlar 17–33»`; son dərs – `«Natural ədədlər (7/7): fəsil testi»` (yenə öz aralığı ilə).
   - Sahələr: `section`, `tt_pages = 'TT 2025 (IX), s.4–8'`, `tasks = [{kind:'sinif',…},{kind:'ev',…},{kind:'mustaqil',…}]`,
     `resources = 'TT 2025 (IX), s.4–8; S 17–25; E 26–31; M 32–33'` (+ `; P007: natural-numbers`),
     `assessment = 'Formativ: şifahi sorğu, tapşırıq'` / son dərsdə `'Formativ: fəsil testi'`, `assessment_type = 'formativ'`,
     sınaq dərslərində `assessment = 'Sınaq imtahanı'`. `semester` – tarixə görə (mövcud qayda).
   - `sections` (bölmə seçimi) – yalnız seçilən fəsillər açılır; Cəbr/Həndəsə sınağı öz hissəsi seçilibsə qalır.
4. `lessons_for` / önbaxış / tətbiq / əlavə proqram – `format == 'toplu'` olduqda `expand_toplu` çağırılır; qalan axın dəyişmir.
5. Kitabxana sıralaması: IX sinif + məqsəd `buraxilis9` və ya `sinif` → «uyğun» (mövcud `purpose_fits`).

## 4. Mərhələ 2 – P007 testi plan dərsinə (A-bloku üzərində)
1. `GET /api/programs/toplu/questions?lesson_id=&scope=lesson|ev|chapter` – plan dərsi bu proqramdandırsa, fəslin P007 faylındakı
   aktiv `BankQuestion`-ları qaytarır: `scope=lesson` – dərsin bütün S/E/M aralığı, `ev` – yalnız ev tapşırığı aralığı,
   `chapter` – bütün fəsil. `qid` rəqəm deyilsə və ya aralıqdan kənardırsa – götürülmür. Cavab: `{file, in_bank, questions:[{id, qid, kind}],
   missing: [aralıqda olub bazada olmayan nömrələr], url}`.
2. Mövzu testi formasında (mövcud: müəllim plan mövzusuna onlayn test təyin edir) yeni düymə **«Toplu tapşırıqlarından (P007)»**:
   seçim – «Dərsin tapşırıqları» / «Ev tapşırığı (onlayn yoxlama)» / «Fəsil testi: N təsadüfi sual» (defolt N = 15, qapalı:açıq ≈ 2:1);
   → `OnlineTask` bazadakı suallardan (surət – mövcud qayda), ad: «Natural ədədlər · tapşırıqlar 26–31 (ev)». Qarışdırma – mövcud.
3. Fayl faktiki bazada yoxdursa (`in_bank=false`) – düymə yerinə «P007-də aç» linki və izah.
4. Sınaq dərsləri: C-blokunda «Toplu sınağı» – ② Cəbr (fəsil 1–14, hər fəsildən 2 sual), ③ Həndəsə (15–22), ① diaqnostik (hər fəsildən 1),
   ④ `exam-2025` faylı olduğu kimi (25 sual – real imtahan forması). Nəticə «Sınaq jurnalı»na və reytinqə (mövcud axın).
   Eyni sinif üçün təkrar sınaqda əvvəl verilmiş suallar (qid) təkrarlanmır.
5. Analitika: P007 əsaslı testlərin nəticəsi **fəsil üzrə faizə** çevrilir («Natural ədədlər – 62 %»), zəif fəsillər Zəif qrupun
   əlavə proqramında bölmə seçimi kimi təklif olunur.

## 5. Mərhələ 3 – İnterfeys
- Proqramlar kitabxanası: kart «Riyaziyyat – IX sinif buraxılış hazırlığı (DİM Test toplusu 2025)», nişanlar «IX», «buraxılış»,
  «2836 tapşırıq», «P007 testləri»; «Bax» – fəsillər cədvəli (bu promtun §1 cədvəli kimi), «Bazada» sütunu.
- Önbaxış: dərs sayı, fəsillərə bölgü, ehtiyat dərslərdən hansılar düşdü, xəbərdarlıqlar; Cəbr/Həndəsə düymələri.
- Plan sətrində S/E/M aralıqları və səhifələr oxunaqlı (mövcud `tasks_text`); gündəlik plan (AI) bunları avtomatik görür
  («Test toplusu səhifələri», ev tapşırığı №) – əlavə iş yoxdur, yalnız yoxla. Plan sətrində «Onlayn test» ikonu (P007 bazadadırsa).
- Telefonda cədvəl sıxılmır (mövcud responsiv qaydalar).

## 6. Testlər (`tests/test_api_programs_toplu.py`)
- JSON: 22 fəsil, tapşırıqların cəmi 2836, hər fəsildə `1 ≤ closed ≤ tasks`, səhifələr artan və kəsişmir, hər fəsildə `p007.lesson`,
  cavab sahəsi yoxdur.
- `ensure_builtin` iki dəfə çağırılır – bir proqram.
- `expand_toplu`: 170 / 136 / 102 / 40 / 15 yuva → dərs sayı = yuva sayı; hər fəsil üzrə S/E/M aralıqlarının birləşməsi = 1..tasks
  (boşluq və kəsişmə yoxdur); fəslin son dərsi «fəsil testi»; 15 yuvada xəbərdarlıq; ehtiyatların çıxma ardıcıllığı §3.3;
  `sections` – yalnız Həndəsə hissəsi → yalnız 15–22 fəsillər + «Sınaq: Həndəsə».
- Tətbiq: resurs sətri `parse_resources`-dan keçəndə eyni `tt_pages`/`tasks` alınır (gediş-dönüş).
- Suallar: fixture-də P007 faylı (qid 1..30) → `scope=ev` yalnız E aralığı; deaktiv sual qaytarılmır; `qid` rəqəm olmayan – atılır;
  bazada olmayan fayl → `in_bank=false`, `url` var; başqa müəllimin dərsi – 403/404; sınaqda təkrar qid yoxdur.
- Bütün köhnə testlər keçir.

## 7. Qəbul meyarları
Müəllim IX sinfinə (əlavə proqram, səviyyə qrupu ilə) və ya fərdi hazırlıq qrupuna (əsas proqram) bu proqramı önbaxışla qoşur;
hər dərsdə toplunun səhifəsi və S/E/M tapşırıq nömrələri var, gündəlik planda və ev tapşırığında görünür; bir kliklə həmin
tapşırıqlardan (P007) onlayn test yaradılır; fəsil testi və sınaqlar P007 bankından; il 2025 imtahan tapşırıqları ilə bitir;
cavab açarı və PDF repoda yoxdur; `pytest` və `tsc` təmiz.

## 8. Götürülən qərarlar (dəyişmək olar)
- Fəsil ardıcıllığı – kitabdakı kimi (Cəbr 1–14, sonra Həndəsə 15–22). Alternativ (Cəbr/Həndəsə növbələşən) – müəllim bölmə seçimi
  ilə iki əlavə proqram (Cəbr və Həndəsə ayrıca) qoşa bilər.
- S:E:M = 50:35:15; minimum 2 dərs/fəsil; diaqnostika P007 ilə, 2025 imtahan tapşırıqları yekun üçün saxlanılır.
- Qapalı/açıq sərhədləri cavab cədvəlindən (səh. 156–165) oxunub; şübhə olarsa PDF-də yoxla (indeks = səhifə − 3).

**İcra ardıcıllığı:** Mərhələ 1 (+ testlər) → Mərhələ 3-ün kitabxana/önbaxış hissəsi → Mərhələ 2 → analitika (§4.5).
Paralel iş (viktorina, fəsil 17–18 + qid) – görülüb, bax §2.
