# Rus sektoru IX sinfi «Sınaqlar»da görünmür (şagird Arşad) – promt (21.10.2026)

İstifadəçi: «класс русского сектора 9-й не видно. Ученик Аршад. В тестах (Sınaqlar) класс не виден.»

## Hələ dəqiqləşməyib
Brauzer (Chrome) qoşulmamışdı, canlı DB-yə çıxış yox idi – canlı məlumat görülməyib.
Hansı yerdə görünmədiyi yoxlanmalıdır: (a) müəllim → Sınaqlar → «Yeni sınaq» sinif siyahısı
(`frontend/src/pages/teacher/OnlineExams.tsx`, `GET /api/exams-online/targets`), (b) seriya/fayl seçimi
(`backend/app/api/exam_series.py`, grade süzgəci), (c) HUB viktorina (`viktorina-roster.js`, sinif → qrup → şagird).

## Ehtimal olunan səbəblər (kodda tapılıb)
1. **Fənn adı fərqlidir.** `OnlineExams.tsx:220` sinifləri `t.subject === subject` ilə süzür. Rus sektoru dərsinin fənni
   «Математика» / «Riyaziyyat (rus)» kimi yazılıbsa, sinif yalnız fənn siyahısında başqa fənn seçiləndə görünür.
   Həll: fənn adını normallaşdır (AZ/RU sinonimləri bir fənn) və ya seçici «bütün fənlər» göstərsin.
2. **Sinif rəqəmi tanınmır.** `backend/app/domain/classes.py:grade_of` yalnız latın I/V/X və rəqəm tanıyır.
   Rus klaviaturası ilə yazılmış «IХ а» (kiril Х, I) → `grade=None` → sinfə görə sınaq süzgəci (`_grade_ok`,
   `grade_fits`) onu kənarda qoyur. Həll: kiril І/Х/V oxşar hərflərini latına çevir + test `tests/` (grade_of('IХ а') == 9).
3. **Dərs başqa iş sahəsindədir** (`ws_cond`, şəxsi workspace) və ya arxivlənib / Arşad ana sinfə yox, qrupa yazılıb.

## Addımlar
1. Chrome qoş → canlıda Siniflər: rus sektoru IX sinfinin adı, `grade`, dərsin fənni, müəllimi, Arşadın sinfi.
2. Səbəbə görə düzəliş (1 və/və ya 2 – ikisi də ziyansızdır, ikisini də et), AZ/EN/RU mətnlər `t()` ilə.
3. pytest (aid testlər) + `npm run build` → commit → push → Render deploy → canlıda yoxla.
