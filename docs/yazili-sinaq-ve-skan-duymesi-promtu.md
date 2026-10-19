# Yazılı test / sınaq / imtahan (hər sinifdə, fərdi də) + ümumi çap forması + hər yerdən «📷 Skan» · promt (19.10.2026)

Birləşdirir: bu fayl + docs/ferdi-yazili-imtahan-promtu.md (fərdi sinifdə xəta yox idi – sadəcə test/sınaq üçün kağız rejimi
və cavab kartı yox idi, müəllim imtahanı onlayn keçirdi). Rəqəmlərin dəyişməsi – docs/reqem-variantlari-promtu.md.

## İstifadəçi tələbi
1. İstənilən testi / sınağı / imtahanı **yazılı** təyin etmək: vərəq + QR-li cavab kartı + açar – məktəb və fərdi siniflərdə, plansız da.
2. Sınaqlar üçün **ümumi çap forması** (DİM üslubunda bir cavab vərəqəsi), hər sınaqda eyni görünüş.
3. Skan üçün hər dəfə Jurnala girməmək – tətbiqin **aşağısında daimi «📷 Skan» düyməsi**.

## Mövcud vəziyyət (kod)
- Kağız kart + skan yalnız KSQ/BSQ: `ExamVariant` → `variants/print`, `api/exam_scans.py`, `domain/ksq_scan.py`,
  oxuyucu `domain/ksq_reader.py` (A–E dairələri, açıq sualda 8 xana, Claude API).
- Mövzu testi / sınaq yalnız onlayndır (`OnlineTask`, `TaskAttempt`, `TestBatch`).
- QR imzalıdır və hər şeyi daşıyır: `ksq_card.qr_payload(exam_id, student_id, code)` → skanda sinif/imtahan seçmək lazım deyil.

## Rol
Baş mühəndis + qiymətləndirmə metodisti. Mövcud KSQ kart/skan/oxuyucu mexanizmini **təkrar istifadə et**, yeni oxuyucu yazma.

## A. Yazılı təyinat (test, sınaq, sərbəst yazılı iş)
- Test təyin edəndə **«Necə yazırlar»**: ○ Onlayn ○ Yazılı (kağız) ○ İkisi də
  (EN «Online / On paper / Both», RU «Онлайн / Письменно (на бумаге) / Оба»).
- Variant rejimi: «hamıya eyni» (DİM sınağı) · «hamıya eyni, rəqəmlər fərqli» · «hər şagirdə fərqli suallar».
- **Sərbəst yazılı iş** (KSQ/BSQ deyil): plan tələb olunmur – müəllim mövzu və ya bank fayllarını seçir, 5–30 sual, 100 bal,
  istənilən tarix; fərdi məkanda da işləyir (`has_summative` və yarımil şərti yalnız KSQ/BSQ üçün qalır).
- Nəticə testin öz nəticəsinə düşür (Testlər → Nəticələr, sinif müqayisəsi, reytinq); jurnala yalnız «jurnala yaz» seçilibsə.
  «İkisi də»: onlayn və yazılı bal yanaşı, fərq ⚠ (KSQ-dakı kimi).
- Texniki: kart/skan `exam_id`-ə bağlıdır → yazılı test üçün `Exam` yazısı (`kind`: `TEST` | `SINAQ` | `YI`;
  `online_task_id` / `batch_id`). `ExamVariant`, `ExamScan`, apelyasiya, «köçürmə şübhəsi – yeni variant» dəyişmədən işləyir.
  Fərdi məkan məxfiliyi qalır (docs/ferdi-sinif-promtu.md). Miqrasiya – istifadəçi razılıq verdi (19.10.2026).

