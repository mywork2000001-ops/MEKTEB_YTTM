# Müəllim hissəsinin funksional və metodik auditi — 29.09.2026

Üsul: yerli serverdə 6 real perspektiv planla bütün müəllim səhifələrinin və tablarının avtomatik gəzilməsi
(kompüter 1366 px və telefon 390 px ölçüsündə; JS xətaları, 4xx/5xx sorğular, enə daşma yoxlanıb), jurnal və KSQ/BSQ
qaydalarının API ilə sınanması, metodist baxışı ilə kodun oxunması. Nəticə: 105 avtomatik test keçir.

## Gəzilən bölmələr
Əsas səhifə, Siniflər, Jurnal (Gündəlik, Şagirdlər, KSQ/BSQ, Yarımil, Mövzular, Xülasə), Perspektiv plan, Həftəlik cədvəl,
Onlayn tapşırıqlar, Materiallar, Analitika (İcmal, Dərs sayı, Müvəffəqiyyət, Reytinq, Güclü/orta/zəif, Risk, Davamiyyət,
Çap), Sinif rəhbəri, Çat, Tənzimləmələr (bütün tablar). JS xətası və uğursuz sorğu: **0**.

## Tapılan və düzəldilən səhvlər

| № | Səhv | Növ | Düzəliş |
|---|---|---|---|
| 1 | 1-ci saatda verilən ev tapşırığı həmin gün 5-ci saatda «Yoxlanılacaq» kimi çıxırdı | metodik | Yalnız əvvəlki günlərdə verilən ev tapşırığı yoxlanılır |
| 2 | Üzrlü səbəbdən dərsdə olmayan şagirdə qiymət yazmaq olurdu | metodik | Qayıb və üzrlü şagirdə qiymət yazılmır (serverdə və jurnalda) |
| 3 | Gələcək tarixli dərsə (14 günə qədər) davamiyyət və qiymət yazılırdı | metodik/məlumat | Gələcək dərsə yalnız mövzu və ev tapşırığı yazılır; jurnalda bu hissə gizlənir |
| 4 | Qayıb şagirdin ev tapşırığı «etmədi» kimi yazıla bilirdi | metodik | Dərsdə olmayan şagirdin ev tapşırığı yoxlanmır, onun faizini korlamır |
| 5 | KSQ başqa yarımilin tarixi ilə yaradıla bilirdi (məs. I yarımil KSQ-si martda) | metodik | Tarix seçilmiş yarımilin içində olmalıdır |
| 6 | Bir yarımildə iki BSQ yaradıla bilirdi (yarımil qiyməti hansının götürüləcəyi bilinmirdi) | metodik | Hər yarımildə bir BSQ: I yarımildə BSQ-1, II yarımildə BSQ-2 |
| 7 | Telefonda «Analitika → Çap / PDF» önbaxışı ekranı enə daşırırdı | görünüş | Önbaxış öz sürüşmə sahəsindədir |
| 8 | «Sinif rəhbəri» admin üçün başqa müəllimlərin siniflərini (məs. XI b) göstərirdi | məntiq | Yalnız öz sinifləri; admin üçün ayrıca «Bütün siniflər» qutusu |

## Metodik yoxlama — uyğun olanlar
- Perspektiv plan: 6 planın 1222 dərsinin tarixi cədvəllə tam uyğundur. KSQ sayı X e-də 6 + 6 dir, BSQ-1 26.01-də, BSQ-2 14.06-da (BSQ qaydası).
- Jurnal: mövzu, standartlar, resurslar, sinif/müstəqil iş və ev tapşırığı plandan gəlir; «Plandan» düyməsi var.
- Yarımil qiyməti: (KSQ ortası) × 0,4 + BSQ × 0,6, adi yuvarlaqlaşdırma.
- KSQ/BSQ bal → faiz → qiymət (0–30 → 2, 31–60 → 3, 61–80 → 4, 81–100 → 5); tapşırıq və standart üzrə təhlil var.
- Formativ test: düzgün cavab / sual sayı → faiz → qiymət.
- Müvəffəqiyyət, keyfiyyət, SOU, dərs sayı (plan / keçilməli / yazılıb / yazılmayıb / qalan / geriləmə); «Planla tarix» uyğunluğu.
- Davamiyyət: 25% və daha çox buraxma xəbərdarlığı.

## Tövsiyələr (qərar tələb edir)
1. KSQ/BSQ günü eyni dərsdə formativ qiymət də yazmaq mümkündür. Adətən summativ gündə formativ qiymət qoyulmur. İstəsəniz, bloklamaq olar.
2. Onlayn testin qiyməti jurnala avtomatik düşmür (hazırda ayrıca hesablanır). Jurnala köçürmək seçimi əlavə oluna bilər.
3. İlin ortasında cədvəl dəyişəndə «cədvəlin qüvvəyə minmə tarixi» (bax: sagird-auditi.md).
