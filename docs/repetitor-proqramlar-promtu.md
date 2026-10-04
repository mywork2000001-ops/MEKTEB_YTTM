# Perspektiv plan proqramları – sinif/qrup üçün seçimin genişləndirilməsi (04.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən. Mövcud proqramlar kitabxanası
(docs/perspektiv-proqramlar-promtu.md) məktəb ilinin quruluşuna bağlıdır. Məqsəd: həm məktəb, həm fərdi (repetitor) qrupları üçün
proqram seçimini peşəkar səviyyəyə çatdırmaq – qrupun öz kurs müddəti, repetitor formatlı proqramlar, proqramın bir hissəsinin
seçilməsi, Word planının birbaşa kitabxanaya yüklənməsi, sinif rəqəminin aydın təyini, mənbə məkanın göstərilməsi.

## 0. Sabit qaydalar (pozulmur)
- **Proqramlar qarışdırılmır**: heç bir dərs, mövzu, standart və ya resurs bir proqramdan digərinə köçmür. Bölmə seçimi – eyni
  proqramın daxilində süzgəcdir; daxili hazırlıq proqramı mənbə kitabın strukturundan ayrıca proqram kimi qurulur.
- Rəsmi plan formatı, `working_plan`, «Mövzunu saxla», jurnalda yazılmış mövzuların dondurulması – dəyişmir.
- Fərdi məkan qaydası: müəllimin dərs sorğularında `ws_cond(user)`; proqramlar müəllimə məxsusdur (məkanlar arasında görünür –
  məktəb planını repetitorluqda istifadə etmək olur), amma mənbə məkan göstərilir.
- Kurs müddəti verilməyibsə hər şey əvvəlki kimidir (geriyə uyğunluq): tədris ilinin əvvəli – sonu.
- Hər mərhələ: miqrasiya (lazımsa) → backend → testlər → frontend → `tsc` → ayrıca commit.

## Mərhələ 1 – Kiçik düzəlişlər
1. **Səssiz imtina.** `POST /api/classes/{id}/join` – `program_id` verilib, cədvəl boşdursa: 400 «Proqramı tətbiq etmək üçün dərs
   saatlarını işarələyin». Proqram tapılmırsa – 404 (indi də var).
2. **Sinif rəqəmi qoşulma formasında.** Sinfin/qrupun rəqəmi müəyyən deyilsə (`class_grade` → None: «Həftəsonu qrupu», qarışıq
   qrup) qoşulma formasında xəbərdarlıq və «Sinif rəqəmi» seçimi; `JoinIn.grade` – sinfin rəqəmi əl ilə yazılmayıbsa yazılır.
   Seçim dəyişəndə proqram siyahısı yenidən sıralanır (`/api/programs?grade_hint=`).
3. **Mənbə məkan.** `_out` → `workspace: 'school' | 'private' | null` (ümumi kitab proqramı). Siyahıda «fərdi məkan» / «məktəb»
   nişanı – yalnız müəllimin öz proqramlarında, aktiv məkandan fərqlidirsə vurğulu.

## Mərhələ 2 – Qrupun kurs müddəti
- `teaching_assignments.starts_on`, `ends_on` (Date, null) – miqrasiya.
- `JoinIn.starts_on / ends_on`: tədris ilinin daxilində, `starts_on ≤ ends_on`; yalnız biri də verilə bilər.
- Dərs yuvaları aralığı = `[max(il.start, starts_on), min(il.end, ends_on)]`: `plan_ctx` (jurnal, mövzu icrası, portal, analitika)
  və `programs.capacity` (önbaxış, tətbiq, əlavə proqram tarixləri) eyni köməkçidən (`ta_range`) istifadə edir.
- `class_out.mine` → `starts_on`, `ends_on`. Qoşulma formasında «Kurs müddəti» (fərdi məkanda açıq, məktəbdə «Ətraflı» altında).
- Sınaq: 01.11–31.01 kursu → yuvalar yalnız bu aralıqda; aralıqdan kənar gündə jurnal günündə dərs yoxdur.

