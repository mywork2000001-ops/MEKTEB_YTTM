# Onlayn test, sınaq imtahanı, səviyyə qrupları və əlavə məşğələ – audit və peşəkar promt

**Rol:** məktəb İKT mütəxəssisi + riyaziyyat metodisti + qiymətləndirmə üzrə mütəxəssis.
**Versiya:** 02.10.2026, v4 (müəllimin modeli + yoxlama düzəlişləri + səviyyə qrupları + əlavə məşğələ: əyani və onlayn). Baza commit: `70f7be1`.

## 0. Məqsəd – 5 blok
| Blok | Nə edir |
|---|---|
| **A. Mövzu testi** | Müəllim perspektiv planda mövzuya onlayn testi **özü** təyin edir; «Siniflər» filtrində eyni mövzulu digər siniflərini seçir; hər testin başlama/bitmə tarixi var |
| **B. Formativ jurnal** | Mövzu testinin nəticəsi həmin mövzunun dərsinə **bal (düz/cəmi) + qiymət** kimi düşür |
| **C. Sınaq imtahanları** | Planla əlaqəsiz, **ayrıca** seçilir; nəticə «Sınaq jurnalı»na, **sinif** və **ümumi** reytinqə düşür |
| **D. Səviyyə qrupları** | Sinif daxilində (və istəyə görə paralel siniflərdən) **Zəif / Orta / Güclü** qruplar; ilkin bölgü **buraxılış balı və reytinqə** görə avtomatik, sonra müəllim düzəldir |
| **E. Əlavə məşğələ** | **Əyani və onlayn** əlavə məşğələ kursu – gündəlik plandan ayrı **öz perspektiv planı** (tarix, saat, format, mövzu, material, test); **şagird və valideyn planı görür**; iştirak və nəticə **statistikası** izlənilir |

Avtomatik test seçimi / AI uyğunlaşdırma bu mərhələdə **yoxdur** – testi müəllim seçir.

---

## 1. Audit – mövcud vəziyyət

| Var | Çatışmır / problem |
|---|---|
| `OnlineTask` (bank / öz sualı, `opens_at`–`closes_at`, müddət, qarışdırma, `student_ids`) | Plan mövzusuna bağlı deyil; «mövzu testi» ilə «sınaq» fərqlənmir |
| `/copy` – surəti başqa sinfə | Bir neçə sinfə eyni anda göndərmək yoxdur; surətlər əlaqəsizdir → ümumi reytinq qurulmur |
| `/to-journal` → `Mark(kind='test', test_correct, test_total, grade)` | Əl ilə və **tarixə görə**; qayıb şagirdi ötürür (onlayn test üçün yanlışdır); müəllimin əl ilə yazdığı «test» qiymətini üstələyə bilər |
| Test bazası: mənbə → fayl → sual | Faylın fənni, sinfi, növü (mövzu/sınaq) yoxdur |
| `rules.rank()` – bərabər bal → eyni yer | Sınaq reytinqi yoxdur |
| `LevelOverride` (fənn üzrə əl ilə səviyyə) + analitikada avtomatik səviyyə: IX buraxılış balı (`score_math`) → nəticə reytinqi, həddlər 70/40 | Səviyyə yalnız **etiketdir**: qrup kimi istifadə olunmur (testi, dərsi «Zəif qrupa» göndərmək olmur); ilkin bölgü sınaq nəticəsini nəzərə almır; V–IX siniflərdə buraxılış balı yoxdur; bölgünün önizləməsi, kilidi, tarixçəsi yoxdur |
| Sərbəst tədris qrupu (paralel siniflərdən üzv) | Səviyyəyə görə avtomatik doldurulmur |
| Gündəlik plan (AI, ARTİ forması) – dərs cədvəlinə bağlı | **Əlavə məşğələ anlayışı yoxdur**: cədvəldən kənar əyani/onlayn məşğələnin planı, şagirdə görünməsi, davamiyyəti və effektinin ölçülməsi yoxdur |
| Sinfin səviyyəsi | `SchoolClass`-da sinif rəqəmi sahəsi yoxdur – yalnız addan («IX a», «11 p») |

---