## B. Ümumi sınaq cavab vərəqəsi (çap forması)
Bir A4, bütün sınaqlarda eyni quruluş – yalnız say dəyişir (sınaqdan götürülür):
1. **Başlıq:** məktəb / fərdi məkan adı, sınağın adı və №, fənn, sinif, tarix; sağda QR və variant kodu (iri).
2. **Şagird:** ad soyad (çap olunmuş) + imza xətti; boş forma üçün – ad və kod üçün əl ilə yazı xanaları.
3. **Test hissəsi:** 1–N, hər sətirdə A B C D E dairələri, 2–3 sütunda; nümunə «düzgün qaralama ● / səhv ⊗ ✓».
4. **Açıq (kodlaşdırılan) cavablar:** hər sual – 8 kvadrat xana (`0–9 - , / ;`), yuxarıda nümunə «-2,5» xanalarda.
5. **Həlli yazılan suallar** (DİM-də yazılı açıq): şagird həlli ayrıca vərəqdə / sual kitabçasında yazır; kartda hər sual üçün
   **«Müəllim balı»** dairələri `0 · ¼ · ½ · ¾ · 1` (sınağın bal qaydasına görə) – müəllim yoxlayıb qaralayır, skan onu da oxuyur.
6. **Alt hissə:** «Yekun bal» (skan doldurur), müəllim imzası; künclərdə 4 qara oriyentir kvadratı (əyri şəkil düzəlişi).
- Rejimlər: **adlı** (hər şagirdə QR + variant) və **boş forma** (QR-də yalnız imtahan; skanda şagird siyahıdan seçilir).
- Sual kitabçası ayrıca çap olunur (2 sütun, KaTeX); «hamıya eyni» rejimində sinifə bir kitabça + hər şagirdə kart.
- Dil: forma AZ, istəyə görə RU/EN (sınaq dilinə görə; rus bölməsi şagirdləri üçün). Çap ölçüsü – qara-ağ, toner qənaəti.
- Mövcud KSQ kartı da bu forma ilə eyniləşdirilir (bir şablon, `print.ts` + backend kart quruluşu).
- Oxuyucu: `ksq_reader` slot növləri genişlənir – `mcq`, `open`, `score` (müəllim balı dairələri); prompt və test nümunələri əlavə.

## C. Daimi «📷 Skan» düyməsi
- Müəllim interfeysində hər səhifədə: kompüterdə sağ-aşağı üzən düymə, telefonda alt paneldə.
- Pəncərə: «Şəkil çək» (kamera) / «Fayl yüklə» (şəkillər, PDF; bir şəkildə bir neçə kart). Ardıcıl skan – pəncərə bağlanmır.
- `POST /api/scans/any`: QR → imtahan + şagird → müəllimin öz imtahanıdırmı (deyilsə 403) → mövcud skan axını.
  QR yoxdur/oxunmur → «Şagird və imtahanı seçin» (son 7 günün imtahanları yuxarıda).
- Nəticə elə pəncərədə: «Əliyev Ə. – Sınaq-3 · 78 bal → 4 ✓», şübhəli xana sarı – toxun, düzəlt.
- Düymədə nişan: çap olunub, nəticəsi olmayan imtahan sayı. Şagird/admin interfeysində düymə yoxdur.

## D. Mətnlər, keyfiyyət
- Bütün yeni mətnlər AZ/EN/RU (`t()` / `tt()`, `i18n.ts`); şagirdə görünən server mesajları da.
- İcra ardıcıllığı: C (miqrasiyasız) → A → B → canlı yoxlama. Hər addımda əvvəl test, sonra kod.

## Qəbul meyarları
- Yazılı mövzu testi və sınaq (məktəb və fərdi sinif) → çap HTML: kitabça + hər şagirdin kartı (QR) + açar → `scans/any` → nəticə.
- Kart: test dairələri, 8 xana, müəllim balı dairələri oxunur; boş forma – əl ilə şagird seçimi ilə qəbul olunur.
- `scans/any` başqa müəllimin QR-ini rədd edir; mövcud KSQ skan və kart testləri keçir.
- `pytest` (aid testlər), `npm run build` uğurlu; Chrome-da 1396×663 və telefon ölçüsü; Render deploy success.
