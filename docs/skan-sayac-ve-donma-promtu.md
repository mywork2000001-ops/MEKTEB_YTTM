# Ardıcıl skan: «2 kart – Göndərildi 4» və «bal hesablanır yazıb donur» (13.10.2026)

## Şikayət (müəllim)
1. «İki kart çəkdim, altda “Göndərildi: 4” yazır.»
2. «Cabbarlı Kamal Mənsur oğlu – “bal hesablanır” yazıb donur.»

## Diaqnoz (canlı sayt, 13.10.2026 ~19:20 Bakı)
| # | Fakt | Mənbə |
|---|---|---|
| 1 | X c KSQ-1: 2 skan, hər ikisi **qiymətləndirilib** (Cabbarlı 33,5; Ələkbərli 34). Kart oxunub – donan kameranın ekranıdır | `GET /api/exam-scans/3/4` |
| 2 | Açar 1: `400 – models/gemini-2.5-flash is no longer available to new users` (Google yeni hesablara 2.5-i vermir) | `POST /api/ai/scan-keys/1/test` |
| 3 | Açar 2: `429 – quota exceeded` | test |
| 4 | Açar 3–5 işləyir; açar 3 bu gün 3 kart oxuyub (2 şagird → bir kart **iki dəfə** oxunub) | `/api/ai/scan-keys` |
| 5 | `call_gemini` 429-da 20 s gözləyib təkrar edirdi. `_ctx.solo` thread-local idi, oxunuş isə ThreadPoolExecutor-da gedir, ona görə həmişə «tək açar» sayılıb gözləyirdi. Yoxlama modeli `gemini-2.5-pro` pulsuz kvotada 429 verir, hər kart +20…40 s | kod |
| 6 | Açar 1-in xətası `AiError` deyildi, açar dincə qoyulmurdu: **hər kart** əvvəl açar 1-ə gedirdi | kod |
| 7 | «Göndərildi» sayğacı hər uğurlu yükləməni sayırdı, əvəzetmələr də daxil. «Yenidən skan (köhnəni əvəz et)» açıq olanda eyni kartın təkrar çəkilişi köhnəni əvəz edir, **yenidən oxudur** (kvota) və sayğacı artırır | kod |
| 8 | Ekranda «bal hesablanır» – bu, **köhnə kameranın** mətnidir. Telefonda deploy-dan əvvəl açılmış səhifə yenilənməyib (SPA). Yeni versiyanı görmək üçün səhifəni yeniləmək lazım idi, interfeys bunu bildirmirdi | müşahidə |

## Qərarlar
### A. Gemini modelləri (köhnəlməyə davamlı)
- Standart modellər Google-un «ən son» ləqəbləridir: `gemini-flash-latest` (oxunuş), yoxlama – `gemini-flash-lite-latest`
  (fərqli model, pulsuz kvotada var; Pro pulsuz kvotada 429 verir). Siyahıda `gemini-pro-latest` və 2.5 modelləri də qalır.
- **Avtomatik model keçidi**: 400/404 «no longer available» / «not found» / «not supported» xətalarında:
  - Google-un təklif etdiyi model («use models/X») götürülür, yoxdursa – eyni ailənin `-latest` ləqəbi;
  - bir dəfə təkrar edilir;
  - seçim açar+model üçün yadda saxlanır (növbəti kartlar birbaşa düzgün modelə gedir).
- `thinkingConfig` qəbul olunmursa (yeni nəsil modellər), parametrsiz bir dəfə təkrar edilir.
- Gündəlik plan və rəy (`ai.complete`) üçün də eyni model keçidi işləyir.
- Model xətası alternativdən sonra da qalırsa → `ai:model`: açar 10 dəqiqə dincə qoyulur və növbəti açar işləyir.
  Tənzimləmələrdə «model əlçatan deyil» göstərilir.

### B. Gözləmə yox – növbəti açar
- 429-da 20 saniyəlik yuxu **ləğv edilir**: açar dincə qoyulur, kart həmin anda növbəti açarla oxunur. Tək açar varsa,
  kart gözləyir və növbəti dövrədə oxunur.
- Yoxlama oxunuşu (B, C, D) limitdədirsə, səssiz keçilir: əsas oxunuş kifayətdir, kart gecikmir.

