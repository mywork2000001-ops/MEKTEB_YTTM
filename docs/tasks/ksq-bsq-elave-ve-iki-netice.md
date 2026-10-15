# Tapşırıq: Əlavə KSQ/BSQ, onlayn + yazılı nəticə yanaşı, müəllimin seçdiyi qiymət, şagirdə cavab kartı, sualın bank ünvanı və apelyasiya
- Tarix: 2026-10-15   Müəllif: Rəhbər (Claude)
- İcraçı: claude-ds pro (kod) → claude-ds flash (EN/RU lüğət yoxlaması)
- Budaq: qwen/ksq-bsq-elave-iki-netice
- Gözlənilən xərc: ≈ 1,5–2 $ (4 mərhələ, hər biri ayrıca commit)
- ⚠️ Miqrasiya var → canlı Neon DB-yə tətbiqini **Rəhbər** edir, icraçı yalnız alembic faylını yazır.

## Məqsəd (müəllimin dili ilə)
1. Müəllim plandakı KSQ/BSQ-dən əlavə **əlavə KSQ və əlavə BSQ** yarada bilsin (məs. buraxan, zəif yazan və ya qiymətini yaxşılaşdırmaq istəyən şagirdlər üçün).
2. Şagird eyni KSQ/BSQ-ni **həm onlayn, həm kağızda** yazıbsa, hər iki nəticə **yanaşı saxlanılsın** (biri digərini silməsin);
   müəllim jurnala gedəcək qiyməti özü seçsin: onlayn / yazılı / ən yüksək / əl ilə.
3. İmtahandan sonra hər şagird öz **cavab kartını** görsün (portalda və çapda): sual, öz cavabı, düzgün cavab, bal.

## Mövcud vəziyyət (yoxlanılıb)
- `backend/app/models.py:432` `Exam` – `UniqueConstraint(assignment_id, kind, semester, no)`; `kind` = KSQ|BSQ.
- `backend/app/api/exams.py:81` `_check_exam` – BSQ yarımildə **yalnız 1**, nömrəsi = yarımil; `ExamIn.no ≤ 20`.
- `backend/app/models.py:475` `ExamScan` – `UniqueConstraint(exam_id, student_id)` → onlayn və kağız oxunuşu **eyni sətirə** düşür, köhnəsi `history`-yə gedir.
- `backend/app/models.py:499` `ExamScore` – şagird başına **1 bal**; `exam_scans.py:59` və `exams.py:203` onu üstələyir.
- `ksq_online.py:133` `send` – yenidən göndərəndə köhnə onlayn cəhd **silinir**.
- `exams.py:240` yarımil qiyməti: `(KSQ cəmi/sayı)×0,4 + BSQ×0,6` (`semester_grade`).
- Kağız cavab kartı artıq var: `domain/ksq_card.py`, oxuma `domain/ksq_reader.py`, `domain/ksq_scan.py`.

## Nə etmək lazımdır

### Mərhələ 1 — Əlavə KSQ/BSQ (commit 1)
1. `models.py` `Exam`: yeni sahələr
   - `extra_of: int | None` → FK `exams.id` (ondelete SET NULL) – hansı imtahanın əlavəsidir;
   - `extra_students: list[int] | None` (JSON) – yalnız seçilən şagirdlər üçün (None = bütün sinif).
   - Unikal məhdudiyyəti dəyiş: `(assignment_id, kind, semester, no, extra_of)` əvəzinə sadə yol – əlavələrə `no` ardıcıl verilir (`no` əsas imtahanınkı ilə eyni, `extra_seq` 1,2,… yeni sahə) → `UniqueConstraint(assignment_id, kind, semester, no, extra_seq)`, əsasda `extra_seq = 0`.
2. Alembic miqrasiyası `backend/alembic/versions/<yeni>.py`: sahələr + köhnə constraint drop / yenisi create; mövcud sətirlərdə `extra_seq = 0`. Downgrade da yazılsın.
3. `exams.py` `ExamIn`: `extra_of: int | None`, `extra_students: list[int] | None`. `_check_exam`:
   - `extra_of` varsa: əsas imtahan eyni `ta`, eyni `kind`, eyni yarımil olmalıdır; BSQ üçün «1 BSQ» qaydası yalnız **əsas** BSQ-yə aiddir; tarix əsasdan **sonra** olmalıdır;
   - `extra_students` bu sinfin şagirdləri olmalıdır.
   - `create_exam` – `extra_seq = max(mövcud)+1`.
