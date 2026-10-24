# Tapşırıq: Metodik düzəlişlər (audit 24.10.2026)
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)
- İcraçı: `kodcu` (Agent tool, bu sessiyadan); miqrasiya (M8) və canlı yoxlama — Rəhbər
- Budaq: `metodik/<etap>` (hər etap ayrıca worktree, birləşdikdən sonra silinir)
- Mənbə: `docs/metodik-audit-2026-10-24.md` (M1–M14 — orada səbəb və qərar)

## Məqsəd (müəllimin dili ilə)
Şagird səhvini dərhal görsün və üzərində işləsin, müəllim sinfin tipik səhvini bir baxışda tapsın; testlər təkrarlanmasın,
qiymətləndirmə şəffaf olsun. Rəsmi KSQ/BSQ qaydaları dəyişmir.

## Ümumi qaydalar (hər etap)
- Yeni/dəyişən hər UI mətni AZ/EN/RU: `t('…')` / `tt('…')`, lüğət `frontend/src/i18n.ts` (təkrar açar = xəta). Server mesajı şagirdə görünürsə — `_L` ilə 3 dil.
- Test seçimi/təyini ilə bağlı hər şey **yalnız** `backend/app/plan_tests.py` (RESOLVERS / POST_STEPS / opts) — CLAUDE.md «tək mühərrik».
- KSQ/BSQ şkalası, yarımil formulu, BSQ qaydaları — **toxunma**.
- Defolt davranış dəyişirsə — yalnız aşağıda yazılan hallarda; qalan hər şey müəllim seçimi ilə (defolt = indiki).
- Hər etapın sonunda: aid pytest + `npm run build` (frontend; `tsc -b`). `npx tsc --noEmit` YOXLAMIR.

---
## Etap 1 (P1) — dərhal fayda, miqrasiyasız
### 1.1 M1 — formativ testdə cavablar təhvildən sonra
1. `backend/app/plan_tests.py:~440` (`show_answers='after_close'`): mövzu testi (KSQ/BSQ/sınaq/diaqnostika deyil) **və** bağlanma = `NO_DEADLINE` olduqda `show_answers='after_submit'`. Müddətli testlər — dəyişmir.
2. Enjin `after_submit`-i tanıyırsa yoxla (`models.py:617`, `api/portal.py` cavab/izah açılışı); tanımırsa — portalda: attempt `submitted_at` varsa və task `show_answers=='after_submit'`-dirsə izah və düzgün cavab göstərilsin.
3. Müəllim formasında (OnlineExams/AssignTests) seçim «Cavablar: təhvildən sonra / bağlanandan sonra» görünsün, defolt yuxarıdakı qaydaya görə.
- Test: `backend/tests/test_plan_tests.py` — müddətsiz mövzu testi → `after_submit`; müddətli → `after_close`; KSQ üçün test yaranmır (köhnə test qalır).

### 1.2 M2 — distraktor təhlili
1. `backend/app/test_stats.py`: hər sual üçün seçilmiş variantların paylanması (`TaskAttempt.answers` + `order` ilə orijinal indeksə çevir; şuffle nəzərə alınsın!), boş cavab ayrıca. «Populyar səhv»: eyni yanlış variantı seçənlər ≥30% və ≥3 şagird.
2. API: mövcud «Sual təhlili» endpoint-inə (`Reports.tsx:47` hansını çağırırsa) `options: [{label, n, pct, correct}]`, `popular_wrong` əlavə et.
3. Frontend «Sual təhlili»: hər sualın altında üfüqi zolaqlar (A–E, boş), düzgün variant yaşıl, populyar səhv narıncı + «Dərsdə izah edin» nişanı.
- Test: yeni `backend/tests/test_distractors.py` — 5 şagird, qarışıq sıra, paylanma düzgün; `input` tipli sualda paylanma yox (yalnız düz/səhv).

### 1.3 M3 — «Səhvlər üzərində iş»
1. Model dəyişmədən: `OnlineTask`-dan törəmə task (mövcud `task_groups`/retake mexanizmi varsa ondan istifadə) — yalnız şagirdin səhv/boş sualları, `kind` mövzu testi kimi, **jurnala yazılmır** (`task_journal.py`-da istisna), müddətsiz, `after_submit`.
2. Şagird portalı: təhvil + izahdan sonra düymə «Səhvlər üzərində iş» (bir dəfə). Bank imkan verirsə səhv sualın əvəzinə eyni mövzudan analoq (`plan_tests.analog_pick` məntiqi), yoxdursa eyni sual.
3. Müəllimə: «Sual təhlili»/şagird hesabatında «Səhv üzərində iş: 3/5 düzəldi».
- Test: jurnal qiyməti dəyişmir; ikinci dəfə başlatmaq olmur (409, mesaj 3 dildə); KSQ/BSQ/sınaq üçün düymə yoxdur.

### 1.4 M4 — auto_tests təsviri
`backend/app/auto_tests.py:1-6` docstring-i real defoltlara uyğunlaşdır (taymer yox, müddətsiz, cavablar M1-ə görə). UI-da «Avtomatik mövzu testi» izahı (Siniflər/plan tənzimləmələri) eyni mətn, 3 dildə. Davranış dəyişmir.

### 1.5 M5 — i18n
`frontend/src/pages/student/Surveys.tsx:36` «Cavab ver» → `tt('Cavab ver')` + `i18n.ts`: `'Cavab ver': ['Answer', 'Ответить']`. Eyni faylda və `pages/student/*`-də `t(`/`tt(` olmadan qalan AZ mətnləri grep et (`>[A-ZƏÖÜÇŞĞİ][a-zəöüçşğı]` JSX), tapılanları da çevir.

