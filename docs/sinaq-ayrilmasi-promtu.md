# Prompt: mövzu testləri və sınaqların tam ayrılması, silmə, sıralama və filtrlər

**Kontekst.** «Müəllim köməkçisi» (FastAPI + React). Onlayn testlər `online_tasks` cədvəlindədir, növü `kind`:
`movzu` (perspektiv planın mövzusuna bağlı), `sinaq` (sınaq paketi `test_batches`), `extra` (əlavə məşğələ testi),
`NULL` (yeniləmədən əvvəlki adi tapşırıq). Müəllimin tələbləri (03.10.2026) aşağıdadır – hamısı birlikdə icra olunur.

## 1. Bölgü qaydası (əsas)
- **Mövzu testi** – yalnız perspektiv planın mövzusundan yaradılan test (`kind = movzu`). Yeri: **«Onlayn tapşırıqlar»**.
- **Sınaq** – perspektiv plana bağlı olmayan **hər** test: köhnə adi tapşırıqlar, viktorinadan götürülən testlər, sınaq
  faylları, «Yenidən göndər» ilə plandan kənara çıxan surətlər. Yeri: **«Sınaq imtahanları»** (jurnal, reytinq).
- Əlavə məşğələ testləri öz bölməsində qalır (dəyişmir).
- Köhnə məlumat miqrasiya ilə köçürülür: eyni müəllim + eyni ad + eyni suallar (müxtəlif siniflər) = bir sınaq paketi.

## 2. Silmə
- Sınaq silinəndə **sistemdən tam silinir** (nəticələr və şagird cəhdləri ilə) – müəllimdə də, şagirddə də; arxiv yoxdur.
- Mövzu testi silinəndə «Silinənlər»ə düşür: oradan **geri qaytarmaq** və ya **birdəfəlik silmək** olar.
- Arxivdə qalmış köhnə sınaqlar miqrasiyada tam silinir. Birdəfəlik silmə adın yazılması ilə təsdiqlənir.

## 3. Müəllim – «Onlayn tapşırıqlar»
- Yalnız mövzu testləri görünür. Yeni test perspektiv plandan («🧪 Test») yaradılır – səhifədə bu barədə qeyd.
- Hərəkətlər: canlı izlə / nəticələr, link göndər, yenidən göndər, kağız variant, redaktə, sil.

## 4. Müəllim – «Sınaq imtahanları»
- Bütün sınaqlar (köhnələr də). «+ Yeni sınaq».
- Sınağın içində hər sinif üzrə: canlı izlə / nəticələr, link göndər, yenidən göndər, kağız variant, redaktə
  (öz dərsləri üçün), jurnal və reytinq əvvəlki kimi. «Sil» – birdəfəlik.

## 5. Şagird – «Tapşırıqlar»
- İki bölmə (sekmə): **Mövzu testləri** və **Sınaqlar**. Silinmiş sınaq heç yerdə görünmür; sınaq nəticəsi «Nəticələrim»də.

## 6. Sıralama və filtrlər (müəllimin hər iki səhifəsi və şagird)
- Sıralama: **mövzu üzrə** (planın № sırası; sınaqlarda – ad) və **tarix üzrə** (açılma vaxtı, yenidən köhnəyə).
- Dövr filtri: **hamısı · gün · həftə · ay · yarımil · il** + «‹ ›» ilə əvvəlki/növbəti dövr, cari dövrün adı göstərilir
  (məs. «29.09 – 05.10», «oktyabr 2026», «I yarımil 2026/27», «2026/27 tədris ili»).
  Yarımil: I – sentyabr–yanvar, II – fevral–avqust; tədris ili 1 sentyabrdan.
- Görünüş səliqəli: başlıqlar, sayğac, boş nəticədə izah; mobil (360 px) üçün sətirlər sıxılmır.

## 7. Formativ jurnalda sınaqlar – ayrıca, keçirildiyi günə uyğun
- **Jurnal səhifəsi (ay):** hər sınaq keçirildiyi günün (açılma tarixi) dərslərindən sonra **ayrıca «Sınaq» sütunu** kimi
  (mavi fon). Xanada şagirdin faizi (cərimə nəzərə alınmaqla), bağlandıqdan sonra yazmayana «yox». Ayın sınaq ortası ayrıca sütunda.
- **Formativ «Orta» qiymətə sınaq daxil edilmir** – nə jurnal səhifəsində, nə xülasədə, nə yarımil qiymətində.
- **Yekun («Xülasə»):** formativ göstəricilərdən sonra ayrıca blok – sınaq sayı (yazdığı / keçirilən), sınaq orta %,
  son sınaq %, dinamika (son − əvvəlki; artım yaşıl, azalma qırmızı). Yarımil seçimi sınaqlara da tətbiq olunur.
- **«Yarımil»:** KSQ/BSQ formulasından sonra ayrıca «Sınaq» və «Sınaq orta %» – «yarımil qiymətinə daxil deyil» qeydi ilə.
- Sınaq keçirilən gün dərs yoxdursa da (həftəsonu), sütun həmin tarixdə göstərilir – jurnalda boş dərs yaradılmır.
- **Çap / PDF:** eyni sütunlar; jurnal çapında «Sınaq imtahanları» siyahısı (tarix – ad) və izah.

## 8. Əlavə təkliflər (müəllimin təsdiqi ilə növbəti addım)
- Sınaq xanasında faizlə yanaşı 2–5 şkalası ilə qiymət (məs. «75% · 4») – yalnız məlumat üçün.
- Şagird və valideyn portalında «Nəticələrim»də sınaq dinamikası qrafiki (sınaqdan sınağa faiz).
- Ardıcıl iki sınaqda nəticəsi 10%-dən çox düşən şagird üçün müəllimə xəbərdarlıq və səviyyə qrupunu dəyişmək təklifi.

## 9. Qəbul meyarları
- Plana bağlı olmayan test «Onlayn tapşırıqlar»da görünmür, «Sınaq imtahanları»nda görünür; şagirddə «Sınaqlar»dadır.
- Sınaq silindikdən sonra nə müəllimin, nə şagirdin heç bir siyahısında yoxdur (bazada da yoxdur).
- Jurnal səhifəsində sınaq keçirildiyi günün ayrıca sütunundadır, formativ ortaya təsir etmir; yekunda ayrıca blokdadır.
- Filtrlər və sıralama hər iki rolda işləyir; bütün backend testləri keçir, frontend yığılır.