4. Yarımil qiyməti (`exams.py:240` ətrafı və `semester_grade`): əlavə imtahan **ayrıca KSQ kimi sayılmır** – şagirdin əsas imtahan üzrə qiyməti = müəllimin seçdiyi nəticə (Mərhələ 2), əlavədə yazıbsa əlavənin qiyməti də seçim siyahısına düşür. Buraxıb əlavədə yazana – əlavənin qiyməti.
5. Variantlar, kağız kartı, onlayn göndərmə əlavə imtahanda da işləsin (`roster` yerinə `extra_students` filtri – bir köməkçi funksiya `exam_roster(db, ta, e)` yaz və `exams.py`, `ksq_online.py`, `exam_scans.py`-də istifadə et).
6. Frontend `pages/teacher/Exams.tsx`: imtahan kartında «➕ Əlavə KSQ» / «➕ Əlavə BSQ» düyməsi → tarix + şagird seçimi (çek-boks, «buraxanlar», «2 alanlar», «hamısı» sürətli seçim). Siyahıda adı: `KSQ-2 · əlavə 1`.

### Mərhələ 2 — Onlayn və yazılı nəticə yanaşı (commit 2)
1. `models.py` `ExamScan`: `source: str` (`paper` | `online`), constraint → `UniqueConstraint(exam_id, student_id, source)`. Miqrasiya: mövcud sətirlər `read_by == 'online'`/onlayn cəhddən gəlibsə `online`, qalanı `paper` (icraçı əvvəlcə kodda onlayn nəticənin `ExamScan`-a necə yazıldığını tapıb kartın sonunda yazsın).
2. `models.py` `ExamScore`: `chosen: str` (`online` | `paper` | `max` | `manual`, default `max`), `points` = jurnala gedən yekun bal (köhnə məntiq dəyişmir – digər modullar `points` oxuyur).
   Yekun bal hesablayan bir funksiya: `recompute_score(db, e, student_id)` – seçimə görə `points/item_marks` doldurur; `manual` olanda toxunmur.
3. `exam_scans.py:59` və onlayn təhvil yeri: `ExamScore`-u birbaşa üstələmək əvəzinə öz `source`-lu `ExamScan`-ı yazıb `recompute_score` çağırsın.
4. `ksq_online.py` `send` (resend): onlayn cəhd silinsə də, onlayn `ExamScan` nəticəsi `history`-də saxlanılsın; kağız nəticəyə **heç vaxt** toxunulmasın.
5. Yeni endpoint: `PUT /exams/{ta_id}/{exam_id}/choice/{student_id}` body `{chosen, points?}` – audit yazılsın (`audit(db,user,'update','exam_choice',…)`).
   Hamı üçün birdən: `PUT /exams/{ta_id}/{exam_id}/choice` body `{chosen}` («hamıya: ən yüksək»).
6. `exam_result` cavabına hər şagird üçün `online: {points, grade}`, `paper: {points, grade}`, `chosen` əlavə et.
7. Frontend `Exams.tsx` nəticə cədvəli: sütunlar **«Onlayn» | «Yazılı» | «Jurnala»**; «Jurnala» xanasında seçim (Onlayn / Yazılı / Ən yüksək / Əl ilə). İki nəticə fərqlidirsə (≥ 1 qiymət fərqi) sarı nişan «⚠ fərq» – köçürmə şübhəsi ilə əlaqəli ola bilər.
8. Jurnal (`api/journal.py`) yalnız `ExamScore.points`-i oxumağa davam edir – dəyişiklik lazım deyil, yoxla.

### Mərhələ 3 — Şagirdə cavab kartı (commit 3)
1. `api/portal.py`: `GET /portal/exams/{exam_id}/card` – yalnız öz kartı, yalnız müəllim **«Nəticəni şagirdlərə göstər»** etdikdən sonra (yeni `Exam.results_published_at: datetime | None`, eyni miqrasiyaya). Cavab: hər sual üçün `{n, text(ml), my_answer, correct, points, earned}`, hər mənbə üçün ayrıca (onlayn / yazılı), və jurnala gedən yekun.
   Kağızda «lost» (`ExamScan.lost`) suallar «sayılmadı» kimi göstərilsin.