**Etap 1 qəbul:** müddətsiz test təhvilindən dərhal sonra izah görünür; «Sual təhlili»-ndə paylanma; səhv üzərində iş jurnalı dəyişmir; build + pytest ok; RU/EN yeni açarlar.

---
## Etap 2 (P2)
### 2.1 M6 — formativ şkala (sinif tənzimləməsi)
`TeachingAssignment` (və ya mövcud JSON tənzimləmə sahəsi — miqrasiyasız variant üstün) `formative_scale: {3: 31, 4: 61, 5: 81}`; defolt = KSQ şkalası (`rules.py:46-59`). `api/tasks.py:48` mövzu testində `summative_grade` əvəzinə `formative_grade(points, scale)`. Qiymətin yanında səviyyə sözlə (`rules.py:7-8`: yüksək/orta/aşağı). Tənzimləmələr → Sinif: 3 rəqəm + «Defolta qaytar».
- Test: defolt şkala ilə nəticələr indiki ilə eyni (regressiya); dəyişdirilmiş şkala yalnız mövzu testinə təsir edir, KSQ-yə yox.

### 2.2 M7 — mövzu testində anti-təkrar
`plan_tests.py:_pick` (`:399-411`): həmin sinfə həmin mövzu üzrə əvvəl verilmiş sualları (sual imzası/bank id ilə — `task_groups.py` imzası) çıxar; bank çatmırsa təkrara icazə + `rows[i]['warn']='təkrar suallar: N'`. `analog_pick`-lə ortaq köməkçi funksiya çıxar (kopya yox).
- Test: `test_plan_tests.py` — ikinci təyin birincidən fərqli suallar; bank kiçikdirsə xəbərdarlıq.

### 2.3 M8 — bank sualında standart (miqrasiya — Rəhbər!)
`BankQuestion.standard: str | None`. Doldurma skripti: mövzu → plan dərsinin standartı (`models.py:317`). «Standartlar üzrə» hesabat onlayn cavabları sual standartı ilə hesablasın, yoxdursa köhnə yol (dərs). **Kodcu yalnız model + skript + hesabat yazır; miqrasiyanı canlı DB-də Rəhbər işə salır** (istifadəçi razılığı və backup).

### 2.4 M9 — uyğunluq sualında qismən bal
`api/tasks.py:37-40` `is_ok` yanında `part_score(q, ans) -> 0..1`: uyğunluq tipində düz eşlənmiş sətirlərin payı (sətir yalnız tam düz olanda sayılır), sualın çəki balına vurulur. `correct` sayı (tam düz) dəyişmir, `points` qismən. Müəllim əl düzəlişi — əvvəlki kimi tam düz/səhv.
- Test: «1:ab,2:c,3:de» üçün «1:ab,2:c,3:d» → 2/3 bal; formatlar (`1-ab`, `1:a,b`) eyni qəbul olunur.

### 2.5 M10 — «Təkrar testi» (interval təkrar)
`plan_tests.py`-a yeni növ (RESOLVER): mövzu bitəndən 14 və 42 gün sonra, sinfin həmin mövzuda ortası <60% idisə, 5–7 suallıq test (həmin mövzu(lar) bankından, M7 anti-təkrarı ilə), jurnala yazılmır, müddətsiz. Gündəlik `auto_tests` onu eyni mühərrikdən alır; sinifdə ayrıca açar «Təkrar testləri» (defolt söndürülü).
- Test: 13-cü gün yaranmır, 14-cü gün yaranır; orta ≥60% — yaranmır; ikinci dəfə yaranmır.

---
## Etap 3 (P3) — pilotdan sonra
- **M11** səviyyəyə görə sual payı (Zəif 60/30/10, Orta 30/50/20, Güclü 10/40/50 — asan/orta/çətin), 100 bala normallaşdırma; əvvəl bir sinifdə pilot.
- **M12** risk faktorları 0..1 xətti (`rules.py:81-111`), çəkilər və rəng həddləri eyni; köhnə ikili nəticə ilə müqayisə testi.
- **M13** təhvildən sonra könüllü «Nə qədər əminsən?» (3 seçim) + «Nə çətin idi?»; müəllimə sinif üzrə xülasə; qiymətə təsir yox.
- **M14** sertifikat tənzimləmələrində iki qaydanın izahı (mövzu ≥90% və seriya pillələri 31/61/81/91), məntiq eyni.

## Toxunma
`domain/rules.py` KSQ/BSQ/yarımil funksiyaları, `exam_logic.py`, apelyasiya məntiqi, `scoring.py` çəkiləri, rəsmi çap formaları (yalnız AZ).

## Kontekst (yalnız bunları oxu)
`docs/metodik-audit-2026-10-24.md`, `docs/plan-testleri-skripti-promtu.md`, `backend/app/plan_tests.py`, `api/tasks.py:30-80`,
`api/portal.py` (task/attempt hissəsi), `test_stats.py`, `task_journal.py:1-30`, `models.py:600-670`, `frontend/src/pages/teacher/Reports.tsx` (Sual təhlili), `pages/student/Tasks.tsx`.

## Cavab formatı
docs/agent-sistemi-promtu.md §7: dəyişən fayllar, test sayı (keçən/ümumi), build nəticəsi, açıq suallar.
