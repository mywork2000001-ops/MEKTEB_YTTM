# KSQ / BSQ: 30 sual · 100 bal · hər şagirdə tam fərqli suallar · bir A4 · Claude API ilə avtomatik yoxlama

**Rol:** baş mühəndis + qiymətləndirmə metodisti. **Obyekt:** Müəllim köməkçisi — `app/models.py` (Exam, ExamScore, PlanLesson,
BankQuestion), `app/api/exams.py`, `app/domain/scoring.py` (100 ballıq qayda), `app/domain/rules.py` (`GRADE_BANDS`),
`app/scheduler.py`, frontend `pages/teacher/Exams.tsx`, `print.ts`, `pages/teacher/Settings*.tsx`.
**İstifadəçi tələbi (12.10.2026):** müəllim yalnız çap edir və skan edir; suallar avtomatik seçilir; **hər KSQ və BSQ — 30 sual,
cəmi 100 bal**; **bütün şagirdlərin sualları ciddi şəkildə fərqli** (heç bir təkrar yoxdur); cavabların çoxu açıq; kart fotosunu
**sistemdəki Claude API açarı** ilə avtomatik yoxlayır; yenidən yükləmə / «Yenilə» → yoxlama təzədən aparılır.
**Qiymət şkalası (dəyişməz, `GRADE_BANDS` artıq belədir):** 0–30 bal → **2**, 31–60 → **3**, 61–80 → **4**, 81–100 → **5**.
**Qayda:** əvvəl uğursuz test → düzəliş → bütün testlər → `tsc` + `vite build` → brauzer (real foto ilə) → commit → push.
Claude API kodu `claude-api` bələdçisinə uyğun (model ID-ləri, şəkil girişi, strukturlaşdırılmış JSON çıxışı).

## A. Audit (12.10.2026) və peşəkar qərarlar
| № | Tapıntı (kod) | Qərar |
|---|---|---|
| 1 | Plan mövzusu ↔ bank əlaqəsi yalnız P0010 fayl adına görədir (`bank/match.py`, `Matcher`); «mövcud standart uyğunlaşdırması» yoxdur | Hovuz = KSQ aralığındakı hər plan mövzusu üçün `Matcher`-in ilk 2 faylı + parametrli şablonlar |
| 2 | `diff_auto` çox sualda boşdur → fallback «test=asan, açıq=orta» — **çətin** slotlar dolmur | Slot çətinliyi **hədəfdir**: əvvəl dəqiq səviyyə, sonra qonşu səviyyə; slotun **balı sabitdir** (ədalət balla qorunur); ədalət hesabatı göstərilir |
| 3 | Açıq cavabların çoxu kartın xanalarına yazıla bilməz (`x=3`, `√2`, `π`, mətn) | Açıq slota yalnız **«kart üçün yararlı»** cavab: `-12`, `2,5`, `3/7`, `1;4` (≤ 8 simvol, yalnız `0-9 - , / ;`); qalan suallar yalnız test slotuna |
| 4 | Ciddi təkrarsızlıq: 25 şagird × 30 = 750 fərqli sual — bir mövzu+növ+səviyyə hovuzu çatmaya bilər | Ardıcıllıq: (1) slotun mövzusu → (2) KSQ aralığının başqa mövzusu (eyni növ/səviyyə) → (3) parametrli şablon → (4) yenə çatmırsa **yaratma rədd edilir** və dəqiq çatışmazlıq siyahısı. Təkrar heç vaxt |
| 5 | Barmaq izi: bankda eyni sual müxtəlif fayllarda ola bilər | Unikallıq `content_hash` + normallaşdırılmış mətn üzrə; şablonda — şablon + parametrlər |
| 6 | Keçmiş suallar: `OnlineTask.questions[*].bank_id` (onlayn test/sınaq) + əvvəlki `exam_variants` | Hər ikisi şagirdin tarixçəsi kimi istisna edilir |
| 7 | `Exam.items` + `ExamScore.item_marks` + `grade_from_points` artıq var | 30 slot `Exam.items`-ə (bal ilə) yazılır, `max_points=100` — mövcud jurnal/yarımil hesabları dəyişmədən işləyir |
| 8 | 45 dəqiqəlik dərsdə 30 sual (21 açıq) ağırdır | İstifadəçi tələbi qüvvədədir (30); kartda vaxt yazılmır, müddəti müəllim təyin edir; sonradan Parametrlərdən slot sayı dəyişə bilər |
| 9 | QR yaratmaq/oxumaq üçün paket yoxdur (`cv2`, `qrcode` yoxdur) | Yaratma — `segno` (təmiz Python, SVG); oxuma — `opencv-python-headless` (mərhələ 3); QR məzmunu HMAC imzalı (saxta kart rədd) |
| 10 | Claude SDK yoxdur | `anthropic` paketi (mərhələ 4), açar şifrələnmiş (`ai_settings` şifrələmə funksiyası təkrar istifadə) |

