# Sınaq seriyası – bir neçə sınağın birdən göndərilməsi və tarix üzrə avtomatik bölgüsü (06.10.2026)

## 1. Problem
Müəllim viktorina layihəsinə (hub, `Sinaqlar/YYYY/*.html`, bankda mənbə `sinaqlar`; həmçinin `p009`, `p012`, `p004`) hər həftə
bir neçə yeni sınaq əlavə edir. İndi hər sınağı «Sınaq imtahanları → Yeni sınaq»da əl ilə yaratmaq, sualları seçmək, sinifləri
və vaxtı yazmaq lazımdır. Məqsəd: **bir dəfə qurmaq** – sınaqlar seçilən dövrilikdə (gün / həftə / ay) siniflərə özü getsin,
bankda yeni sınaq görünəndə o da növbəyə düşsün.

## 2. Anlayışlar
- **Sınaq seriyası** (`exam_series`): kimə (siniflər/qruplar, istəyə görə şagirdlər), hansı mənbədən (mənbə açarları +
  sinif səviyyəsi), nə vaxt (dövr: `day` | `week` | `month`, hər N dövrdə bir, həftənin günü / ayın günü, açılma saatı,
  açıq qalma müddəti saatla), necə (həll müddəti, cərimə 0/3/4, cavabların göstərilməsi, sualların qarışdırılması).
- **Növbə** (`queue`): göndəriləcək bank fayllarının ardıcıllığı (müəllimin seçdiyi sıra). Hər yuvaya bir fayl.
- **Avtomatik əlavə** (`auto_new`): sinxronizasiyada mənbədə yeni sınaq faylı (növ `sinaq`, sinif səviyyəsi uyğun, bu seriyada
  əvvəl olmayan) görünəndə növbənin sonuna əlavə olunur.
- **Göndərilənlər** (`done`): `[{file_id, batch_id, at}]` – təkrar göndərilmir.

## 3. Qaydalar
1. Yuva vaxtı gələndə (`now ≥ next_at`) növbənin ilk faylı adi sınaq kimi yaradılır – mövcud `create_exam` ilə eyni nəticə
   (`TestBatch kind='sinaq'`, hər sinfə `OnlineTask kind='sinaq'`, «Sınaq jurnalı» və reytinq dəyişmir). Suallar faylın aktiv
   sualları (≤ 100), surət. Ad – faylın adı. Açılır `next_at`, bağlanır `next_at + window_hours`.
2. Sonra `next_at` bir dövr irəli: gün – `+every` gün; həftə – `+7·every` gün (seçilmiş həftə günü); ay – `+every` ay
   (ayın günü ayda yoxdursa – ayın son günü). Keçmişdə qalmış yuvalar toplanmır: server yatıbsa, bir dəfə göndərilir və
   növbəti yuva gələcəkdən hesablanır.
3. Növbə boşdursa seriya gözləyir (yuva keçir, sınaq yaranmır); yeni fayl gələndə növbəti yuvada gedir.
4. Faylın sualı yoxdursa və ya bankdan çıxarılıbsa – atlanır, növbədən silinir, jurnal (audit) qeydi.
5. Hüquq: seriyanı yaradan müəllim yalnız öz dərslərinə (admin – məktəbin dərslərinə), bir seriya – bir fənn (mövcud qayda).
6. Seriya dayandırıla (`active=false`), növbəsi dəyişdirilə (sıra, silmə, əlavə), silinə bilər – yaradılmış sınaqlar qalır.
7. İş fonda gedir (scheduler, 15 dəq.) + seriya yaradılanda/dəyişəndə dərhal bir dəfə.

## 4. API (`/api/exam-series`)
- `GET /files?sources=sinaqlar,p012&grade=11` – sınaq faylları (id, label, questions, kind, grades, source).
- `GET` – müəllimin seriyaları + hər biri üçün önbaxış: növbəti 6 yuva (tarix, saat, fayl adı).
- `POST` – yarat; `PATCH /{id}` – parametrlər, `active`, `queue`; `DELETE /{id}`.

## 5. İnterfeys («Sınaq imtahanları» səhifəsi)
Bölmə **«Avtomatik sınaq seriyaları»**: «Yeni seriya» forması – ad, siniflər (mövcud hədəflər siyahısı), mənbə(lər),
sinif səviyyəsi, sınaqların siyahısı (çoxlu seçim, seçilmə sırası = göndərilmə sırası, «hamısını seç»), «yeni sınaqları
avtomatik əlavə et», dövr (Gün / Həftə / Ay), hər N, həftənin günü / ayın günü, başlama tarixi, açılma saatı, açıq qalma
(saat), həll müddəti, cərimə, cavablar. Önbaxış: «13.10 (B.e.) 15:00 – OTK №2 …». Seriya kartı: növbəti yuva, növbədə N,
göndərilib M, «Dayandır / Davam et», «Sil», növbədən çıxarmaq.

## 6. Qəbul
5 sınaq seçilir, «Həftə, B.e. 15:00, 48 saat» → hər bazar ertəsi bir sınaq siniflərdə açılır; həftə ərzində viktorina-ya yeni
sınaq əlavə olunur → sinxronizasiyadan sonra növbəyə düşür və növbəti yuvada gedir; nəticələr adi sınaq kimi reytinqdə.
Yeni testlər yazılmır (istifadəçinin qərarı); mövcud `pytest` və `tsc -b` təmiz.
