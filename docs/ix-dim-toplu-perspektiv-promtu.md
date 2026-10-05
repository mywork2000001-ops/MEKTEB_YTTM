# IX sinif DİM – «Test toplusu 2025» əsasında perspektiv plan proqramı və P009 testləri ilə əlaqə (05.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən (IX sinif buraxılış imtahanı üzrə).
**Məqsəd.** DİM «Riyaziyyat. Test toplusu 2025» (IX sinif, 9 illik buraxılış) kitabından **ayrıca perspektiv plan proqramı**
qurmaq: hər dərsə toplunun konkret səhifələri və tapşırıq nömrələri (sinifdə / ev / müstəqil) yazılsın, hər fəslin sonunda
**P009 «Riyaziyyat 11 DİM» buraxılış-diaqnostikindən** həmin mövzuya uyğun sualla test, il ərzində sınaqlar və 2025-ci ilin real
imtahan tapşırıqları ilə yekun olsun. Proqram kitabxanada görünür, müəllim onu IX sinfinə (adətən **əlavə proqram** kimi, səviyyə
qrupu üçün) və ya fərdi hazırlıq qrupuna (**əsas proqram** kimi) qoşur.

Əlaqəli sənədlər (oxu, qaydalarını pozma): `perspektiv-proqramlar-promtu.md` (kitabxana, proqramlar qarışdırılmır),
`repetitor-proqramlar-promtu.md` (kurs formatı, məqsəd `buraxilis9`, bölmə seçimi), `plan-test-uygunlugu-promtu.md`
(mövzu testi A-bloku, sınaq C-bloku, səviyyə qrupları D-bloku), `gundelik-plan-promtu.md` (S/E/M aralıqları gündəlik plana düşür).

**Məlumat faylı (hazırdır):** `backend/app/program_data/dim_toplu_9_2025.json` – 22 fəsil (səhifələr, tapşırıq sayı, qapalı/açıq
sərhədi, P009 sual nömrələri), 2025 imtahan tapşırıqları, P009-un 25 sual yuvası (`ix` – IX proqramına düşürmü), göstərici bölgü.

---

## 0. Sabit qaydalar (pozulmur)
- **Proqramlar qarışdırılmır**: bu proqram yalnız öz JSON şablonundan açılır; IX sinfin rəsmi planından və «Sinif testləri»
  proqramından heç nə köçürülmür. Bölmə seçimi – yalnız bu proqramın daxilində süzgəc.
- **Cavab açarları repoya yazılmır**: JSON-da yalnız struktur (səhifə, say, sərhəd). PDF (`Dim 2025 Toplu 9-cu sinif.pdf`, 94 MB, skan)
  repoya getmir – `.gitignore`-da `*.pdf` var, `git add` edərkən yoxla.
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

| № | Fəsil | Hissə | Səh. | Tapş. | Qapalı | P009 sualı | Dərs (5/4/3 saat) |
|---|---|---|---|---|---|---|---|
| 1 | Natural ədədlər | Cəbr | 4–8 | 113 | 1–75 | 19 | 7 / 5 / 4 |
| 2 | Adi və onluq kəsrlər | Cəbr | 9–14 | 126 | 1–104 | 1 | 7 / 6 / 4 |
| 3 | Faiz. Nisbət. Tənasüb | Cəbr | 15–23 | 177 | 1–104 | 20, 21 | 9 / 7 / 5 |
| 4 | Həqiqi ədədlər | Cəbr | 24–27 | 87 | 1–80 | 1 | 5 / 5 / 4 |
| 5 | Tam cəbri ifadələr | Cəbr | 28–31 | 94 | 1–65 | – | 6 / 5 / 4 |
| 6 | Çoxhədlinin vuruqlara ayrılması | Cəbr | 32–37 | 112 | 1–92 | – | 7 / 5 / 4 |
| 7 | Rasional kəsrlər | Cəbr | 38–44 | 116 | 1–90 | 3, 14 | 7 / 5 / 4 |
| 8 | Kvadrat köklər. Həqiqi üstlü qüvvət | Cəbr | 45–52 | 176 | 1–145 | 4 | 9 / 7 / 5 |
| 9 | Birməchullu tənliklər və məsələlər | Cəbr | 53–60 | 190 | 1–130 | 6, 15, 16 | 10 / 8 / 5 |
| 10 | Tənliklər sistemi | Cəbr | 61–65 | 109 | 1–50 | 17 | 6 / 5 / 4 |
| 11 | Bərabərsizliklər və bərabərsizliklər sistemi | Cəbr | 66–73 | 177 | 1–140 | 7 | 9 / 7 / 5 |
| 12 | Funksiyalar və qrafiklər | Cəbr | 74–84 | 169 | 1–145 | 9 | 9 / 7 / 5 |
| 13 | Çoxluqlar | Cəbr | 85–88 | 81 | 1–60 | 5 | 5 / 4 / 3 |
| 14 | Ehtimal nəzəriyyəsi və statistika | Cəbr | 89–97 | 118 | 1–80 | 5, 22 | 7 / 6 / 4 |
| 15 | Həndəsənin əsas anlayışları | Həndəsə | 98–104 | 118 | 1–70 | – | 7 / 5 / 4 |
| 16 | Üçbucaqlar | Həndəsə | 105–110 | 112 | 1–72 | 12, 23 | 7 / 5 / 4 |
| 17 | Çoxbucaqlılar. Dördbucaqlılar | Həndəsə | 111–116 | 120 | 1–70 | 24 | 7 / 6 / 4 |
| 18 | Çevrə və dairə | Həndəsə | 117–124 | 121 | 1–52 | 13 | 7 / 6 / 4 |
| 19 | Fiqurların sahəsi | Həndəsə | 125–134 | 206 | 1–145 | 24 | 10 / 8 / 6 |
| 20 | Hərəkət. Oxşarlıq | Həndəsə | 135–141 | 98 | 1–50 | – | 6 / 5 / 4 |
| 21 | Koordinatlar metodu | Həndəsə | 142–150 | 150 | 1–120 | 13 | 8 / 6 / 5 |
| 22 | Çoxüzlülər, onların səthi və həcmi | Həndəsə | 151–153 | 66 | 1–47 | 25 | 5 / 4 / 3 |
| | **Cəmi** | | | **2836** | | | **160 / 127 / 94** + ehtiyat 10 / 9 / 8 |

