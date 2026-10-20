# Kart: işlənməyən testlərin TAM siyahısı (audit: `docs/audit/hesabatlar-ve-islenmeyenler-audit-2026-10-20.md` §I)

**İcraçı:** `kodcu` (worktree). Canlı DB, deploy, push, miqrasiya – YOX. Tək mənbə `class_missing` qalır – yeni paralel hesablama yazma.
CLAUDE.md: hər yeni mətn AZ/EN/RU (`t()` + `i18n.ts`, təkrar açar yox), `npm run build`.

## Addımlar
1. **M1 – defolt hamısı:** `MissingReport.tsx` defolt `plan='all'`, gözlənilənlər GÖRÜNÜR (`only_missed=0`). Süzgəclər qalır, lakin
   yuxarıda sayğac: «Cəmi N · bağlanıb, yazılmayıb X · açıq (gözlənilir) Y · plan günü keçib Z» – hər biri klikləndikdə süzgəc.
   Sətir/xanada vəziyyət nişanı: «yazmayıb» (qırmızı), «gecikir» (narıncı), «açıq» (boz).
2. **M2 – eyni say:** Ana səhifə (`missing_summary`), «hamısı PDF» (`missing_all_api`) və panel eyni defolt parametrlərlə `class_missing`
   çağırır; test: Ana səhifə `total` == panel defolt `total`.
3. **M3 – dövr:** işlənməyənlər üçün dövr süzgəci **son tarix / plan günü**nə görə (`plan_date`, yoxdursa `closes_at`, müddətsizdə açılış);
   işlənməmiş test dövrün başlanğıcından əvvəl açılıbsa da görünür. `class_matrix`-in başqa istifadəçiləri (matris, şagird hesabatı)
   dəyişməsin – yeni parametr (`period_by='due'`) yalnız `class_missing`-də.
4. **M4:** «Semestr» hazır dövrü – 1-ci yarımil 15.09–31.01 (və ya `config` yarımil sərhədləri varsa onlar), heç vaxt gələcək tarix.
5. **M5 – bütün siniflər:** panelin sinif seçimində «Bütün siniflərim» (defolt): hər sinif bir başlıq (Disclosure), daxilində mövcud cədvəl;
   API – mövcud `missing-all` `format=json` (yoxdursa əlavə et, `class_missing` üzərində).
6. **M6:** batch-siz sınaq tapşırığı öz `t{id}` vahidi ilə toplanır (`test_stats.py:78`), atılmır.
7. **M7/M8 izah:** panelin altında qısa «ⓘ Siyahıya daxil deyil: hələ açılmamış testlər, üzrlü qeydlər, arxiv dərslər, çıxmış şagirdlər,
   növsüz tapşırıqlar» (AZ/EN/RU). «Yazmayanlar» nişanının alt yazısı: «yalnız bağlanmış testlər».
8. **M9:** surət kökü audit sətri olmadıqda `OnlineTask` sahələri ilə (eyni `batch_id`/`test_id` + eyni `assignment_id` + adda «təkrar») tapılmasın –
   yalnız mövcud məntiqi saxla, amma `_roots` üçün test əlavə et (audit sətri var → bir vahid).

## Testlər (`backend/tests/test_missing_report.py`-ə əlavə)
- açılışı dövrdən əvvəl, son tarixi dövr daxilində olan işlənməmiş test görünür (M3);
- batch-siz sınaq siyahıdadır (M6);
- Ana səhifə sayı == panel defolt sayı (M2);
- müddətsiz işlənməmiş test defolt görünür (M1).

## Yoxlama
`backend/.venv/Scripts/python.exe -m pytest -q backend/tests/test_missing_report.py backend/tests/test_missing_list.py backend/tests/test_unlimited_tests.py`
(PYTHONIOENCODING=utf-8), `cd frontend && npm run build`. Hesabat: budaq, commit, fayllar, test sayı, build, edilməyənlər.
