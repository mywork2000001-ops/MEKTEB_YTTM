# Audit: Əlavə məşğələ / Məşğələ qrupları (20.10.2026)

Yalnız oxuma auditi; kod dəyişmədi. Fayllar: `backend/app/api/extra.py`, `models.py` (ExtraCourse 870, ExtraSession 888, ExtraAttendance 909),
`levels.py`, `programs.py`, `api/programs.py`, `plan_tests.py`, `bank/match.py`, `analytics.py::_extra`, `frontend/src/pages/teacher/ExtraCourses.tsx` (448 sətir).

## 1. Funksional audit

### 1.1 Nə işləyir
- Kurs yaratma (`extra.py:233`): cədvəl → tarixlər avtomatik (`generate`, 140), tətil çıxılır, mövcud tarix+saat təkrar yaranmır (idempotent), məktəb cədvəli ilə toqquşma xəbərdarlığı.
- Üzvlük: audience = `ta_ids` + `levels` (dinamik, `LevelOverride`-dan) və ya `student_ids` (əl ilə). `add_members/remove_member` (356/376) auditoriyanı «seçilmiş şagirdlər»ə çevirir.
- Məşğələ: mövzu (plan_lesson_id və ya sərbəst mətn), davamiyyət (`mark_held`), onlayn qoşulma, məşğələ testi (`session_test`, 618), statistika (`stats`, 660: iştirak %, risk, əvvəl/sonra, iştirakçı ↔ digərləri).
- Şagird portalı (`student_courses`, 731) səviyyə etiketini göstərmir: cavabda `levels` yoxdur, yalnız `title/goal/teacher/sessions`. Düzgündür.
- Analitikada (`analytics.py:121 _extra`) şagirdin məşğələ iştirakı sinif analitikasına düşür.
- Testlər: `tests/test_api_extra.py`, `test_api_extra_members.py`, `test_api_levels.py`, `test_plan_tests.py` mövcuddur (proqram bağlılığı üçün test yoxdur).

### 1.2 Boşluqlar və xətalar
1. **Cədvəl dəyişdirilə bilmir.** `CoursePatch` (258) cədvəl/başlama tarixi/format sahəsi daşımır; yalnız `ends_on` uzadılır (`generate(frm)` yalnız əlavə edir, heç vaxt silmir). Cədvəl səhvdirsə kursu arxivləyib yenidən yaratmaq lazımdır, mövzular itir.
2. **`PUT /sessions/{sid}` ilə `status='held'`** (`SessionIn.status`, 426; `_apply_session` 440) `mark_held`-dəki vaxt yoxlamasını (518) və davamiyyəti keçir: gələcək məşğələ «keçirildi» ola bilər, statistika pozulur.
3. **`session_test` (618)** məşğələdə artıq `batch_id` olsa belə yenisini yaradıb əvvəlkini sessiz əvəz edir (köhnə tapşırıqlar yetim qalır). İdempotent deyil.
4. **`bulk_topics` (550):** yalnız `not s.topics` və `date >= today` olan məşğələlərə yazır; təkrar çağırışda qalan mövzular («left») növbəti çağırışa keçir, amma proqramın mövqeyi yadda saxlanmır; yəni «ardıcıllığın harada qaldığı» məlum deyil.
5. **`suggest_topics` (571)** planı yalnız `ta_ids[0]` üçün qaytarır (595); çox sinifli qrupda (məs. 7A+7B) digər sinfin PlanLesson-ları təklif olunmur. `_plan_ids` isə bütün ta-lardan icazə verir: uyğunsuzluq.
6. **PlanLesson-a bağlılıq:** məşğələ mövzusu yalnız kursun siniflərinin **əsas** perspektiv planından (PlanLesson) ola bilər (448). Əlavə proqram (`AssignmentProgram`) və DİM «Sinif testləri» PlanLesson yaratmır, `dated()` ilə hesablanır. Yəni zəif qrupa V–IX «Sinif testləri» mövzusunu bağlamaq indi mümkün deyil (yalnız sərbəst mətn).
7. **Performans (N+1):** `list_courses` (212) hər kurs üçün `members()` (roster + LevelOverride sorğuları, ta başına) və `_sessions`, `session_out` (hər məşğələ üçün ayrıca attendance sorğusu) çağırır. `analytics._extra` (121) hər dərs/çağırışda **bütün** aktiv kursları (məktəblər üzrə, owner süzgəci olmadan, 126) oxuyur. `student_groups` (395) hər kurs üçün `members()` + hər ta üçün `roster`.
8. **`members()` səviyyə üzrə dinamikdir:** `levels` seçilibsə, Jurnalda şagirdin səviyyəsi dəyişəndə qrup tərkibi sessiz dəyişir (köhnə davamiyyət qalır, şagird portaldan itir). Bu bəzən istənilən, amma müəllimə göstərilmir.
9. **Qrup tipi yoxdur.** Heç bir sahə «inkişaf/tərəqqi» deyil; yeganə işarə `audience.levels` (Zəif/Güclü) və ya sərbəst `title`. `add_members` isə `levels=None` edir (369), yəni əl ilə əlavə edilmiş qrupda tip tamamilə itir.
10. Kiçik: `generate` dövrü gündə-gün gəzir (366 gün × cədvəl; qəbul olunandır). `patch_course` ends_on qısaldanda `held` olmayan məşğələləri silir, amma `cancelled` + `batch_id` olanda test tapşırıqları qalır.

