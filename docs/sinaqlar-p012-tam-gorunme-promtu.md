# Promt: «Sınaqlar» və P012 sınaqları – Seriya və Sınaq imtahanlarında tam görünsün (TAİM-siz)

## Məqsəd
Viktorina-dakı (`Documents/Claude/Projects/viktorina.html`) iki mənbənin **bütün** faylları Müəllim köməkçisində
iki yerdə tam görünsün və seçilə bilsin:

| Mənbə (bank `source_key`) | Qovluq | Fayl sayı |
|---|---|---|
| `sinaqlar` – «🗂 Sınaqlar (illər üzrə)» | `Projects/Sinaqlar/2022, 2025, 2026` | 34 (`SINAQLAR_LESSONS`) |
| `p012` – «P012 · Riyaziyyat 11 Buraxılış» | `Projects/P012_Riyaziyyat_11_Buraxilis` | 40 (ÜSİ-1…20, MSİ-1…20) |

Yerlər:
1. **Sınaq imtahanları → Sınaq seriyası** (`frontend/src/pages/teacher/ExamSeries.tsx`, `backend/app/api/exam_series.py`).
2. **Sınaq imtahanları → Yeni sınaq** (`OnlineExams.tsx` → `BankPicker` in `TaskEditor.tsx`).

**TAİM (P004) lazım deyil** – hər iki yerdən çıxarılsın.

## Tapılan səbəblər (06.10.2026 yoxlanıb)
Viktorina canlıdadır (34 sınaq siyahıda, fayllar 200 qaytarır), P012-nin açıq (`type:"input"`) sualları da artıq
`normalizeAny` ilə idxal olunur. Problem Müəllim köməkçisi tərəfindədir:

1. **Təsnifat** – `backend/app/bank/classify.py`: `SOURCE_KIND`-də `sinaqlar` yoxdur, ona görə növ addan çıxarılır.
   34 fayldan **10-u «movzu»** olur və seriyada (`f.kind == 'sinaq'` filtri) görünmür:
   - OBM mövzu sınaqları (5): «OBM — Natural ədədlər (Variant A)», «Çoxluqlar», «Adi və onluq kəsrlər»,
     «Nisbət. Tənasüb. Faiz», «Həndəsənin əsas anlayışları»;
   - Riyaziyyat RF — Buraxılış MS1…MS5 (2022) – `_SINAQ` regex-i `MSİ` tanıyır, `MS1` yox.
   Bundan başqa OBM və RF fayllarında sinif yoxdur (`grades=[]`).
2. **Seriya mənbələri** – `ExamSeries.tsx:16` `SOURCES`-da `['p004', 'P004 · TAİM']` var – çıxarılmalıdır.
3. **Siyahı tam açılmır** – `BankPicker`-də bölmə siyahısı `maxHeight: 220` (`TaskEditor.tsx` ~165), seriyada
   `maxHeight: 320` (`ExamSeries.tsx` ~122): 34 + 40 fayl kiçik qutuda sürüşür, «hamısı görünmür» təəssüratı yaranır.
   Sınaq imtahanlarında `BankPicker` `kinds` almır – P004 (əgər admin aktiv edibsə) və mövzu mənbələri də
   qarışıq görünür.

## Ediləcəklər
### 1. Təsnifat (backend)
- `classify.py`: `SOURCE_KIND['sinaqlar'] = 'sinaq'` (bu qovluqda hər fayl 3-cü tərəf sınağıdır; «yekun»/«diaqnostik»
  qaydaları əvvəlki kimi üstündür). `_SINAQ`-a `\bMS\d` əlavə et (ehtiyat üçün).
- Sinifsiz fayllar: RF «Buraxılış» → `[11]`; OBM – adda sinif yoxdur, `[]` qalsın (bütün siniflərdə görünür) və ya
  `Sinaqlar/docs/SINAQLAR_METHODOLOGY_PROMPT.md`/fayl başlığından sinif tapılırsa onu yaz. Təxmin etmə.
- Mövcud bazanı yenilə: sinxronizasiya təsnifatı yalnız fayl yenidən oxunanda tətbiq edir, ona görə Alembic
  miqrasiyası (və ya `/api/bank/sync?force=true`) ilə `meta_locked=false` olan `sinaqlar` fayllarına `apply()` işlət.
  Admin əl ilə kilidlədiyi fayllara toxunma.

### 2. Sınaq seriyası
- `SOURCES`-dan P004-ü çıxar; qalanlar: Sınaqlar, P012, P009.
- Backend `/api/exam-series/files` və `_sync_new`: `p004` mənbəyini rədd et (köhnə seriyada qalıbsa sükutla at).
- Fayl siyahısı: mənbə və il üzrə qruplaşdır (Sınaqlar → 2026/2025/2022, P012 → ÜSİ/MSİ), hər qrupda «hamısını seç»,
  sayğac «seçilib N / cəmi M». Qutu hündürlüyü `min(60vh, …)`, telefonda tam en.
- Sinif filtri seçiləndə sinifsiz fayllar da görünsün (indiki `_grade_ok` kimi) və boz «sinif göstərilməyib» nişanı alsın.

### 3. Sınaq imtahanları (yeni sınaq)
- `OnlineExams.tsx`-də `BankPicker`-ə mənbə süzgəci ver: yalnız `sinaqlar`, `p012`, `p009` (+ «yekun»/mövzu bölmələri
  lazımdırsa – indiki legend-ə uyğun ayrıca «digər mənbələr» düyməsi ilə). P004 göstərilməsin.
- Bölmə siyahısı hündürlüyü `60vh`, il/qrup başlıqları, axtarış qalır. `BankPicker`-in digər istifadəçiləri
  (TaskEditor) dəyişməsin – yeni parametr (`sources?: string[]`, `tall?: boolean`) ilə.

### 4. Yoxlama
- Lokal: seed + `uvicorn` 8801 (bax yaddaş «local-browser-audit»), bank sinxronu ilə real viktorina-dan oxut;
  Seriyada «Sınaqlar» seçiləndə **34**, «P012» seçiləndə **40** fayl görünməlidir; P004 heç yerdə yoxdur.
- Yeni sınaqda OBM «Natural ədədlər» və RF MS3 seçilib göndərilə bilir.
- `pytest` (yeni test yazma – yalnız mövcudları işlət), `npm run build` (`tsc -b`).
- Commit + push, sonra canlıda (`Ayarlar → Test bazası → Yenilə (force)`) sayları təsdiqlə.
