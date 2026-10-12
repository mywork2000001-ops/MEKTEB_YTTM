# Qalan işlər — vahid promt (12.10.2026, audit + qərarlar)

**Rol:** baş mühəndis. **Layihələr:** Müəllim köməkçisi (bu repo), Sinaqlar və viktorina (`Claude/Projects`), EduHub (ayrı repo).
**Hər mərhələdə qayda:** uğursuz test → düzəliş → `pytest` → `npm run build` (tsc -b) → brauzer (390 px + 1280 px, AZ və RU) →
commit → push → **Render deploy statusu `success`** (gh api deployments) — yalnız bundan sonra «hazırdır» deyilir.
Hər yeni mətn AZ/EN/RU. Rəsmi sənədlər AZ.

## Prioritet sırası
| № | İş | Niyə bu sırada |
|---|---|---|
| 1 | A — yoxlamalar və serverin sağlamlığı | sayt işləməsə, qalanı mənasızdır |
| 2 | B — KSQ/BSQ-nin tamamlanması | ilk KSQ-lər yaxındır |
| 3 | C — rus dili (müəllim + server + tarixlər) | rusdilli şagird/müəllim |
| 4 | D — jurnal və siyahıların səliqəsi | gündəlik iş |
| 5 | E — viktorina saytında 100 ballıq sistem | ayrı repo |
| 6 | F — Sinaqlar dalğa 2–4 | həftəlik axın |

## A. Yoxlamalar və server
- **A1. Fon işlərinin nəticəsi** (tidy, şagird birləşdirmə, sertifikat tidy, kart oxunuşu). Render loqunu müəllim görmür.
  **Qərar:** Tənzimləmələr → Admin → «Son fon işləri» bölməsi: AuditLog-dan son 20 fon işi (nə vaxt, nə etdi, xəta). Qeyri-müəyyən
  birləşdirmələr («ambiguous») siyahı və «Birləşdir» düyməsi ilə.
- **A2. Limitlər (~15.10.2026):** Neon compute saatları, Render 750 saat, yaddaş (512 MB).
  **Qərar:** kart şəkilləri serverdə açılmazdan əvvəl ≤ 2400 px-ə kiçildilir (yaddaş zirvəsi); bir yükləmədə ≤ 40 fayl qalır;
  yükləmə fonda növbə ilə (eyni anda 1). Admin panelində «Resurslar»: baza ölçüsü, fayl ölçüsü (`file_blobs`), bu ay kart sayı.
- **A3. Saxlama müddəti:** kart kəsikləri 60 gün sonra avtomatik silinir (promt §5 — hələ edilməyib). Gecə fon işi.

## B. KSQ / BSQ
- **B1. Redaktə, silmə, onlayn keçirmə** — `docs/ksq-redakte-onlayn-promtu.md` (hazır promt).
  **Qərar (onlayn):** rejim imtahan səviyyəsində «Kağız / Onlayn / Hər ikisi»; «Hər ikisi»ndə müəllim şagird üzrə seçir
  (məs. xəstə şagird evdən onlayn). Onlayn variant = həmin şagirdin kağız variantı (eyni suallar, eyni bal) → ədalət.
- **B2. Variantlara baxış və tək sualı dəyişmək** (promt §2 sonu). Dəyişəndə təkrarsızlıq + 20% sinifarası qayda yenə yoxlanır;
  çapdan sonra dəyişsə — xəbərdarlıq «vərəqi yenidən çap edin».
- **B3. Xərc sayğacı:** Claude cavabındakı `usage` (input/output token) skan qeydinə yazılır; Admin → «Claude: bu ay N kart, ≈ X $».
  **Qərar:** aylıq limit (standart 600 kart/məktəb); limit dolanda kartlar «gözləyir» qalır, ehtiyat yol (idxal) işləyir.
- **B4. Real foto dəqiqliyi:** müəllim 3 vərəq çap edir, şagird kimi doldurur (fərqli əl yazısı, qələm/karandaş), 20 foto
  (işıq, bucaq). Hədəf: dairələr ≥ 98 %, açıq xanalar ≥ 95 %. Nəticəyə görə: kartda xana ölçüsü, model təlimatı, LOW həddi.
  **İstifadəçidən lazım:** fotolar + Claude açarı (Tənzimləmələr → Süni intellekt → Anthropic).