### 1.3 Kursa proqram bağlamaq üçün tələb olunanlar
**Məlumat modeli variantları**
- **A (miqrasiyasız):** `ExtraCourse.audience` JSON-una `program_id`, `program_level`, `kind: 'inkisaf'|'tereqqi'`, `program_cursor` əlavə et. Üstünlük: migrasiya yoxdur (JSON). Çatışmazlıq: sorğulanmır, tipləşdirilmir; `add_members` kimi funksiyalar audience-i yenidən yazır, açarları itirmək riski (369, 387: `dict(c.audience)` saxlayır, amma `create` yeni dict qurur).
- **B (miqrasiya, tövsiyə):** `extra_courses` cədvəlinə `kind String(10) null`, `program_id FK plan_programs null`, `program_sections JSON null`. Bir `ALTER TABLE ADD COLUMN` (null, defolt yoxdur) — təhlükəsizdir. Canlı DB üçün istifadəçi razılığı lazımdır (layihə qaydası).
- **C:** ayrıca `ExtraCourseProgram` cədvəli (çox proqram: bir qrupa «V–VI təkrar» + «VII Sinif testləri»). `AssignmentProgram`-ın nümunəsi var (203). Hələlik lazımsız.

**Mövzuların proqram ardıcıllığından doldurulması**
- `programs.lessons_for(db, program, ta, sections)` (752) TA-nın cədvəlinə görə dərs yuvaları üçün açır; kursun öz cədvəli üçün **uyğun deyil** (məşğələ həftədə 1–2 dəfə, öz tarixləri). Yeni funksiya lazımdır: `programs.topic_sequence(program, sections) -> list[{section, topic, no}]` (şablondakı mövzu siyahısı, `expand`-ın daxili yürüyüşündən çıxarılmalı) və sonra `extra.fill_from_program(db, c)`: planlaşdırılmış, mövzusuz, `date >= today` məşğələlərə sıra ilə yazır (`bulk_topics` məntiqi, 559–565).
- Sessiya mövzusu `{plan_lesson_id: null, text: "5.2 Kəsrlər [DİM Sinif testləri V]"}` kimi saxlanır; `program_key + topic_no` əlavə sahə kimi (`TopicRef`-ə `ref` sahəsi) yazılsa test təyini asanlaşır.
- **Cədvəl dəyişəndə yenidən hesablama:** `fill_from_program(..., reflow=True)` yalnız `planned` + `held olmayan` + `proqramdan gələn` (`ref` işarəli) məşğələləri silib mövqeyi `held` sayına görə davam etdirir. Əl ilə yazılmış mövzuya toxunmur. Əvvəl 1.2/1-ci bənd (cədvəli dəyişmək) düzəlməlidir.
- **İdempotentlik:** hər məşğələ `ref` daşıyır; təkrar çağırış yalnız `ref`-i olmayan boş məşğələni doldurur; eyni `ref` ikinci dəfə yazılmır (kursun `program_cursor`-u və ya mövcud `ref`-lərin max indeksi).

