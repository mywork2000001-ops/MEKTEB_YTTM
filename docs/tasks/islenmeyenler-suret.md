# Kart: işlənməyənlər / matris hesabatlarının sürəti (P1, canlıda > 60 san.)

**Fakt (20.10.2026, canlı, deploy 390444a):** `/api/results-center/missing-all?format=json` 60+ san. cavab vermir; bu vaxt `/api/my/lessons` 6,8 san.
(server bloklanır). Ana səhifə `missing-summary` eyni yolu işlədir. Neon uzaq DB – hər sorğu ~10–30 ms, N+1 sorğular dəqiqələrə çevrilir.
**İcraçı:** `kodcu` (worktree). Canlı DB / deploy / push – YOX. Nəticə (saylar, statuslar) DƏYİŞMƏMƏLİDİR – yalnız sürət.

## Ehtimal olunan səbəblər (kodda yoxla, ölç)
1. `test_stats._visible_tasks(kind='sinaq')` `ta_ids` verilsə də məktəbin BÜTÜN sınaq tapşırıqlarını götürür, hər batch üçün `_access`;
   `collect` sonra bütün sətirləri qurur, `class_matrix` yalnız `r['ta_id'] == ta.id`-ni saxlayır. `missing-all` hər dərs üçün bunu təkrarlayır → N × bütün məktəb.
2. `collect` / `class_matrix` / `class_missing` dövrlərində `db.get(PlanLesson|OnlineTask|TestBatch|TeachingAssignment, …)` – N+1.
3. `unit_tasks`, `_roots` (AuditLog), `exam_published`, attempts – hər test/şagird üçün ayrıca sorğu.

## Addımlar
1. **Ölçmə əvvəl:** test fixture-də (≥ 3 dərs, ≥ 10 test, sınaq batch-ləri başqa siniflərdə də) SQLAlchemy `before_cursor_execute` sayğacı ilə
   `class_missing` (1 dərs) və `missing_all_api` json üçün sorğu sayını yaz (hesabatda «əvvəl/sonra»).
2. `ta_ids` verildikdə sınaq tapşırıqları SQL səviyyəsində `assignment_id IN ta_ids` ilə süzülsün (`_access` yalnız qalan batch-lərə).
3. Toplu yükləmə: PlanLesson, OnlineTask, TestBatch, TaskAttempt, ExamScore – `IN (...)` ilə bir dəfə, lüğətdən oxu; `_roots` üçün AuditLog bir sorğu.
4. `missing-all` / `missing-summary`: dərslər üzrə ortaq məlumatı bir dəfə topla (məs. `collect` bütün `ta_ids` üçün bir dəfə, sonra dərslərə böl),
   `class_missing`-ə əvvəlcədən hesablanmış matris ötürmək imkanı (parametr), məntiq təkrarlanmasın.
5. Hədəf: 1 dərs `class_missing` ≤ 40 sorğu; `missing-all` sorğu sayı dərs sayına xətti, ≤ 40 × dərs. Testdə assert et (yuxarı həd).
6. Mövcud testlər dəyişmədən keçməlidir: `test_missing_report.py test_missing_list.py test_unlimited_tests.py test_class_matrix.py
   test_student_report.py test_api_results_center.py test_api_exams_online.py test_copy_unlimited_participation.py test_exam_series.py`.

## Yoxlama
`cd backend && PYTHONIOENCODING=utf-8 <venv python> -m pytest -q <yuxarıdakılar> tests/test_missing_perf.py`; backend-only – build lazım deyil
(frontend toxunularsa `npm run build`). Hesabat: sorğu sayı əvvəl/sonra (1 dərs, bütün dərslər), commit, test sayı, edilməyənlər.
