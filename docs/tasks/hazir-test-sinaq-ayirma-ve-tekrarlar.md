# Tapşırıq kartı: «Hazır test / sınaq» – mövzu testləri ilə sınaqları ayırmaq, təkrar göndərişləri birləşdirmək
**Tarix:** 19.10.2026 · **Sifarişçi:** müəllim · **Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree)
**Status:** icrada (istifadəçi: «promt hazırla, icra et, hesabat ver»)

## 0. Rol və qaydalar
Sən `kodcu`-san. `CLAUDE.md`: hər yeni UI mətni AZ/EN/RU (`t()`/`tt()`, `frontend/src/i18n.ts`, təkrar açar yox);
yoxlama – `npm run build` (frontend) + aid pytest. Miqrasiya YOXDUR. Canlı DB-yə toxunma. Worktree-də işlə, main-ə birləşdirmə.
**Toxunma:** `api/journal.py`, `api/exams.py`, `api/classes.py`, `api/students.py`, `api/programs.py`, `api/common.py`,
`frontend/src/api.ts` – onları paralel başqa icraçılar dəyişir.

## 1. Problem (canlı diaqnoz, 19.10.2026, yalnız oxu)
«Testlər və sınaqlar → Yazılı (kağız) iş → Yazılı iş yarat → Hazır test / sınaq» siyahısı (`PaperExams.tsx::Create`,
mənbə `GET /api/tasks/{ta}`, `api/tasks.py:299`) bir düz `<select>`-dir, açılma tarixinə görə sıralanır:
| Sinif | mövzu | sınaq | məşğələ (extra) | Təkrar |
|---|---|---|---|---|
| X b | 24 | 10 | 3 | mövzu №5 ×2; «OTK … №1 (IX sinif)» ×4 (eyni paket 18, yenidən göndəriş: 9, 2, 10 şagird, hamı) |
| X c | 16 | 10 | 3 | mövzu №1, №24, №25, №26 – hər biri ×2 |
| X e | 14 | 6 | 3 | №27 ×2 |
| XI a | 38 | 6 | – | №22 ×2, №23 ×3, №28 ×2 |
Nəticə: məktəb siniflərində 30–44 sətirlik siyahıda mövzu testləri, sınaqlar və məşğələ testləri bir-birinə qarışır;
eyni test «Yenidən göndər» (şagird alt-qrupuna) ilə bir neçə dəfə görünür – müəllim hansını seçəcəyini bilmir.
Əlavə: X b-də IX sinif sınağı (OTK IX) var – sinif rəqəmi uyğun deyil, bunu göstərmək lazımdır.
«Mövzu testləri» bölməsi (`/api/tasks/mine`) yalnız `movzu` göstərir – orada sınaq qarışmır, amma təkrar göndərişlər orada da ayrı-ayrı sətirdir.

## 2. Həll (Rəhbərin qərarları)
### 2.1 Ümumi «test qrupu» məntiqi (backend, bir yerdə – təkrar kod olmasın)
`backend/app/task_groups.py` (yeni): `group_tasks(tasks) -> list[Group]`.
- Qrup açarı: `kind == 'sinaq'` → `('sinaq', batch_id)` (batch_id yoxdursa – sual imzası);
  digərləri → `(kind, plan_lesson_id, sual imzası)`; sual imzası = sıralı `bank_id`-lər (yoxdursa – mətnin sha1-i) – yəni
  **eyni suallı** yenidən göndəriş = bir qrup; eyni mövzuya fərqli suallı test (məs. «mövzu testi» və «P0010 testi») – ayrı qalır.