**Məşğələ testləri `plan_tests.py` vasitəsilə (layihə qaydası: tək mühərrik)**
- Mühərrik `TeachingAssignment` + `PlanLesson` üzərində işləyir (`plan_items`, `resolve`, `build_task`); məşğələ mövzusu PlanLesson olmadığından birbaşa tətbiq olunmur. Düzgün yol: `plan_tests.py`-ə **yeni mənbə** əlavə etmək (RESOLVERS: `r_extra_program`) — verilmiş `grade` + `topic_no` üçün `GradeMatcher`/`bank` faylını seçir (`r_grade_matcher`, 232-ni təkrar işlədir), `build_task`-ı `kind='extra'` və `batch_id` ilə çağırır. `extra.session_test` yalnız nəticə yazır, seçim məntiqini özündə saxlamır. Yeni API: `/api/plan-tests/*` altında və ya `extra.py`-dan `plan_tests.assign_extra(db, user, course, date_from, date_to, opts)`; test `tests/test_plan_tests.py`-də.
- V–VIII üçün `PENDING_GRADES={5,6,7,8}` (`bank/match.py:28`): bank sualları hələ hazır deyil; nəticə «Gözlənilir» (`R_PENDING`). Yəni inkişaf qrupu V–VIII-də proqram mövzuları və planı alacaq, amma avtomatik test hələlik yalnız IX üçün (X–XI bu həyata keçirmənin xaricindədir). Bu, UI-də açıq göstərilməlidir («testlər hazırlanır»).

**Qrup tipinin müəyyənləşdirilməsi**
- Etibarlı: yeni `kind` sütunu (B) + yaradılışda `levels==['Zəif']`-dən defolt təklif. `title`-dan ağıl yürütmək (regex «Zəif/Güclü») kövrəkdir; `audience.levels` isə `add_members` ilə silinir (369). Köhnə kurslar üçün bir dəfəlik miqrasiya skripti: `levels==['Zəif']` → inkişaf, `['Güclü']` → tərəqqi, qalanı null (əl ilə).

**Çoxlu qrupa kütləvi təyinat**
- `POST /api/extra/assign-program` `{course_ids|all_inkisaf: true, program_mode: 'auto-grade', dry_run}`: hər kurs üçün sinif (ta → `class_grade`) → `dim-sinif-testleri-{grade}` (V–IX; kurs bir neçə sinifdən ibarətdirsə ən aşağı və ya əksəriyyət, xəbərdarlıqla). Əvvəl `dry_run` hesabatı (neçə kurs, hansı proqram, neçə məşğələ doldurulacaq), sonra təsdiq. `plan_tests.assign` ilə eyni `Report` üslubu. Təkrar işlətmə təhlükəsizdir (yuxarıdakı `ref` qaydası). `audit()` yazılır.

## 2. Metodik audit