## 2. Əvvəlki promtun yoxlanması – tapılan boşluqlar və mənim əlavələrim
| № | Boşluq (v2) | Düzəliş (v3) |
|---|---|---|
| 1 | «Eyni səviyyə» deyilir, amma sinif rəqəmi heç yerdə saxlanmır | `SchoolClass.grade` (int, NULL): addan/UTİS sinfindən doldurulur («IX a»→9, «11 p»→11), redaktə olunur; sərbəst qrupda – üzvlərin sinfindən (hamısı eynidirsə) və ya əl ilə |
| 2 | Admin/tədris hissəsinin bütün məktəbə sınaq təyini `own_assignment` ilə ziddiyyət təşkil edir | Ayrıca icazə: admin istənilən sinfə sınaq göndərir; nəticəni həmin sinfin fənn müəllimi də görür |
| 3 | Məktəbdən getmiş (passiv) və arxiv şagirdlər | Reytinqdən, səviyyə bölgüsündən, yeni tapşırıqdan çıxarılır; köhnə nəticəsi tarixçədə qalır |
| 4 | Bölünmə qrupu | «Eyni mövzu» filtrinə bölünmə və tədris qrupları da daxildir; «sinifdə yer» bölünmə qrupunda – **ana sinif** üzrə |
| 5 | Sınaqda açıq suallar | `check()` ilə avtomatik yoxlanır; müəllim sual üzrə düzəliş edə bilər → bal və reytinq yenidən hesablanır |
| 6 | Test başlayandan sonra redaktə | Kimsə başlayıbsa suallar dəyişmir (yalnız bitmə tarixini uzatmaq, ad, hədəf); batch-ı bütöv və ya bir sinif üzrə arxivləmək olur |
| 7 | Jurnala yazılandan sonra cəhd sıfırlanır / bitmə uzadılır | Yazılış idempotentdir: eyni `task_id`-li qiymətlər yenilənir, sıfırlanan cəhdin qiyməti silinir |
| 8 | Saat qurşağı | Default vaxtlar `Asia/Baku` ilə; sinfin öz zəngi (`bells`) nəzərə alınır |
| 9 | Bildiriş | Yeni test/məşğələ şagirdin «Bu gün» və «Tapşırıqlar» səhifəsində; PWA bildirişi (mövcud `sw.js`) – istəyə görə |
| 10 | Gələn il | Batch-ı (mövzu testi) gələn ilin eyni mövzusuna surətləmək |

**v4 auditi (əlavə məşğələ ilə birlikdə) – yeni tapıntılar**
| № | Boşluq | Düzəliş (v4) |
|---|---|---|
| 11 | Mövcud `Mark` cədvəlində bir dərsdə bir şagirdə yalnız **bir** «test» qiyməti ola bilər (unikal açar) | Mövzu testi dərsdə əl ilə yazılmış «test» qiymətini üstələmir; toqquşma hesabatda «əl ilə qiymət var» kimi göstərilir |
| 12 | Planın yenidən yüklənməsi sıra № üzrə yeniləyir, silinən mövzu `SET NULL` olur | Test mövzusuz qalırsa plan sətrində yox, «Tapşırıqlar»da «mövzu planda yoxdur» nişanı ilə görünür; jurnala yazılış dayanır, müəllim mövzunu yenidən seçir |
| 13 | Şagird müddət bitəndə təhvil verməyib | `expire_due` avtomatik təhvil verir → nəticə jurnala düşür (yazdığı qədər); heç cavab yoxdursa – 0 deyil, «yazmayıb» |
| 14 | Əlavə məşğələ testləri | `kind='extra'` – jurnala düşmür, məşğələ statistikası və səviyyə təkliflərinə gedir |
| 15 | Əlavə məşğələ müəllimin dərs yükü hesabatına düşmür | Kurs hesabatında keçirilən saatlar (tədris hissəsi üçün çap) |
| 16 | Əlavə məşğələnin effekti subyektiv qiymətləndirilir | Statistika: iştirakçı ↔ iştirak etməyən (eyni sinif, eyni testlər), kursdan əvvəl ↔ sonra |
| 17 | Valideyn məlumatlandırılmır | Portalda kurs planı və uşağın iştirakı; ardıcıl 2 buraxma – müəllimə risk nişanı |

---

## 3. Qaydalar (pozulmaz)
**Ümumi**
1. Rəsmi plan, bank və jurnal strukturu dəyişmir; yeni əlaqələr ayrıca sahə/cədvəllərdə. Plan yenidən yüklənəndə `plan_lesson_id` əlaqələri sıra № + mövzu mətni üzrə bərpa olunur.
2. Hər yaratma/redaktə/silmə/jurnala yazılış/səviyyə dəyişikliyi audit jurnalına düşür. Şagirdin şəxsi məlumatı xarici xidmətə getmir.
3. Passiv/arxiv şagird yeni tapşırığa, reytinqə, səviyyə bölgüsünə daxil edilmir.

