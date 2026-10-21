# Kart: tətbiqdə dəftər yoxlaması – alt mövzuların icrası (AI, 21.10.2026)

**Sifarişçi:** müəllim: «dəftərdən yoxlama imkanı» (sinif şagirdlərinin dəftərləri – alt mövzular icra olunubmu).
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Metodika:** `docs/defter-yoxlama-promtu.md` (statuslar, şərh qaydası – eyni).
**Qaydalar:** CLAUDE.md – AZ/EN/RU (`t()`, `i18n.ts` yalnız Grep); `npm run build` + aid pytest; miqrasiya – yalnız yeni nullable sütun.

## Mövcud
- `Material(kind='task', needs_submission)` → şagird `MaterialSubmission` (text + bir fayl: dəftər şəkli/PDF) göndərir;
  müəllim `grade`/`comment` yazır (api: materials/submissions – Grep et).
- Görmə (vision) AI artıq var: `app/domain/ksq_reader.py` – müəllimin öz açarı (Gemini / OpenRouter / Anthropic), `call_gemini`,
  `call_openrouter`, `call`, model köhnəlməsi/503 ehtiyatları. Açar/parametrlər – KSQ skanı hansı ayarı oxuyursa, eyni.
- Alt mövzular: bank suallarının alt mövzu nişanları (`app/bank_labels.py`, subtopic) – mövzu üzrə.

## 1. Backend
- `app/defter.py`: `check_notebook(cfg, images: list[bytes], topic: str, subtopics: list[str], lang: str) -> dict`.
  Promt `docs/defter-yoxlama-promtu.md`-dən (sistem mətni modulda, qısa): JSON çıxışı
  `{legible: bool, items: [{subtopic, status: 'done'|'partial'|'missing'|'illegible', wrong: [str], note}], summary_az,
    student_comment: {az, ru, en}}`. Status dəyəri yalnız bu 4-dən biri; parse səhvi → 502 mesajı (AZ/EN/RU).
  Şəkil: jpeg/png birbaşa; PDF – ilk 3 səhifə JPEG-ə (PyMuPDF artıq istifadə olunursa; yoxdursa yalnız şəkil).
  Vision çağırışını ksq_reader-dən təkrar yazma – ümumi kiçik köməkçi çıxar və ya mövcud funksiyanı yenidən istifadə et.
- Miqrasiya: `material_submissions.ai_check` (JSON, nullable) – nəticə + `checked_at`, `model`.
- API (müəllim, öz sinfi):
  - `GET /api/materials/{mid}/subtopics` – materialın sinfi + başlığı/mövzusu üzrə təklif olunan alt mövzular (bank nişanları;
    tapılmasa – boş, müəllim özü yazır).
  - `POST /api/materials/{mid}/submissions/{sid}/check` body `{subtopics: [..], topic?}` → bir dəftəri yoxla, `ai_check`-ə yaz.
  - `POST /api/materials/{mid}/check-all` body `{subtopics}` → fonda bütün yoxlanmamış göndərişlər (ardıcıl, xəta olan keçilir),
    `GET …/check-all` – vəziyyət (neçəsi hazır).
  - `GET /api/materials/{mid}/check.csv` – şagird;alt_movzu;status;sehv;serh (müəllim üçün, AZ).
- Şagird: öz göndərişində yalnız `student_comment[lang]` və alt mövzu statusları görünür (səviyyə sözləri yox – `LEAK` qaydası).

## 2. Frontend (müəllim – göndərişlər siyahısı olan səhifə)
- Düymə «🤖 Dəftəri yoxla» (hər göndərişdə) və «🤖 Hamısını yoxla»; dialoqda alt mövzular siyahısı (təklif + redaktə, sətir-sətir).
- Nəticə: cədvəl şagird × alt mövzu (✅ 🟡 ❌ ❔), sonda hər alt mövzunun icra faizi; «CSV yüklə».
- Müəllim nəticəyə baxıb `comment`-ə «şərhi köçür» edə bilər (avtomatik qiymət QOYULMUR).
- Şagird səhifəsində (Materials) – şərh öz dilində. Bütün mətnlər `t()` + `i18n.ts` (EN/RU).

## 3. Testlər – `tests/test_defter.py`
AI çağırışı monkeypatch: JSON parse və status normallaşması; API icazələri (başqa müəllim – 404); `ai_check` yazılır; check-all
xətada davam edir; CSV sütunları; şagird cavabında yalnız öz dilində şərh. Aid pytest + tam pytest `-q | tail`; `npm run build`.

## Çıxış
Worktree budağında commit; main, push, deploy, miqrasiya yoxlaması – Rəhbər.

## Əlavə 21.10 – əl ilə rejim (məktəbdə müəllim dəftərə gözlə baxır)
- `Materiallar → 📓 Dəftər`: bütün sinif × alt mövzu cədvəli (telefonda üfüqi sürüşmə, sabit ad sütunu); xanaya toxunuş: boş → ✅ → 🟡 → ❌ → boş,
  🟡-də qısa şərh (səhv nömrələri). Dərhal yazılır (`PUT /api/materials/{mid}/mark`), «saxla» düyməsi yoxdur.
- Cavab göndərməyən şagirdə də işarə qoyulur: cavabsız (mətnsiz/faylsız) `MaterialSubmission` yaranır, «təhvil verib» sayılmır.
- Saxlama – AI ilə eyni `material_submissions.ai_check`; `source: 'manual'|'ai'` (sətir səviyyəsində). Əl işarəsi AI-ni üstələyir,
  AI təkrar yoxlama əl işarələrinə toxunmur.
- İtki: hər alt mövzunun icra faizi (✅ / sinif) + `GET /api/materials/{mid}/check.csv`. Şagird yalnız ÖZ statuslarını görür.

## Qeyd (Rəhbər)
PDF dəstəklənmir (PyMuPDF yoxdur) – yalnız JPG/PNG/WebP/GIF; real AI çağırışı canlıda yoxlanmalı; Gemini model ehtiyatları (call_gemini) təkrar istifadə olunmayıb.
