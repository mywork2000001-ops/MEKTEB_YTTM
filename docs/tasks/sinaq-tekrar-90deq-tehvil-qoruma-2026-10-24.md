# Tapşırıq: Sınağı şagirdə yenidən göndərmək, 90 dəqiqə, «Təhvil ver» ən sonda, imtahanda köçürmə/süni zəka qorunması
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)   İcraçı: `kodcu` (worktree)
- İstifadəçi: «повторно можно отправить ученику сынаг… дай девяносто минут выполнения… təhvil verməni ən axıra ver ki şagird səhvən təsdiq vurmasın və sonda təhvil verəndə təsdiq istəsin, köçürmənin və süni zəkanın imtahanlar zamanı imkansız et; telefonda sağdan çağırma menyusu, digərlərində aşağı hissəni vuranda Gemini gəlir»
- Paralel iş: başqa kodcu `exam_series.py` + `show_answers='teacher'` (docs/tasks/sinaq-seriyasi-gunde-iki-2026-10-24.md) üzərindədir — `exam_series.py`, `_can_review`-ə toxunma; miqrasiya lazımdırsa — yalnız yeni sütun, `down_revision='e6b0d4f8a2c5'` (birləşmədə Rəhbər zənciri düzəldəcək).

## İndiki vəziyyət (kodda yoxlanıb)
- `frontend/src/pages/student/Tasks.tsx:229`: «Testi bitir» düyməsi **yuxarıdakı yapışqan başlıqdadır** (barmaq tez-tez dəyir). Təsdiq pəncərəsi var (`review`, «Bəli, təhvil ver», `armed`).
- Qoruma (`Tasks.tsx:133-145`, `styles/extra.css:155`): copy/cut/paste/contextmenu/dragstart/selectstart bloklanır, `user-select:none`, `-webkit-touch-callout:none` (yalnız iOS). Android-də uzun basma / mətn seçimi menyusu («Gemini», «Axtar», «Circle to Search») hələ çıxa bilir; şəkil (`img`) və KaTeX elementləri ayrıca seçilə bilir.
- Ekrandan çıxma (`visibilitychange`) yalnız cavabları saxlayır; müəllim bilmir. Tam ekrandan çıxışlar (`exits`) sayılır, serverə getmir.
- Təkrar: `exams_online.py:83-150,342,392` — bütün sinfə təkrar sınaq (allow_repeat). Bir şagirdə yenidən göndərmək yoxdur.

## Qərarlar
1. **Yenidən göndərmək (bir / bir neçə şagird):** `POST /api/tasks/{task_id}/resend` `{student_ids:[..], window_hours?: int=0}` — yalnız `kind='sinaq'` (və adi test) tapşırıqlarında; müəllim/admin hüququ. Mövcud tapşırığın surəti: eyni suallar (deepcopy), `title + ' (təkrar)'`, `student_ids` = seçilənlər, `opens_at=now`, `closes_at` = NO_DEADLINE (0) və ya window_hours, eyni `duration_min/shuffle/show_answers/penalty`, yeni `TestBatch(kind=…, title=… (təkrar))` — mövcud «(təkrar)» nişanı reytinqdə işləyir. Köhnə cəhd və nəticə qalır. Audit. UI: sınaq jurnalı / tapşırıq nəticələri cədvəlində şagird seçimi + «Yenidən göndər» (təsdiq pəncərəsi: «N şagirdə yenidən göndərilsin? Köhnə nəticə qalır»).
2. **90 dəqiqə:** sınaq yaratma formasında, seriya formasında və `auto-all` defoltu — `duration_min=90` («doxsan dəqiqə» — humanTime sözlə). Mövcud tapşırıqlara toxunma. (`SOLVE_MINUTES`-də 90 var.) Seriyanın defoltunu başqa kodcu dəyişir — sən yalnız `OnlineExams.tsx`/sınaq yaratma formasının defoltunu.
3. **«Təhvil ver» ən sonda:** başlıqdakı «Testi bitir» düyməsini sil. Sual naviqasiyası: «‹ Əvvəlki» / «Növbəti ›». **Son sualda** (və sual siyahısının altında, səhifənin ən aşağısında) «Testi təhvil ver» düyməsi; mövcud təsdiq pəncərəsi qalır (cavabsız suallar, «Testə qayıt» əsas düymə, «Bəli, təhvil ver» — 2 saniyə `armed` gecikməsi saxlanır). Vaxt bitəndə avtomatik təhvil — dəyişmir.
4. **Köçürmə / süni zəka qorunması (imtahan rejimi):**
   - Sual sahəsi üçün CSS: `user-select:none; -webkit-user-select:none; -webkit-touch-callout:none; -webkit-tap-highlight-color:transparent` — KaTeX, `img` (`pointer-events:none` şəkildə, `draggable=false`), `.q-opt` daxil. `contextmenu`, `selectionchange` (seçim yaranarsa `getSelection().removeAllRanges()`), `touchstart` uzun basma (>450 ms, input/textarea xaricində) — `preventDefault` passive:false ilə yalnız sual sahəsində (skrol pozulmasın — test et).
   - `beforeprint` / Ctrl+P blok (var), `PrintScreen` açarı — `navigator.clipboard.writeText('')` cəhdi.
   - **Fokus itkisi qeydi:** `visibilitychange→hidden`, `window.blur` (Gemini/assistent pəncərəsi, «Circle to Search», başqa tətbiq) — hər hadisə sayılır və serverə `POST /api/portal/tasks/{id}/focus` `{n, ms}` (cəhdə yazılır: `TaskAttempt`-də JSON sahəsi varsa ora, yoxdursa yeni nullable `focus_log JSON` sütunu). Qayıdanda şagirdə xəbərdarlıq: «Testdən çıxdınız (N dəfə). Müəllim bunu görür.» Tam ekrandan çıxışlar da eyni sayğaca.
   - Müəllimə: nəticə cədvəlində / sınaq jurnalında sətirdə nişan «⚠ N dəfə çıxıb (cəmi M san.)».
   - **Dürüst qeyd (UI-də kiçik izah, müəllimə):** Android-in sistem assistenti (Gemini, «Circle to Search» — naviqasiya zolağını basıb saxlamaq) brauzerdən tam bağlana bilməz; sistem bunu **qeyd edir və müəllimə göstərir**.
