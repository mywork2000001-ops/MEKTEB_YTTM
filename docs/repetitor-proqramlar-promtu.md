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

## Qəbul meyarları
- Bütün mövcud testlər keçir; hər mərhələyə yeni testlər (`tests/test_api_programs_course.py`).
- Kurs müddəti verilməyən sinif/qrupda heç bir nəticə dəyişmir.
- Proqramlar qarışmır: bölmə seçimi yalnız bir proqramın daxilində; tətbiqdə əvvəlki plan kitabxanada qalır.
- Frontend `tsc` təmiz; telefon görünüşündə formalar sıxılmır.
