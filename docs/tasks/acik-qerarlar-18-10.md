# Açıq qərarlar – 18.10.2026 (Rəhbərin qərarları, istifadəçi tam icazə verdi)

## Q1. Altmövzu adının RU/EN tərcüməsi (şagird cavab kartı) — MİQRASİYASIZ
Qərar: `BankFile.label`-ə sütun əlavə edilmir. Adlar viktorina.html-dən yalnız AZ gəlir (439 ad, p004 xaric).
- `backend/app/bank_labels.json`: `{"<AZ ad>": {"ru": "...", "en": "..."}}` – tam AZ ad açar kimi.
- `backend/app/bank_labels.py`: `label_ml(name, lang) -> str` (json bir dəfə yüklənir, lru_cache; tapılmasa – AZ; `az` – dəyişməz).
  Açar tapılmasa, `"<rəqəm>. "` prefiksini ayırıb qalanını da yoxla (prefiks saxlanır).
- `portal.py` `exam_card_view`: `q['topic'] = label_ml(q['topic'], user.language)` (ref pop-dan sonra). Müəllim görünüşü dəyişmir.
- Test: `backend/tests/test_bank_labels.py` – ru/en/az/naməlum ad/prefiks.
- Yeni adlar bankda görünəndə AZ qalır (zərərsiz); json-u sonra genişləndirmək olar.

## Q2. Onlayn ekranda slot №-si — DƏYİŞİKLİK YOX
Səbəb: onlayn ekranda sıra `shuffle` ilə qarışır; ekranda 1..N təbii sıra qalır. Apelyasiya nömrə yazmaqla deyil,
kartdakı sətrin «⚖ Apelyasiya» düyməsi ilə verilir – slot avtomatik düzgün gedir. İmtahan zamanı əlavə nömrə şagirdi çaşdırar.

## Q3. Programs.tsx (müəllim) – AZ/EN/RU
`frontend/src/pages/teacher/Programs.tsx`: bütün görünən mətnlər `t()`/`tt()`; lüğət `frontend/src/i18n.ts` (təkrar açar yox!).
Server mesajları/proqram adları (məlumat) tərcümə olunmur. Yoxlama: `npm run build` (frontend).

## Q4. Ehtiyat nüsxə (db-backup.yml) – istifadəçinin girişi lazımdır
- Drive qovluğu «Backup silmek olmaz» hazırda **«linki olan hər kəs – redaktor»** → istifadəçi əl ilə «Məhdud» etməlidir (API ilə silmək imkanı yoxdur).
- Sirlər (NEON_BACKUP_URL, BACKUP_PASSPHRASE, MK_GDRIVE_*) Google/Neon girişi tələb edir – istifadəçi ilə birlikdə, ayrıca sessiyada.

## Q5. XI peşə KSQ-1 (P013) – 18 sual (yalnız 1-ci bölmə)
Səbəb: KSQ yalnız keçilmiş bölməni yoxlamalıdır; 2-ci bölmədən sual əlavə etmək ədalətsizdir. Faiz/bal 18 üzərindən.
Exam id 7 sual sayı canlıda yoxlanır; artıq 18-dirsə – dəyişiklik yoxdur.

## Q6. Tarixə bağlı (indi yox)
~25.10 Neon compute saatları; 27.10 `exam_*_backup_20261013` cədvəllərinin silinməsi – yalnız istifadəçinin «OK»-u ilə.

Yoxlama: `pytest tests/test_bank_labels.py` + aid testlər, `npm run build`, push → Render deploy success.