**A–B. Mövzu testi və formativ jurnal**
4. «Eyni mövzu» filtri: yalnız müəllimin öz dərsləri, eyni fənn və `grade`; mövzu normallaşdırılmış mətnə görə tapılır, tapılmırsa əl ilə seçilir; hər sinfə öz `plan_lesson_id`-si.
5. Tarix: başlama < bitmə, müddət ≤ aralıq, bitmə keçmişdə ola bilməz. Default – həmin sinifdə mövzunun **işçi plan** üzrə dərsinin sonu → ertəsi gün 22:00; «hamısına eyni vaxt» seçimi.
6. Jurnala yazılış: test bağlananda (və ya «İndi yaz»); dərs = jurnalda bu mövzunun yazıldığı dərs, yoxdursa işçi plan dərsi; bölünmüş mövzu → **sonuncu** dərs; dərs hələ keçməyibsə – gözləyir; KSQ/BSQ dərsinə yazılmır.
7. Qiymət: `test_correct/test_total` → faiz → `summative_grade`; yazmayana qiymət **yazılmır**; dərsdə qayıb olmaq mane deyil; əl ilə yazılmış «test» qiyməti üstələnmir (hesabatda göstərilir).
8. Səviyyəyə görə variantlı mövzu testi (D bloku) jurnala eyni qayda ilə düşür; faiz öz variantının sual sayından hesablanır.

**C. Sınaq**
9. Sınaq formativ və KSQ/BSQ qiymətinə təsir etmir. Reytinqdə yalnız **birinci təhvil verilmiş cəhd**; sıfırlanmış cəhd «təkrar» nişanı ilə. Bərabər bal – eyni yer. Sınaq **variantsız** olur (hamıya eyni suallar) – reytinq müqayisəli olsun.
10. Məxfilik: müəllim/admin bütün reytinqi adlarla görür; şagird və valideyn yalnız öz yerini və ümumi statistikanı (orta, ən yüksək).

**D. Səviyyə qrupları**
11. Səviyyə **fənn üzrədir** (riyaziyyatda «Güclü», dildə «Orta» ola bilər) – mövcud `LevelOverride` cədvəli genişləndirilir, ayrıca jurnal/plan **yaranmır** (bölünmə qrupundan fərqli olaraq bu, sinif daxilində virtual qrupdur).
12. İlkin bölgü avtomatikdir, amma **önizləmə → təsdiq** ilə tətbiq olunur; müəllimin əl ilə qoyduğu (kilidli) səviyyəyə toxunulmur.
13. Sonrakı yenidən hesablamalar (hər sınaqdan/KSQ-dan sonra) **təklif** kimi göstərilir, avtomatik dəyişmir; histerezis: şagird yalnız hədddən ən azı 5 bal o tərəfə keçəndə köçürülmə təklif olunur.
14. Səviyyə etiketi şagird və valideyn portalında **göstərilmir** (stiqma). Şagird yalnız ona göndərilən tapşırığı/dərsi görür.

**E. Əlavə məşğələ (əyani və onlayn)**
15. Əlavə məşğələ **dərs cədvəlindən və gündəlik plandan ayrıdır**: rəsmi planın saatlarına girmir, işçi planı sürüşdürmür, mövzunu
    «keçildi» etmir, formativ/summativ jurnala qiymət yazmır. Öz **perspektiv planı** (məşğələ planı) var.
    İstisna: **«əvəzedici»** onlayn dərs (karantin, hava şəraiti – adi dərs distant keçirilir) – o zaman adi dərs kimi jurnala düşür.
16. Format: **əyani** (otaq), **onlayn** (keçid – yalnız `https://`), **qarışıq** (hər məşğələdə ayrıca seçilir). Onlayn keçid şagirdə
    başlamazdan 10 dəqiqə əvvəl aktiv olur; tətbiq video yazmır, yalnız müəllimin verdiyi yazı keçidini saxlayır (razılıq – məktəbin qaydası).
17. Məşğələ planı **şagirdə və valideynə görünür**: tarix, saat, format, otaq/keçid, mövzu, material, ev tapşırığı, öz iştirakı və test nəticəsi.
    Başqa şagirdin iştirakı/nəticəsi və səviyyə etiketi göstərilmir (§3.10, §3.14).
18. Statistika yalnız **keçirildi** kimi qeyd olunmuş məşğələlər üzrə hesablanır; ləğv/köçürülən məşğələ iştiraka mənfi təsir etmir.
19. Toqquşma: şagirdin və ya müəllimin həmin vaxtda məktəb cədvəlində dərsi, otağın başqa məşğələdə olması – xəbərdarlıq (qadağa deyil).
20. Tətil və bayram günlərinə (mövcud təqvim) məşğələ planlaşdırılmır.

---

## 4. Peşəkar promt (icraçı üçün)

