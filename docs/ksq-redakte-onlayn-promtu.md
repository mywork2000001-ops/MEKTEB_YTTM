# KSQ / BSQ: redaktə, silmə və onlayn keçirmə (istifadəçi tələbi, 12.10.2026 — promt; «icra et» gözləyir)

**Obyekt:** `backend/app/api/exams.py` (Exam, ExamScore, ExamVariant), `api/exam_scans.py`, `api/tasks.py` + `portal.py` (onlayn test
mexanizmi), frontend `pages/teacher/Exams.tsx`. Hər yeni mətn AZ/EN/RU; yoxlama `npm run build` + pytest + brauzer; deploy statusu yoxlanır.

## 1. Redaktə
- KSQ/BSQ sətrində «✏ Redaktə»: tarix, başlıq, yarımil; sual sayı (variantlar yaradılmayıbsa və ya nəticə yoxdursa).
- Variantlarda tək sualı «Dəyiş» (təkrarsızlıq qaydası yenə yoxlanır), açarı düzəlt → həmin sualı alan şagirdlər avtomatik
  yenidən hesablanır (skan → `apply`), jurnalda audit qeydi.
- Nəticə yazılıbsa: tarix/başlıq dəyişir, slot planı dəyişmir (xəbərdarlıq).

## 2. Silmə
- «🗑 Sil» — `ConfirmName` (adı yazaraq təsdiq). Nəticə/skan varsa: əvvəl xəbərdarlıq, sonra Exam + ExamScore + ExamVariant +
  ExamScan (+ fayllar) birlikdə silinir; audit. Planlı KSQ silinəndə plan sətri qalır («Hazırla» yenidən görünür).
- Yalnız öz dərsi (own_assignment); admin hamısını.

## 3. Onlayn keçirmə
- KSQ/BSQ yaradılarkən rejim: **Kağız** | **Onlayn** | **Hər ikisi** (şagird seçir / müəllim şagird üzrə təyin edir).
- Onlayn: hər şagirdin öz variantı (ExamVariant) onlayn test kimi verilir — `OnlineTask(kind='ksq', student_ids=[sid])` və ya
  variant snapshot-u ilə xüsusi start; vaxt pəncərəsi, müddət; sualların qarışdırılması; tam ekran, tab dəyişmə qeydi.
- Nəticə eyni yola düşür: `ExamScore.points/item_marks` (100 bal, 30/60/80 şkalası) — kağız və onlayn bir jurnalda.
- «▶ Davam etsin» və «↻ Yenidən göndər» onlayn KSQ üçün də işləyir; nəticələr yalnız müəllim açanda göstərilir.

## 4. Testlər
- Redaktə: nəticəli imtahanda slot planı dəyişmir; açar düzəlişi → skan balları yenidən hesablanır.
- Silmə: bütün asılı qeydlər silinir, başqa sinfin imtahanına toxunulmur; yad müəllim 403.
- Onlayn: şagird yalnız öz variantını görür, cavab vərəqdəki kimi qiymətləndirilir, ExamScore yazılır; kağız + onlayn qarışıq sinif.
