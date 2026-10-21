# Kart: KSQ əsasında onlayn sınaq (21.10.2026)

**Sifarişçi:** müəllim: «sessiyada KSQ hazırladım – onun əsasında sınaq da yarat».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Qaydalar:** CLAUDE.md – AZ/EN/RU; test seçimi yalnız `app/plan_tests.py`
(yeni seçim qaydası lazımdırsa – orada RESOLVERS/opts); `npm run build` + aid pytest.

## Mövcud
- KSQ/BSQ = `Exam` (kağız/onlayn), şagird variantları `ExamVariant.questions` (hər sualda `bank_id`, `key`, mövzu/alt mövzu, `points`).
- Onlayn sınaq: `POST /api/exams-online` (`ExamIn`: title, duration_min, bank_ids, custom, shuffle, show_answers, penalty, targets[…]),
  UI – `frontend/src/pages/teacher/OnlineExams.tsx` (yaratma pəncərəsi, təkrar/sinif xəbərdarlıqları – `repeats`, `grade_issues`).

## Tələb
1. KSQ kartında (Jurnal → KSQ / BSQ, `Exams.tsx`, imtahan sətri və «Nəticələr» pəncərəsi) düymə **«🎯 Bu KSQ əsasında sınaq»**.
2. Pəncərə: rejim seçimi
   - **Analoji suallar** (defolt) – KSQ-nin hər sualının alt mövzusundan (bank faylı/mövzu) BAŞQA bank sualı, eyni çətinlik/tip;
     KSQ-də istifadə olunmuş suallar və bu sinfə əvvəl verilmişlər çıxılır (mövcud «əvvəl verilmiş» məntiqi – `exams.py:537`).
     Seçim məntiqi `plan_tests.py`-də yeni opsiya kimi (məs. `analog_of=exam_id`), burada təkrarlanmır.
   - **Eyni suallar** – A variantının (və ya bütün variantların unikal) bank sualları.
   Sual sayı = KSQ-dəki sayı; tapılmayan alt mövzu – xəbərdarlıq (say) + boş qalmır, eyni mövzudan başqa sual.
3. «Davam et» → onlayn sınaq yaratma pəncərəsi **doldurulmuş** açılır: başlıq «<KSQ adı> – sınaq», hədəf – həmin sinif/dərs,
   suallar; müəllim vaxtı/tarixi dəyişib göndərir (mövcud axın, xəbərdarlıqlar işləyir). Avtomatik göndərmə YOXDUR.
4. API: `GET /api/exams/{ta}/{exam}/as-sinaq?mode=analog|same` → `{title, bank_ids, missing: [...], targets: [{ta_id}]}` (öz dərsi; başqa
   müəllim 404).
5. Testlər: analog – KSQ sualları və əvvəl verilmişlər yoxdur, sayı bərabər, alt mövzular uyğun; same – bank_ids eyni; icazə 404;
   OnlineExams prefill – build.