> Sən FastAPI + SQLAlchemy + React (TS) tətbiqində işləyən baş proqramçısan. Mövcud kod üslubunu (Azərbaycan dilində şərhlər,
> `audit()`, `own_assignment`, `plan_ctx`, `taught_lesson`, `roster`, `_snapshot`, `finalize`, `rank`, `level`, `useLoad`, `Drawer`,
> `Pill`, `Seg`) saxla. Mövcud tapşırıqlar, səviyyələr və analitika əvvəlki kimi işləməyə davam etməlidir. Yuxarıdakı qaydalar (§3) pozulmazdır.
>
> **0. Model və miqrasiya (bir Alembic faylı, `upgrade → downgrade → upgrade` yoxlanır)**
> - `SchoolClass.grade` (int NULL) + addan/UTİS-dən doldurma (`domain/classes.grade_of()`), Siniflər redaktəsində sahə.
> - `TestBatch(id, kind 'movzu'|'sinaq', title, subject, grade, bank_file_ids JSON, scoring JSON, created_by, created_at, archived_at)`.
> - `OnlineTask` + `kind` ('movzu'|'sinaq'|NULL), `batch_id`, `plan_lesson_id` (SET NULL), `journal_auto` (default True), `journal_done_at`,
>   `variants` JSON NULL (`{"Zəif": [...], "Orta": [...], "Güclü": [...]}` – səviyyəyə görə sual dəstləri).
> - `Mark.task_id` (SET NULL).
> - `BankFile` + `subject`, `grades` JSON, `kind` ('movzu'|'sinaq'|'yekun'|'diaqnostik'), `meta_locked`; `bank/classify.py` (P001→5, P011→6,
>   P007→9, P009/P012→11, Sınaqlar – addan; «Sınaq/ÜSİ/MSİ/Variant/Yekun» → sinaq/yekun, «İlkin yoxlama» → diaqnostik), admin `PATCH /api/bank/files/{id}`.
> - `LevelOverride` + `source` ('auto'|'manual'), `locked` (bool), `score` (float), `components` JSON, `placed_at`; yeni `LevelHistory(assignment_id,
>   student_id, old, new, source, at, by)`.
> - `ExtraCourse`, `ExtraSession`, `ExtraAttendance` – E bloku (aşağıda).
>
> **A. Mövzu testi (perspektiv plan üzərindən)**
> 1. `GET /api/plan/{ta}/topics/{pl}/peers` – eyni fənn + `grade` üzrə müəllimin digər dərsləri (bölünmə/tədris qrupları daxil): `{ta_id, class_name,
>    plan_lesson|null, working_date, lesson_end, already_has_test}`; mövzu tapılmayan sinfə həmin sinfin plan siyahısı.
> 2. `POST /api/plan/{ta}/topics/{pl}/test` – `title, bank_ids, custom, variants?, duration_min, shuffle, show_answers, journal_auto,
>    targets: [{ta_id, plan_lesson_id, opens_at, closes_at, audience: all|levels[]|student_ids}]`. Bir `TestBatch(kind='movzu')` + hər sinfə
>    `OnlineTask`, bir tranzaksiyada (biri səhvdirsə heç biri yaranmır).
> 3. `GET /api/plan/{ta}` – hər dərsə `tests: [{task_id, state gözlənilir|açıqdır|bitib, opens_at, closes_at, submitted, total, avg_pct, journal}]`.
> 4. `Plan.tsx`: sətirdə «🧪 Test» + nişan («açıqdır 03.10 15:00–04.10 22:00 · 12/25», «bitib · 72 % · jurnala yazılıb»). Drawer:
>    Suallar (`BankPicker`, fənn+sinif filtri, yalnız `kind='movzu'`; «Öz sualım»; istəyə görə «Səviyyəyə görə variant» – 3 dəst),
>    Siniflər (işarələmə, №mövzu, işçi plan tarixi, başlama/bitmə, hədəf: bütün sinif / Zəif / Orta / Güclü / seçilmiş), müddət,
>    «Bağlananda formativ jurnala yaz», «Göndər».
> 5. `Tasks.tsx`: «Mövzu testi» nişanı, mövzu №, batch üzrə qruplaşdırma (siniflərin müqayisəsi: orta faiz, yazanlar).
>
> **B. Formativ jurnala yazılış**
> 1. `app/task_journal.py: write_topic_marks(db, task)` – §3.6–3.8; nəticə `{date, period, topic, copied, updated, removed, skipped[{ad, səbəb}]}`.
> 2. Mövcud `/to-journal` mövzu testi üçün bu funksiyanı çağırır. Planlaşdırıcı hər 15 dəq: bağlanmış, `journal_auto`, yazılmamış testlər →
>    `expire_due` → `write_topic_marks`. Cəhd sıfırlananda və bitmə uzadılanda yenidən işləyir.
>
> **C. Sınaq imtahanları**
> 1. Onlayn tapşırıqlar → «Sınaq imtahanları» tabı. Bankdan yalnız `sinaq/yekun` (sinfə uyğunlar yuxarıda); bütöv sınaq (orijinal sıra) və ya seçilmiş suallar.
> 2. Siniflər (müəllimin istənilən dərsləri; admin – istənilən sinif), hər birinə başlama/bitmə (default eyni), müddət (default 60 dəq / sınağın öz vaxtı).
> 3. `POST /api/exams-online` → `TestBatch(kind='sinaq')` + `OnlineTask(kind='sinaq')`; `scoring`: sual başına 1 bal (və ya faylın balı), «səhv cərimə»
>    (default söndürülü), 100 bal şkalası.
> 4. `GET /api/exams-online/{batch}` – Sınaq jurnalı: şagird, sinif, düz/səhv/boş, bal, faiz, sinifdə yer, ümumi yer; siniflərin orta balı və reytinqi;
>    sual üzrə həll faizi (ən çox səhv edilənlər); açıq suala müəllim düzəlişi.
> 5. `GET /api/exams-online/rating?subject=&grade=` – kumulyativ: orta faiz, iştirak sayı, dinamika (son − əvvəlki), sinifdə/ümumi yer, «ən çox irəliləyənlər».
> 6. Portal → Nəticələr → «Sınaqlar»: öz balı, yeri, orta/ən yüksək, dinamika qrafiki (§3.10). Çap: sınaq jurnalı, reytinq.
>
> **D. Səviyyə qrupları (Zəif / Orta / Güclü)**
> 1. `app/levels.py: compute(db, ta) -> [{student, components, score, proposed, current, locked, change}]`:
>    - komponentlər (0–100): **IX buraxılış balı** (`score_math`, X–XI üçün; fənnə uyğun bal – dil üçün `score_language`), **sınaq ortası** (C bloku,
>      ≥1 sınaq), **fənn reytinqi** (analitikadakı `rating`: formativ + KSQ/BSQ), **diaqnostik test** (bankda `kind='diaqnostik'`, V–IX üçün);
>    - çəkilər (dəyişdirilə bilər): ilin əvvəli – buraxılış 100 %; məlumat yığıldıqca – buraxılış 30 / sınaq 40 / reytinq 30; olmayan komponent çıxarılır,
>      çəkilər yenidən normallaşdırılır; məlumatı olmayan şagird – «təyin edilməyib»;
>    - bölgü: **sabit həddlər** 70/40 (mövcud `LEVEL_HIGH/LEVEL_MID`, default) və ya «bərabər bölgü (üçdəbir)», minimum qrup ölçüsü 3.
> 2. API: `GET /api/levels/{ta}/preview?mode=&weights=` (önizləmə), `POST /api/levels/{ta}/apply` (seçilən sətirlər; kilidlilər toxunulmur,
>    `LevelHistory`), `PUT /api/levels/{ta}/{student}` (əl ilə + kilid), `GET /api/levels/{ta}/suggestions` (§3.13 histerezis ilə köçürmə təklifləri).
> 3. `POST /api/levels/cross-class` – paralel siniflərdən (eyni fənn, `grade`) seçilmiş səviyyənin şagirdləri ilə **sərbəst tədris qrupu** yaradır
>    (mövcud qrup mexanizmi; məs. «IX – riyaziyyat, güclü qrup»), sonra müəllim ona əlavə məşğələ təyin edə bilər.
> 4. İstifadə: hədəf seçimi (A.4, C, E), səviyyəyə görə variantlı mövzu testi, gündəlik plan promtunda qrup tərkibi (artıq var), analitikada qrup üzrə orta göstəricilər.
> 5. İnterfeys: Jurnal → yeni «Səviyyə qrupları» tabı – üç sütun (Zəif / Orta / Güclü) kart şəklində, şagirdi sürüşdürüb köçürmək, 🔒 kilid,
>    «Avtomatik bölgü» → önizləmə cədvəli (komponentlər, bal, təklif, dəyişiklik) → «Tətbiq et», «Təkliflər (3)» nişanı, tarixçə, çap.
>
> **E. Əlavə məşğələ (əyani və onlayn) – öz perspektiv planı, şagird görünüşü, statistika**
> 1. Model: `ExtraCourse(id, owner_id, assignment_id NULL, title, subject, grade, format əyani|onlayn|qarışıq, audience JSON
>    {class_ids|levels|student_ids|group_id}, schedule JSON [{weekday, start, end, room?, link?}], starts_on, ends_on, goal, archived_at)`;
>    `ExtraSession(id, course_id, seq, date, start, end, format, room, link, topics JSON [{plan_lesson_id?, text}], goals, material_ids JSON,
>    homework, task_id NULL, status planned|held|cancelled|moved, moved_to NULL, recording_url, note)`;
>    `ExtraAttendance(session_id, student_id, status var|yox|üzrlü|gecikdi, joined_at NULL)`.
> 2. **Məşğələ planı (perspektiv):** kurs yaradılanda cədvəl + tarix aralığından məşğələ tarixləri avtomatik qurulur (tətillər çıxılır);
>    müəllim hər məşğələyə mövzu(lar) təyin edir – əsas perspektiv plandan (keçmiş mövzular da – təkrar üçün), bir neçə mövzu, və ya sərbəst mətn.
>    Toplu təyin: «№12–№20 mövzularını ardıcıl paylaşdır». Mövzu təklifləri: zəif qrupa – mövzu testi < 60 % / «təkrar» statuslu mövzular;
>    güclü qrupa – sınaqda ən çox səhv edilən mövzular, növbəti bölmə. Məşğələni köçürmək / ləğv etmək (səbəb), əlavə məşğələ qoşmaq.
>    Çap: məşğələ planı (№, tarix, saat, format, mövzu, material).
> 3. API: `GET/POST /api/extra`, `GET/PATCH/DELETE /api/extra/{id}`, `POST /api/extra/{id}/generate` (tarixləri qur), `PUT /api/extra/{id}/sessions/{sid}`,
>    `POST /api/extra/{id}/sessions/{sid}/held` (keçirildi + davamiyyət), `POST /api/extra/{id}/sessions/{sid}/test` (A blokunun test pəncərəsi ilə,
>    `kind='extra'`, jurnala yazılmır), `GET /api/extra/{id}/stats`.
> 4. **Şagird / valideyn portalı:** «Əlavə məşğələlər» – kursun planı (keçmiş və gələcək), növbəti məşğələ kartı «Bu gün»də (onlayn – «Qoşul»
>    10 dəq əvvəl aktiv, əyani – otaq), material, ev tapşırığı, öz iştirakı (5/7) və test nəticələri. `GET /api/portal/extra`, `POST /api/portal/extra/{sid}/join`.
> 5. **Statistika (müəllim):** hər məşğələ – iştirak (gələn/cəmi), test orta faizi; hər şagird – iştirak faizi, test ortası, **dinamika**
>    (məşğələ testləri + mövzu testləri + sınaq: kursdan əvvəl ↔ kursdan sonra); kurs üzrə – orta iştirak, plan icrası (keçirilən/planlaşdırılan),
>    **iştirakçılar ↔ iştirak etməyənlər** (eyni sinif, eyni mövzu testləri/sınaq üzrə orta fərq), səviyyə qrupları üzrə; risk: ardıcıl 2 buraxma.
>    Qrafiklər: iştirak zolaqları, nəticə dinamikası xətti. Çap: kurs hesabatı (tədris hissəsi üçün – keçirilən saatlar).
> 6. «Əvəzedici» onlayn dərs: adi dərsin yuvası seçilir → həmin dərsin jurnal yazısı yaradılır, mövzu icrası adi qayda ilə (§3.15).
> 7. İnterfeys: müəllim – yeni «Əlavə məşğələ» səhifəsi (kurslar → Plan | Davamiyyət | Statistika tabları), Ana səhifədə və Dərs cədvəlində
>    bugünkü məşğələlər; şagird – «Bu gün»də kart və ayrıca «Məşğələlər» səhifəsi; telefon eni (360 px) üçün kart görünüşü.
>
> **F. Testlər**
> `grade_of`; bank təsnifatı; peers (səviyyə, normallaşdırma, başqa müəllimin sinfi görünmür, qruplar); çox sinfə göndərmə (tranzaksiya, hər sinfə
> öz mövzu və tarix, hədəf səviyyə); tarix yoxlamaları; jurnala yazılış (mövzunun dərsi, sonuncu dərs, gələcək → gözləyir, yazmayan qiymətsiz,
> əl ilə qiymət qorunur, KSQ dərsi, idempotent, sıfırlama → silinmə, variant faizi); sınaq (formativə düşmür, bal, cərimə, birinci cəhd,
> bərabər bal, sinif/ümumi yer, kumulyativ, açıq sual düzəlişi, admin icazəsi); səviyyə (komponentlər, çəkilərin normallaşdırılması, həddlər/üçdəbir,
> kilid, histerezis, passiv şagird, tarixçə, cross-class qrup); əlavə məşğələ (tarixlərin qurulması, tətillər, jurnala düşmür, əvəzedici → düşür, keçid https, hədəf,
> şagird yalnız öz kursunu və iştirakını görür, statistika yalnız keçirilənlər üzrə, iştirakçı ↔ iştirak etməyən, toqquşma); məxfilik (şagird səviyyəsini və başqasının reytinqini görmür); icazələr (başqa müəllim → 404).

