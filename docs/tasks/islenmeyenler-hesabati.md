# Kart: işlənməyənlər – peşəkar hesabat (promt: `docs/islenmeyenler-hesabati-promtu.md`)

**İcraçı:** `kodcu` (worktree). Canlı DB, deploy, push, miqrasiya – YOX. CLAUDE.md qaydaları (AZ/EN/RU, `npm run build`).
Promtun §2 (metodika) və §3 (H1–H4) – qəbul meyarlarıdır; burada yalnız texniki yol.

## Backend
1. `backend/app/student_report.py`:
   - `class_missing` genişlənir (geriyə uyğun – köhnə sahələr qalır): hər şagirdə `assigned`, `done`, `missed` (yazmayıb),
     `pending` (gözlənilir), `rate` (%; məxrəc 0 → None), `streak` (ardıcıl buraxma), `risk` ('critical'|'attention'|'ok'),
     `advice_key`; zirvədə `summary` (students_total, tests, avg_rate, full, critical, attention) və `tests` (test üzrə: key, date, title, no,
     assigned, done, rate, missed). `MISSING_RISK = {'critical': 50, 'attention': 80, 'streak': 3}`.
   - **Təkrarsızlıq:** `class_matrix` sütunlarında «Yenidən göndər» surətləri (mövcud təkrar göndəriş qruplaşdırması – `tasks.py`
     / hazır test-sınaq ayırma kodunda axtar) bir məntiqi testə birləşir; şagird hər hansı variantı işləyibsə – işləyib.
     Şagird sətri `student_id` üzrə unikal. Bunu test et (surət + orijinal → 1 sütun; iki dəfə roster → 1 sətir).
   - Hamısı (yalnız işlənməyənlər yox) şagirdlər `summary` üçün sayılır; `rows`-da defolt yalnız borcu olanlar, `all=1` – hamı.
   - `status` filtri: `only_missed=1` – gözlənilənlər çıxarılır.
2. `backend/app/missing_list_print.py` – yeni üslub (məktəb sənədi, A4, Times, səliqəli boz başlıq, risk rəngli nöqtə + mətn – ağ-qara çapda da oxunsun):
   `class_html` (H1: başlıq, göstəricilər paneli, Cədvəl 1, Cədvəl 2, şərti işarələr, imza), `class_xlsx` (iki vərəq: «Şagirdlər», «Testlər»),
   `students_html` (H2), yeni `all_classes_html` (H3), `share_text(m, lang, names)` (H4; names: full|short|none).
3. `backend/app/api/results_center.py`:
   - mövcud endpoint-lərə `only_missed`, `all` parametrləri;
   - yeni `GET /class/{ta}/missing-share?lang=az|en|ru&names=full|short|none` → `{text}`;
   - yeni `GET /missing-all?format=pdf&from&to&kind` → H3 (öz dərslərim).
   Dövr: `from/to` (frontend preset-ləri hesablayır).
4. Testlər `backend/tests/test_missing_report.py`: göstəricilər, risk hədləri, streak, surət birləşməsi, təkrarsız sətir, share_text (3 ad rejimi),
   H3 endpoint 200 + PDF başlığı; mövcud missing testləri keçməlidir.

## Frontend
1. `ClassMatrix.tsx` «İşlənməyənlər» rejimi → **hesabat paneli**: dövr preset düymələri (Bu həftə / Bu ay / Semestr / Aralıq),
   növ, «Gözlənilənləri də göstər»; göstərici kartları (orta icra %, kritik, diqqət, tam icra); şagird cədvəli (risk nişanı, icra % zolağı,
   işlənməyən testlər çipləri, tövsiyə); «Test üzrə» açılan bölmə; düymələr: «🖨 Sinif hesabatı (PDF)», «Excel», «Şagird vərəqələri (PDF)»,
   «📤 Qrupa göndər» (pəncərə: dil, ad rejimi + etik xatırlatma, mətn önbaxışı, «📋 Kopyala», «Paylaş» – `navigator.share` fayl ilə, yoxdursa yüklə).
2. Müəllim əsas səhifəsində / Nəticələr mərkəzində «Bütün siniflərim – xülasə (PDF)» düyməsi.
3. `StudentReport.tsx` – mövcud düymə H2-ni yükləyir (dəyişiklik yalnız lazım olsa).
4. Bütün yeni mətnlər `t()` + `i18n.ts` (AZ/EN/RU, Grep ilə, təkrar açar yox).

## Yoxlama
`backend/.venv/Scripts/python.exe -m pytest tests/test_missing_report.py tests/<mövcud missing/matrix testləri> -q 2>&1 | tail -5`;
`cd frontend && npm run build 2>&1 | tail -5` (node_modules yoxdursa – junction, sonra sil).
PDF nümunələri: test fixture-dan H1 və H2-ni `../_tmp_pdf/` (git-ə yox) qovluğuna yaz – Rəhbər baxacaq; yolları hesabata yaz.
Hesabat: budaq, commit, fayllar, test sayı, build, PDF yolları, edilməyənlər.

## Əlavə (promt §5 – məcburi)
- **Plan günü** (§5.1): `class_missing`-də hər test üçün `plan_date` (OnlineTask.plan_lesson_id → PlanLesson tarixi; fallback-lar promtda),
  şagird×test statusu `late_open` (plan günü keçib, yazmayıb) / `late_done` (+ `late_days`) / `on_time` / `not_due`. Defolt filtr – `late_open`.
  Göstəricilər: `rate_on_time`, `rate_total`. Sütun «Gecikmə (gün)». Testlər: plan günü fallback-ları, gecikmə günləri.
- **Tələb et** (§5.2): `POST /api/results-center/class/{ta}/missing-request` `{student_ids, task_keys?, message?, new_deadline?, reopen?}` →
  mövcud bildiriş mexanizmi ilə şagirdə bildiriş (dil – şagirdin dili, AZ/EN/RU şablon), `reopen` – bağlanmış testi `copy_task` məntiqi ilə
  yalnız həmin şagirdlərə; `missing_requests` cədvəlinə yaz. Hesabat sətrində `requests: {count, last}`. Testlər: bildiriş yaranır, reopen, tarixçə.
- **Araşdır** (§5.3): `GET /api/results-center/student/{sid}/missing-investigate?ta={ta}` → test üzrə faktlar (cəhd başlayıb/təhvil, vaxt,
  bildiriş/tələb, son giriş – mövcud sahə varsa, plan günündə davamiyyət); `PUT …/missing-note` `{task_key, student_id, reason, note}`
  (reason: excused|technical|no_device|forgot|refused|other). `excused` – məxrəcdən çıxır. Hesabatda səbəb sütunu + səbəblər xülasəsi.
- **Miqrasiya:** alembic – yalnız yeni cədvəllər `missing_notes`, `missing_requests` (mövcud cədvəllərə toxunma); testlərdə yaradılır.
- Frontend: sətirdə «📩 Tələb et», «🔍 Araşdır» (pəncərə: faktlar + səbəb seçimi + qeyd), toplu seçim checkbox-ları və «Tələb göndər».