- Qrup: `main_task_id` (student_ids = None olan ən erkən; yoxdursa – ən erkən), `task_ids`, `sends` (say), `students`
  ('all' və ya birləşmiş say), `submitted` (cəm), `first_opens_at`, `last_opens_at`, `title` (əsasın adı), `kind`, `seq`
  (plan dərsi №), `grade_hint` (başlıqdan «(IX sinif» və s. – sinif rəqəmi), `has_paper` (qrupun hər hansı tapşırığı üçün yazılı iş var).
- Testlər `backend/tests/test_task_groups.py`.

### 2.2 Yazılı iş üçün mənbə siyahısı
`GET /api/paper-exams/{ta}/sources` (yeni, `paper_exams.py`): `{movzu: [...], sinaq: [...], extra: [...]}` – hər biri qrup siyahısı;
`movzu` – plan № üzrə artan (№ yoxdursa – sonda, tarixə görə), `sinaq` – tarix azalan, `extra` – tarix azalan; arxivdəkilər yoxdur,
`ksq` yoxdur. `grade_mismatch: true` – `grade_hint` sinfin rəqəmindən (`class_grade`) fərqlidirsə.
`POST /api/paper-exams/{ta}` (`task_id` ilə): tapşırıq qrupdadırsa – **şagirdlər qrupun birləşməsi** (hər hansı göndəriş «hamı»dırsa – bütün
sinif), «artıq var» (409) yoxlaması qrupun bütün tapşırıqları üzrə; Exam.online_task_id = əsas tapşırıq. Kağız ↔ onlayn nəticə
müqayisəsi (`results`) qrupun bütün tapşırıqlarındakı cəhdləri nəzərə alsın (şagirdin təhvil verdiyi cəhd).

### 2.3 UI – `PaperExams.tsx::Create`
- «Hazır test / sınaq» rejimində əvvəl **Növ** seçimi (seq düymələri): «📝 Mövzu testləri (n)» · «🏆 Sınaqlar (n)» · «Məşğələ testləri (n)»
  (boş növ gizli). Defolt – mövzu testləri.
- Siyahı: mövzu – «№5 Çoxluq anlayışı…» (uzun ad 80 simvolda kəsilir, tam ad `title`-da); sınaq – ad + tarix.
  Təkrar göndəriş: «· 4 göndəriş» nişanı; `has_paper` – «· yazılı var» və seçilmir (disabled);
  `grade_mismatch` – «· IX sinif üçün» xəbərdarlığı.
- Axtarış sahəsi (≥ 10 sətir olanda): ad üzrə süzgəc.
- Seçilmiş qrupun altında qısa məlumat: «Şagirdlər: hamı / 21», «Təhvil: 14», «Tarix: 05.10 – 07.10».
- Bütün mətnlər AZ/EN/RU.

### 2.4 «Mövzu testləri» siyahısında təkrarlar (Tasks.tsx) – yalnız görünüş
`/api/tasks/mine` cavabına `group_key` və `group_sends` əlavə et (eyni `group_tasks` ilə). Siyahıda yenidən göndərişlər
əsas testin altında açılan sətir kimi («↳ yenidən göndəriş: 9 şagird, 07.10»); say nişanı «2 göndəriş». Mövcud əməliyyatlar
(izlə, paylaş, yenidən göndər, sil) hər göndəriş üçün əvvəlki kimi işləyir. Sıralama/filtr məntiqi dəyişmir.

## 3. Yoxlama
- pytest: `test_task_groups.py`, `test_paper_exams.py`, `test_viktorina_paper.py`, `test_scans_any.py`, tasks testləri (| tail -20).
- `npm run build` (| tail -15).
- Ssenari testi: eyni test 3 dəfə yenidən göndərilib (alt-qruplar) → mənbə siyahısında 1 qrup, `sends=3`, yazılı iş bütün birləşmiş şagirdlərə.

## 4. Hazırdır, əgər
- Yazılı iş pəncərəsində mövzu testləri, sınaqlar və məşğələ testləri ayrı seçilir; təkrar göndərişlər bir sətirdir.
- «Mövzu testləri» siyahısında yenidən göndərişlər əsas testin altında qruplanıb.
- Testlər yaşıl, build OK; commit worktree budağında (AZ mesaj + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
