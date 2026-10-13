# Kart oxuyucusu: ayrıca süni intellekt bölməsi, 5 API açarı və avtomatik keçid (13.10.2026)

## Tələb (istifadəçi)
«Kart oxuyucusu üçün süni zəkada ayrıca hissə olsun. 5 API açar olsun, hamısında Google AI Studio seçimi imkanı olsun.
Limit bitəndə avtomatik dəyişsin.»

## Kontekst
- KSQ/BSQ cavab kartlarını süni intellekt oxuyur (`domain/ksq_reader.py`). Hazırda yeganə mənbə müəllimin, sonra adminin
  ümumi «Süni intellekt» açarıdır, və bu açar gündəlik planlar üçün də istifadə olunur.
- 13.10.2026: OpenRouter balansı bitdi (402). 31 kart günlərlə gözlədi, müəllim əl ilə oxumalı oldu.
- Google AI Studio (Gemini) pulsuz açar verir, amma kvotası var: dəqiqəlik (RPM) və günlük (RPD). Bir açarın kvotası bir
  sinfin kartlarına çatmaya bilər. Bir neçə açar növbə ilə işləsə, pulsuz kvota praktiki olaraq 5 dəfə artır.

## Məqsəd
Müəllim kart oxuyucusu üçün **5 ayrıca açar** daxil edir: hər birində provayder, model, açar və «aktiv» işarəsi olur.
Oxuyucu açarları sıra ilə istifadə edir. Açarın limiti, balansı bitəndə və ya açar səhv olanda **həmin anda növbəti
açara keçir**, kart gözləmir və müəllimdən heç nə tələb olunmur. Bütün açarlar tükənəndə kart gözləyir. Müəllim bunu bir
dəfə, öz dilində və hansı açarın nə vaxt bərpa olunacağı ilə birlikdə görür.

## Qərarlar
### 1. Saxlama
- `users.ai_settings.scan_keys` – ən çox 5 element: `{provider, model, key (şifrəli), on}`.
  - Yeni miqrasiya lazım deyil (JSON sahə).
  - Ümumi «Süni intellekt» parametri (`put_ai` / `del_ai`) `scan_keys`-ə toxunmur.
- Provayderlər: **Google Gemini (AI Studio)** – standart, OpenRouter və Anthropic. Hamısı şəkil oxuyur və funksiya çağırışını
  dəstəkləyir.
- Açar heç vaxt geri göndərilmir: yalnız maska (`••••abcd`). Boş sahə köhnə açarı saxlayır.

### 2. Açar hovuzu (`ksq_reader.key_pool`)
Növbə: `MK_ANTHROPIC_API_KEY` → müəllimin kart açarları (1–5) → müəllimin ümumi açarı → məktəb adminin kart açarları →
adminin ümumi açarı. Təkrar açar (eyni provayder + açar) bir dəfə sayılır.

### 3. Avtomatik keçid
- Açarın xətası AiError kodu ilə gəlir. Açar «dincə» qoyulur (yaddaşda, açarın izi – sha256, açarın özü saxlanmır):
  - `ai:rate` – dəqiqəlik limit → 65 s.
  - Gemini günlük kvota (`PerDay`) → 3 saat (kvota Sakit okean vaxtı ilə gecə yarısı yenilənir).
  - `ai:credit` – balans bitib → 6 saat.
  - `ai:key` – açar səhvdir → 24 saat.
- Kart həmin anda növbəti açarla oxunur. Əsas oxunuş (A) uğursuz olarsa, bütün kart növbəti açarla təkrar oxunur.
  Yoxlama oxunuşları (B, C, D) uğursuz olarsa, mövcud qayda qalır: jurnala yazılır, kart oxunur.
- Şəbəkə və 5xx xətası olarsa, növbəti açar sınanır, amma açar dincə qoyulmur.
- Bütün açarlar dincdədirsə:
  - Karta ən tez bərpa olunan açarın kodu yazılır, kart `pending` qalır.
  - Fon işi (`read_pending`) növbəni dayandırır, qalan kartlara sorğu getmir.
  - Növbəti dövrədə açar bərpa olubsa, oxunuş özü davam edir.