Dərs sayı – göstəricidir (170 / 136 / 102 yuva: həftədə 5 / 4 / 3 saat × 34 həftə); tətbiqdə sinfin cədvəlindən hesablanır.

## 2. P009 ilə əlaqə – nə var və nəyi nəzərə almaq lazımdır
- P009 = «Riyaziyyat 11 DİM – Buraxılış-diaqnostiki»: **30 variant × 25 sual**, DİM buklet ardıcıllığı: 1–13 qapalı, 14–18 açıq,
  19–25 situasiya. Hər sual yuvası sabit mövzudur (JSON `p009.slots`). Ünvan: `…/P009_Riyaziyyat_11_DIM/test.html?variant=N`.
- Tətbiqin test bazasında P009 artıq var: `BankSource 'p009'`, `BankFile.lesson = 'test.html?variant=N'`, `kind = 'sinaq'`,
  `grades = [11]` (`bank/classify.py`). **Ancaq viktorina çıxarıcısı yalnız 1–13 qapalı sualları götürür** → bazada hər variantın
  `BankQuestion.n = 1..13` sualı = P009 yuvası 1..13 (sıra saxlanılır). 14–25 bazada yoxdur – yalnız link kimi verilir.
- **Səviyyə:** P009 XI sinif formatıdır. IX üçün yalnız `ix: true` yuvalar istifadə olunur (20 yuva; bazada – 9 qapalı: 1, 3, 4, 5, 6,
  7, 9, 12, 13). `ix: false` (2 kompleks, 8 ardıcıllıq – toplu-da fəsil yoxdur, 10 triqonometriya, 11 üstlü tənlik, 18 loqarifm) –
  bu proqramda göstərilmir. Bunu UI-də müəllimə açıq yaz: «P009 – XI sinif səviyyəsi; güclü qrup və qabaqlayıcı məşq üçün».
- 30 variantda eyni yuva = eyni tip, fərqli ədədlər → bir fəsil üçün **30 fərqli, eyni çətinlikli** sual (şagirdlərə fərdi variant).

## 3. Mərhələ 1 – Daxili proqram (backend)
1. `programs.py`: `ensure_builtin` `dim_toplu_9_2025.json`-dan **bir** ümumi proqram yaradır (idempotent, `key = 'dim-toplu-9-2025'`):
   `kind = 'adaptive'`, `grade = 9`, `subject = 'Riyaziyyat'`, `data = {'template': {...format: 'toplu'}, 'purposes': ['buraxilis9', 'sinif'],
   'source_short': 'TT 2025 (IX)'}`. Təsvir: «22 fəsil, 2836 tapşırıq; hər dərsə toplu səhifələri və S/E/M tapşırıqları; fəsil sonunda
   test (P009 uyğun sualları), sınaqlar, 2025 imtahan tapşırıqları ilə yekun».
2. Yeni şablon formatı `format: 'toplu'` (köhnə `school` / `course` toxunulmur). `tpl_sections` – fəsillər bölmə kimi
   (`section = '1. Natural ədədlər'`, `part = Cəbr|Həndəsə` → mövcud «Cəbr / Həndəsə» bölmə seçimi işləyir);
   `program_detail` bölmələrdə tapşırıq sayı və səhifələri göstərir.