## 0. Müəllimin bütün işi
1. KSQ/BSQ tarixi gəlir → sistem özü variantları hazırlayır.
2. «Çap et» → sinif üçün bir PDF: hər şagirdə **bir A4 vərəq** (iki üzlü).
3. Yazdıqdan sonra kartları tətbiqdə telefonla çəkir («📷 Kartları skan et») və ya skan PDF yükləyir.
4. Bir neçə dəqiqə sonra jurnalda bal (0–100) və qiymət (2–5). Şübhəli xanalar sarı nişanla — istəsə baxır.

## 1. Test quruluşu — 30 slot, 100 bal
Bütün şagirdlərdə **eyni slot planı** (növ + çətinlik eyni) → hər slotun balı hamıda eynidir (ədalət), suallar isə fərqli.

| Slot | Növ | Çətinlik | Say | Bal (hər biri) | Cəmi |
|---|---|---|---|---|---|
| 1–5 | test (A–E) | asan | 5 | 1,5 | 7,5 |
| 6–9 | test (A–E) | orta | 4 | 2,5 | 10 |
| 10–14 | açıq | asan | 5 | 2,5 | 12,5 |
| 15–24 | açıq | orta | 10 | 4 | 40 |
| 25–30 | açıq | çətin | 6 | 5 | 30 |
| | | | **30** | | **100** |

- **Açıq — 21 sual (70%)**, test — 9 (30%). Ballar mövcud `scoring.py` qaydasından (növ × çətinlik, 0,5-ə yuvarlaq, cəmi 100) alınır
  və test yaradılanda dondurulur. Slotlar mövzu üzrə qarışıq düzülür (asandan çətinə).
- Nəticə = toplanan bal (0–100) → qiymət `summative_grade()` ilə (yuxarıdakı şkala). `Exam.max_points = 100`.
- Admin şkalanı / slot planını Parametrlərdən dəyişə bilər, amma standart budur.

## 2. Sualların avtomatik seçilməsi — ciddi təkrarsızlıq
- **Mövzular:** perspektiv plandan — KSQ: əvvəlki KSQ-dan bu tarixə qədər keçilmiş dərslər; BSQ: yarımilin bütün mövzuları.
  Slotlar mövzulara saat payına görə paylanır (hər mövzuya ən azı 1 slot).
- **Mənbə:** bank (`BankQuestion`, sinif + mövzu + növ + çətinlik uyğun) + **parametrli şablonlar** (`question_templates`:
  mətn şablonu, parametr diapazonları, cavab düsturu, yoxlama şərtləri — məs. tam cavab, kəsr ixtisar olunur).
- **Təkrarsızlıq (mütləq qayda):**
  1. Sinifdə heç iki şagirdin heç bir sualı eyni deyil (mətn barmaq izi ilə, parametrli sualda — eyni parametrlər dəsti də yox).
  2. Bir şagirdin 30 sualı arasında da təkrar yoxdur.
  3. Şagirdə əvvəl verilmiş suallar (onlayn test, sınaq, əvvəlki KSQ/BSQ) seçilmir.
  4. Bank hovuzu çatmırsa — həmin slot parametrli şablondan doldurulur (hər şagirdə fərqli ədədlər, cavab avtomatik hesablanır).
  5. Şablon da yoxdursa — **çap bloklanır** və müəllimə dəqiq siyahı: «Kvadrat tənliklər · açıq · orta: 25 şagird üçün 14 sual var,
     11 çatmır». Səssiz təkrar heç vaxt olmur. (Çatışmayan şablonları Claude ilə hazırlamaq — §7.)
- **Ədalət yoxlaması:** hər slotda bütün şagirdlərin sualları eyni mövzu + çətinlikdə; `diff_auto` statistikası olan suallarda
  slot üzrə düzgün cavab faizi fərqi ±10%-dən çox olmamalı.
- Saxlanma: `exam_variants(exam_id, student_id, code, questions_snapshot JSON, created_at)`; çapdan sonra dəyişmir.
  Müəllim istəsə «Variantlara bax» və tək sualı «Dəyiş» edə bilər (təkrarsızlıq qaydası yenə yoxlanır).

## 3. Çap — bir A4 vərəq (iki üz)
- **Ön üz:** başlıq (məktəb, sinif, KSQ-1, tarix, şagird adı, variant kodu, «100 bal») + suallar 1–16, 2 sütun, 9,5–10 pt,
  hər sualın yanında balı («4 b»); düsturlar vektor.
- **Arxa üz:** suallar 17–30 (yuxarı ~55%) + **cavab kartı** (aşağı ~45%, qırıq xətlə kəsilir).
- **Cavab kartı:** 4 küncdə marker, **QR** (exam_id · student_id · variant · yoxlama cəmi), şagird adı (çap);
  1–9 — A–E dairələri; 10–30 — 6 simvollu xanalar (`0–9 - , / ;`), 3 sütun × 7 sətir; nümunə: «kəsr 3/7, onluq 2,5, mənfi -4».
- Sığmazsa: şrift/aralıq avtomatik kiçilir; şəkilli suallar kiçildilir; yenə sığmazsa həmin slot üçün şəkilsiz sual seçilir.
- Ayrıca: «müəllim açarı» (variant üzrə cavablar və ballar).

