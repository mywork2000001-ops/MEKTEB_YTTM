# Kart: addım 5 – «Hər şagirdə öz rəqəmləri» tətbiqdə (19.10.2026)

Mənbə: docs/yazili-testler-master-promtu.md (addım 5), docs/reqem-variantlari-promtu.md (mərhələ 1, 1b, 2).
Hazır: `backend/scripts/reqem_variantlari.py` (generator), `backend/scripts/avto_reqem.py` (AI-sız avtomatik şablon), 22 test.

## İş
1. **Nüvəni tətbiqə köçür:** generator + avto_reqem məntiqi → `backend/app/domain/own_numbers.py` (və ya alt paket);
   `scripts/*` CLI-lar o modulu idxal edən nazik qabıq qalsın, 22 test keçsin. sympy artıq requirements-dədir.
2. **API:** `own_numbers.apply(questions, students, exam_code) -> (per_student_questions, report)`; seed = imtahan kodu + şagird +
   slot (determinizm), sinifdə təkrarsız dəst; mənbə açarı yoxlaması; uyğun olmayan sual – dəyişmir (hesabatda səbəb).
   Ağır hesab üçün limit: bir sual ≤ 2 s, bütün sinif ≤ 30 s (Render free, 512 MB); aşsa – sual dəyişmir.
3. **Harada işləyir:**
   - Yazılı iş (`api/paper_exams.py`): `variant_mode='same_numbers'` (indi 400) – hazır test/sınaq və sərbəst iş üçün.
   - KSQ/BSQ variantları (`api/exams.py::_make`): yeni seçim `own_numbers` (`same_for_all` ilə birlikdə də: eyni suallar, fərqli ədəd).
   - «🚩 Köçürmə şübhəsi – yeni variant» (retake): şablonlu sualda yeni ədədlər (seed-ə `R1/R2` əlavə).
   - Onlayn yazı KSQ/yazılı işdə mövcud `ExamVariant`-dan gedir → eyni ədədlər avtomatik. Onlayn mövzu testi (OnlineTask)
     üçün şagirdə ayrıca sual lazımdırsa – mümkünlüyünü qiymətləndir; böyükdürsə etmə, hesabatda yaz.
   - Açar, skan, apelyasiya, müəllim açarı çapı – donmuş `ExamVariant.questions`-dan, dəyişmədən.
4. **UI (AZ/EN/RU, i18n.ts):** variant rejimində seçim «Hamıya eyni suallar, hər şagirdə öz rəqəmləri» /
   «Same questions, own numbers for each student» / «Одинаковые вопросы, у каждого свои числа»; yaradandan sonra hesabat:
   «🔢 {n} sualda rəqəmlər dəyişdi, {m} sual dəyişmir» + açılan siyahı (sual № və səbəb). Müəllim açarında hər şagirdin öz cavabı.
5. **Miqrasiya yoxdur** (nəticə `ExamVariant.questions`-da donur). Lazım olarsa – əvvəl soruş (Claude).

## Testlər
- paper_exams same_numbers: 25 şagird → kvadrat tənlik sualında 25 fərqli ədəd/açar; fixed sual hamıda eyni; skan qiymətləndirməsi
  şagirdin öz açarı ilə; retake yeni ədəd; KSQ `own_numbers`; köhnə KSQ/paper testləri keçir.
- `npm run build` (frontend) uğurlu. Push/deploy/canlı DB – yox (Claude edir).