5. Bütün yeni mətnlər AZ/EN/RU (`t()`, i18n.ts sonuna, təkrar açar yox — əvvəl grep). Server mesajları şagirdə görünürsə — EN/RU.

## Testlər
- resend: seçilən şagirdə yeni tapşırıq, köhnə qalır, başqa şagird görmür, başqa müəllim 403/404, KSQ-da 400.
- focus: POST sayğacı artırır, başqa şagirdin cəhdinə 404, təhvildən sonra qəbul edilmir (və ya sayılmır); müəllim siyahısında `focus` sahəsi.
- Frontend: `npm run build`. Mövcud pytest (portal, tasks, exams) keçməlidir.

## Toxunma
`exam_series.py`, `_can_review`/`show_answers` (paralel iş), KSQ skan, apelyasiya, cərimə qaydası.

## Cavab formatı
docs/agent-sistemi-promtu.md §7 (rusca): fayllar, miqrasiya, i18n açarları, pytest, build, açıq suallar.

## Əlavə 6: Sınaqda apelyasiya (istifadəçi: «а также возможность апелляции»)
### Tapıntı
`ExamAppeal` (models.py:537) yalnız `exam_id` (KSQ/BSQ) üçündür; onlayn sınaqda (`OnlineTask kind='sinaq'`) apelyasiya yoxdur.
### Qərarlar
- Yeni cədvəl `task_appeals` (eyni miqrasiyada): `id, task_id (FK online_tasks CASCADE, index), student_id (FK students CASCADE), q_index, bank_id, q (JSON snapshot: text/options/answer/explanation — ExamAppeal.bank_ref['q'] üslubu), my_answer, correct_at_time, reason (Text, 5–1000 simvol), status open|accepted|rejected, teacher_reply, decided_by, decided_at, created_at`; unikal (task_id, student_id, q_index).
- Şagird: `POST /api/portal/tasks/{id}/appeals {q_index, reason}` — yalnız təhvil vermiş, `kind='sinaq'`, şagird sualın nəticəsini görə bildikdə (`_can_review` True — müəllim cavabları göndərəndən sonra) və **7 gün** ərzində (review açılandan); bir sual — bir apelyasiya. Şagird review ekranında sualın altında «Apelyasiya ver» (mətn sahəsi + göndər), sonra status nişanı və müəllimin cavabı. `_can_review` funksiyasını **çağır**, dəyişmə.
- Müəllim: `GET /api/exam-appeals/inbox` cavabına sınaq apelyasiyaları da əlavə (`kind:'sinaq'`, `task_id`, sinif, şagird, sual snapshot, şagirdin cavabı, açar, səbəb) — mövcud `/appeals` səhifəsi və `AppealCard` eyni kartla göstərsin (sınaq nişanı). `open-count` sayğacına da daxil.
- Qərar: `PUT /api/task-appeals/{id}` `{status, teacher_reply, apply_all?: bool}` — rədd yalnız cavabla (KSQ qaydası kimi). **Qəbul** → `TaskAttempt.manual[str(q_index)] = True` və cəhdin balı yenidən hesablanır (mövcud `finalize`/düz say məntiqi ilə; KSQ şkalası yox). `apply_all=True` → eyni `TestBatch`-in bütün cəhdlərində həmin sual (eyni `bank_id`, yoxdursa eyni q_index) hamıya düz sayılır (açar səhv olanda). Şagirdə bildiriş varsa — qərar haqqında (AZ/EN/RU).
- Testlər: icazə (təhvilsiz/görə bilməyəndə 403, 7 gündən sonra 400, təkrar 409), inbox-da görünmə, qəbul → bal artır, apply_all → hamıda, rədd cavabsız 400, başqa müəllim 404.
