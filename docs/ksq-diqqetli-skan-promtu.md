# KSQ: diqqətli skan – səliqəsiz əl yazısı, bir şagird və bütün sinif (13.10.2026)

## Tələb
«Uşaqlar səliqəsiz yazır, cavab qəbul olunmur. Skan diqqətli olsun – ayrıca şagird və bütün sinif üçün. Tam audit.»

## Tam audit (bu gün aşkar edilən və düzəldilən hər şey)
| # | Mərhələ | Problem | Düzəliş |
|---|---|---|---|
| 1 | Çap | suallar kəsilirdi (şəkillər ölçmədən sonra) | `fit` şəkilləri gözləyir, sığmayanı arxa üzə keçirir, qırmızı xəbərdarlıq |
| 2 | Çap | kartın son sətri (28–30) kəsik zonasından kənarda | xanalar `flex`, kart yoxlaması; `ZONE y1 = 112` |
| 3 | Kadr | kart tam düşmürdü – kənar ağ, «boş» | `zone_inside` → «yenidən çək» |
| 4 | Yükləmə | eyni kart dəfələrlə (pul) | bir blank – bir dəfə; «Yenidən skan (köhnəni əvəz et)» |
| 5 | Növbə | yeni kart 31 kartın arxasında | yeni kart növbəsiz; bir kart – bir iş (`_busy`) |
| 6 | Model | OpenRouter `claude-sonnet-5-5` etibarsız | «/»-suz ad → standart model |
| 7 | Oxunuş | xana sərhədi «/», «,» kimi; sətirlər qarışır | `cells` (xana-xana), kart düzümü promtda |
| 8 | Oxunuş | əminlik faydasız (0/859 < 0,7) | mümkünlük yoxlaması + ikinci model |
| 9 | Oxunuş | **səliqəsiz əl yazısı** (1/7, 6/3, 4/9) | **bu promt** – böyüdülmüş sütunlar + səsvermə |
| 10 | Bal | görünməyən suala 0 | «⊘» şagird üzrə, avtomatik «Kağıza düşməyən suallar» |
| 11 | Müqayisə | – | `_same`: 0,5 = 1/2, kök sırası, «−», «.» – yaxşıdır, dəyişmir |

## Qərarlar – diqqətli oxunuş
1. **Böyüdülmüş sütunlar** (`strips`): kəsik 3 sütuna bölünür. Hər sütun ±5 mm üst-üstə düşür, kontrast artırılır,
   ≤2× böyüdülür, kəskinləşdirilir. Modelə hansı şəkildə hansı nömrələrin olduğu deyilir (`_columns`). Sətir qarışmır,
   rəqəm böyük görünür.
2. **Səsvermə** (`_decide`):
   - Mümkün olmayan oxunuş səs deyil.
   - Ən azı iki eyni oxunuş varsa, o qəbul edilir (bəzi oxunuşlar fərqlidirsə əminlik 0,9, hamısı eynidirsə 1,0).
   - Bərabər səs (2:2) olarsa, böyüdülmüş oxunuş seçilir, xana sarı olur.
   - Razılıq yoxdursa, xana sarı olur, alternativlər (`alt`, `alts`) saxlanır. Müəllim bir kliklə qəbul edir.
3. **Hər skanda avtomatik**: A (əsas model, bütün kart) ‖ B (ikinci model, açıq suallar). Fikir ayrılığı və mümkün olmayan
   xanalar üçün C (böyüdülmüş sütunlar, əsas model) işə düşür, sonra səsvermə. Əlavə xərc yalnız şübhəli kartlarda yaranır.
4. **Müəllim düymələri**:
   - **«🔍 Diqqətli oxu»** – bir şagirdin kartı. A + B + C + D (sütunlar ikinci modellə) – 4 oxunuşdan səsvermə.
   - **«🔍 Sinfi diqqətli oxu»** – bütün kartlar.
   - **«🔍 Yalnız baxılmalılar (N)»** – yalnız sarı xanası olan kartlar.
   - Fonda işləyir, siyahı özü yenilənir.
   - Müəllimin düzəltdiyi xanalar (`by: teacher`) saxlanır. Əvvəlki oxunuş tarixçəyə yazılır. `read_by` = `…+diq`.
5. **Sarı xana** – şəkil və alternativ yanında. Müəllim baxıb təsdiqləyir və ya düzəldir. Bal dərhal yenidən hesablanır.
6. Xərc: kart başına 2 sorğu (şübhəlidə 3), diqqətli oxunuşda 4. Aylıq limit 600 kartdır, Resurslarda görünür.
7. AZ/EN/RU.

## Yoxlama
- pytest `test_ksq_scan.py` (16): səsvermə, bərabər səs, müəllim düzəlişi saxlanır, sütun şəkilləri (3 JPEG), yalnız sarılar.
- Canlı: X c – «Sinfi diqqətli oxu», Ağazadə M. kartı şəkillə tutuşdurulur (10–27).