---

## 5. İcra ardıcıllığı
| № | İş | Harada | Yoxlama |
|---|---|---|---|
| 1 | Miqrasiya: `grade`, `TestBatch`, `OnlineTask`/`Mark`/`BankFile`/`LevelOverride` sahələri, `LevelHistory`, `Extra*` | `models.py`, `migrations/` | `alembic` |
| 2 | `grade_of`, bank təsnifatı, admin redaktəsi | `domain/classes.py`, `bank/classify.py`, `api/bank.py` | test |
| 3 | Mövzu testi: peers + çox sinfə göndərmə | `api/plan.py`, `api/tasks.py` | test |
| 4 | Formativ jurnala yazılış + planlaşdırıcı | `app/task_journal.py`, `scheduler.py` | test |
| 5 | Plan səhifəsi «🧪 Test», Tapşırıqlar batch görünüşü | `Plan.tsx`, `TaskEditor.tsx`, `Tasks.tsx` | `tsc` |
| 6 | Sınaq: yaratma, jurnal, reytinq, portal, çap | `api/exams_online.py`, `OnlineExams.tsx`, `api/portal.py`, `student/Results.tsx` | test, `tsc` |
| 7 | Səviyyə qrupları: hesab, önizləmə, tətbiq, təklif, cross-class | `app/levels.py`, `api/levels.py`, `Journal.tsx` (tab) | test, `tsc` |
| 8 | Səviyyəyə görə hədəf və variantlı test | `api/plan.py`, `api/portal.py` | test |
| 9 | Əlavə məşğələ: kurs, məşğələ planı, davamiyyət, test, statistika, portal | `api/extra.py`, `app/extra_stats.py`, `ExtraCourses.tsx`, `student/Extra.tsx`, `student/Today.tsx` | test, `tsc`, `vite build` |
| 10 | Brauzer yoxlaması (360 px daxil), canlıda `alembic upgrade head` | – | əl ilə |

