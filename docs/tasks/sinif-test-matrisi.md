# Tapşırıq: Sinif üzrə «kim nəyi işləyib» matrisi – mövzu testləri (formativ) və sınaqlar, adlı siyahı (19.10.2026)

İstifadəçi: «hansı şagird hansı mövzu testlərini (formativ) və sınaqları işləyib – müəllim hesabatı üçün sinif üzrə adlı siyahıda».

## Audit (nə var)
- Nəticələr → Reytinq (orta %), Yazmayanlar (`/results-center/missing` – şagird üzrə yazmadığı testlər), Sinif (`_class_data`: şagird
  xülasəsi given/wrote/missed + testlər siyahısı ayrıca), Şagird hesabatı (`app/student_report.py`, bir şagird).
- **Yoxdur**: bir cədvəldə **şagird × test** – sətir = şagird (ad soyad), sütun = hər mövzu testi (№ + mövzu, tarix) və hər sınaq (adı ilə,
  `sinaq_name`), xana = nəticə; kağız KSQ/BSQ/yazılı sınaq da; çap və Excel.

## Tələb
1. `app/student_report.py`-də `class_matrix(db, user, ta_id, kind: movzu|sinaq|all, date_from, date_to)` – mövcud `collect` +
   `student_results`-in mənbə qaydaları (onlayn + nəşr olunmuş kağız, təkrarsız; `topic_no`, `sinaq_name`) təkrar istifadə olunur.
   Cavab: `columns: [{key, kind: movzu|sinaq|ksq|bsq, no, title, date, assigned_count}]`, `rows: [{student_id, full_name,
   cells: {key: {status: yazıb|yazmayıb|təyin olunmayıb|gözlənilir (hələ açıqdır)|nəşr olunmayıb, pct, grade}}, wrote, given, avg_pct}]`,
   sütun altı: yazan sayı / təyin olunan, orta %.
2. API: `GET /api/results-center/class/{ta_id}/matrix?kind=&from=&to=&format=json|xlsx|pdf` (müəllim, `own_assignment`).
   xlsx – openpyxl (mövcud `analytics.export_xlsx` üslubu: məktəb adı, sənəd adı, dövr, imza, başlıq hər səhifədə, A4 albom);
   pdf – mövcud `render_pdf` (student_report_print kimi).
3. UI: Nəticələr → «Sinif və qrup» → yeni nişan/düymə **«Kim nəyi işləyib»**: süzgəc (Mövzu testləri / Sınaqlar / Hamısı, dövr),
   cədvəl – sol sütun sabit (ad), başlıqda № + qısa mövzu (tam ad title-da), xana: rəngli % (≥80 yaşıl, 50–79 sarı, <50 qırmızı),
   «✗ yazmayıb» qırmızı, «—» təyin olunmayıb, «⏳» açıqdır; sətir sonu «yazıb/təyin», orta %. Ada klik → Şagird hesabatı. Düymələr:
   «🖨 Çap», «⬇ Excel», «Yazmayanlara yenidən göndər» (mövcud resend). Telefonda üfüqi sürüşmə yalnız cədvəlin içində.
4. Məxfilik: yalnız öz dərsləri; fərdi məkan məktəbə qarışmır; nəşr olunmamış skan balı müəllimdə «nəşr olunmayıb» (bal görünür, amma
   işarəli), çapda mötərizədə.
5. Mətnlər AZ/EN/RU (`t()` + i18n.ts – öz blokunda, Grep ilə təkrar yoxla); rəsmi çap/Excel – AZ.
6. Testlər `tests/test_class_matrix.py`: 3 şagird × 2 mövzu testi + 1 sınaq + 1 kağız KSQ → statuslar düzgün; təyin olunmayan
   şagird «—»; açıq test «⏳»; xlsx açılır (openpyxl load); başqa müəllim – 404.
7. Yoxlama: aid pytest + `npm run build`.
