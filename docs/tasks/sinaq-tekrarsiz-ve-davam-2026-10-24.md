# Tapşırıq: Sinif üçün sınaq təkrarı olmasın (seriyalar daxil) + «Sinif davam etsin» səhvi
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)   İcraçı: `kodcu` (worktree)
- İstifadəçi: «reestrdə siniflər üçün təkrar olmasın peşəkar promt hazırla (seriya sınaqlarında da); bir də «Sinif davam etsin» vuranda köhnə testlər bitir. Bu səhvi aradan qaldır.»

## A. Təkrarsızlıq — şagird eyni sınağı iki dəfə almasın
### İndiki vəziyyət (kodda yoxlanıb)
- `api/exam_series.py` `_given_to` / `exams_online.given_files` təkrarı **dərs (ta_id) üzrə** yoxlayır. Sinif və onun qrupu (`SchoolClass.parent_id`, məs. «X b» və «X b (riyaziyyat qrupu)») ayrı dərslərdir → qrupdakı şagird eyni sınağı iki dəfə alır. Canlıda 24.10: seriya 11 (X b) və 12 (X b qrupu) eyni 2 faylı (1906, 1765) göndərdi; seriya 11 əl ilə dayandırıldı.
- Eyni sınaq bankda iki fayl kimi ola bilər (fərqli ad, eyni suallar) — `check-sinaqlar` «repeat» tapır (məs. sim-10-buraxilis q2 = hedef-9-buraxilis q6), tətbiq bunu bilmir.
- Seriyalar arasında (bir şagird iki seriyanın hədəfindədir) yoxlama yoxdur.
### Qərarlar
1. **Şagird səviyyəsində «verilib»** — bir funksiya `domain/given.py: given_students(db, file_ids, student_ids) -> {file_id: set(student_id)}`: şagirdin aid olduğu **bütün** dərslərdə (sinif + qrup + fərdi), `kind='sinaq'` tapşırıqlarında `questions[*].bank_id`-lərindən fayla qayıdır (və ya mövcud `given_files` mexanizmi ilə — yenidən yazma, genişləndir). Arxivlənmiş tapşırıq da sayılır. «(təkrar)» — müəllimin bilərəkdən yenidən göndərməsi — sayılır, amma bloklamır.
2. **Məzmun təkrarı:** iki bank faylı **eyni sayılır**, əgər sualların ≥ 80%-i eynidir (normallaşdırılmış mətn heşi: kiçik hərf, boşluq, LaTeX boşluqları, variant sırası nəzərə alınmır). `BankFile`-ə miqrasiyasız: hesab gecəlik (`scheduler`) və ya bank sinxronundan sonra keşlənir (`services`-də mövcud keş üslubu; yoxdursa yaddaşda `lru_cache` + fayl id-ləri dəyişəndə sıfırlanır). `same_as(file_id) -> set(file_id)`.
3. **Seriya (`_send`, `_sync_new`, `series_out`, `auto-all` növbəsi):** fayl (və onun «eyni» faylları) şagirdə artıq verilibsə — **həmin şagird `student_ids`-dən çıxarılır**; sinifdə heç kim qalmırsa — sinif atlanır; heç bir sinifdə heç kim qalmırsa — fayl atlanır (sayılmır, növbəti götürülür). Qrup + ana sinif eyni seriyada/iki seriyada olsa da şagird bir dəfə alır. Önbaxışda «N şagird artıq yazıb — onlara getməyəcək».
4. **Əl ilə yaratma (`exams_online` create):** mövcud təkrar xəbərdarlığı (409 + allow_repeat) şagird səviyyəsinə və «eyni məzmun»a genişlənir: «Bu sınaq (və ya eyni sualları olan «…») X b qrupunun 12 şagirdinə artıq verilib». `allow_repeat=True` — müəllim təsdiqi ilə göndərilir (indiki kimi).
5. **HUB reyestri** (`scripts/reestr.cjs`) dəyişmir — o PDF səviyyəsindədir; bu kart tətbiqin bankı/sinifləri üçündür.
### Testlər
- Qrup + ana sinif: iki seriya → şagird faylı bir dəfə alır; qrupda olmayan sinif şagirdi alır.
- Məzmun eyni iki fayl: biri verilib → ikincisi seriyada atlanır; 70% eyni → atlanmır.
- Əl ilə yaratma: şagird səviyyəsində 409, allow_repeat ilə keçir.
- Mövcud `test_exam_series*`, `test_api_exam*` keçməlidir.