### C. Təkrar oxunuşdan qorunma (kvota)
- Server: `replace=true` olsa belə, eyni şagirdin kartı **son 90 saniyədə** qəbul edilibsə, təkrar sayılır
  (`already`), oxunmur. Ancaq açıq **«↻ Bu kartı yenidən çək»** (`force=true`) bu qoruma olmadan əvəz edir.
- Kamera: «Yenidən skan» rejimində bu sessiyada qəbul edilmiş şagird avtomatik çəkilişlə təkrar göndərilmir.

### D. Sayğac
- «Qəbul edildi: N şagird» – sessiyada **fərqli şagird** sayı. Əvəzetmə ayrıca göstərilir: «əvəz edildi: K».
  «qalıb: N şagird» saxlanılır.

### E. Kamera heç vaxt «donmur»
- Nəticə gözlənərkən sorğu 10 dəqiqəyədək davam edir (əvvəl 5). Overlay-də həmişə «↻ Yoxla» düyməsi var.
  30 saniyədən sonra «Keç – sonra oxunsun» çıxır.
- Oxunuş 60 saniyədən uzun çəkərsə, səbəb göstərilir: hansı açar limitdədir, və ya «oxunuş növbədədir».

### F. Köhnə versiya xəbərdarlığı
- Tətbiq açıq qalanda hər 5 dəqiqədə bir və pəncərəyə qayıdanda `/` yüklənir, cari `assets/index-*.js` ilə müqayisə
  olunur.
- Fərq varsa, yuxarıda banner çıxır: **«Yeni versiya hazırdır – Yenilə»**. Kamera açılanda yoxlama dərhal edilir.
- Bunun məqsədi müəllimin telefonunda köhnə kameranın qalmamasıdır.

### G. Mətnlər – AZ/EN/RU.

## Yoxlama
- pytest:
  - Gemini 400 «no longer available» → təklif olunan modelə keçid;
  - `thinkingConfig` xətası → parametrsiz təkrar;
  - 429 → yuxu yoxdur, növbəti açar;
  - 90 saniyəlik təkrar qoruması və `force`.
- `npm run build`, deploy.
- Canlı: 5 açarın testi; bir kart → bal ≤ 30 saniyədə.

---

## Deploy-dan sonra canlı yoxlama (13.10.2026 ~20:00)
- Açar 1: «model tapılmadı» artıq yoxdur, keçid işləyir. Amma Google yeni model üçün **503 «high demand»** qaytarır
  (müvəqqəti yüklənmə).
- Səhv: `GEMINI_FIX` **bütün açarlar üçün ortaq** idi. 2.5-in hələ işlədiyi açarlar (3–5) da yüklənmiş yeni modelə keçdi və
  hamısı 503 verdi.

### Düzəliş H – model seçimi açar üzrə, 503 – ehtiyat model
- `GEMINI_FIX` açarı = (açarın izi, model). Hər açar öz işləyən modelini saxlayır.
- 503 / «UNAVAILABLE» / «overloaded» / «high demand» – bir dəfə **eyni açarda ehtiyat model** sınanır, ardıcıllıq belədir:
  `gemini-flash-latest → gemini-2.5-flash → gemini-flash-lite-latest → gemini-2.5-flash-lite` (cari və köhnəlmiş modellər
  atlanır). Yenə 503 olarsa → `ai:busy`: açar 60 s dincə, növbəti açar.
- Plan və rəy (`ai.complete`) üçün də eynidir.

## Əlavə tələb: «Müəllimdə uşağın cavabının qarşısında sistemin (testin) düz cavabı da olsun»
- Skan → şagird → xana şəbəkəsi: hər xanada **şagirdin cavabı (redaktə olunur)** və onun qarşısında **«✓ düz: X»**
  (variantın açarı, `key_value`).
  - Səhv cavab qırmızı fonda, düz cavab yaşıl görünür.
  - Ləğv edilmiş və ⊘ suallar boz göstərilir.
- API: `GET /api/exam-scans/{ta}/{exam}` → hər skanda `keys: {slot: düz cavab}` (yalnız müəllim görür).
- Mətnlər AZ/EN/RU.
