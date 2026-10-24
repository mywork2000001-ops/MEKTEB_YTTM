# Tapşırıq: Sınaq seriyası — gündə 2 sınağa qədər, yenidən köhnəyə; bütün siniflər üçün avtomatik seriya
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)   İstifadəçi: «построй авто сынаг для классов (школы и ферди)… серию сынаг на каждый день максимум 2 сынаг с нового на старый»
- İcraçı: `kodcu` (worktree). Miqrasiya canlıda — Rəhbər.

## İndiki vəziyyət (kodda yoxlanıb)
- `backend/app/api/exam_series.py`: hər yuvada (`run_series`) növbədən **yalnız 1** sınaq gedir (`break`); növbə müəllimin seçdiyi sıradadır, `_sync_new` yeniləri **sona** əlavə edir (köhnədən yeniyə).
- `ExamSeries` (models.py:605) — `per_slot`/sıra sahəsi yoxdur. `BankFile.held_on` (sınağın tarixi) var.
- Müəllim hər sinif üçün seriyanı əl ilə qurmalıdır; fərdi məkan (School.kind='private', models.py:44) sinifləri ayrıca.

## Qərarlar
1. **İki sahə** `ExamSeries`-də (miqrasiya, nullable, `down_revision = 'e6b0d4f8a2c5'`, yalnız add_column, downgrade):
   - `per_slot: int` — bir yuvada neçə sınaq (1 və ya 2; NULL = 1). API: `Field(1, ge=1, le=2)`.
   - `newest_first: bool` — növbə **yenidən köhnəyə** (NULL = False — köhnə seriyalar dəyişmir).
2. **Sıra açarı** (bir funksiya `_newest_key(f)`): `held_on` azalan (NULL — sonda), sonra `BankFile.id` azalan.
   `newest_first` olanda: yaradılanda növbə bu açarla sıralanır; `_sync_new` yeni faylları sona yox, açara görə **yerinə** qoyur (praktikada önə); PATCH ilə növbə əl ilə dəyişəndə müəllimin sırası saxlanır, amma sonrakı yenilər yenə açarla yerləşir.
3. **`run_series`**: yuvada `per_slot` qədər uğurlu göndəriş (`_send` None olan / bankdan çıxmış — sayılmır, növbəti götürülür). İkinci sınaq eyni açılma vaxtında. `done`-a hər biri ayrıca. Gündə maksimum = `per_slot` (period='day', every=1 → gündə ≤ 2). Keçmiş yuvalar toplanmır (indiki qayda qalır).
4. **`series_out` önbaxışı**: hər yuvada `per_slot` fayl (`labels` siyahısı; köhnə `label`/`file_id` sahələri birinci fayl üçün qalır — frontend uyğunluğu).
5. **«Bütün siniflər üçün avtomatik seriya»** — `POST /api/exam-series/auto-all`:
   - Müəllimin bütün aktiv dərsləri (`TeachingAssignment`) **həm məktəbdə, həm fərdi məkanda** (sahibi olduğu bütün məkanlar; admin üçün də yalnız öz dərsləri). Hüquq `_can_target` qaydası ilə eyni (məkan yoxlaması aktiv məkandan asılıdırsa — hər məkan üçün düzgün yoxla, yoxlamanı zəiflətmə).
   - Hər dərs üçün **bir seriya** (bir sinif = bir seriya; qrup sinfi də ayrıca), əgər o dərsdə artıq **aktiv** seriya yoxdursa (varsa — atlanır, cavabda «artıq var»).
   - Parametrlər (body, hamısı defoltlu): `period='day'`, `every=1`, `per_slot=2`, `newest_first=True`, `auto_new=True`, `sources=['sinaqlar','p012','p009']`, `open_time='15:00'`, `window_hours=48`, `duration_min=0`, `penalty=0`, `show_answers='after_close'`, `shuffle=True`, `grade` = sinfin rəqəmi.
   - Növbə: sinfə **uyğun** (`grade_fits`) və bu sinfə **hələ verilməmiş** (`_given_to`) bütün `kind='sinaq'` faylları, `_newest_key` sırası ilə. Uyğun fayl yoxdursa da seriya yaranır (auto_new gözləyir) — cavabda «növbə boş».
   - `dry_run: bool = True` defolt: heç nə yazmadan siyahı qaytarır `[{ta_id, class_name, space: 'school'|'private', subject, queue_n, first: [ilk 2 adı], status: 'create'|'exists'|'empty'}]`. `dry_run=False` — yaradır (yaradılandan sonra `run_series(only=id)` adi `create_series` kimi), audit.
6. **Frontend `ExamSeries.tsx`** (sözlə, rəqəm sahəsi yox):
   - Formada «Hər dəfə: bir sınaq / iki sınaq» və «Sıra: yenidən köhnəyə / seçdiyim sıra ilə» (yeni seriyada defolt — yenidən köhnəyə). Canlı cümləyə əlavə: «hər gün iki sınaq, ən yenisindən başlayaraq». `humanTime.ts`-dəki `numWord` istifadə et.
   - Siyahı başında düymə **«Bütün siniflər üçün avtomatik seriya»** → əvvəl dry_run cədvəli (sinif, məktəb/fərdi, növbədə neçə sınaq, ilk iki ad, status) → «Yarat» (yalnız status=create olanlar). Saat/açıq qalma seçimi formadakı DurationSelect-lərlə (defolt 15:00, iki gün).
   - Önbaxışda yuvada iki ad.
   - Bütün yeni mətnlər AZ/EN/RU (`t()`, i18n.ts sonuna, təkrar açar yox — əvvəl `grep`).

