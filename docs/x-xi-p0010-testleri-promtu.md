# X–XI sinif: perspektiv plan dərsinə P0010 testlərinin avtomatik seçilməsi (06.10.2026)

## Məqsəd
X və XI sinif dərslərində (perspektiv plan, məs. DİM «Sinif testləri» X/XI proqramı) müəllim mövzuya onlayn test açanda
**P0010 «Riyaziyyat Test Bank» (abituriyent test toplusu)** suallarından mövzuya uyğun olanlar **avtomatik** seçilib forma
doldurulsun – IX sinifdə P007 kimi (bax docs/ix-dim-toplu-perspektiv-promtu.md).

## Mənbə
- P0010 viktorina-da `p003` mənbəyidir («P0010 · Blok İmtahan»): fayllar `p1-sNN-tY.html`, etiket `«<bölmə> — <alt mövzu>»`
  (34 bölmə: s01 Natural ədədlər … s28 Triqonometrik funksiyalar, s29 Funksiyalar və qrafiklər … s38 Kompleks ədədlər) +
  yekun testlər (`test-variant-1/2`, `test-dim-mixed`).
- Tətbiqdə: `BankSource 'p003'`, `BankFile.label` = viktorina etiketi. Sual nömrəsi ilə kitab əlaqəsi yoxdur – uyğunluq
  **mövzu adına görə** qurulur.

## İş
1. `app/bank/match.py` – `p0010_matches(db, topic, section, limit)`: aktiv, mənbəyi açıq, sualı olan `p003` mövzu faylları
   plan mövzusu + bölmə adı ilə müqayisə olunur (normallaşdırma – `norm_topic`; söz kökü = ilk 5 hərf; köməkçi sözlər
   atılır; mövzu sözlərinin üst-üstə düşməsi əsas, bölmə – əlavə çəki). Bal > 0 olanlar azalan sıra ilə.
2. `GET /api/plan/{ta_id}/topics/{pl_id}/p0010?file_id=&n=15`: yalnız X–XI sinif (başqa sinifdə `eligible=false`).
   Cavab: `{eligible, matches:[{file_id,label,count,score}], file, title, questions}` – `file_id` verilməyibsə ən uyğun fayl;
   fayldakı suallar ≤ n isə hamısı, çoxdursa n təsadüfi (qapalı:açıq ≈ 2:1), nömrə sırası ilə; surət – mövcud `_snapshot`.
3. Mövzu testi formasında (TopicTest.tsx): X–XI dərsində forma açılan kimi ən uyğun faylın sualları **özü əlavə olunur**
   (seçilmiş sual hələ yoxdursa) və ad «№… <mövzu> – P0010 testi» olur; blok «P0010 testləri (mövzuya uyğun)» – digər uyğun
   fayllar düymə kimi (birinə klik – həmin faylın sualları əlavə olunur), sual sayı N dəyişdirilə bilər, uyğun fayl yoxdursa izah.
   Avtomatik əlavə olunanları müəllim siyahıdan silə bilər; heç nə müəllimsiz göndərilmir.
4. Testlər yazılmır (istifadəçinin qərarı); mövcud `pytest` və `tsc -b` təmiz.

## Qəbul
X və ya XI sinfin plan dərsində «Mövzuya onlayn test» açılır → P0010-dan mövzuya uyğun suallar artıq seçilib, digər uyğun
fayllar bir kliklə; IX və aşağı siniflərdə dəyişiklik yoxdur.

## Əlavə (06.10.2026): hər plan dərsi P0010-a bağlı
- `GET /api/plan/{ta}` – X–XI sinifdə hər dərsə `p0010 = {file_id, label, url}` (ən uyğun fayl, `bank/match.py::Matcher` –
  bank bir dəfə oxunur). Plan sətrində «P0010: <fayl>» linki, düymə «🧪 Test (P0010)».
- Gündəlik plan (AI) kontekstinə «P0010 test bankı (mövzuya uyğun fayl)» sətri – yalnız X–XI-də.
- Uyğunluq mövzu adına görədir, saxlanılmır: P0010 bankı yenilənəndə bağlantı özü yenilənir.
- Müəllim redaktə edir: plan sətrində «P0010: …» yanında ✎ – «Avtomatik», «P0010 bağlantısı yoxdur» və ya istənilən P0010 faylı
  (uyğunlar öndə, qalanı bölmələr üzrə). Seçim `lesson_bank_links` cədvəlində (miqrasiya a9c3e5f7b1d2), avtomatikdən üstündür;
  mövzu testi forması da həmin faylı götürür. `PUT /api/plan/{ta}/topics/{pl}/p0010 {mode: auto|none|file, file_id}`.

## Əlavə: hər plan dərsinə avtomatik mövzu testi
- Perspektiv plan → «Hər dərsə avtomatik mövzu testi» (`teaching_assignments.auto_tests`, miqrasiya c2e4a6b8d0f1,
  `PUT /api/plan/{ta}/auto-tests`). `app/auto_tests.py` hər 15 dəq. (scheduler) bu günün dərslərinə test yaradır:
  X–XI – P0010 (müəllimin seçdiyi və ya ən uyğun fayl, ≤ 15 sual), «Test toplusu» – P007 (dərsin S/E/M aralığı).
  Açılır dərsin sonunda, bağlanır ertəsi gün 22:00, 20 dəq., nəticə formativ jurnala; KSQ/BSQ və testi olan dərs atlanır.