3. `expand_toplu(tpl, dates, sem1_end, sections=None) -> (lessons, warnings)`:
   - **Ehtiyat dərslər** (yuvaya görə, əvvəl bunlar çıxır): ① ilk dərs – «Diaqnostik test» (2025 imtahan tapşırıqları yox! – P009
     IX-yuvalarından 1 variant); ② Cəbr bitəndə – «Sınaq: Cəbr» (P009 IX-yuvaları, növbəti variant); ③ Həndəsə bitəndə – «Sınaq: Həndəsə»;
     ④ sonda 2 dərs – «2025 buraxılış imtahanı tapşırıqları (səh. 154–155): icra» və «… təhlil»; ⑤ qalan ehtiyat – fəsillər arası
     «Ümumi təkrar». Yuva azdırsa: ⑤ → ② ③ → ① → ④-ün təhlil dərsi; sonra fəsillər minimuma enir (fəsil başına 1 dərs); yenə sığmırsa –
     xəbərdarlıq (mövcud mətn üslubunda).
   - **Fəsillərə bölgü:** hər fəslə ən azı 2 dərs, qalanı tapşırıq sayına mütənasib (ən böyük qalıq – mövcud `_share`).
   - **Fəsil daxilində:** 1..tasks tapşırıqları dərslərə ardıcıl, bərabər bölünür (qapalılar əvvəl, açıqlar sonra – çətinlik artır);
     hər dərsin hissəsi S : E : M ≈ 50 : 35 : 15 (yuvarlaqlaşdırma – S-ə; hissə boşdursa yazılmır). Aralıqlar fəsil üzrə **boşluqsuz və
     üst-üstə düşmədən** 1..tasks-ı əhatə edir.
   - Mövzu: `«Natural ədədlər (2/7): tapşırıqlar 17–33»`; son dərs – `«Natural ədədlər (7/7): fəsil testi»` (yenə öz aralığı ilə).
   - Sahələr: `section`, `tt_pages = 'TT 2025 (IX), s.4–8'`, `tasks = [{kind:'sinif',…},{kind:'ev',…},{kind:'mustaqil',…}]`,
     `resources = 'TT 2025 (IX), s.4–8; S 17–25; E 26–31; M 32–33'` (+ son dərsdə `; P009: sual № 19, variant 1–30`),
     `assessment = 'Formativ: şifahi sorğu, tapşırıq'` / son dərsdə `'Formativ: fəsil testi'`, `assessment_type = 'formativ'`,
     sınaq dərslərində `assessment = 'Sınaq imtahanı'`. `semester` – tarixə görə (mövcud qayda).
   - `sections` (bölmə seçimi) – yalnız seçilən fəsillər açılır; Cəbr/Həndəsə sınağı öz hissəsi seçilibsə qalır.
4. `lessons_for` / önbaxış / tətbiq / əlavə proqram – `format == 'toplu'` olduqda `expand_toplu` çağırılır; qalan axın dəyişmir.
5. Kitabxana sıralaması: IX sinif + məqsəd `buraxilis9` və ya `sinif` → «uyğun» (mövcud `purpose_fits`).

## 4. Mərhələ 2 – P009 testi plan mövzusuna (A-bloku üzərində)
1. `GET /api/programs/toplu/p009?lesson_id=` – plan dərsi bu proqramdandırsa, fəslin `p009` yuvalarını qaytarır:
   `[{n, type, topic, ix, in_bank: n <= 13, variants: [{variant, bank_question_id|null, url}]}]` (yalnız `ix: true`, yalnız aktiv
   `BankQuestion`; bazada olmayan 14–25 – yalnız `url`).
2. Mövzu testi formasında (mövcud: müəllim plan mövzusuna onlayn test təyin edir) yeni düymə **«P009-dan topla»**: yuva(lar) və variant
   sayı seçilir (defolt: fəslin bütün qapalı IX-yuvaları × 5 variant) → `OnlineTask` bazadakı suallardan (surət – mövcud qayda)
   yaradılır, ad: «P009 · Natural ədədlər (sual 19) · 5 variant». **Hər şagirdə fərqli variant** seçimi – `shuffle`/`student_ids`
   mövcud mexanizmlə; yoxdursa – sadə: suallar qarışdırılır, hamıya eyni dəst.
3. Açıq/situasiya yuvaları (14–25) bazada olmadığı üçün – test formasında «P009-da aç (variant N)» linki; plan dərsinin resursunda
   da link. (İstəyə görə ayrıca iş: `viktorina.html::extractP009` açıq sualları da `normalizeOpenQ` ilə çıxarsın – bu, **başqa repo**dur
   (`Documents/Claude/Projects`), öz sterojları ilə; burada edilmir.)