## Testlər (`tests/test_exam_series_daily.py`)
- per_slot=2: bir yuvada 2 sınaq, növbəti gün yenə 2; per_slot=1 köhnə davranış; `_send` None olan fayl sayılmır.
- newest_first: held_on azalan, NULL sonda; `_sync_new` yeni faylı önə qoyur; newest_first=False — sona (köhnə).
- auto-all: dry_run yazmır; məktəb + fərdi məkanın dərsləri ikisi də siyahıda; aktiv seriyası olan — `exists`; başqa müəllimin dərsi yoxdur; verilmiş sınaq növbəyə düşmür; sinfə uyğun olmayan düşmür.
- Miqrasiya up → down → up (müvəqqəti SQLite, mövcud testlərin üsulu ilə).
- Mövcud `tests/` seriya testləri keçməlidir. `npm run build` (frontend; worktree-də node_modules — əsas repodan junction, sonda `cmd /c rmdir`).

## Toxunma
Sınaq təkrar qadağası (`_given_to`), cərimə, `create_exam`, apelyasiya, KSQ.

## Cavab formatı
docs/agent-sistemi-promtu.md §7: fayllar, miqrasiya revision/down_revision, i18n açarları, pytest, build, açıq suallar.

## Əlavə (istifadəçi, 24.10): «с пятницы 23 октября, бессрочные, правильные ответы учитель отправляет ученику или нескольким»
### Tapıntı (kodda yoxlanıb)
`api/portal.py:311` `_can_review`: müddətsiz (`is_unlimited`) testdə cavablar şagird **təhvil verən kimi** açılır — müddətsiz sınaqda birinci təhvil verən düzgün cavabları sinif yoldaşlarına ötürə bilər. Müəllimin cavabları özünün göndərməsi rejimi yoxdur.

### Qərarlar
7. **Yeni rejim `show_answers='teacher'`** («Cavabları müəllim göndərir»): şagird cavabları yalnız müəllim ona göndərəndə görür (müddətsiz olsa da). Mövcud rejimlər dəyişmir.
   - Sütun `TaskAttempt.answers_released_at` (nullable DateTime) — eyni miqrasiyada. `_can_review`: `t.show_answers == 'teacher'` → `a.answers_released_at is not None` (yoxlama `is_unlimited`-dən **əvvəl**). Bütün `show_answers` Literal-larına (`tasks.py:196,755`, `exam_series.py SeriesIn`, `exams_online` yaratma) `'teacher'` əlavə.
   - `POST /api/tasks/{task_id}/release-answers` `{student_ids: [..]}` (boş/yox = təhvil verənlərin hamısı) — yalnız təhvil vermiş cəhdlərə; hüquq — tapşırığın müəllimi/admin; audit; cavab `{released: n, not_submitted: [adlar]}`. Sınaq paketi üçün `POST /api/exams-online/batches/{batch_id}/release-answers` (paketin bütün siniflərində, eyni body) — mövcud prefiks/ad üslubuna uyğunlaşdır.
   - Geri alma: `DELETE` eyni yol (səhvən göndəribsə; şagird artıq baxıbsa da bağlanır).
   - Şagirdə bildiriş mövcud bildiriş mexanizmi varsa — «Müəllim «{ad}» sınağının düzgün cavablarını göndərdi» (AZ/EN/RU).
   - Müəllim UI: sınaq/tapşırıq nəticələri cədvəlində (Sınaq jurnalı və tapşırıq nəticəsi — harada şagird sətirləri var) seçim qutuları + «Düzgün cavabları göndər (seçilənlərə)» və «Hamısına göndər»; sətirdə nişan «cavablar göndərilib · tarix». Formada (sınaq, seriya, test) yeni seçim «Cavabları müəllim göndərir».
8. **Seriya başlama tarixi keçmişdə ola bilər (≤ 14 gün)** və müddətsiz seriyada (`window_hours=0`) qaçırılmış yuvalar yaradılanda **bir dəfə doldurulur**: hər keçmiş yuva üçün `per_slot` sınaq, `opens_at` = həmin yuvanın vaxtı (sıra: ən yeni sınaq ən erkən yuvaya — yəni növbə sırası ilə). Müddətli seriyada keçmiş yuvalar indiki kimi atlanır.
9. **auto-all defoltları yenilənir:** `start=2026-10-23` (body-də dəyişdirilə bilər, defolt — bu gün), `window_hours=0` (müddətsiz), `show_answers='teacher'`, `period='day'`, `per_slot=2`, `newest_first=True`. Dry-run cədvəlində hər sinif üçün «indi açılacaq: N» (23 və 24.10 → 4).
### Əlavə testlər
- `teacher` rejimi: müddətsiz sınaqda təhvildən sonra review 403; release-dən sonra 200; başqa şagird hələ 403; DELETE → yenə 403; təhvil verməmişə release olmur.
- Keçmiş start + müddətsiz: 2 gün × 2 = 4 sınaq, opens_at yuva vaxtları; müddətli seriyada doldurma yoxdur; start > 14 gün əvvəl — 422.

### Dəqiqləşdirmə (istifadəçi, 24.10)
Rejim «teacher»-də şagird öz balını (bal, faiz, düz/səhv/boş sayı – sınaqda olduğu kimi qiymətsiz) təhvil verən kimi görür; yalnız sual-sual düzgün cavablar (review, «Səhvlərim», çap) müəllim göndərənə qədər bağlıdır. Göndərmə bir və ya bir neçə şagirdə (seçim qutuları). Test: teacher rejimində təhvildən sonra siyahıda bal/faiz görünür, review 403.