## B. «Sinif davam etsin» köhnə/bitmiş cəhdləri açıb yenidən bitirir
### Tapıntı (`api/tasks.py:667-679`, `_resume` 647-664)
- `resume_all` **təhvil vermiş hər şagirdi** (`a.submitted_at`) yenidən açır — normal bitirənlər də; nəticələri silinir (`correct/total/grade/points=None`, jurnal qiyməti `Mark` silinir).
- Müddətli test bağlanıbsa (`closes_at` keçib) və ya müddətsiz testdə `a.deadline = t.closes_at` keçmişdədirsə — açılan cəhd dərhal `expire_due` ilə yenidən avtomatik təhvil olur («köhnə testlər bitir»), nəticə «0 / boş» kimi yenidən hesablanır.
### Qərarlar
6. `resume_all` yalnız **təsadüfən kəsilənləri** açır: `auto_submitted=True` (vaxt bitib) **və ya** təhvil verilməyib + deadline keçib. Özü «Təhvil ver» basanlar (`auto_submitted=False`) açılmır. Cavab `{resumed, skipped_submitted}`; UI tostu: «Davam edə bilən şagird: N (özü təhvil verən M şagird toxunulmadı)».
7. `_resume`: yeni deadline **keçmişdə ola bilməz** — müddətsiz testdə `max(closes_at, now + qalan/10 dəq)`, müddətli testdə tapşırıq `closes_at` keçibsə yalnız bu cəhd üçün `deadline = now + minutes` (tapşırığın `closes_at`-ı dəyişmir) və portal start/save/submit bu cəhdi `a.deadline`-a görə qəbul edir (`closes_at`-a görə rədd etmir). `expire_due` — yalnız `a.deadline <= now`.
8. Nəticə **dərhal silinmir**: köhnə nəticə (`correct/total/points/grade`) və jurnal qiyməti şagird yenidən təhvil verənə qədər saxlanır (yeni sütun lazım deyil — mövcud dəyərlər qalır, təhvildə yenilənir; `Mark` yalnız yeni təhvildə yenilənir). Əgər bu, mövcud hesabatlarda «yazır» statusu ilə ziddiyyət yaradırsa — status «davam edir» kimi göstərilsin.
9. Fərdi «▶ Davam etsin» (`resume_attempt`) — müəllim bilərəkdən seçir, ona görə özü təhvil verən şagird üçün də işləyir, amma 7–8 qaydaları ona da tətbiq olunur.
### Testlər
- resume_all: özü təhvil verən açılmır; vaxtı bitən açılır; bağlanmış müddətli testdə açılan cəhd dərhal bitmir (expire_due-dan sonra hələ açıqdır); müddətsiz testdə deadline gələcəkdədir; köhnə bal təhvilə qədər saxlanır.

## Ümumi
AZ/EN/RU (`t()`), i18n.ts sonuna, təkrar açar yox. Miqrasiya lazım olarsa — `down_revision='f1c5a9d3e7b4'`. `npm run build` + aid pytest. Canlı DB-yə toxunma, push etmə. Cavab: §7 rusca.

## Əlavə (istifadəçi, 24.10): «silinənlər varsa 30 baldan yuxarı geri qaytar; sınaq seriyası ancaq siniflər üçün olsun, X b riyaziyyat qrupu üçün olmasın»
10. **Bərpa (canlı, bir dəfəlik):** admin endpoint `POST /api/admin/restore-resumed` `{dry_run: bool=True, min_points: float=30, since?: date}`: audit jurnalında `resume_all` (və `resume_minutes`) qeydləri olan tapşırıqlarda **hazırda təhvil verilməmiş, cavabları olan** cəhdlər üçün balı saxlanmış cavablardan hesabla (mövcud `finalize`/`score` ilə, yazmadan); bal > `min_points` (100 ballıq `points`, yoxdursa faiz) → `finalize(auto=False)` ilə bərpa et, `submitted_at` = audit qeydindən əvvəlki təhvil vaxtı (bilinmirsə — `started_at + duration` və ya resume vaxtı), jurnal qiyməti əvvəl avtomatik yaranırdısa — eyni yolla yenidən. ≤ 30 olanlar açıq qalır (şagird davam edə bilər). Cavab: siyahı `[{task, sinif, şagird, bal, action: restore|keep_open}]`. Yalnız admin; audit. Test: dry_run yazmır; 30-dan yuxarı bərpa, aşağı açıq qalır.
11. **Seriya yalnız siniflər üçün:** `auto-all` qrup dərslərini (`SchoolClass.parent_id` olan sinif) **daxil etmir**; seriya formasında qrup seçiləndə xəbərdarlıq «Qrup üçün seriya tövsiyə olunmur — şagirdlər ana sinifdən alır». (Canlıda Rəhbər «X b (riyaziyyat qrupu)» seriyasını dayandırdı, «X b» açıldı.)