- **B5. Şablon suallarının tərcüməsi:** 20 parametrli şablon mətni hələ yalnız AZ → `{az, ru, en}` (rusdilli şagirdin vərəqi).
- **B6. Planda olmayan KSQ üçün mövzu aralığı:** plan yoxdursa variant yaratmaq olmur. **Qərar:** müəllim mövzuları əl ilə seçə bilsin
  (perspektiv plandan siyahı, çoxseçimli).

## C. Rus dili
- **C1. Müəllim tətbiqi (mərhələ 3):** Bu gün, Jurnal (gündəlik), Testlər və sınaqlar, KSQ/BSQ, Siniflər, Tənzimləmələr — bütün
  görünən mətnlər `t()`. **Qərar:** müəllimin dili `user.language`; rəsmi çaplar (jurnal, plan) AZ qalır.
- **C2. Server mesajları (mərhələ 4):** **Qərar:** backend dəyişmir — `api.ts`-də `message()` server mətnini `tt()`-dən keçirir;
  tez-tez çıxan ~60 xəta mətni lüğətə. Şagird portalının bildirişləri artıq server tərəfdə dildədir.
- **C3. Tarixlər və aylar:** `azDT` hazırda həmişə AZ ay adları verir («oktyabr») → istifadəçinin dilinə görə (RU: «октября»);
  rəsmi çaplarda AZ.
- **C4. Avtomatik yoxlama `tools/check-ru.cjs`:** şagird və müəllim səhifələrində RU rejimində Azərbaycan hərfli sətirləri sayır
  (bu sessiyada istifadə edilən skript repoya); hər böyük dəyişiklikdən sonra.

## D. Səliqə
- **D1.** «Testlər və sınaqlar» siyahısında filtr zolaqları (Hamısı/Açıq/Gözlənilir/Bağlanıb, Mövzu/Tarix, dövr) → açılan siyahılar
  (Nəticələr kimi «lsel» paneli) — bütün tətbiqdə eyni görünüş.
- **D2.** Jurnal → «Jurnal səhifəsi» (cədvəl) telefonda: ad sütunu sabit, üfüqi sürüşmə yalnız cədvəldə.
- **D3.** Müəllim «Bu gün» ekranı: bu günün dərsləri → bir toxunuşla həmin dərsin jurnalına (`/journal?date=…&p=…`).

## E. Viktorina saytında 100 ballıq sistem
- `Claude/Projects/viktorina.html` + EduHub `lib/viktorina/grade.ts` hələ «düz/cəmi» sayır. `docs/yuz-balliq-sistem-promtu.md`
  qaydası ilə (növ × çətinlik balları, cəmi 100, 30/60/80 şkalası). O repo qaydaları: `check-tests.cjs`,
  `check-viktorina-import.cjs`, `viktorina-grade-parity.ts` (iki tətbiqdə eyni bal).

## F. Sinaqlar
- **Dalğa 2:** 2025/26 arxivi (OTK 28.12, 25.01, 01.02, 22.02; Güvən 01.02, 22.02; VIII OTK; Eyler «buraxılış sınaq 2» 9/10/11).
- **Dalğa 3:** XI Təkrar №1–5, 85-6, S. Abdullayev.
- **Dalğa 4:** Ümumi sınaq 1–20 — **əvvəl istifadəçidən soruşulur**.
- Hər dalğa: spec → `make-sinaq.cjs` → `catalog-add.py` → build → `check-sinaqlar.cjs` + `check-viktorina-import.cjs` → push.

## G. İstifadəçinin qərarı lazım olan suallar
1. OBM sınağı hansı sinifdir (indi XI)?
2. Reytinqə düşmək üçün iştirak həddi (məs. testlərin ≥ 50 %-ni yazıb)?
3. Claude açarını kim daxil edəcək (admin bir dəfə — hamı üçün)?
4. KSQ onlayn rejimi standart olaraq: Kağız (tövsiyə) və ya Hər ikisi?
5. Dalğa 4 (Ümumi sınaq 1–20) lazımdırmı?
