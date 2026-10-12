# Məşğələ qrupları «Siniflər və qruplar» bölməsində – promt

**İstək (12.10.2026):** əlavə məşğələ qruplarını «Siniflər» bölməsinə köçür; siniflərdən məşğələ qruplarına şagird əlavə
etmək və çıxarmaq mümkün olsun. Peşəkar, səliqəli; düzəlişləri qeyd et.

## Mövcud vəziyyət (audit)
- Məşğələ kursu ayrıca menyu bəndidir («Əlavə məşğələ»); kursun şagirdləri = seçilmiş siniflər (+ səviyyə və ya seçilmiş
  şagirdlər). Başqa sinifdən **bir şagirdi** əlavə etmək üçün bütün sinfi kursa qoşmaq lazımdır; tək şagirdi çıxarmaq –
  bütün siyahını yenidən seçməklə. Şagird kartında onun hansı qrupda olduğu görünmür.

## Qaydalar
1. Menyuda «Əlavə məşğələ» yoxdur; «Siniflər və qruplar» səhifəsinin başında **Siniflər · Məşğələ qrupları** seçimi;
   «Məşğələ qrupları» – kurslar, plan, davamiyyət, statistika (əvvəlki bütün imkanlar). `/extra` → `/classes?tab=extra`.
2. Qrupun «Şagirdlər» bölməsində: üzvlər (sinifi ilə) + **«✕ çıxar»**; **«+ Şagird əlavə et»** – sinif seçilir (açılan
   siyahı), həmin sinfin şagirdləri qeyd qutuları ilə (artıq üzv olanlar işarəli).
3. Şagird kartında (Siniflər → şagird): **«Məşğələ qrupları»** – qrupun yanında qeyd qutusu: işarələ – əlavə, götür – çıxar.
4. Server: `GET /api/extra/{id}/candidates`, `POST /api/extra/{id}/members` {student_ids}, `DELETE /api/extra/{id}/members/{sid}`,
   `GET /api/extra/student/{sid}`. Şagird yalnız müəllimin **eyni fəndən** dərsi olan sinifdən əlavə olunur (məktəb və fərdi
   hazırlıq qarışmır); əlavə/çıxarma auditoriyanı «seçilmiş şagirdlər» siyahısına çevirir (sinfin qalanı avtomatik qoşulmur);
   arxiv kursu dəyişmir; keçmiş davamiyyət silinmir.
5. Testlər: əlavə (başqa sinifdən), çıxarma, başqa fənn/məktəb – 404/400, arxiv – 400.

## Hesabat (12.10.2026 – icra olundu)
- Menyudan «Əlavə məşğələ» çıxarıldı; «Siniflər və qruplar» → **Siniflər · Məşğələ qrupları**; `/extra` → `/classes?tab=extra`.
- Qrup → «Şagirdlər»: üzvlər sinif nişanı ilə, **✕ çıxar**; **+ Şagird əlavə et** – sinif açılan siyahıdan (defolt –
  əlavə ediləsi şagirdi olan ilk sinif), qeyd qutuları, «Hamısını seç», «Qrupa əlavə et (N)».
- Şagird kartı → **Məşğələ qrupları**: qeyd qutusu ilə əlavə / çıxar.
- Server: `candidates`, `members` (POST/DELETE), `student/{sid}`; eyni fənn və aktiv məkan; arxiv – 400; sonuncu şagird
  çıxarılmır; sinfindən heç kim qalmayanda sinif qrupdan çıxır. Test: `tests/test_api_extra_members.py`.
- Brauzer (lokal test bazası, DOM): yönləndirmə, əlavə (X c-dən tək şagird → 5), çıxarma (→ 4), kartdan əlavə (→ 5).
