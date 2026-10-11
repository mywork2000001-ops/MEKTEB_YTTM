# Test tapşırıqları, sınaqlar və nəticələr – audit (11.10.2026)

Promt: `docs/test-sinaq-audit-promtu.md`. Yoxlanan: `api/tasks.py`, `api/exams_online.py`, `api/exam_series.py`, `api/portal.py`
(şagird testləri), `api/results_center.py`, `test_stats.py`, `certificates.py`, `domain/answers.py`; müəllim və şagird ekranları.
Üsul: kodun oxunması → hər tapıntı üçün **əvvəlcə uğursuz test** (`tests/test_api_exam_audit.py`, 5/5 uğursuz idi) → düzəliş →
bütün testlər (217 keçdi) → ayrıca test bazası ilə lokal serverdə brauzer yoxlaması (şagird XE, müəllim/admin).

## Tapıntılar və düzəlişlər

| № | Ciddilik | Səhv | Nəticəsi | Düzəliş |
|---|---|---|---|---|
| 1 | **Yüksək** (bütövlük) | «Bağlandıqdan sonra» cavablar sinfin öz bağlanma vaxtına görə açılırdı | Bir neçə sinfə fərqli vaxtla verilən sınaqda erkən bağlanan sinfin şagirdi düzgün cavabları (Cavablara bax, Səhvlərim, çap) **başqa sinif hələ yazarkən** görürdü | `review_opens_at`: paketin ən gec bağlanması; bütün şagird endpointləri |
| 2 | **Yüksək** (çökmə) | Sınaq panelində bir sinfin «Redaktə»si sualları yalnız həmin sinifdə dəyişirdi | Paketdə sual sayı fərqli → sınaq jurnalı, reytinq, şagird nəticələri, bildirişlər **500 xətası**; sual analizi və reytinq fərqli testləri müqayisə edirdi | Sınaq sualı paketin bütün siniflərində birlikdə dəyişir; hər hansı sinifdə başlayıblarsa – 409; jurnal fərqli sual sayına davamlı |
| 3 | Orta | Cərimə yalnız sınaq jurnalında tətbiq olunurdu | Eyni sınaq üçün şagird «Nəticələrim»də iki fərqli faiz (66,7% və 58,3%), siyahıda «orta» cərimə­siz, sertifikat faizi və yeri cərimə­siz | Vahid `exam_score` (bal, faiz, düz/səhv/boş): jurnal, siyahı, şagird (açıq və bağlı), Test nəticələri, sertifikat |
| 4 | Orta (qayda) | Sınaqda şagirdə qiymət göstərilirdi | «Tapşırıqlar» siyahısında «2/3 → 4», təhvil bildirişində qiymət – halbuki sınaq qiymətə təsir etmir | Sınaqda qiymət `null`, əvəzində faiz |
| 5 | Aşağı | Boş açıq suala müəllim «Düz say» basanda | Səhv sayı **−1** | Boş + düz sayılan sual boş sayılmır |
| 6 | Aşağı | Cavab ölçüsü məhdud deyildi | Bir cavabda istənilən uzunluqda mətn bazaya yazılırdı | Açıq cavab ≤ 500 simvol, ≤ 100 sual (422) |
| 7 | Aşağı | Eyni anda iki «Başla» | Unikal açar xətası → 500 | Eyni cəhd qaytarılır |
| 8 | Aşağı (UI) | «təkrar» nişanının regex-i (`\s`, `\(` əvəzinə `s`, `(`) | «… (təkrar)» adlı sınaq nişansız qalırdı | Regex düzəldildi |
| 9 | Aşağı (UI) | Hələ açıq sinfin yazmamış şagirdləri jurnalda «yazmayıb» | Müəllim yanlış nəticə çıxara bilərdi | «gözlənilir» (Test nəticələri ilə eyni) |

Köhnə test (`test_timed_task_flow`) plandan kənar testə qiymət gözləyirdi – sistemdə bu test sınaqdır, gözlənti yeniləndi.

## Brauzer yoxlaması (lokal, ayrıca test bazası)
- Sınaq «cərimə 4», X e (bağlanıb) + X c (açıq). X e şagirdi: 2 düz, 1 səhv.
- Şagird: Tapşırıqlar → Sınaqlar: «2/3 · 58,3%», «Cavablara bax» yoxdur; `review` – 403; Nəticələrim: sınaq kartı 58,3% və
  onlayn testlər 58% – eyni; Səhvlərim boş. Konsolda xəta yoxdur.
- Müəllim: siyahıda «orta 58,3%»; təkrar sınaq təsdiqsiz 409, təsdiqlə «(təkrar)» + nişan; jurnal: 1,75 bal → 58,3%, cərimə «4 səhv = −1».

## Yaxşı vəziyyətdə olanlar
Cavab açarı `start`-da göndərilmir; taymer server vaxtı ilə, 10 san. güzəşt; bank API-si yalnız işçilərə; başqa müəllimin şagird
adları gizli; başqa məkan – 404; AI rəyində adlar kodlanır; təkrar sınaq və başqa sinfin sınağı təsdiq tələb edir.

## Qalan risklər / tövsiyələr
1. **Bildirişlər** (hər 5 dəq.) hər bağlanmış sınaq üçün bütün paketi hesablayır. Sınaq sayı artdıqca yük artır – 512 MB-lıq
   pulsuz Render instansında bu, yaddaş təzyiqinə əlavə olunur (bax: aşağı). Növbəti addım: nəticə keşi.
2. «Təhvil verdikdən dərhal sonra» seçimi bir neçə sinifli sınaqda cavabları digər siniflərə ötürə bilər – müəllimə xəbərdarlıq.
3. Sınaq sertifikatı sinfin vaxtı bitəndə verilir (paket hələ açıq ola bilər) – yer sinif üzrədir, cavab sızmır.

## Render (11.10.2026, Gmail)
- **19:43 – «muellim-komekcisi exceeded its memory limit»**: instans yaddaş limitini (pulsuz plan – 512 MB) aşıb, avtomatik
  yenidən başladılıb. Metrikada həmin saatdan əvvəl trafik zirvəsi var. Pulsuz planda yaddaş qrafiki yoxdur.
- **«Your free Render database expires soon: muellim-db» – 28.10.2026-da dayandırılır**, sonra güzəşt müddətindən sonra silinir.
- Render: 14.10.2026 05:00 (Bakı) planlı infrastruktur işləri.