- Gemini-də 20 saniyəlik təkrar yalnız dəqiqəlik limitdə və yalnız hovuzda başqa açar yoxdursa olur.
- Sayğac: hər açarın bu gün oxuduğu kart sayı, son xətası və «dincdədir … qədər» vəziyyəti (yaddaşda).
- `read_by` = `gemini#2` (provayder + açarın nömrəsi), aylıq ümumi sayğac dəyişmir.

### 4. API (`api/scan_keys.py`)
- `GET  /api/ai/scan-keys` – 5 sətir: provider, model, maska, on, vəziyyət (`ok` / `cooldown` + `until` + `code`),
  bu gün oxunan kartlar, provayder siyahısı.
- `PUT  /api/ai/scan-keys` – `{keys:[{provider, model, api_key|null, on}] ×≤5}` (sıra – istifadə sırası). Kilidli
  tənzimləmə (`settings_unlocked`).
- `POST /api/ai/scan-keys/{i}/test` – açar kiçik bir mətn sorğusu ilə yoxlanır. Uğurlu olarsa, açar dincdən çıxarılır.
- `POST /api/ai/scan-keys/reset` – bütün dincləri sıfırla (müəllim balansı artırıb).

### 5. Interfeys (Tənzimləmələr → Süni intellekt → **«Kart oxuyucusu»**)
- Ümumi paneldən ayrı panel, 5 kart: «Açar 1 … 5».
  - Hər kartda: provayder (standart – Google Gemini · AI Studio), model (siyahıdan), açar (şifrə sahəsi), «Aktiv»,
    «Yoxla», «Sil».
  - Vəziyyət nişanı: ✓ hazırdır, ⏸ limit (HH:MM-ə qədər), ✕ açar səhvdir, balans bitib. Bu gün oxunan kart sayı.
  - Sıranı dəyişmək üçün ↑ ↓.
- AI Studio açarının linki (aistudio.google.com/apikey) və qısa izah olur: «Hər Google hesabı – ayrıca pulsuz kvota».
- «Dincləri sıfırla» düyməsi.
- Skan ekranında `ai_error` banneri bütün açarlar tükənəndə göstərilir və «Tənzimləmələr → Kart oxuyucusu»na yönləndirir.
- Bütün mətnlər AZ/EN/RU (`i18n.ts`).

### 6. Təhlükəsizlik
- Açarlar `secret_encrypt` ilə şifrələnir, loglarda yalnız açarın nömrəsi görünür.
- Skan şəkli yalnız seçilmiş provayderə gedir. Şəkildə şagird adı yoxdur (yalnız cavab zonası).

## Yoxlama
- pytest:
  - hovuzun sırası və təkrar açarın atılması;
  - 1-ci açar `ai:rate` → kart 2-ci açarla oxunur, `read_by` = `gemini#2`;
  - hamısı tükənib → kart `pending` + kod, növbə dayanır;
  - `put_ai` `scan_keys`-ə toxunmur;
  - açar maskalanır.
- `npm run build`, Render deploy statusu.

---

## Əlavə tələb: üç ayrı süni intellekt (istifadəçi, 13.10.2026)
«Kart oxuyucu süni zəka açarı ayrı, gündəlik planlaşdırma süni zəkası ayrı, rəy süni zəka ayrı. Audit et, icra elə.»

### Audit – süni intellekt harada işləyir (13.10.2026)
| Təyinat | Yer (backend) | Ekran | Əvvəl | İndi |
|---|---|---|---|---|
| Gündəlik plan | `lessonplans.generate` → `ai_config(user)` | Gündəlik plan → «Süni intellektlə hazırla» | ümumi açar | **«Gündəlik plan»** açarı (`ai_settings` kök sahələri – geriyə uyğun) |
| Pedaqoji rəy (nəticələr) | `results_center.make_review` | Test nəticələri → «Süni intellektin pedaqoji rəyi» | ümumi açar | **«Rəy»** açarı (`ai_settings.review`) |
| Sorğu rəyi | `surveys.make_review` | Şagird sorğusu → «Süni intellektin rəyi» | ümumi açar | **«Rəy»** açarı |
| Kart oxunuşu | `ksq_reader.key_pool` | KSQ → Skan | ümumi açar | **«Kart oxuyucusu»** – 5 açar, avtomatik keçid |
| Bağlantı yoxlaması | `POST /api/ai/test` | Tənzimləmələr | ümumi | `?purpose=plan|review` |