**İnkişaf (Zəif) → DİM «Sinif testləri» (V–IX): əsasən məntiqlidir, amma sərt yox, uyğunlaşdırılmış**
- Sinif testləri sinif standartının mövzu ardıcıllığıdır; zəif şagirdlər üçün əsas problem çox vaxt **əvvəlki sinfin** boşluqlarıdır (kəsrlər, mənfi ədədlər, tənliklər, faiz). Yalnız öz sinfinin proqramını ardıcıl keçmək uğursuzluğu təkrarlaya bilər. Tövsiyə: hər qrupun ilk 2–3 məşğələsi **əvvəlki sinfin əsas mövzuları** (prerekvizit xəritəsi: VII → V–VI kəsr/faiz/tənlik; IX → VII–VIII cəbr, həndəsə) və yalnız sonra cari sinfin Sinif testləri sırası. V sinif üçün: ibtidai (IV) məzmunla körpü.
- **Formativ/summativ:** məşğələ testləri kiçik formativ yoxlamadır (5–8 sual, 10–15 dəq.), jurnala yazılmır; bu Azərbaycan təcrübəsinə (formativ qiymətləndirmə + KSQ/BSQ) uyğundur. Məşğələ əsas dərsin KSQ/BSQ-sini əvəz etməməlidir; KSQ/BSQ-dən əvvəl **hazırlıq məşğələsi** təyin etmək olar (KSQ tarixləri planda var).
- **Diaqnostik giriş və çıxış testi:** `levels.py` artıq `diaqnostik` komponenti saxlayır (BankFile.kind=='diaqnostik'). Qrupun ilk məşğələsi qısa diaqnostik (öz sinfi + əvvəlki sinif mövzuları), sonuncusu eyni formatda çıxış testi olmalıdır; `stats` indi «əvvəl/sonra»nı kursdan əvvəl/sonra bütün mövzu/sınaq testlərinin ortası ilə müqayisə edir (692–693), bu qaba və məşğələ ilə əlaqəsiz təsirləri qatır. Kursa bağlı giriş/çıxış testi daha dürüst göstəricidir.
- **Tempo:** həftədə 1×45 dəq. ilə bir mövzu/məşğələ asan olmayacaq (Sinif testləri 40–70 mövzu). `lessons_for` kimi büdcə hesabı (`budget_summary`) kurs üçün də göstərilməli: «X mövzu, Y məşğələ var, Z mövzu atılacaq/birləşdiriləcək». Zəif qrupda qaçırılan mövzular **ən çətin yox, əsas** (A səviyyə variant) seçilməlidir: «variant A/B» bölgüsündən yalnız A.
- **Variantlar:** Sinif testlərində A/B/C var (`grade_variants`/`variant_for`, programs.py:706–725). İnkişaf qrupu: A + B, tərəqqi qrupu: B + C. Bu, indi `AssignmentProgram.level` ilə qismən qurulub, amma `ExtraCourse`-dan keçmir.

**Tərəqqi (Güclü) qrupu:** yalnız Sinif testləri deyil; tövsiyə olunan tərkib:
- sinfin perspektiv planından **irəlidə** 1–2 mövzu (qabaqlayıcı), əsas dərsdən ayrılmayan;
- C səviyyəli və olimpiada tipli tapşırıqlar (`PlanProgram.purposes` içində `olimpiada` və `buraxilis9/11` kurslar artıq var), IX–XI üçün DİM formatlı buraxılış/qəbul tapşırıqları (`dim_toplu_9_2025`, `hazirliq-buraxilis-9`);
- açıq cavablı, çoxaddımlı, sübut/əsaslandırma tapşırıqları; vaxt məhdudiyyəti ilə DİM formatı;
- V–VIII güclü qrup üçün «perspektiv proqram» təyini üçün uyğun **hazır** proqram hələ yoxdur (`PlanProgram.level='Güclü'` ilə proqramlar yalnız əl ilə yaradılıb). Əvvəl bu proqramlar siyahısı hazırlanmalıdır (öz kartı).

**Effektin ölçülməsi:** (a) giriş/çıxış testi (eyni mövzu çətinliyi, fərqli variant); (b) davamiyyət (indi var, risk = ardıcıl 2 «yox»); (c) iştirakçı ↔ digər şagirdlərin irəliləyişi (`compare`, 700–712) — seçim qərəzi var (daha motivli şagird iştirak edir), buna görə hesabatda «səbəb deyil, əlaqə» qeydi; (d) nəticə ≥ həddi aşan şagird üçün **keçid təklifi**.

