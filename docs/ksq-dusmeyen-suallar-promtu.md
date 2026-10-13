# KSQ: kağıza düşməyən sualların nəzərə alınması – bütün siniflər (13.10.2026)

## Tələb
«KSQ-larda (siniflərdə) kağıza düşməyən sualları nəzərə almaq üçün promt hazırla və peşəkar olaraq icra et.»

## Vəziyyət
- 13.10.2026-dan əvvəl çap olunan vərəqlərdə (X b, X c, X e, XI a – KSQ-1) bəzi suallar görünmürdü. Çap ölçməsi
  şəkillər yüklənməmiş aparılırdı, `overflow:hidden` sualları kəsirdi. Ən çox 1-ci üzdə 14–16, 2-ci üzdə 27–30 kəsilirdi.
- Şagird görmədiyi suala cavab verə bilməz. Ona 0 bal yazmaq ədalətsizdir.
- Bazada variantlar tamdır (30 sual), problem yalnız kağızdadır. Çap düzəldilib (`ksqPrint.fit`).

## Qərarlar
1. **Şagird üzrə «⊘ kağızda yox idi»** (`exam_scans.lost`): bu sual həmin şagird üçün sayılmır, qalan suallar üzrə bal
   100-ə miqyaslanır (`grade(..., annulled)`). Ümumi «ləğv» (bütün sinif üçün) ayrıca qalır.
2. **Avtomatik təyin** – skan bölməsində «⊘ Kağıza düşməyən suallar» düyməsi. Yalnız köhnə çaplı imtahanlarda görünür:
   `printed_at < 2026-10-13 11:00 UTC`.
   - brauzer köhnə çapı gizli çərçivədə təkrarlayır: 10 pt, şəkillər yüklənəndən sonra, sütundan kənara çıxan suallar.
     Nəticə: `{şagird: [slot]}` (`estimateOldCut`);
   - server: **kəsilmiş ∩ kartda boş cavab → ⊘**.
   - Kəsilmiş sayılan, amma cavabı olan sual görünürmüş: ⊘ götürülür, sual sayılır.
   - Müəllimin başqa ⊘-larına toxunulmur.
   - Yenidən skan / yenidən oxunuşdan sonra düyməni yenə basmaq olar (idempotent).
3. **Hesabat**: dəyişən şagirdlər, ⊘ sualları, bal «əvvəl → sonra». Audit jurnalına yazılır.
4. **Müəllim nəzarəti**: skan detalında hər xanada «⊘» düyməsi (əl ilə qoy/götür). Kağızla tutuşdurmaq tövsiyə olunur.
5. **Yeni çaplar**: çap pəncərəsi hər sualın və cavab kartının vərəqdə olduğunu yoxlayır. Sığmayan varsa – qırmızı və ad.
   Köhnə çapın kəsəcəyi suallar siyahısı göstərilir (yenidən çap üçün).
6. AZ/EN/RU.

## İcra planı
- X c, X e (skan olunub): kartları «Yenidən skan (köhnəni əvəz et)» ilə yenidən skan et. Yeni kəsikdə son sətir 28–30 var.
  Yeni oxunuşdan sonra «⊘ Kağıza düşməyən suallar» düyməsini bas.
- X b, XI a (skan yoxdur): KSQ yazılmayıbsa – vərəqləri yenidən çap et. Yazılıbsa – skandan sonra düyməni bas.

## Yoxlama
- pytest `test_ksq_scan.py::test_scan_flow` (lost-auto: kəsilmiş ∩ boş, cavablı – sayılır); `npm run build`; deploy.
