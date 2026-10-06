# Promt: Sınaq imtahanlarında eyni sınaq təkrar verilməsin

## Məqsəd
«Sınaq imtahanları» bölməsində eyni sınaq (viktorina faylı – Sınaqlar / P012 / P009) **eyni sinfə ikinci dəfə**
düşməsin. İndi heç bir yoxlama yoxdur: müəllim «Yeni sınaq»da artıq verilmiş faylı yenidən seçə bilir, seriya isə
əl ilə verilmiş (və ya başqa seriyanın verdiyi) sınağı növbəsində saxlayıb yenə göndərir. Nəticədə siyahıda eyni adlı
iki sınaq, sınaq jurnalında və kumulyativ reytinqdə ikiqat hesab, şagirdlərdə «bunu yazmışdıq» qarışıqlığı yaranır.

Bilərəkdən təkrar (məs. zəif nəticədən sonra yenidən yazdırmaq) **qadağan deyil**, amma yalnız müəllimin açıq
təsdiqi ilə və siyahıda aydın «təkrar» nişanı ilə.

## Anlayış: «sınaq bu sinfə verilib»
- Fayl F dərsə (ta) verilib sayılır, əgər həmin dərsin arxivlənməmiş `OnlineTask(kind='sinaq')` tapşırıqlarının
  sualları arasında F-in aktiv suallarının **ən azı yarısı** (`bank_id` → `BankQuestion.file_id`) varsa.
  Yarıdan az – «qismən istifadə olunub» (xəbərdarlıq, blok yox).
- Mənbə yalnız snapshot-dakı `bank_id`-dir (öz sualı və redaktə olunmuş sualda da `bank_id` saxlanır).
- Silinmiş/arxivlənmiş sınaq sayılmır – müəllim sınağı silib yenidən verə bilər.

## Ediləcəklər
### Backend
1. `exams_online.py` – köməkçi `given_files(db, ta_ids) -> {file_id: {used, of, classes:[{ta_id, class_name, title,
   at, batch_id}]}}` və `GET /api/exams-online/given?ta_ids=…` (yalnız müəllimin hədəfləyə bildiyi dərslər).
2. `POST /api/exams-online`: `allow_repeat: bool = False`. Seçilmiş suallar hər hansı hədəf sinfə artıq verilmiş faylı
   təkrarlayırsa → **409** `{message, repeat:[{class_name, label, title, at}]}`. `allow_repeat=true` olanda yaradılır,
   başlığa (yoxdursa) « (təkrar)» əlavə olunur, audit-də `repeat=true`.
   Əlavə: eyni dərsdə eyni adlı aktiv sınaq artıq varsa da 409 (ad toqquşması siyahıda qarışıqlıq yaradır).
3. Seriya (`exam_series.py`):
   - `_send`: fayl artıq verilmiş siniflər atlanır; heç bir sinif qalmırsa fayl göndərilmir, növbədəki
     növbəti fayla keçilir (yuva boş qalmır).
   - `_sync_new`: hədəf siniflərin hamısına artıq verilmiş fayllar növbəyə düşmür.
   - `GET /api/exam-series/files?ta_ids=…` hər fayla `given: [class_name…]` qaytarır.
   - `series_out`-da növbədəki elementə `given` nişanı (müəllim növbədə nəyin atlanacağını görür).

### Frontend
1. `BankPicker` – yeni `given?: Record<number, Given>` parametri: verilmiş fayl boz, «verilib · 9a 05.10» nişanı;
   **«Verilmişləri göstər»** açarı (standart – gizli), sayğac «N verilmiş sınaq gizlədilib». Digər istifadəçilər
   (Tapşırıq, Mövzu testi, Əlavə kurslar) dəyişmir.
2. `OnlineExams → NewExam`: seçilmiş siniflərə görə `given` yüklənir; 409 gələndə izahlı xəbərdarlıq və
   «Bilərəkdən təkrar göndərirəm» qutusu – yalnız işarələnəndə yenidən göndərilir.
3. Sınaqlar siyahısı: eyni başlıqlı (və ya « (təkrar)») sınaq «təkrar» nişanı alır.
4. `ExamSeries → NewSeries`: siniflər seçiləndə verilmiş fayllar «verilib» nişanı ilə gizlədilir (açarla görünür),
   «Hamısını seç»/«hamısı» verilmişləri götürmür. Seriya kartında növbədə verilmiş fayl «atlanacaq» nişanı alır.

## Yoxlama
- `pytest` (yeni test yazma – yalnız mövcudları işlət), `npm run build` (`tsc -b`).
- Lokal ssenari (TestClient): sınaq yarat → eyni fayl eyni sinfə → 409; `allow_repeat` → yaranır, ad « (təkrar)»;
  başqa sinfə → problemsiz; seriya növbəsində verilmiş fayl → atlanır, növbəti göndərilir.
- Commit + push.

## Əlavə tələblər (06.10.2026, istifadəçi)
### A. Adi «Yeni sınaq»da Sınaqlar və P012 görünmür (seriyada görünür)
Səbəb: `BankPicker` mənbəni `enabled && active` ilə süzür, seriya (`_files_q`) isə yalnız `enabled` + aktiv fayllara
baxır. Mənbənin `active` bayrağı sinxronda geri qala bilir. Həll: seçici də seriya kimi – `enabled && (active ||
questions > 0)` (aktiv sualı olan mənbə görünür).

### B. Sinfə yalnız öz sinfinin sınağı (11 → yalnız 11-in sınaqları; 10-a 11-in sınağı yox)
- `grade_fits(file, class_grade)`: fayl `grades`-ində sinfin rəqəmi varsa – avtomatik olar. Başqa sinfin və ya
  **sinfi göstərilməmiş** fayl – yalnız müəllimin təsdiqi ilə («qalanları təsdiq gözləsin»). Sinfin rəqəmi
  bilinmirsə yoxlanmır.
- `POST /api/exams-online`: uyğunsuzluq → 409 `{message, grade:[…]}`; `allow_other_grade=true` ilə keçir.
- Seriya: `ExamSeries.other_ok` (miqrasiya `c3e5a7b9d1f2`) – müəllimin təsdiqlədiyi fayllar. Növbədə uyğunsuz fayl
  təsdiqsiz → 409. `_send` hər sinif üçün yoxlayır (10 və 11 qarışıq seriyada 11-in sınağı yalnız 11-ə gedir).
  `auto_new` yalnız ən azı bir hədəf sinfə uyğun faylı növbəyə qoyur.
- UI: seçicilərdə «başqa sinfin» / «sinfi göstərilməyib» nişanı, standart gizli; seçiləndə təsdiq qutusu.