**Qruplar arası hərəkət:** `levels.suggestions` (histerezis 5 bal, `levels.py`) Jurnalda var, amma məşğələ qrupuna bağlı deyil. Təklif: çıxış testindən sonra `stats`-da «Orta/Güclü səviyyəyə yüksəlib, qrupdan çıxarmaq?» siyahısı; əksinə, tərəqqi qrupunda uğursuz olan üçün «inkişafa keçir?». Qərar həmişə müəllimindir; şagirdə etiket göstərilmir.

**Yük:** bir şagird həm inkişaf, həm başqa fənn kursunda ola bilər; `student_groups` (395) yalnız eyni müəllimin kurslarını görür. Limit (öneri): şagirdə həftədə ≤ 2 məşğələ və ya ≤ 90 dəq. əlavə yük; qrup ölçüsü 6–15; hazırda ölçü məhdudiyyəti və yük xəbərdarlığı yoxdur. Məktəb cədvəli ilə yalnız **müəllimin/sinfin dərsləri** toqquşması yoxlanır (`conflicts`, 123); eyni şagirdin iki məşğələsinin vaxt toqquşması yoxlanmır.

## 3. Digər audit

**i18n (AZ/EN/RU).** `ExtraCourses.tsx`-də 125 `t()` var, lakin tərcümə edilməyən sətirlər qalıb: səhifə başlığının altyazısı (`Top sub=`, 33), «Heç biri/Hamısını seç/səviyyəsiz» (160), süzgəc etiketləri «Hamısı/səviyyəsiz» (157), cədvəl başlıqları `['№','Tarix','Vaxt','Format','Mövzu','Ev tapşırığı','Status']` (215, çap), `'Qeyd'` (324), `'Əlavə məşğələ'` Drawer başlığı (289), `'Arxiv boşdur.'` (39), `ok="Geri qaytarıldı"/"Arxivə köçürüldü"` (220–221), `'Siniflər'` seqment etiketi və həftənin günləri `DAYS` (20, Classes.tsx:40). Server mesajları (`HTTPException` mətnləri) yalnız AZ: müəllim üçün ola bilər, amma layihə qaydasına görə şagirdə görünənlər (`join` 782–784, «Bu məşğələ əyanidir…») EN/RU qarşılığı almalıdır. Sinif cədvəlinin `DAYS` (extra.py:35) də serverdə AZ qısaltmadır və şagird portalında AZ görünür. Rəsmi çap («Planı çap et») AZ qala bilər (qayda: rəsmi sənəd).

**Məxfilik.** Portal cavabı səviyyə etiketi və başqa şagird adı daşımır (yoxlandı: 731–771). **Risk:** `title` şagirdə görünür (766) — müəllim «Zəif qrup – təkrar» yazarsa etiket sızır. UI mətni (105) yalnız xəbərdarlıq edir: «Şagird öz səviyyəsini görmür», amma başlıq buna tabe deyil. Təkliflər: yaradılışda `title`-da `Zəif|Güclü|inkişaf|tərəqqi` sözü varsa xəbərdarlıq; və ya ayrıca `public_title` (miqrasiyasız: avtomatik neytral ad «Riyaziyyat məşğələsi – VII sinif»). Eyni zamanda `goal` sahəsi də şagirdə açıqdır (767).

**UX.** Müəllimin yolu: Siniflər → Məşğələ qrupları → Yeni kurs (≈ 8–10 klik: ad, format, dərs, səviyyə, cədvəl, tarix) → kursu aç → «Mövzuları paylaşdır» → mövzuları seç. Proqram əlavəsi ilə hədəf: «Yeni kurs» formasında «Tip: İnkişaf/Tərəqqi» seçimi → proqram avtomatik təklif → «Yarat» (≤ 6 klik) və kütləvi təyinat (bir klik, dry-run hesabatı). Hazırda 10 məşğələyə mövzu əl ilə seçilir. `suggest-topics` yalnız «təkrar» statusu və <60 % testlərə əsaslanır, proqram məzmunundan istifadə etmir.

