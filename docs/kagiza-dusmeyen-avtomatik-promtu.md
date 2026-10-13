# Kağıza düşməyən suallar – təzə skanlarda avtomatik (13.10.2026)

## Tələb (müəllim)
«Şagirdlərin bir hissəsində 30 test əvəzinə əksik test görünür. Bunu şagirdlər üçün nəzərə al: çap vərəqində 30 testə görə
bal verilib, ancaq sual sayı 28, 29-dur.»

## Kontekst
- 13.10.2026-dan əvvəlki çapda (`printed_at < PRINT_FIX_AT`) şəkillər ölçmədən sonra yükləndiyi üçün vərəqin sonundakı 1–2
  sual kağıza düşmürdü. Kartda isə 30 xana var idi və bal 30 suala görə hesablanırdı.
- Mövcud həll – «⊘ Kağıza düşməyən suallar» düyməsi (docs/ksq-dusmeyen-suallar-promtu.md):
  - brauzer köhnə çapın düzümünü təkrarlayıb kəsilmiş sualları təxmin edir (`estimateOldCut`);
  - server «kəsilmiş ∩ kartda boş» sualları `lost` (⊘) edir və bal qalan suallar üzrə 100-ə miqyaslanır.
- Problem:
  - bütün skanlar silinib (təzədən skan), `lost` qeydləri də silinib;
  - düymə əl ilədir; müəllim hər skandan sonra basmalıdır, unudulsa şagird cəzalanır.

## Qərarlar
1. **Təxmin serverdə saxlanır**: `exam_variants.unprinted` (JSON, slot siyahısı) – miqrasiya.
   - Yalnız köhnə çap olunmuş variantlar üçün; yeni çapda heç nə kəsilmir.
   - `POST /exam-scans/{ta}/{exam}/lost-auto` təxmini həm saxlayır, həm mövcud skanlara tətbiq edir.
2. **Avtomatik tətbiq**: `apply()` (hər oxunuş / yenidən hesablama) skanda `lost` hələ təyin olunmayıbsa
   (`None` – müəllim əl ilə dəyişməyib), `lost = unprinted ∩ boş cavab` təyin edir.
   - Kəsilmiş sayılan, amma cavabı yazılmış sual sayılır (görünürmüş).
   - Müəllimin ⊘ düzəlişlərinə toxunulmur.
3. **Brauzer təxmini özü işləyir**: skan bölməsi açılanda, vərəqlər köhnə çapdırsa və təxmin hələ saxlanmayıbsa, təxmin fonda
   bir dəfə hesablanıb saxlanır. Müəllimdən heç nə tələb olunmur. Düymə əl ilə yenidən hesablama üçün qalır.
4. **Görünürlük**:
   - Müəllim: skanda ⊘ boz xana, «sayılmır, bal qalanlar üzrə 100-ə».
   - Kamera: böyük nəticədə «N sual vərəqə düşməyib – sayılmır».
   - Şagird: «🧾 Kartım»da həmin suallar «sayılmır».
5. Bal: `grade()` ləğv və ⊘ sualları çıxarır, qalanların balını 100-ə miqyaslayır (mövcud məntiq).

## Yoxlama
- pytest:
  - `unprinted` saxlanır (yalnız köhnə çap);
  - yeni skan: kəsilmiş + boş → ⊘, bal 100-ə;
  - kəsilmiş + cavablı → sayılır;
  - müəllimin ⊘ dəyişikliyi saxlanır.
- `npm run build`, deploy, canlı: X c-də skan siyahısı açılanda təxmin saxlanır.
- Mətnlər AZ/EN/RU.
