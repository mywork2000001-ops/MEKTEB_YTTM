# Test nəticələri – tamamlama promtu (II mərhələ)

> Tarix: 04.10.2026. Əsas spes: docs/test-neticeleri-promtu.md (61b4ba1, 81d4f96).
> Müəllimin tapşırığı: «işin tam icrası üçün peşəkar promt hazırla, əlavələrini et, filtrə «Hamısı» hissəsini qeyd et;
> ardıcıl icra, sonda tam hesabat».

## 0. Rol və qaydalar

Aparıcı mühəndis kimi I mərhələnin qaydalarını saxla: mövzu testi ilə sınaq **bir cədvəldə qarışmır** («Hamısı» – iki hissə
yan-yana/ardıcıl göstərilir, ortaları birləşdirilmir); məxfilik (`ws_cond`, `_access`, adlar AI-yə getmir); çap yalnız `print.ts`.
Hər addımdan sonra: pytest, `npx tsc -b`, `npm run build`, brauzer (1366 və 360 px).

## 1. Filtrlərdə «Hamısı»

| Yer | Əvvəl | İndi |
|---|---|---|
| Səhifənin üstü – **Növ** (bütün tablar üçün ümumi) | yox (hər tab özü) | **Hamısı** · Mövzu testləri · Sınaqlar (cihazda yadda qalır) |
| Reytinq | Mövzu testləri · Sınaqlar | Növ filtrindən: «Hamısı» – iki ayrı reytinq ardıcıl, çapda iki bölmə |
| Yazmayanlar | öz seçimi | ümumi Növ filtri |
| Şagird / Sinif və qrup / Ümumi | həmişə ikisi | Növə görə: Hamısı – ikisi, digəri – yalnız seçilən hissə (ekran, çap, AI rəyi) |
| Sinif və qrup – sinif | yalnız bir sinif | **Hamısı (bütün siniflərim)** + siniflər |
| Səviyyə | Bütün sinif · Zəif · Orta · Güclü | **Hamısı** · Zəif · Orta · Güclü |
| Dövr | Hamısı · Həftə · Ay · Yarımil · İl | dəyişmir |
| Reytinq – sinif | Bütün siniflərim | **Hamısı (bütün siniflərim)** |

Backend: `GET /api/results-center/class` (ta_id-siz – bütün dərslərim; səviyyə hər dərsin öz bölgüsündən), AI rəyində `kind`
(scope `class` ta_id-siz – «bütün siniflərim»), rəy açarına növ əlavə olunur.

## 2. Əlavələr

1. **Reytinqdə sıralama**: Yer · Dinamika · İştirak (məs. ən çox irəliləyən və ya ən az yazan yuxarıda).
2. **Excel (CSV) ixracı**: reytinq və yazmayanlar – UTF-8 BOM, «;» ayırıcı (Excel-də düz açılır).
3. **«Yazmayanlar» tabında sayğac**: xroniki yazmayanların sayı nişanda.
4. **Müəllim üçün izah səhifəsi** (artifact WeWZfH4NhjM88aBKZ3pnCm) «Test nəticələri» ilə yenilənir.
5. **Videolar**: interfeys dəyişdiyi üçün müəllim və fərdi videolarda «Test nəticələri» kadrları yenidən çəkilir (səs eyni, +6%).

## 3. Qəbul meyarları

- «Hamısı» seçiləndə heç bir yerdə mövzu testi və sınaq faizi bir ortaya qarışmır.
- Bütün siniflər üzrə sinif hesabatı: hər şagird öz dərsinin səviyyəsi ilə; şagird iki dərsdə varsa – hər sətir öz dərsində.
- CSV Excel-də Azərbaycan hərfləri ilə düz açılır.
- Testlər: «Hamısı» sinif hesabatı, AI `kind`, mövcud 197 test keçir.

## 4. Mərhələlər

1. Promt (bu sənəd) → 2. Backend (`class` bütün siniflər, AI `kind`) + testlər → 3. Frontend (Növ filtri, «Hamısı», sıralama,
CSV, sayğac) → 4. Yoxlama (pytest, tsc, build, brauzer) → 5. Commit → 6. İzah səhifəsi və videolar → 7. Yaddaş və tam hesabat.
Push avtomatik rejimdə qadağandır – istifadəçiyə qalır.
