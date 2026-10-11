# Test tapşırıqları, sınaqlar və nəticələr – peşəkar audit promtu

**Rol:** Sən bu tətbiqin baş mühəndisi, qiymətləndirmə (assessment) metodisti, təhlükəsizlik auditoru və QA mühəndisisən.
Obyekt: onlayn test tapşırıqları (mövzu testi, plandan kənar test), sınaq imtahanları (tək və bir neçə sinfə, avtomatik seriya),
nəticələr (sınaq jurnalı, «Test nəticələri» mərkəzi, şagirdin «Nəticələrim»i, sertifikatlar, bildirişlər).
Hər tapıntını **əvvəlcə uğursuz testlə sübut et → düzəlt → testlər keçsin → lokal brauzerdə (noutbuk + 393 px telefon) yoxla →
commit et**. İstifadəçinin qərarını tələb edən məsələləri ayrıca «Sual» siyahısına yaz, kodda özbaşına dəyişmə.

**Sabit qaydalar (pozma):** sınaq formativ və KSQ/BSQ qiymətinə təsir etmir, şagirdə sınaqda qiymət göstərilmir (yalnız faiz və yer);
sınaq balı = düz − səhv ÷ N (cərimə seçilibsə), faiz = max(0, bal) ÷ sual sayı; bərabər bal – eyni yer; başqa müəllimin sinfindəki
şagirdin adı gizlidir (yer və bal qalır); şagird başqasının adını/nəticəsini görmür; cavab açarı şagirdə yalnız icazə verilən vaxtda
gedir; server vaxtı əsasdır (Asia/Baku göstərilir, UTC saxlanılır); sınaq sinfə yalnız öz sinfinin faylından və təkrar olmadan
(təsdiqsiz) verilir; silinmiş sınaq tam silinir; KSQ/BSQ bal→%→qiymət 0–30→2, 31–60→3, 61–80→4, 81–100→5.

## 1. Cavab açarının qorunması (bütövlük)
- [ ] Şagirdə gedən hər cavabda (`start`, `tasks`, `results`, `review`, `exams`, `notifications`) `correct`/`answer`/`explanation`
      yalnız `_can_review` doğru olanda var.
- [ ] **Bir neçə sinfə verilmiş sınaq / mövzu testi paketi:** «bağlandıqdan sonra» – sinfin öz bağlanması yox, **paketin ən gec
      bağlanması**. Erkən bağlanan sinif cavabları başqa sinif hələ yazarkən görməməlidir (Review, Səhvlərim, çap).
- [ ] «Təhvil verdikdən dərhal sonra» seçimi bir neçə sinifli sınaqda risklidir – müəllimə xəbərdarlıq.
- [ ] Müəllim API-si (`/full`, `attempt`) yalnız sahib/tam icazəli müəllimə.

## 2. Hesablama ardıcıllığı
- [ ] Sınaq faizi **hər yerdə eyni funksiya ilə** (cərimə daxil): sınaq jurnalı, siyahıdakı «orta», şagirdin açıq sınaqdakı «öz
      faizi», «Nəticələrim → Onlayn testlər», təhvil cavabı, sertifikat (faiz və yer), Test nəticələri mərkəzi.
- [ ] Sınaqda qiymət şagirdə heç yerdə görünmür (siyahı, təhvil bildirişi, nəticələr).
- [ ] Düz/səhv/boş: müəllimin əl ilə «düz say»ı boş cavaba verilsə də səhv sayı mənfi olmamalı.
- [ ] Yer: bal üzrə (eyni bal – eyni yer); sinif və ümumi; açıq sınaqda şagirdə yer göstərilmir.

## 3. Məlumat bütövlüyü
- [ ] Bir sınaq paketinin bütün sinif tapşırıqlarında suallar eynidir: bir sinifdə «Redaktə» → sual dəyişikliyi paketin bütün
      siniflərinə; kimsə başlayıbsa – 409. Sual sayı fərqli olsa belə jurnal 500 verməsin.
- [ ] Cəhdin sıfırlanması, «Yenidən göndər», silmə (arxiv / tam) – nəticə, jurnal qiyməti və sertifikat uyğun qalır.
- [ ] Eyni anda iki «Başla» (iki cihaz/klik) – 500 yox, eyni cəhd.
- [ ] Cavab ölçüsü məhduddur (açıq cavab ≤ 500 simvol) – bazaya böyük mətn yazılmır.
- [ ] Vaxt: avtomatik təhvil, 10 san. şəbəkə güzəşti, server yatıb oyananda seriyanın yuvası.

## 4. Məxfilik
- [ ] Sınaq jurnalı, reytinq, «Test nəticələri», AI rəyi (adlar kodlanır) – başqa müəllimin şagird adı yoxdur; başqa məkan – 404.
- [ ] Şagird portalı: yalnız öz nəticəsi, yer, sinif ortası.

## 5. İnterfeys (brauzerdə)
- [ ] Müəllim: Sınaq imtahanları (siyahı, «təkrar» nişanı, yeni sınaq, jurnal, siniflər, suallar, cavablar/əl ilə yoxlama,
      seriyalar, reytinq), Tapşırıqlar (canlı izlə, yenidən göndər, redaktə), Test nəticələri.
- [ ] Şagird: Tapşırıqlar (mövzu/sınaq), həll ekranı (taymer, avtomatik saxlama, təhvil), Nəticələrim, bildirişlər.
- [ ] 393 px: üfüqi sürüşmə yox; konsolda xəta yox; şəbəkədə 4xx/5xx yox.

## 6. Performans
- [ ] Şagird bildirişləri hər 5 dəqiqədə – bağlanmış hər sınaq üçün bütün paketin hesablanması N×M; ehtiyac olarsa keş.

## 7. Hesabat
- [ ] `docs/test-sinaq-auditi.md`: tapıntılar cədvəli (ciddilik, nəticə, düzəliş, test), brauzer yoxlaması, qalan risklər, suallar.
- [ ] Bütün backend testləri, frontend `tsc`/build; ayrıca commit.