Mərhələ təklifi: **I** – 1–5 (mövzu testi + jurnal), **II** – 6 (sınaq + reytinq), **III** – 7–8 (səviyyə qrupları), **IV** – 9 (əlavə məşğələ). Hər mərhələ ayrıca commit və yoxlama.

---

## 6. Fikirlərim (metodist və İKT baxışı)
1. **Testi müəllimin seçməsi düzgündür** – bank faylları mövzulara bir-bir uyğun gəlmir (P007 bölmədir, P003 bloklar üzrədir).
2. **Tarix hər sinfin öz dərsindən** – paralel siniflərdə eyni mövzu fərqli günlərə düşür; eyni vaxt qoyulsa bir sinif mövzunu keçmədən yazar.
3. **Yazmayana «2» yox** – onlayn test evdə yazılır; boş xana müəllimə siqnaldır.
4. **Sınaq üçün qısa pəncərə** (bir gün, 2–3 saat), sualların və variantların sırası qarışdırılmış – yoxsa cavablar paylaşılır, reytinq ədalətsiz olur. Mövzu testində geniş aralıq problem deyil.
5. **Reytinqdə dinamika** – buraxılışa hazırlıqda yer deyil, artım motivasiya edir; şagird yalnız öz yerini görsün.
6. **Səviyyə qrupları – sabit həddlər üçdəbirdən yaxşıdır.** Üçdəbir bölgü güclü sinifdə də şagirdlərin 1/3-ni «zəif» edir; 70/40 həddi isə real mənimsəməni göstərir. Üçdəbir yalnız qrupları bərabər ölçüdə saxlamaq lazım olanda (məs. əlavə məşğələ üçün) seçilsin.
7. **İlkin bölgüdə buraxılış balı tək meyar olmamalıdır.** IX buraxılış balı X sinifdə yaxşı başlanğıcdır, amma oktyabrdan sonra ilk sınaq və KSQ-1 nəticəsi daha dəqiqdir – çəkilər buna görə dəyişir. V–IX siniflər üçün ilin əvvəlində **diaqnostik test** (bankda «İlkin yoxlama» var) yeganə obyektiv mənbədir.
8. **Səviyyə dəyişməsi təklif olmalıdır, avtomatik yox** – şagird hər sınaqdan sonra qrupdan qrupa «atılsa», həm müəllim, həm şagird üçün qarışıqlıq yaranar; histerezis (5 bal) bunu qarşılayır. Rüb sonunda bir dəfə baxmaq kifayətdir.
9. **Səviyyə etiketi şagirdə göstərilməsin** – «zəif qrup» yazısı motivasiyanı salır; şagird sadəcə ona uyğun tapşırığı alır. Valideyn görüşündə müəllim bunu şifahi izah edir.
10. **Səviyyəyə görə variant yalnız mövzu testində** – sınaqda hamıya eyni suallar olmalıdır, əks halda reytinq müqayisə edilə bilməz.
11. **Əlavə məşğələnin öz planı olmalıdır** – ad-hoc «bu gün məşğələ var» yazmaq şagirdi də, valideyni də çaşdırır. Kurs (məs. «IX – buraxılışa hazırlıq, 12 həftə, şənbə 10:00») əvvəlcədən planlananda şagird nə vaxt hansı mövzunun keçiləcəyini bilir və hazırlaşır; bu, iştirakı artırır.
12. **Effekti rəqəmlə göstərmək** – məşğələyə gələnlərlə gəlməyənlərin eyni mövzu testləri və sınaqlar üzrə orta fərqi tədris hissəsi və valideyn üçün ən inandırıcı göstəricidir. Hər məşğələnin sonunda 5–8 suallıq qısa test bunun üçün kifayətdir.
12a. **Əyani və onlayn formatı qarışdırmaq olar** – məs. həftədə bir əyani (məktəbdə), bir onlayn (evdən) məşğələ; statistika format üzrə də ayrılır ki, hansının effektiv olduğu görünsün.
12b. **Zəif qrup üçün məşğələ – təkrar, güclü qrup üçün – sınaq/olimpiada**. Məşğələ planına mövzu təklifi buna görə səviyyə qrupuna bağlanır (D və E blokları birlikdə işləyir).
13. Gələcək addım (bu mərhələdə yox): mövzu testi < 60 % → Jurnal → Mövzularda «Təkrar» statusunun **təklifi**; əlavə məşğələ üçün AI ilə qısa plan (gündəlik plan generatorundan ayrı, qısa forma).

