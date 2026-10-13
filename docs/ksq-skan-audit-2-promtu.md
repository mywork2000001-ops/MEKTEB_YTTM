# KSQ skanı – təkrar audit (13.10.2026, axşam)

## Tələb
«Skanın auditini yenidən et, promt yaz, öz qərarlarını əlavə et və icra et.»

## Audit – canlı məlumat (X c KSQ-1: 18 kart, X e KSQ-1: 13 kart)
| Yoxlama | Nəticə |
|---|---|
| Test sualları (1–9), kart şəkli ilə tutuşdurma | düzgün oxunur (Ağazadə M.: 9/9) |
| Açıq suallar (10–30) | **kütləvi səhv oxunuş**: «20»→«2/0», «30»→«3/0», «35»→«3,5», «16»→«1/3», «12»→«1/2», «40»→«Y/9», «150»→«» |
| Səbəb 1 | model xanaları ayıran şaquli xətləri «/», «,», «1» kimi oxuyur; sətir/nömrə qarışır; bir sətirlik `value` |
| Səbəb 2 | əminlik (confidence) faydasızdır: 859 xanadan 0-ı < 0,7 – ikinci oxunuş heç işləmirdi |
| Kəsik zonası | `ZONE y1 = 106 mm` kartın aşağı sərhədi idi; çapda sətirlər ~9 mm (ekranda 8,6) → **son sətir (28, 29, 30) kəsikdə yox idi** – həmin cavablar heç oxunmurdu |
| Kart düzümü | açıq xanalar `inline-block` – sətir hündürlüyünə baza xətti boşluğu əlavə edir |
| Kəsik ölçüsü | 6 px/mm – əl yazısı rəqəmlər üçün az |
| Bal | X c / X e balları **oxunuş səhvinə görə aşağıdır** (şagirdin günahı deyil) |
| Xərc | OpenRouter `anthropic/claude-sonnet-4.5`, aylıq limit 600 kart |

## Qərarlar
1. **Xana-xana oxunuş:** açıq sualda model `cells` (8 xana ayrıca) qaytarır, server birləşdirir. Promtda açıq şəkildə:
   «xanaları ayıran şaquli xətlər simvol deyil», nümunə `["2","0",…]` = «20»; kartın düzümü (3 sütun, sətir-sətir
   1,2,3 / 4,5,6) və «cavabı nömrəsinin yanındakı sətirdən oxu».
2. **Mümkünlük yoxlaması** (`plausible`): açıq cavab yalnız `ədəd[,ədəd][/ədəd][;…]` forması; məxrəc 0 olmaz.
   Uyğun gəlməyən («2/0», «7/», «Y/9») → confidence aşağı → **ikinci oxunuş** + müəllimə sarı.
3. **Kəsik:** `ZONE y1 106 → 112 mm`, `PX_MM 6 → 8`.
4. **Kart çapı:** xanalar `flex` (baza xətti boşluğu yoxdur); çap pəncərəsi kartın bütün sətirlərinin vərəqdə
   olduğunu yoxlayır, olmasa – qırmızı və şagird adı.
5. **Yenidən skan rejimi:** skan bölməsində «Yenidən skan (köhnəni əvəz et)» – bütün kamera/fayl yükləmələri köhnəni
   əvəz edir (bir blank – bir dəfə qaydası müvəqqəti söndürülür).
6. **Mövcud kartlar:** kəsiklər köhnədir (son sətir yoxdur) → X c və X e kartları **yenidən skan edilməlidir**. Sonra
   «kağızda görünməyən suallar» (⊘) qaydası yenidən hesablanır: çapda kəsilmiş (təxmin) ∩ boş cavab.
7. AZ/EN/RU.

## Yoxlama
- pytest (`test_ksq_scan.py`); `npm run build`; Render deploy.
- Canlı: «Yenidən oxu» ilə X c – Ağazadə M. kartı şəkil ilə tutuşdurulur (10–27 açıq cavablar).
