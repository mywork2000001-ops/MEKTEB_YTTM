# KSQ/BSQ: süni intellekt xətaları ekranda və onlayn yazı (13.10.2026)

## Tələb
1. OpenRouter balansı bitəndə hər kartın altında üç dildə uzun mətn çıxırdı. Bu səliqəsiz və anlaşılmazdır.
   Xəta bir dəfə, müəllimin dilində, nə etmək lazım olduğunu deyərək göstərilməlidir. Növbəti kartlar boş yerə göndərilməməlidir.
2. Kağız vərəq olmadan, kağızı itən və ya dərsdə olmayan şagird KSQ/BSQ-ni **onlayn** yazmalıdır. Bunun üçün
   şagirdin **öz variantı** (eyni suallar, eyni açar) istifadə olunur, bal eyni jurnala yazılır.

## Rol
Sən bu layihənin baş mühəndisisən: FastAPI + SQLAlchemy (backend), React + TS (frontend), Render + Neon.
Mövcud axınları təkrar yazmırsan, onlara qoşulursan: test ekranı (portal), kart qiymətləndirməsi (`exam_scans.apply`).

## Qərarlar
### A. Süni intellekt xətası
- `ksq_reader._ai_error`: 402 / «credit» → `ai:credit`, 401/403 → `ai:key`, 429 → `ai:rate`. Aylıq limit dolubsa → `ai:limit`.
  Kartda yalnız **kod** saxlanır.
- `ai:credit`, `ai:key`, `ai:limit` olduqda `read_pending` dövrü dayanır. Qalan kartlar `pending` qalır, sorğu getmir.
- `GET /api/exam-scans/{ta}/{exam}` → `ai_error` (gözləyən kartlardan birincinin kodu). Interfeys bir xəbərdarlıq qutusu
  göstərir (AZ/EN/RU), kart sətrində `ai:` kodu göstərilmir.
- Mətnlər:
  - `ai:credit` – balans bitib, openrouter.ai-də artırın, kartlar gözləyir və sonra özü oxunacaq.
  - `ai:key` – açar səhvdir.
  - `ai:rate` – çox sorğu, bir az sonra özü davam edəcək.
  - `ai:limit` – aylıq limit dolub (admin artıra bilər).

### B. Onlayn KSQ/BSQ (`api/ksq_online.py`, miqrasiya `e7a9c1d3f5b8`)
- `online_tasks.exam_id`. Hər şagird üçün ayrıca `OnlineTask(kind='ksq', student_ids=[sid])`, suallar = `ExamVariant.questions`.
- Mövcud test ekranı istifadə olunur: tam ekran, taymer, avtomatik saxlama, vaxt bitəndə avtomatik təhvil.
- Təhvil (`tasks.finalize`) → `record()`: cavablar oxunuşa çevrilir (`mcq` indeks → hərf), `ExamScan(read_by='online')`,
  `apply` → `ExamScore`. Kağız skanı varsa, köhnə oxunuş tarixçəyə keçir.
- Şagirdə bal **göstərilmir**: təhvil cavabı `ksq: true`. Tapşırıq «Nəticələr»də yoxdur, nəticəni imtahan kimi müəllim açır.
- Onlayn KSQ müəllimin «Tapşırıqlar» siyahısında, formativ analitikada, səviyyə diaqnostikasında və sual tarixçəsində
  **sayılmır**.
- API:
  - `GET  /api/ksq-online/{ta}/{exam}` – şagirdlər, status (`none/waiting/open/doing/done/missed`), kağız/onlayn, bal.
  - `POST /api/ksq-online/{ta}/{exam}` – göndər. Parametrlər: `student_ids` (yoxdursa – nəticəsi olmayan hamı),
    `opens_at`, `window_hours`, `duration_min`, `shuffle`, `resend`. Yazmağa başlamış şagirdə toxunulmur.
  - `POST /api/ksq-online/{ta}/{exam}/cancel` – yalnız başlamamış şagirdlər üçün.

### C. Müəllim ekranı (`Exams.tsx`, «Kağız variantlar» → **5. Onlayn yazı**)
- Ayarlar: müddət (dəq), açılış (indi / tarix-saat), pəncərə (saat), sual sırası qarışsın.
- Şagird siyahısı: ad, status rəngi, bal, «kağız» / «onlayn» nişanı, seçmək üçün qutu.
- Düymələr:
  - «Nəticəsi olmayanlara göndər».
  - «Seçilənlərə göndər».
  - «↻ Yenidən göndər» (seçilənlər, `resend`).
  - «Geri götür».
- Skan siyahısında onlayn nəticə 💻 nişanı ilə görünür, şəkil yoxdur. Xanalar redaktə və ⊘ ilə idarə olunur.
  «Diqqətli oxu» onlayn nəticə üçün gizlədilir.
- Şagird ekranı: təhvildən sonra «Təhvil verildi – nəticəni müəllim açacaq».
- Bütün yeni mətnlər AZ/EN/RU (`i18n.ts`).

## Yoxlama
- `npm run build` (frontend), `python -m compileall`, pytest (`test_ksq_scan.py`).
- Render deploy + miqrasiya. Canlı yoxlama: bir şagirdə 5 dəqiqəlik onlayn KSQ → təhvil → jurnalda bal, skan siyahısında 💻.

### D. Kartın oxunuşu üçün Google Gemini (AI Studio) – istifadəçi tələbi
«Skan üçün API olaraq Gemini Google AI Studio da seçilə bilsin.»
- Tənzimləmələr → «Süni intellekt» → **Google Gemini** + AI Studio açarı (aistudio.google.com/apikey, pulsuz kvota).
  Seçim ayrıca yoxdur: müəllimin, sonra adminin seçdiyi provayder kartları da oxuyur.
- `ksq_reader.call_gemini`: `generateContent`, şəkil `inline_data`, `functionDeclarations` submit_card,
  `functionCallingConfig.mode = ANY`, `temperature 0`, düşünmə: Flash – 0, Pro – 128 token.
- Modellər: əsas – müəllimin seçdiyi `gemini-*` (standart `gemini-2.5-flash`). Açıq cavabların müstəqil ikinci oxunuşu
  `gemini-2.5-pro` ilə gedir (əsas Pro-dursa – Flash). Səsvermə və böyüdülmüş sütunlar dəyişmir.
- Xətalar:
  - 429 (dəqiqəlik pulsuz limit) – 20 saniyə gözləyib bir dəfə təkrar edilir, sonra `ai:rate` (kart gözləyir).
  - 400 «API key not valid» və 401/403 → `ai:key`.
- `read_by = gemini…`, aylıq sayğac (admin) Gemini oxunuşlarını da sayır.
- Test: `test_gemini_call_parsing`.
