# Köçürmə şübhəsi – cavabları sil, yeni variant ver, yenidən çap et (14.10.2026)

## Rol və məqsəd
Sən «Müəllim köməkçisi»nin baş mühəndisisən. Müəllim KSQ/BSQ-da şagirdin köçürdüyündən şübhələnirsə, bir düymə ilə:
1. şagirdin cavabları (kağız kartın skanı, onlayn cəhd) və jurnaldakı balı silinsin;
2. ona **tam yeni variant** verilsin – eyni sual sayı, slot-slot eyni növ (test/açıq), çətinlik və bal, amma
   sinifdəki heç bir variantda, eyni imtahanın başqa siniflərində və şagirdin əvvəlki testlərində olmayan suallar;
3. yalnız **onun vərəqi** (və açarı) yenidən çap olunsun.

## Həll
- API: `POST /api/exams/{ta}/{exam}/variants/{student_id}/retake` `{note?}` (`backend/app/api/exams.py` `retake`).
  - sual seçimi – `ksq_variants.pick_one` (mövzu aralığı perspektiv plandan, `_prepare`); sual çatmırsa 409, heç nə dəyişmir;
  - kod dəyişir: `KSQ1-05 → KSQ1-05R1 → R2…` – köhnə vərəqin QR/kartı artıq qəbul olunmur (`exam_scans.apply` kodu yoxlayır);
  - silinir: `ExamScan`, `ExamScore`, onlayn KSQ tapşırığı və cəhdi; kəsik şəkli storage-da qalır, köhnə bal/kod audit jurnalına;
  - `printed_at`, `unprinted` sıfırlanır.
- Çap: `GET …/variants/print?students=5` – yalnız seçilən şagirdlərin vərəqi və açarı (yalnız onlar «çap olunub» işarələnir).
- Şübhəlilər: 2-ci addımda «🚩 Köçürmə şübhəsi ilə yeni variant verilənlər» siyahısı (ad, yeni kod, tarix, silinmiş bal, neçə dəfə) və şagird düyməsində 🚩 – mənbə audit jurnalı (`_suspects`).
- UI: İmtahanlar → KSQ → «Kağız variantlar» → 2-ci addım → şagirdə toxun → «🚩 Köçürmə şübhəsi – yeni variant» →
  təsdiq (iki addım) → «🖨 Yeni vərəqi çap et» / «🔑 Müəllim açarı». Mətnlər AZ/EN/RU.
- Onlayn yazmaq lazımdırsa: 5-ci addımda şagirdi seçib yenidən göndər (yeni variant gedir).

## Qəbul meyarları
- `tests/test_ksq_variants.py::test_retake_after_cheating`: bal və skan silinir, bütün suallar yeni, slot quruluşu eyni,
  kod `R1`, sonra `R2`; çap yalnız bir vərəq.
- `npm run build` uğurlu; deploy statusu success.
