# Testlər və sınaqlar: ad siyahısı → seçəndə sinfin şagirdləri; redaktə və sil görünən yerdə

**Səhifə:** https://muellim-komekcisi.onrender.com/tests?s=sinaq (və `?s=movzu`) — `frontend/src/pages/teacher/TestsHub.tsx`,
`OnlineExams.tsx` (sınaqlar), `Tasks.tsx` (mövzu testləri); backend `app/api/exams_online.py`, `app/api/tasks.py`.
**İstifadəçi tələbi (12.10.2026):** «sınaq və testlərin adları siyahıda gəlsin, seçəndə sinif şagirdlərinin adları görsənsin
(sınağı və testi redaktə etmə, silmə imkanı olsun)».
**Qayda:** əvvəl uğursuz test → düzəliş → bütün testlər → `tsc` + `vite build` → lokal brauzer → commit → push.

## 0. İndiki vəziyyət (audit)
| | Sınaq imtahanları | Mövzu testləri |
|---|---|---|
| Siyahı | sətir — ad, siniflər, vaxt; klik → «Sınaq jurnalı» pəncərəsi | kart — ad, sinif, vaxt |
| Şagird adları | yalnız pəncərədə, «Jurnal» sekmesində | yalnız «Nəticələr / Canlı izlə» pəncərəsində |
| Redaktə | gizlidir: jurnal → «Siniflər və idarə» sekmesi → «⋯» → Redaktə (hər sinif ayrıca); **sınağın adını dəyişmək olmur** | «⋯» menyusunda |
| Sil | jurnal pəncərəsinin ən altında | «⋯» menyusunda |

Nəticə: funksiyalar var, amma müəllim tapmır — 3–4 klik dərinlikdə.

## 1. Siyahı (hər iki bölmə)
- Hər sınaq/test bir sətir: **ad** (qalın), siniflər, tarix, vəziyyət, «N/M yazıb».
- Sətirdə həmişə görünən 3 düymə: **👥 Şagirdlər** · **✏ Redaktə** · **🗑 Sil** (mobil — ikon + qısa söz).
- Sətrə (və ya «👥 Şagirdlər»-ə) klik → sətrin **altında açılır** (pəncərə yox): sinif-sinif şagird adları
  (əlifba ilə) + hər birinin vəziyyəti: «yazıb — 76%» / «yazır» / «yazmayıb» / «gözlənilir». Yenidən klik — bağlanır.
  Sinif başlığında «18/25 yazıb · orta 64%». Başqa müəllimin sinfində adlar gizli qalır (mövcud qayda — `access: own`).
- «Ətraflı jurnal →» keçidi köhnə pəncərəni açır (yer, bal, suallar, çap — dəyişmir).

## 2. Redaktə
- **Sınaq:** pəncərə — «Sınağın adı» (bütün siniflərdə birdən dəyişir; yalnız sınağı yaradan / admin), altında hər öz sinfi
  üçün «Vaxt və suallar →» (mövcud `TaskEditor`). Yeni endpoint: `PATCH /api/exams-online/{batch_id}` `{title}` —
  `TestBatch.title` + paketin bütün `OnlineTask.title`-ları; `access != 'full'` → 403; audit.
- **Mövzu testi:** birbaşa `TaskEditor` (mövcud).

## 3. Sil
- Sətirdəki «🗑 Sil» → sətrin içində təsdiq (adı yazmaqla, mövcud `ConfirmName`): sınaq — tam icazəli bütün siniflərdən,
  digər müəllim yalnız öz sinfindən (mövcud `DELETE`); mövzu testi — «Silinənlər»ə (mövcud arxiv, geri qaytarmaq olur).

## 4. Yoxlama
- Backend testi: `PATCH` adı dəyişir (paket + tapşırıqlar), başqa müəllim üçün 403, boş ad 422.
- Frontend: `tsc --noEmit`, `vite build`; brauzerdə sınaq və mövzu testi: aç-bağla şagird siyahısı, ad dəyişmə, silmə.
