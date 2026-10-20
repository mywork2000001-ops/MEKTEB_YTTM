# Tapşırıq: işlənməyən mövzu testləri və sınaqlar – siyahı və çap (20.10.2026)

Promt: `docs/davam-promtu-2026-10-20.md` §2 Q1. İcraçı: `kodcu`. Əsas: sinif matrisi (`student_report.class_matrix`,
`/api/results-center/class/{ta_id}/matrix`, `ClassMatrix.tsx`, `class_matrix_print.py`).

## Tələb
1. **Backend** `student_report.py`: `class_missing(db, user, ta_id, kind, date_from, date_to)` – `class_matrix`-dən qurulur (təkrar məntiq yox):
   `rows: [{student_id, full_name, lang, items: [{key, kind, no, title, date, status}]}]`, item = xananın statusu
   `yazmayıb` və ya `gözlənilir` (açıq, hələ işləməyib) – həmçinin gələcəkdə əlavə olunacaq `işlənməyib` statusu (müddətsiz test) da daxil
   (statusları bir sabitdə saxla: `MISSING_STATUSES`). Boş siyahılı şagirdlər çıxmır; sıralama – ad.
2. **API** `GET /api/results-center/class/{ta_id}/missing-list?kind=&from=&to=&format=json|pdf|xlsx&per_student=0|1&sid=`
   - `per_student=0` – **sinif üzrə** bir sənəd: cədvəl Şagird | Mövzu testləri (№ + qısa mövzu) | Sınaqlar | Say. Rəsmi – AZ, A4,
     məktəb adı, sinif, fənn, dövr, tarix, müəllim imzası (`class_matrix_print.py` üslubu).
   - `per_student=1` – **hər şagirdə ayrıca vərəqə** («İşləməli olduğun testlər»): hər şagird ayrıca səhifə (page-break), toplu PDF;
     `sid=` – tək şagird. Vərəqə dili şagirdin dilinə görə: AZ və ya AZ|RU (mövcud valideyn hesabatı `student_report_print` dil məntiqi
     neçədirsə, onu təkrar istifadə et). Mətn: şagird adı, sinif, fənn, siyahı (№, mövzu, tarix), «Portalda daxil ol → Testlər» qeydi.
   - Yalnız öz dərsim (`own_assignment`), başqa müəllim 404; audit export.
3. **UI** `ClassMatrix.tsx` («Kim nəyi işləyib» nişanı): rejim keçidi **«Hamısı | Yalnız işlənməyənlər»**. İkinci rejimdə siyahı
   (şagird – çip-lər: «№5 Kvadrat tənlik», «Sınaq: Oktyabr»), say nişanı. Düymələr: «🖨 Sinif üzrə çap», «🖨 Hər şagirdə ayrıca»,
   «⬇ Excel». Şagird hesabatında (Nəticələr → Şagird) düymə «🖨 İşləməli olduğu testlər» (sid=).
4. **Əsas səhifə** («Bu həftə diqqət»): hər sinif üçün «N şagird · M işlənməmiş test» sətri (0-dırsa göstərmə), klik → Nəticələr →
   «Kim nəyi işləyib» həmin sinif + «Yalnız işlənməyənlər». Yüngül say üçün ayrıca `GET /api/results-center/missing-summary` (bütün öz dərslərim,
   yalnız saylar) – hər dərs üçün matrisi qurmaq bahadırsa, sadə sorğu ilə hesabla, amma statuslar matrislə eyni olmalıdır (testlə yoxla).
5. Bütün UI mətnləri `t()` + i18n.ts AZ/EN/RU (Grep ilə təkrar açar yoxla); rəsmi çap AZ.
6. Testlər `tests/test_missing_list.py`: 3 şagird, 2 mövzu testi + 1 sınaq; biri hamısını yazıb (siyahıda yox), biri birini yazmayıb,
   biri açıq testi işləməyib → siyahı düzgün; pdf (per_student 0/1) və xlsx 200 qaytarır; başqa müəllim 404; summary sayları siyahı ilə eyni.
7. Yoxlama: aid pytest (`test_missing_list`, `test_class_matrix`, `test_student_report`) + `npm run build` (frontend).