4. Sınaq dərsləri (Cəbr / Həndəsə / diaqnostik) üçün C-blokunda «IX-ə uyğun P009 sınağı»: bir variantın IX qapalı yuvaları
   (9 sual) → sınaq; nəticə «Sınaq jurnalı»na və reytinqə (mövcud axın). Növbəti sınaq – növbəti variant (təkrar olmasın).
5. Analitika: P009 əsaslı mövzu testi / sınaq nəticəsi **sual yuvası → fəsil** xəritəsi ilə fəsil üzrə faizə çevrilir
   («Natural ədədlər – 62 %»), zəif fəsillər Zəif qrupun əlavə proqramında bölmə seçimi kimi təklif olunur.

## 5. Mərhələ 3 – İnterfeys
- Proqramlar kitabxanası: kart «Riyaziyyat – IX sinif buraxılış hazırlığı (DİM Test toplusu 2025)», nişanlar «IX», «buraxılış»,
  «2836 tapşırıq»; «Bax» – fəsillər cədvəli (bu promtun §1 cədvəli kimi), P009 sütunu `ix`-ə görə.
- Önbaxış: dərs sayı, fəsillərə bölgü, ehtiyat dərslərdən hansılar düşdü, xəbərdarlıqlar; Cəbr/Həndəsə düymələri.
- Plan sətrində S/E/M aralıqları və səhifələr oxunaqlı (mövcud `tasks_text`); gündəlik plan (AI) bunları avtomatik görür
  («Test toplusu səhifələri», ev tapşırığı №) – əlavə iş yoxdur, yalnız yoxla.
- Telefonda cədvəl sıxılmır (mövcud responsiv qaydalar).

## 6. Testlər (`tests/test_api_programs_toplu.py`)
- JSON: 22 fəsil, tapşırıqların cəmi 2836, hər fəsildə `1 ≤ closed ≤ tasks`, səhifələr artan və kəsişmir, `p009` yuvaları 1..25,
  JSON-da cavab sahəsi yoxdur (`answers`, `key`-in dəyəri hərf siyahısı deyil).
- `ensure_builtin` iki dəfə çağırılır – bir proqram.
- `expand_toplu`: 170 / 136 / 102 / 40 / 15 yuva → dərs sayı = yuva sayı; hər fəsil üzrə S/E/M aralıqlarının birləşməsi = 1..tasks
  (boşluq və kəsişmə yoxdur); fəslin son dərsi «fəsil testi»; 15 yuvada xəbərdarlıq; ehtiyatların çıxma ardıcıllığı §3.3;
  `sections=['Həndəsə' hissəsi]` – yalnız 15–22 fəsillər + «Sınaq: Həndəsə».
- Tətbiq: resurs sətri `parse_resources`-dan keçəndə eyni `tt_pages`/`tasks` alınır (gediş-dönüş).
- P009: `in_bank` yalnız 1–13; `ix: false` yuvalar qaytarılmır; deaktiv `BankQuestion` qaytarılmır; başqa müəllimin dərsi – 403/404.
- Bütün köhnə testlər keçir.

## 7. Qəbul meyarları
Müəllim IX sinfinə (əlavə proqram, səviyyə qrupu ilə) və ya fərdi hazırlıq qrupuna (əsas proqram) bu proqramı önbaxışla qoşur;
hər dərsdə toplunun səhifəsi və S/E/M tapşırıq nömrələri var, gündəlik planda və ev tapşırığında görünür; fəsil sonunda bir kliklə
P009-dan həmin mövzunun sualları ilə onlayn test yaradılır; sınaqlar ardıcıl P009 variantları ilə; il 2025 imtahan tapşırıqları ilə
bitir; cavab açarı və PDF repoda yoxdur; `pytest` və `tsc` təmiz.

## 8. Götürülən qərarlar (dəyişmək olar)
- Fəsil ardıcıllığı – kitabdakı kimi (Cəbr 1–14, sonra Həndəsə 15–22). Alternativ (Cəbr/Həndəsə növbələşən) – müəllim bölmə seçimi
  ilə iki əlavə proqram (Cəbr və Həndəsə ayrıca) qoşa bilər.
- S:E:M = 50:35:15; minimum 2 dərs/fəsil; diaqnostika P009 ilə (2025 imtahan tapşırıqları yekun üçün saxlanılır).
- P009 IX üçün «qabaqlayıcı» səviyyədir – defolt olaraq Orta/Güclü qrupa təklif olunur; Zəif qrupa – yalnız müəllim seçərsə.
- Qapalı/açıq sərhədləri cavab cədvəlindən (səh. 156–165) oxunub; şübhə olarsa PDF-də yoxla (indeks = səhifə − 3).

**İcra ardıcıllığı:** Mərhələ 1 (+ testlər) → Mərhələ 3-ün kitabxana/önbaxış hissəsi → Mərhələ 2 → analitika (§4.5).