---

## 7. İcra nəticəsi – I mərhələ (mövzu testi + formativ jurnal), 02.10.2026
- **Miqrasiya** `d1e4f7a2b8c3`: `classes.grade` (mövcud siniflər addan doldurulur), `test_batches`, `online_tasks.kind/batch_id/plan_lesson_id/journal_auto/journal_done_at`, `marks.task_id`; `upgrade → downgrade → upgrade` yoxlanıb.
- **Backend:** `domain/classes.grade_of`, `services.class_grade` (bölünmə qrupu – ana sinifdən, tədris qrupu – üzvlərin sinfindən);
  `api/topic_tests.py` – `GET /api/plan/{ta}/topics/{pl}/peers`, `POST /api/plan/{ta}/topics/{pl}/test`, `POST /api/plan/{ta}/tests/{task}/journal`;
  `GET /api/plan/{ta}` – hər mövzuda `tests`; `app/task_journal.py` – jurnala yazılış (§3.6–3.7) + planlaşdırıcı (15 dəq).
- **Düzəlişlər (yoxlama zamanı tapıldı):**
  - `aware()` qurşaqlı vaxtı UTC-yə çevirmirdi – `+04:00` ilə gələn vaxt SQLite-da 4 saat sürüşürdü;
  - jurnal yazısı yenidən saxlananda onlayn test qiymətinin mənbəyi itirdi və qayıb şagirdin onlayn qiyməti saxlamanı bloklayırdı – indi dəyişdirilməmiş onlayn qiymət mənbəyini saxlayır;
  - cəhd sıfırlananda testdən yazılmış qiymət silinir; bitmə vaxtı dəyişəndə jurnal yenidən yazılır;
  - başlayıb heç cavab verməyən (boş avtomatik təhvil) şagirdə 2 yazılmır – «yazmayıb» kimi hesabatda;
  - planlaşdırıcı bank yeniləməsi söndürülsə də işə düşür (jurnal işi həmişə lazımdır);
  - Tapşırıqlar siyahısında bir neçə günlük testin bağlanma **tarixi** göstərilmirdi (yalnız saat).
- **İnterfeys:** Perspektiv plan – hər mövzuda «🧪 Test» və testin vəziyyəti (gözlənilir / açıqdır · 12/25 / bitib · 72 % · jurnalda);
  `TopicTest.tsx` – siniflər (eyni mövzu, hər birinə başlama/bitmə tarixi-saatı, «hamısına bu sinfin vaxtı», mövzu tapılmayanda əl ilə seçim),
  test bazası + öz sualım, «Bağlananda formativ jurnala yaz»; Tapşırıqlar – «mövzu testi · №N», «jurnala yazılıb / yazılacaq».
- **Yoxlama:** 151 test keçdi (yeni `test_api_topic_tests.py` – 3 test), `tsc`, `vite build` təmiz. Brauzerdə əl ilə yoxlama (360 px daxil) hələ edilməyib.
- **Növbəti:** II mərhələ – sınaq imtahanları + sinif/ümumi reytinq (bank faylının növü – `kind='sinaq'` təsnifatı ilə).