## 4. Claude API ilə avtomatik yoxlama
**Açar sistemdə:** admin bir dəfə daxil edir — Tənzimləmələr → «Claude bağlantısı» (şifrələnmiş saxlanır; ehtiyat — `MK_ANTHROPIC_API_KEY`).
Bütün müəllimlər üçün işləyir. «Bağlantını yoxla» düyməsi; aylıq limit və xərc sayğacı.

**Axın (fon işi):**
1. Yükləmə (şəkil / PDF, bir şəkildə bir neçə kart ola bilər) → kartlar ayrılır → **QR serverdə** oxunur → variant tapılır.
2. Markerlərə görə düzəldilir, **yalnız cavab zonası** kəsilir (adsız) → Claude-a: şəkil + gözlənilən struktur (30 slot, növ,
   xana sayı) → strukturlaşdırılmış JSON `{code, answers:[{slot, value, confidence}]}`.
   Model `claude-sonnet-5-5`; `confidence &lt; 0,85` xanalar avtomatik ikinci oxunuş — `claude-opus-5-5`.
3. **Qiymətləndirmə serverdə** (Claude yalnız oxuyur): açıq cavab — «|» variantları + normallaşdırma (boşluq, vergül↔nöqtə,
   `6/8 = 3/4`, `0,5 = 1/2`, `-4 = −4`); test — hərf. Bal = düzgün slotların balları cəmi → qiymət → `ExamScore` avtomatik yazılır.
4. Etibar ikinci oxunuşdan sonra da aşağıdırsa — bal yazılır, xana «yoxlanılmalı» nişanı alır; müəllim bir kliklə düzəldir.

**Yenidən yoxlama:**
- Eyni kart (eyni QR) yenidən yüklənəndə — köhnə oxunuş arxivə, **tam yenidən hesablama**.
- «🔄 Yenilə» → həmin imtahanın bütün kartları yenidən qiymətləndirilir (açar dəyişibsə yeni açarla); «Yenidən oxu» → şəkillər
  Claude-a təzədən göndərilir.
- Sualın açarı düzəldilsə — həmin sualı alan şagird avtomatik yenidən hesablanır; jurnalda dəyişiklik qeydi (audit).
- Ehtiyat yol (API limiti bitəndə və ya bağlantı olmayanda): `GET /api/exams/scan/pending` + `POST …/scan-import` —
  bu sessiyadakı Claude Code eyni JSON formatı ilə oxuyub göndərə bilir.

## 5. Məxfilik və xərc
- Claude-a yalnız cavab zonası (ad, sinif, məktəb yox); QR — daxili ID.
- Şəkillər 60 gün saxlanır, sonra avtomatik silinir. Xərc: 1 kart ≈ 1 sorğu (+ şübhəli xanalar üçün ikinci oxunuş).

## 6. Mərhələlər
1. Slot planı (30 slot / 100 bal) + `exam_variants` + təkrarsız generator + parametrli şablon mühərriki + testlər.
2. A4 iki üzlü çap + cavab kartı (QR, markerlər). ✅ 12.10.2026: `GET …/variants/print`, `domain/ksq_card.py` (HMAC QR), `frontend/src/ksqPrint.ts`, «🖨 Kağız variantlar».
3. Yükləmə, QR, kəsik, qiymətləndirmə, `scan-import` (ehtiyat yol dərhal işləyir).
4. Claude API (admin bağlantısı, fon işi, ikinci oxunuş, yenidən yoxlama, xərc sayğacı).
5. Telefon skan rejimi (ardıcıl çəkiliş, bulanıq/qaranlıq — «yenidən çək»).

## 7. Şablon bazası (təkrarsızlıq üçün vacib)
- Hər sinif və mövzu üçün parametrli şablonlar: hər birindən ən azı 30 fərqli düzgün variant çıxmalıdır.
- İlk dəst — Claude ilə hazırlanır (bu sessiyada), hər şablonun cavab düsturu avtomatik testlə yoxlanılır
  (100 təsadüfi parametr — cavab düsturla müstəqil həll üst-üstə düşür). Müəllim şablonu söndürə bilər.

## 8. Yoxlama
- Backend: 30 şagird × 30 slot = 900 sual — **sıfır təkrar** (mətn və parametr barmaq izi), keçmiş suallar istisna; hovuz
  çatmırsa çap bloklanır və dəqiq siyahı; ballar cəmi 100, şkala 30/60/80/100; QR yoxlama cəmi; təkrar yükləmə → yenidən
  hesablama; açar dəyişəndə avtomatik düzəliş; Claude cavabı testdə saxta (mock) JSON.
- Real: 20 foto (fərqli işıq, bucaq, əl yazısı) — test dairələri ≥98%, açıq xanalar ≥95% düzgün oxunur.
- Brauzer: çap bir A4-ə (iki üz) sığır; skan → jurnalda bal və qiymət; «Yenilə» işləyir.