**Performans.** 1.2/7-ə bax. Əlavə: `stats` (660) hər üzv üçün `main` testlərini bütün dövrə yükləyir; 30 şagirdli qrup üçün qəbulediləndir, amma qruplar sayı artanda `list_courses` yavaşlayacaq; `members()` nəticəsini sorğu daxilində keşləmək (dict by course) və `session_out` attendance-ı toplu yükləmək (bir `IN` sorğusu).

**Çap/rəsmi sənəd.** «Planı çap et» (215) frontend-də HTML cədvəl çap edir (server PDF yoxdur). Proqramlı kursda çapa: proqram adı, mənbə (DİM Sinif testləri), mövzu nömrəsi, variant, qrup üzvləri (adlı siyahı yalnız müəllim üçün) əlavə olunmalıdır. Məşğələ jurnalı rəsmi jurnaldan ayrıdır (jurnala yazmır), düzgündür.

## 4. Tövsiyələr (prioritet)

**P1 (dəyişiklikdən əvvəl)**
1. Miqrasiya (B): `ExtraCourse.kind`, `program_id`, `program_sections` (`models.py` + alembic/`main.py` miqrasiya mexanizmi; canlı DB — istifadəçi razılığı). Köhnə kurslar üçün səviyyədən `kind` backfill (dry-run).
2. `programs.topic_sequence()` + `extra.fill_from_program()` (+ `ref` sahəsi `TopicRef`-də); `POST /api/extra/{cid}/program` (təyin/ayır/yenidən hesabla), `reflow` yalnız planned+proqram mənşəli məşğələləri.
3. `extra.py:426/440`: PUT ilə `held` təyinini bağla (yalnız `mark_held` yolu); `session_test` təkrar çağırışda 409 və ya əvvəlki batch-i ləğv et (618).
4. `CoursePatch`-ə `schedule` əlavə et, dəyişəndə gələcək `planned`, mövzusuz/proqramdan gələn məşğələləri yenidən qur (`generate` + silmə), `held`-ə toxunma.
5. Şagird görünüşündə `title`/`goal` sızması üçün xəbərdarlıq/neytral ad (`ExtraCourses.tsx` yaratma forması + server validatoru).

**P2**
6. `plan_tests.py`: yeni resolver `r_extra_program` + `assign_extra()`; bütün test seçimi bu mühərrikdən. V–VIII üçün `R_PENDING` göstər; test: `tests/test_plan_tests.py` + `tests/test_api_extra.py` (idempotent təyinat, reflow, held qorunur).
7. Kütləvi təyinat endpointi `POST /api/extra/assign-program` (dry-run + `audit`), qrup sinif nömrəsindən `dim-sinif-testleri-{grade}`; tərəqqi üçün `PlanProgram.level='Güclü'` proqramı və ya IX üçün `hazirliq-buraxilis-9`/olimpiada kursu.
8. Prerekvizit xəritəsi (`program_data/prereq_{grade}.json`): inkişaf qrupunda ilk 2–3 məşğələ əvvəlki sinif mövzuları; giriş/çıxış testi məşğələləri avtomatik yerləşdirilir (1-ci və sonuncu).
9. `stats`: kursa bağlı giriş/çıxış testi ilə əvvəl/sonra; «keçid təklifi» siyahısı (`levels.suggestions` ilə birləşmə).
10. i18n boşluqları (3-cü bölmə), `DAYS`-ın serverdən çıxarılması (frontend `t()`), `join` mesajlarının EN/RU qarşılığı.

**P3**
11. N+1 optimizasiya: `members()` keşi, toplu attendance, `analytics._extra` məktəb/müəllim süzgəci və `ta_id` üzrə qabaqcadan sorğu.
12. Şagird yükü xəbərdarlığı (həftədə > 2 məşğələ / vaxt toqquşması), qrup ölçüsü limiti 6–15 xəbərdarlıq.
13. Çapa proqram/mənbə/variant; çoxlu proqram (C variantı) lazım olsa sonra.
14. `suggest-topics` bütün `ta_ids` üçün plan qaytarsın (extra.py:595), proqram mövzularını da təklif etsin.