## Mərhələ 3 – Repetitor (kurs) formatlı proqramlar
Yeni şablon formatı `template.format = 'course'` (köhnə şablonlar – `'school'`, defolt):
```
{"format": "course", "sections": [{"section": "Həndəsə", "topics": ["Üçbucaqlar", ...]}],
 "mock_after_section": true, "final_mock": true}
```
**Açılma (`expand_course`)**: diaqnostik/KSQ/BSQ/yarımil təkrarı YOXDUR. Kursun bütün yuvaları (I+II yarımil birlikdə):
mövzular → (istəyə görə) hər bölmədən sonra «Sınaq: bölmə» → (istəyə görə) sonda «Yekun sınaq». Yuva azdırsa əvvəl bölmə
sınaqları, sonra yekun sınaq çıxır, sonra mövzular 1 dərsə enir, yenə sığmırsa – xəbərdarlıq. Mövzu dərsləri: yeni material →
məsələ həlli → … → son dərs «Test». `semester` – dərsin düşdüyü tarixə görə (I yarımil sonuna qədər – 1). `assessment_type` –
həmişə `formativ` (repetitor qrupunda summativ yoxdur); sınaq dərsləri `assessment` = «Sınaq imtahanı».

**Daxili proqramlar** (ümumi, `ensure_builtin`, DİM «Sinif testləri» strukturundan, cavabsız):
- «Buraxılış hazırlığı – IX sinif (V–IX mövzuları)»: V–IX siniflərin bölmələri sinif üzrə ardıcıl («V sinif: Natural ədədlər» …).
- «Buraxılış və qəbul (blok) hazırlığı – XI sinif (V–XI mövzuları)»: V–XI.
Hər ikisi ayrıca proqramdır (heç bir sinfin planından köçürmə deyil). Olimpiada / başqa fənn – mənbə material olmadan uydurulmur:
müəllim özü «Kurs proqramı» yaradır (aşağıda); mənbə gələndə ayrıca JSON şablon əlavə olunur.

**Müəllimin kurs proqramı**: `POST /api/programs/course` {title, subject, grade?, level?, description?, outline (mətn),
mock_after_section, final_mock}. Mətn formatı: `# Bölmə` sətri bölmə başlığı, digər boş olmayan sətirlər – mövzu
(«- », «1.» kimi nömrələr atılır). Bölməsiz mövzular «Ümumi» bölməsinə düşür. Redaktə – eyni mətnlə `PUT /api/programs/{id}/course`
(yalnız sahibi). UI: Proqramlar → «+ Kurs proqramı».

## Mərhələ 4 – Proqramın bir hissəsinin seçilməsi
- `teaching_assignments.program_sections`, `assignment_programs.sections` (JSON, null = hamısı) – miqrasiya.
- `program_detail` → `sections: [{name, part, topics|lessons}]` (adaptive: şablondan; fixed: dərslərin `section` sahəsindən, ardıcıl unikal).
- `lessons_for(program, ta, sections)`: adaptive – şablonda yalnız seçilmiş bölmələr (məktəb formatında KSQ yalnız qalan bölmələrə;
  yarımildə bölmə qalmayıbsa həmin yarımilin yuvaları digər yarımilə verilir, xəbərdarlıq); fixed – yalnız seçilmiş bölmələrin dərsləri.
  Seçim boşdursa – 400 «Ən azı bir bölmə seçin».
- `preview?sections=`, `apply` body `{sections}`, `attach` body `{sections}`; tətbiqdə `ta.program_sections` saxlanılır.
- UI: önbaxış və əlavə proqram pəncərəsində bölmələrin çek-siyahısı («Hamısı» / «Heç biri»), «Cəbr / Həndəsə» hissə düymələri
  (şablonda `part` varsa). Seçim dəyişəndə önbaxış yenilənir. Proqram sətrində «3/12 bölmə» nişanı.

## Mərhələ 5 – Word planı birbaşa kitabxanaya
- `POST /api/programs/import` (multipart: file .docx, title?, grade?) → `parse_plan` → `fixed` proqram
  (`school_id` = aktiv məkan, `owner_id` = müəllim, `source` = «Word: fayl adı»); sinfə tətbiq olunmur.
- Xəta/xəbərdarlıqlar cavabda; UI: Proqramlar → «Word planını kitabxanaya yüklə».

## Mərhələ 6 – Fərdi hazırlıqda dərs vaxtı (məktəb zəngi yox, real saat)
Fərdi hazırlıq məktəb deyil: «1-ci saat, 2-ci saat» və məktəbin zəng cədvəli mənasızdır. Repetitor dərsi – **həftə günü + başlama –
bitmə saatı** (məs. Ç.a. 17:00–18:30, Ş. 10:00–11:30); günlərə görə vaxt fərqli ola bilər, dərsin müddəti də (45, 60, 90 dəq.).
- `teaching_assignments.times` (JSON, null): `{"<həftə günü>:<sıra>": "HH:MM–HH:MM"}`. Daxili model dəyişmir: hər gün üçün dərslər
  başlama saatına görə sıralanır və `slots`-da sıra nömrəsi (0, 1, …) kimi saxlanılır – `working_plan`, jurnal, «Mövzunu saxla»,
  proqramın açılması olduğu kimi işləyir.
