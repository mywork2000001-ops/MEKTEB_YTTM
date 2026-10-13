# KSQ skanı: kart tam düşməyibsə – «yenidən çək», bal – dərhal (13.10.2026)

## İstifadəçinin tələbi
«Skan zamanı cavab kartı kadra tam düşmürsə, yenidən skan etməyi istəsin; şagirdin balını da skan zamanı dərhal versin.
Şəkillər harada saxlanacaq? (Google Drive qovluğu: «Müəllim köməkçisi KSQ blank»).»

## Mövcud vəziyyət (kod auditi)
- `ksq_scan.find_cards` QR-ı tapır, cavab zonasını QR-a görə afin çevirmə ilə kəsir (`crop_zone`).
- **Problem:** zona şəklin kənarından çıxanda `fillcolor=255` ilə ağ doldurulur. Kartın bir hissəsi kadrda yoxdursa
  həmin suallar «boş» oxunur və şagirdə 0 bal yazılır – səssiz səhv.
- Kamera (`scanCamera.tsx`) yalnız «✓ Ad» göstərir. Bal fonda, süni intellekt oxuyandan sonra yalnız siyahıda görünür.
- Şəkillər: kəsilmiş zona JPEG kimi `get_storage()` (baza, `db:` açarı) ilə saxlanır, 60 gündən köhnələri gecə silinir.

## Qərarlar
1. **Tam kart yoxlaması (server, `crop_zone`):** zonanın 4 küncü şəkil koordinatlarında hesablanır. Biri şəkildən
   `EDGE_MM = 2` mm-dən çox kənara çıxırsa, kart **saxlanmır**. Cavab `problems[]`-də `kind: 'partial'` olur və mesaj
   gedir: «Kart kadra tam düşməyib – bütün kartı çərçivəyə salıb yenidən çəkin». Köhnə oxunuş toxunulmaz qalır.
2. **Dərhal bal (kamera):** yükləmə cavabındakı `found[].scan_id` ilə kamera hər 2 saniyədən bir (90 saniyəyədək)
   `GET /api/exam-scans/{ta}/{exam}` sorğusu göndərir. Kart oxunanda göstərir: «Ad — 72 bal (14/20)», yoxlanmalı xana
   varsa «· yoxlayın: N». Süni intellekt açarı yoxdursa – «bal: açar yoxdur, siyahıdan əl ilə». Növbəti kartı çəkmək
   gözləmədən mümkündür; son nəticələr kameranın altında siyahıda (son 5).
3. Səs/vibrasiya: uğurlu kartda qısa vibrasiya (`navigator.vibrate(60)`), «yenidən çək» halında iki dəfə.
4. **Şəkillərin saxlanması:** indiki kimi tətbiqin bazasında (Neon). Kəsiklər 60 gün saxlanır, ballar və oxunuş
   həmişəlik qalır. Google Drive-a avtomatik köçürmə üçün serverə Google hesabına giriş lazımdır. Bunu Claude öz
   üzərinə götürmür (açar/şifrə). Təklif olunan yol:
   müəllimin öz Drive-ında Google Apps Script veb-tətbiqi (qovluğa yazan 20 sətirlik skript). Onun URL-i
   Tənzimləmələrə yazılır, server hər kart şəklini ora göndərir. İstifadəçi razılıq versə – ayrıca mərhələ.
5. Bütün yeni mətnlər AZ/EN/RU (`tt()`).

## Yoxlama
- pytest: kənara çıxan zona → `partial`, tam zona → kəsik. `test_ksq_scan.py`.
- `npm run build`; Render deploy statusu.

## Əlavə tələblər (13.10.2026, eyni gün)
- **Bir blank – bir dəfə:** qəbul edilmiş kart (xətasız) təkrar göndərilsə qəbul edilmir (`already[]`, bal dəyişmir, süni intellekt
  pulu getmir). Yenidən skan – yalnız səhv olanda (status `error`) və ya müəllim kamerada «Yenidən skan et» basanda (`replace=true`).
  Kamera bu sessiyada qəbul edilmiş QR-ı avtomatik təkrar çəkmir.
- **KSQ auditi (29/28 sual):** bazada 4 çap olunmuş KSQ-nın (X b, X c, X e, XI a – 76 variant) hamısında 30 sual, açar,
  mətn və şəkil (42 şəkil, hamısı açılır) tamdır. Səbəb çapdadır: `ksqPrint.fit()` şəkillər yüklənməmiş ölçürdü, sonra şəkillər
  sualları `overflow:hidden` altına itələyirdi – 1-ci səhifədə suallar kəsilirdi (istifadəçi: «вопросы обрываются в первой странице»).
  Düzəliş: şəkillərin yüklənməsi gözlənilir; sığmırsa şrift 7 pt-yə, şəkillər 16 mm-ə qədər kiçilir, yenə sığmırsa son suallar
  arxa üzə keçir; arxa üz sığmırsa – qırmızı və adlar; köhnə qaydanın kəsəcəyi vərəqlərin siyahısı göstərilir (yenidən çap).
  Variant və QR dəyişmir – yenidən çap olunan vərəqin kartı etibarlıdır.
- Skanda sual sayı variantdan götürülür (10–30): kartdakı xanalar, oxunuş və bal (`n`/100) variantın öz sual sayına görədir;
  kamera nəticəsi «düz/cəmi» variantın sual sayı ilə göstərilir.
- **Test bazası yaddaşı:** viktorina dəyişəndə tam yenidən oxunuş Render 512 MB-ı aşırdı (12.10 və 13.10 14:05 – Render
  məktubu). İndi: fayllar 20-lik hissələrlə, mətnlər yaddaşda saxlanmır, hər 10 fayldan bir bazaya yazılır (proses ölsə davam
  edir), Chromium səhifəsi hər 40 fayldan bir təzələnir; yarımçıq «running» proses başlayanda bağlanır.
