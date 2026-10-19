# Fərdi sinifdə yazılı imtahan – cavab kartı olmadı · promt (19.10.2026)

> **19.10.2026: docs/yazili-sinaq-ve-skan-duymesi-promtu.md ilə birləşdirildi** (xəta yox idi – kağız rejimi yox idi).

## Problem
18.10.2026 fərdi (repetitor) sinifdə yazılı imtahan keçirmək istənildi – cavab kartları çap olunmadı. Kart yalnız
KSQ/BSQ variantı olanda yaranır (`ExamVariant` → `variants/print`), variant isə bu şərtlərdə alınmır (`api/exams.py`):
- `ta.has_summative` yoxdur → «Bu qrupda KSQ/BSQ keçirilmir»;
- fərdi sinfin perspektiv planı yoxdur / planda KSQ dərsi yoxdur → «Perspektiv planda bu imtahanın aralığında mövzu tapılmadı»;
- bankda mövzu üzrə sual azdır → 409 «sual çatmır»;
- tarix tədris ilinin yarımilindən kənardır (fərdi məkanın öz təqvimi) → 400.

## Rol
Sən «Müəllim köməkçisi»nin baş mühəndisisən. Məqsəd: müəllim **istənilən sinifdə (məktəb və fərdi), plansız da**,
3 addımda yazılı imtahan keçirə bilsin: mövzu seç → çap et (vərəq + cavab kartı + açar) → skan et → bal jurnala.

## Addım 0 – diaqnoz (kod yazmadan əvvəl)
- Lokal DB-də fərdi məkan + sinif yarat, KSQ yaratmağa cəhd et; hansı xəta çıxdığını yaz (yuxarıdakı 4 səbəbdən hansı).
- Render loqunda 18.10.2026 `POST /api/exams` və `/variants` cavablarına bax (yalnız oxumaq). Canlı DB-yə yazmaq yoxdur.
- Səbəb tapılmayana qədər düzəliş etmə; tapıntını HANDOFF-a yaz.

## Həll
1. **Səhv mesajları aydın olsun (AZ/EN/RU) və həll yolu göstərsin:** «Planda KSQ yoxdur – mövzuları əl ilə seçin»,
   «Bu qrupda KSQ söndürülüb – Tənzimləmələrdə yandırın», «Sual çatmır – sual sayını N-ə endirin və ya rəqəmləri dəyişən
   suallar əlavə edin» (docs/reqem-variantlari-promtu.md).
2. **«Sərbəst yazılı iş»** (`Exam.kind = 'YI'`, jurnalda formativ və ya ayrıca sütun – müəllim seçir):
   - plan tələb olunmur: müəllim mövzu(lar)ı və ya bank fayllarını özü seçir, sual sayı 5–30, bal 100-ə bölünür;
   - fərdi məkanda `has_summative` şərti yoxdur; tarix – istənilən gün (yarımil şərti yalnız KSQ/BSQ üçün);
   - variantlar mövcud `generate_auto` ilə (hər şagirdə fərqli) + «hamıya eyni / hamıya eyni, rəqəmlər fərqli» seçimi;
   - çap: mövcud vərəq + QR-li cavab kartı + müəllim açarı; skan / onlayn yazı / apelyasiya dəyişmədən işləyir.
3. **Ehtiyat cavab kartı (internet/variant yoxdursa):** «Boş cavab kartı çap et» – N xana, QR-də yalnız imtahan id-si,
   şagird adını və variant kodunu əllə yazır; skan zamanı müəllim şagirdi siyahıdan seçir.
4. **İmtahandan bir gün əvvəl yoxlama:** imtahan tarixi olan sinifdə variant/kart hazır deyilsə – müəllimə əsas səhifədə
   «Sabah {sinif} – yazılı iş, kartlar çap olunmayıb» xəbərdarlığı.
5. Məxfilik dəyişmir: fərdi sinfin nəticələri məktəb hesabatına düşmür (docs/ferdi-sinif-promtu.md).

## Qəbul meyarları
- Test: fərdi məkanda plansız sinif → «Sərbəst yazılı iş» → variantlar → çap HTML-də hər şagirdin kartı və QR var → skan → bal.
- Test: köhnə 4 səhv halı aydın mesaj qaytarır (EN/RU da). Mövcud KSQ/BSQ testləri dəyişmədən keçir.
- `npm run build` uğurlu, deploy success; yeni mətnlər AZ/EN/RU; miqrasiya (`kind='YI'`) – istifadəçinin razılığı ilə.