- `bell(db, cls, period, ta=None, date=None)`: `ta.times`-da `"{date.weekday()}:{period}"` varsa – həmin vaxt; yoxdursa məktəb
  qaydası (sinfin/məktəbin zəngi). Bütün çağırışlar (jurnal günü, plan, həftəlik cədvəl, portal, gündəlik plan, mövzu testi,
  əlavə məşğələ toqquşması) `ta` və tarixi ötürür.
- `JoinIn.times`: `[{weekday 0–6, start "HH:MM", end "HH:MM"}]` (yalnız fərdi məkanda; məktəbdə 400). Yoxlama: başlama < bitmə,
  müddət 20 dəq. – 4 saat, eyni gündə üst-üstə düşmə yoxdur; müəllimin fərdi məkandakı **başqa qrupu ilə** vaxt toqquşması – 409
  («Ç.a. 17:00–18:30 – «IX hazırlıq» qrupu ilə üst-üstə düşür»). `slots` və `weekly_hours` vaxtlardan hesablanır.
- `class_out.mine.times` – `[{weekday, start, end}]`.
- UI (fərdi məkanda qoşulma forması): saat şəbəkəsi əvəzinə «Dərs vaxtları» siyahısı: gün (B.e.–B.) + başlama + bitmə, «+ Dərs
  əlavə et», sil; altda «Həftədə N dərs · M saat». Məktəb məkanında köhnə şəbəkə qalır.
- Həftəlik cədvəldə fərdi dərslər öz real vaxtları ilə; «Nahar fasiləsi» sətri yalnız məktəb zəngi olan cədvəldə.

## Mərhələ 7 – Fərdi hazırlıqda qrupun sinfi və proqram təyinatı
Fərdi qrup yaradılanda müəllim **qrupun sinfini** (V–XI, «qarışıq» da ola bilər) və **hazırlıq məqsədini** təyin edir; proqram
təklifi buna görə qurulur.
- `classes.purpose` (String, null): `sinif` (cari sinif dərsinə dəstək), `buraxilis9` (IX buraxılış), `buraxilis11` (XI buraxılış),
  `qebul` (qəbul / blok imtahanı), `olimpiada`, `diger`. Məktəb siniflərində – null.
- `PlanProgram.data.purpose` – proqramın təyinatı (daxili hazırlıq proqramları: `buraxilis9`, `buraxilis11`/`qebul`; müəllimin kurs
  proqramında seçilir). DİM «Sinif testləri» proqramları – `sinif`.
- Kitabxana sıralaması (`ta_id`/`class_id` verilibsə): əvvəl məqsədi və sinfi uyğun olanlar, sonra yalnız sinfi uyğun, sonra qalanlar;
  `_out.purpose_fits`. Qoşulma formasında uyğun proqram əvvəlcədən seçilir (məs. IX + buraxılış → «Buraxılış hazırlığı – IX»).
- UI: fərdi məkanda «Yeni qrup» formasında «Sinif» və «Hazırlıq məqsədi»; qrup kartında məqsəd nişanı; sinif formasında redaktə.
  Proqram sətrində «məqsəd: IX buraxılış» nişanı.

## Qəbul meyarları
- Bütün mövcud testlər keçir; hər mərhələyə yeni testlər (`tests/test_api_programs_course.py`).
- Kurs müddəti verilməyən sinif/qrupda heç bir nəticə dəyişmir.
- Proqramlar qarışmır: bölmə seçimi yalnız bir proqramın daxilində; tətbiqdə əvvəlki plan kitabxanada qalır.
- Frontend `tsc` təmiz; telefon görünüşündə formalar sıxılmır.
- Məktəb məkanında dərs saatı/zəng qaydası dəyişmir; fərdi qrupun real vaxtları jurnal, portal və cədvəldə eyni görünür.

**İcra ardıcıllığı:** 1 → 2 → 3 → 6 → 7 → 4 → 5 (məqsəd kurs proqramlarına, vaxtlar qoşulma formasına bağlıdır).