2. `Exams.tsx`: «📤 Nəticələri şagirdlərə göndər» / «geri al» düyməsi; «🖨 Cavab kartlarını çap et» – hər şagirdə 1 səhifə (ad, variant, cədvəl, bal, qiymət). Çap komponenti mövcud çap üslubunu (`variants/print`) təkrarlasın.
3. Şagird portalı `pages/student/Results.tsx`: KSQ/BSQ sətirində «Cavab kartı» düyməsi → modal: ✓/✗ cədvəli, düzgün cavab, izah varsa `ml(x.explanation)`. Variantın sualları **imtahandan əvvəl** heç vaxt göstərilmir (yalnız `results_published_at` sonrası).

### Mərhələ 4 — Sualın bank ünvanı və apelyasiya (commit 4)
Məqsəd: şagird konkret sual üzrə apelyasiya verəndə müəllim axtarmasın – sualın bankdakı yeri dərhal görünsün.
1. **Bank ünvanı** – `ExamVariant.questions[*].bank_id` artıq var (`models.py:446`). Köməkçi `bank_ref(db, bank_id)` →
   `{file_id, label (BankFile.label = altmövzu), n (BankQuestion.n), qid, ref}`; `ref` qısa kod: `«<altmövzu> · №<n>»` + texniki `B<bank_id>`.
   Şablon (`template`) suallarında: `«<altmövzu> · şablon <template> · №<n>»`.
   - Variant yaradılanda `ref` dondurulmuş surətə yazılsın (bank sonra dəyişsə də apelyasiyada köhnə ünvan qalsın); köhnə variantlar üçün oxuyanda hesablansın.
   - Göstərilən yerlər: müəllimin variant/nəticə ekranı (`Exams.tsx`), cavab kartı (portal + çap), müəllimin çap variantında kiçik şriftlə sual altında
     (**yalnız müəllim nüsxəsində**, şagird vərəqində yox – mövzu adı ipucu olmasın).
2. **Model** `ExamAppeal` (yeni cədvəl, eyni miqrasiyaya):
   `id, exam_id, student_id, slot, source (paper|online), bank_id, bank_ref (JSON snapshot), my_answer, correct_at_time, reason (Text ≤ 1000),
   status (open|accepted|rejected), teacher_reply, apply_all (bool), decided_by, decided_at, created_at`;
   `UniqueConstraint(exam_id, student_id, slot, source)` – bir sual üzrə bir apelyasiya.
3. **Şagird** (`portal.py` + `Results.tsx` cavab kartı): hər ✗ (və ✓) sətirdə «⚖ Apelyasiya» düyməsi → səbəb mətni → göndər.
   Müddət: nəticə göndəriləndən **3 gün** (`Exam.appeal_until`, müəllim dəyişə bilər). Status şagirddə görünür: gözləyir / qəbul / rədd + müəllimin cavabı.
4. **Müəllim** (`exams.py` endpointlər + `Exams.tsx` «⚖ Apelyasiyalar (N)» paneli, ana səhifədə nişan):
   hər apelyasiyada – şagird, sual mətni, şəkil, şagirdin cavabı, açar, **bank ünvanı (keçid: bankda bu sual)**, kağızdırsa skan kəsiyi (`crop_key`).
   Qərar:
   - «✓ Qəbul» → həmin slot bu şagird üçün düz sayılır, `recompute_score` (Mərhələ 2); «Əl ilə» seçilmiş bal yenə toxunulmaz – müəllimə xəbərdarlıq.
   - «✓ Qəbul + hamıya tətbiq et» (açar səhv idisə) → bu `bank_id`-li sualı alan **bütün** şagirdlərdə eyni cavab düz sayılır, ballar yenidən hesablanır;
     `BankQuestion` «yoxlanmalı» işarələnir (bankı müəllim/admin düzəldir – avtomatik dəyişmə yox).
   - «✗ Rədd» → cavab mətni məcburi.
   Hər qərar `audit(...,'exam_appeal',...)` – köhnə→yeni bal.
5. Testlər (`test_exam_extra_and_choice.py`-yə əlavə və ya `test_exam_appeal.py`): müddətdən sonra 400; təkrar apelyasiya 409; başqasının imtahanı 403;
   «hamıya tətbiq» 2 şagirdin balını dəyişir, sualı almayan şagirdə toxunmur; bank ünvanı variant surətində qalır.