Aşkar edilən risklər:
1. Bir açarın kvotası və ya balansı bitəndə üç funksiya birdən dayanırdı (13.10: OpenRouter 402 → həm kartlar, həm plan).
2. `put_ai` / `del_ai` `ai_settings`-i yenidən qururdu, başqa sahələri silə bilərdi. İndi `review`, `scan_keys`,
   `header_school` qorunur.
3. Kart oxunuşu müəllimin plan açarını «gizli» istifadə edirdi, müəllim bunu görmürdü.

### Qərarlar
- `ai_config(user, purpose)`: `purpose ∈ {plan, review}`.
  - `plan` – `ai_settings` kök sahələri (köhnə saxlanmış açarlar olduğu kimi işləyir).
  - `review` – `ai_settings.review`. **Boşdursa – plan açarı ehtiyat kimi işləyir** (mövcud müəllimlərdə heç nə qırılmır).
    Interfeys bunu açıq yazır.
- `GET/PUT/DELETE /api/ai/settings?purpose=plan|review`, `POST /api/ai/test?purpose=…`. Hər təyinatın provayderi, modeli və
  açarı müstəqildir, hər birində Google Gemini (AI Studio) var.
- Kart oxuyucusu (`key_pool`):
  - Müəllimin və ya məktəb adminin **kart açarları varsa – yalnız onlar** işlənir. Plan və rəy açarına toxunulmur, kvota
    paylaşılmır.
  - Heç bir kart açarı yoxdursa, keçid dövrü üçün ehtiyat olaraq plan açarı işlənir. Skan ekranı bunu bildirir:
    «Kart oxuyucusu üçün ayrıca açar qoşun».
- Tənzimləmələr → «Süni intellekt»: bir panel, təyinat açılan siyahıdan seçilir (aşağıda «Interfeys – dəqiqləşdirmə»).
- Bütün yeni və dəyişən mətnlər AZ/EN/RU.

### Yoxlama
- pytest: rəy açarı ayrıdır (yoxdursa – plan); `put_ai(plan)` `review` / `scan_keys`-i silmir; kart açarı varsa plan açarı
  hovuzda yoxdur; 1-ci açar limitdədirsə – 2-ci açar.
- `npm run build`, deploy statusu.

### Interfeys – dəqiqləşdirmə (istifadəçi: «hamısı süni zəka hissəsində olsun, bir bölmə içində açılan siyahı ilə»)
- Tənzimləmələr → «Süni intellekt» – **bir panel**. Yuxarıda açılan siyahı «Təyinat» var:
  - 🗂 **Kart oxuyucusu** (KSQ/BSQ skanı) – 5 açar.
  - 📝 **Gündəlik plan**.
  - 💬 **Rəy** (test nəticələri və şagird sorğusu).
- Siyahının hər seçimində yanında status göstərilir: «qoşulub», «açar yoxdur – plan açarı işləyir», «N açar».
- Seçimə görə panelin içi dəyişir: plan və rəy üçün bir açar forması, kart oxuyucusu üçün 5 açar.
- Seçim yadda qalır (localStorage) və URL ilə açılır (`?tab=ai&ai=scan`). Skan ekranındakı xəbərdarlıq birbaşa
  «Kart oxuyucusu»nu açır.

### İcra və audit nəticəsi (13.10.2026)
- Backend:
  - `api/scan_keys.py`;
  - `ksq_reader.key_pool / cool / pool_error`, avtomatik keçid `_read_one` (həm adi, həm «Diqqətli oxu»);
  - `lessonplans.ai_config(user, purpose)`; `results_center` və `surveys` → `review`;
  - `exam_scans`: `ai_error` yalnız bütün açarlar tükənəndə, `scan_fallback`.
- Frontend:
  - Tənzimləmələr → «Süni intellekt»: bir panel, «Təyinat» siyahısı (Kart oxuyucusu / Gündəlik plan / Rəy);
  - skan ekranında «Kart oxuyucusunun açarları ›» linki. AZ/EN/RU.
- Qeyd: dinclik yaddaşdadır (proses üzrə). `MK_WORKERS > 1` olsa, hər proses öz dincliyini saxlayır. Bu zərərsizdir:
  ən çox bir əlavə uğursuz sorğu olur. Server yenidən başlayanda dinclik sıfırlanır.
- Testlər: `test_scan_key_pool_rotation`, `test_ai_purposes_separate`, tam dəst 308 keçdi.
