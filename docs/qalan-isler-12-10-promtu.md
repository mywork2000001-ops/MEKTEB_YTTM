# Qalan işlər və növbəti addımlar – 12.10.2026 (ümumi promt)

**Rol:** baş mühəndis. Bu sənəd 11–12.10.2026 sessiyasında görülən işlərin yekunu, istifadəçinin verdiyi qalan tapşırıqlar
və əlavə tövsiyələrdir. Hər bənd: test → lokal brauzer → commit → push.

## A. Bu sessiyada icra olunanlar (yoxlama üçün)
| Sənəd | Nə |
|---|---|
| `test-sinaq-audit-promtu.md`, `test-sinaq-auditi.md` | sınaq auditi (cavab sızması, cərimə, qiymət, çökmə) |
| `test-bolmeleri-seliqe-promtu.md` | Onlayn tapşırıqlar / sınaqlar / nəticələr səliqəsi, reytinqdə iştirak qaydası |
| `sinaq-tarix-sinif-tekrar-promtu.md` | sınaq tarixi və tarix filtri, təkrar sınaqlar, yenidən göndərmə eyni sınaqa |
| `test-bolmesi-birlesme-promtu.md` | «Testlər və sınaqlar» – bir bölmə, açılan siyahılar; 45 dəq; köhnə testlərin səliqəsi |
| `mesgele-qruplari-sinifler-promtu.md` | məşğələ qrupları «Siniflər»də, şagird əlavə/çıxar |
| `sagird-coxlu-sinif-ve-birlesme-promtu.md` | bir şagird bir neçə sinifdə, təkrar şagirdlərin birləşdirilməsi |
| — | baza Render → Neon (`muellim`), `tools/copy_db.py`; bağlanmış sınaq nəticəsinə keş |

## B. Bu addımda (12.10, axşam)
- [x] **Bir şagird bir neçə sinifdə** (əsas sinif + əlavə siniflər/qruplar): jurnal, testlər, sınaqlar, şagird portalı.
      Siniflər → sinif → «+ Başqa sinifdən», sətirdə «✕ bu sinifdən çıxar»; şagird kartı → «Siniflər və qruplar».
- [x] **Təkrar şagirdlər** (admin): Siniflər → «Təkrar şagirdlər» – cütlər (ad sözləri eyni / biri digərinin içində;
      doğum tarixi fərqlidirsə – yox), saxlanacaq qeyd seçilir, adı yazmaqla «Birləşdir». Bütün qeydlər köçür, silinənin
      sinfi əlavə sinif olur, giriş bağlanır.
- [x] **Nihad (IX + XI → əsas XI) və Hüseyn Əhmədov (X + XI → əsas X)** – miqrasiya `b3c5d7e9f1a2` canlıda bir dəfə,
      yalnız birmənalı halda; nəticə Render logunda «student merge: [...]». Birmənalı deyilsə – «Təkrar şagirdlər»dən əl ilə.
- [x] **Məşğələ qrupuna sinif üzrə əlavə – Zəif / Orta / Güclü ayrıca** (səviyyə – Jurnal → Səviyyə qrupları): çiplər
      sayla, «Bütün «Zəif» seç».
- [x] Sinif rəqəmi adın içindən də: «Buraxılış IX sinif» → 9 (əvvəl tanınmırdı – bu sinfə öz sinfinin sınağı düşmürdü).

## C. İstifadəçinin qərarı lazım olanlar
1. OBM sınaqları (Natural ədədlər, Çoxluqlar…) – hansı sinif üçün? (indi sinifsiz – təsdiqlə verilir)
2. Reytinqdə iştirak həddi – «yarısından çox» (dəyişmək olar, məs. 70%).
3. Neon pulsuz kvotası – 15.10 civarı «Usage»yə baxmaq (Render: 750 saatdan ~555 – kifayətdir, kart yoxdur).

## D. Əlavə tövsiyələrim (növbəti iş)
1. **Telefon (393 px) yoxlaması** – üç yeni ekran (Testlər və sınaqlar, Məşğələ qrupları, Təkrar şagirdlər) real telefonda.
2. **Qeydiyyat linki təkrar yaratmasın:** şagird linklə qeydiyyatdan keçəndə ad sözləri oxşar aktiv şagird varsa –
   müəllimə «bu şagird artıq var?» təsdiqi (təkrarların mənbəyi).
3. **Giriş vərəqi** (login sheet) – əlavə sinif üzvləri də (indi yalnız əsas sinif).
4. **Şagird portalı** – «Bu gün» başlığında əsas sinif; əlavə siniflərin dərsləri artıq görünür – adların yanında sinif.
5. **Render logu** – yeni versiyadan sonra «test tidy» və «student merge» nəticələrini oxumaq (silinən təkrar test sayı,
   birləşdirilən şagirdlər).