## Toxunma (dəyişmə)
- `domain/ksq_reader.py`, `domain/ksq_scan.py`-nin oxuma alqoritmi; `ksq_card.py`-nin kart tərtibatı (QR/zona) – yalnız çağırış yerləri.
- `docs/` qaydaları, `frontend/src/i18n.ts`-də mövcud açarlar (yalnız yeni açar əlavə et, faylı tam oxuma – Grep).
- Canlı DB – miqrasiyanı icraçı işlətmir.

## Kontekst (yalnız bunları oxu)
- `backend/app/models.py:432-541` – Exam, ExamVariant, ExamScan, ExamScore
- `backend/app/api/exams.py:25-131, 186-280` – ExamIn, _check_exam, create, save_scores, yarımil qiyməti
- `backend/app/api/exam_scans.py:40-80` – skandan bala yazma
- `backend/app/api/ksq_online.py:96-200` – onlayn göndərmə/ləğv və təhvil
- `backend/app/api/portal.py:280-310` – şagirdə KSQ göstərilməsi
- `docs/ksq-bsq-kagiz-promtu.md`, `docs/ksq-skan-ekran-ve-onlayn-promtu.md` – mövcud qaydalar

## Qəbul meyarları
- [ ] Müəllim KSQ-2 üçün «əlavə 1» yaradır, yalnız seçdiyi 3 şagirdə variant/kart/onlayn göndərilir; digərlərinin qiyməti dəyişmir.
- [ ] Yarımildə əsas BSQ + əlavə BSQ mümkündür; ikinci **əsas** BSQ yenə 409 verir.
- [ ] Şagird onlayn 70, kağızda 85 yazıb → cədvəldə hər ikisi görünür; «Ən yüksək» → jurnala 85; «Onlayn» seçiləndə 70; kağızı yenidən skan etmək onlayn nəticəni silmir və əksinə.
- [ ] «Əl ilə» seçilmiş bal sonrakı skan/onlayn təhvildə üstələnmir.
- [ ] Yarımil qiyməti formulu dəyişməyib; əlavə imtahan KSQ sayını artırmır.
- [ ] Şagird yalnız nəticə göndəriləndən sonra öz cavab kartını görür, başqasınınkını görə bilmir (403 testi).
- [ ] Çap: hər şagird 1 səhifə, ad + bal + ✓/✗.
- [ ] Hər sualın yanında «altmövzu · №n» görünür (müəllim ekranı, cavab kartı); şagirdin imtahan vərəqində görünmür.
- [ ] Şagird ✗ sual üzrə apelyasiya verir → müəllim panelində sual + bank ünvanı + skan kəsiyi bir yerdə; qəbul → bal dərhal yenilənir.
- [ ] «Hamıya tətbiq et» eyni bank sualını alan bütün şagirdlərin balını düzəldir, bank sualı «yoxlanmalı» olur.
- [ ] Bütün yeni mətnlər AZ/EN/RU (`t()` / `ml()`), server xətaları şagirdə görünənlər EN/RU ilə; jurnal çapı yalnız AZ.
- [ ] `npm run build` (frontend) ok.
- [ ] pytest: `backend/tests/test_exams*.py backend/tests/test_ksq_online*.py backend/tests/test_exam_scans*.py` ok + **yeni** `backend/tests/test_exam_extra_and_choice.py` (əlavə imtahan, iki mənbə, seçim, manual qorunması, portal 403).
- [ ] Alembic: `alembic upgrade head` və `downgrade -1` lokal SQLite/test DB-də ok.

## Mənim əlavələrim (Rəhbər təklifi – kartda daxildir)
- «⚠ fərq» nişanı: onlayn və kağız qiyməti fərqlidirsə – köçürmə şübhəsinə ipucu.
- Sürətli seçim düymələri əlavə imtahan üçün: «buraxanlar», «2 alanlar».
- «Əl ilə» bal qorunur, hər seçim auditə yazılır (kim, nə vaxt, köhnə→yeni).
- Cavab kartı yalnız müəllim «göndər» deyəndən sonra – variantlar sızmasın.
- Apelyasiya müddəti (3 gün), bir sual – bir apelyasiya; səhv açar tapılanda «hamıya tətbiq et» + bank sualı «yoxlanmalı».
- Bank ünvanı variantda dondurulur – bank sonra dəyişsə də apelyasiyada köhnə ünvan itmir.

## Cavab formatı
docs/agent-sistemi-promtu.md §7 – hər mərhələdən sonra: dəyişən fayllar, test çıxışının son 15 sətri, miqrasiya faylının adı, açıq suallar.
