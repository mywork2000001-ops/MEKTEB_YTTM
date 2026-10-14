# Köçürmə şübhəsi – silinmə və icra hesabatı (14.10.2026)

Əsas funksiya: docs/kocurme-subhesi-yeni-variant-promtu.md.

## Rol və məqsəd
Sən «Müəllim köməkçisi»nin baş mühəndisisən. Müəllim şübhəli şagirdə yeni variant verəndən sonra hər şagird üçün
**nə silindiyini** və **yeni yazının icrasını** bir baxışda görməlidir – sübut və nəzarət üçün.

## Tələblər
1. **Silinmə barədə** (audit jurnalından, hər «yeni variant» əməliyyatı üçün):
   - tarix və saat, kim etdi (müəllimin adı), köhnə kod → yeni kod, qeyd;
   - silinənlər: kağız kartın skanı (balı ilə), onlayn yazı, jurnaldakı bal; heç nə yox idisə – «yazı yox idi».
2. **İcra barədə** (cari vəziyyət):
   - yeni vərəq: «çap olunmayıb» / «çap olunub (tarix)»;
   - yeni yazı: «gözlənilir» / «kart oxunur» / «onlayn göndərilib» / «yazıb: N bal» (köhnə balla müqayisə: fərq);
   - növbəti addım üçün düymə: çap olunmayıbsa – «🖨 Yeni vərəqi çap et».
3. Bir neçə dəfə yeni variant verilibsə – hamısı tarixçə kimi (ən yenisi yuxarıda).
4. Hesabat çap oluna bilsin (müdir/valideyn üçün) – rəsmi sənəd kimi yalnız AZ.
5. İnterfeys mətnləri AZ/EN/RU; yeni lüğət açarı təkrarlanmasın.

## Həll
- API: `_variants_out.suspects[]` → `{student_id, full_name, times, old_score, code, at, history[{at, by, old_code, new_code,
  note, deleted{scan_points, read_by, online, score}}], printed_at, now{status, points, online}}`.
- UI: İmtahanlar → KSQ → «Kağız variantlar» → 2-ci addım, sarı «🚩» blokunda hər şagird üçün iki sətir
  (Silinib · İcra), «🖨 Yeni vərəqi çap et», bütün siyahını «🖨 Hesabatı çap et».

## Qəbul meyarları
- Test: retake → history-də silinmiş skan balı və jurnal balı; çapdan sonra `printed_at` dolu; yeni skan → `now.points`.
- `npm run build`, pytest keçir; deploy success.
