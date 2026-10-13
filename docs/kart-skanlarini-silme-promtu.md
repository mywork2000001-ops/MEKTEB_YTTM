# KSQ/BSQ: bütün siniflərdə cavab kartlarının skanlarını sil – təzədən skan (13.10.2026)

## Tələb (istifadəçi)
«Bütün siniflərdə cavab kartlarını sil. Peşəkar promt hazırla və icra elə. Təzədən cavabları skan edəcəm.»

## Niyə lazımdır
13.10.2026 auditlərində köhnə skanlarda bunlar aşkar edildi:
- kəsik zonası 28–30-cu sətirləri tutmurdu;
- açıq cavablar səhv oxunurdu (xana sərhədi «/» kimi);
- bəzi kartlar kadra tam düşməmişdi;
- 31 kart OpenRouter balansı bitdiyindən oxunmamış qaldı.

Qayda «bir blank – bir dəfə» olduğu üçün köhnə skan qaldıqca yeni skan qəbul olunmur. Müəllim bütün kartları yeni
kamera / kəsik / oxuyucu və yeni açar hovuzu ilə (Kart oxuyucusu, 5 açar) təzədən skan etmək istəyir.

## Əhatə
| Obyekt | Nə olur | Səbəb |
|---|---|---|
| `exam_scans` – kağız kartlar (`read_by ≠ 'online'`) | **silinir** | təzədən skan |
| `exam_scores` – həmin şagird + imtahan cütləri | **silinir** | köhnə səhv oxunuşdan bal jurnalda qalmasın; təzə skan yenidən yazır |
| `exam_scans` – onlayn yazılar (`read_by = 'online'`) və onların balı | **qalır** | kağız kart deyil |
| `exam_variants` (suallar, QR, çap tarixi), imtahanlar, açar düzəlişləri, ləğv edilmiş suallar | **qalır** | eyni vərəq/QR keçərlidir |
| Skansız əl ilə yazılmış ballar (`exam_scores`, skanı yoxdur) | **qalır** | müəllimin əl işi |
| Kəsik şəkilləri (`file_blobs`, `db:` açarlı) | **qalır** | ehtiyat nüsxə onlara istinad edir |

## Təhlükəsizlik – geri qaytarıla bilən silmə
1. Silmədən əvvəl tam ehtiyat nüsxə alınır. Silmə və ehtiyat **eyni tranzaksiyada** gedir, yarımçıq vəziyyət qalmır:
   - `exam_scans_backup_20261013` – silinən skanların bütün sütunları (oxunuş, müəllim düzəlişləri, tarixçə, ⊘);
   - `exam_scores_backup_20261013` – silinən balların bütün sütunları.
2. Geri qaytarma: `alembic downgrade` (miqrasiyanın `downgrade`-i). Ehtiyatdan yalnız olmayan sətirlər bərpa olunur,
   təzə skanlar üzərinə yazılmır.
3. Ehtiyat cədvəlləri və şəkillər müəllim təsdiq edəndən sonra ayrıca miqrasiya ilə silinir (təxminən 2 həftə sonra).

## İcra yolu
- Canlı baza (Neon `muellim`) yalnız Render tətbiqindən əlçatandır. Ona görə silmə **bir dəfəlik Alembic data
  miqrasiyası** ilə gedir: `f9b1d3e5a7c9_skanlari_sil`. Deploy zamanı avtomatik bir dəfə işləyir, `alembic_version`
  təkrarını qadağan edir.
- Silmədən sonra Render prosesi yenidən başlayır: nəticə keşi (`result_cache`) və açar dinclikləri təmizlənir.

## Gələcək üçün: müəllim düyməsi
- KSQ → «4. Skan və nəticə» → **«🗑 Skanları sil»** (bir imtahan üzrə).
- Silmədən əvvəl təsdiq tələb olunur: imtahanın adı yazılır (`ConfirmName`).
- API: `DELETE /api/exam-scans/{ta}/{exam}`. Kağız skanlar və onların balları silinir, onlayn yazılar və kəsik şəkilləri qalır. Audit qeydi
  yazılır.
- Mətnlər AZ/EN/RU.

## Yoxlama
- pytest:
  - miqrasiya məntiqi (`clear_paper_scans`): kağız skan və balı silinir, onlayn və əl balı qalır, ehtiyatda sətirlər var;
  - endpoint başqa müəllimin imtahanına 404 qaytarır.
- Deploy statusu `success`.
- Canlı: skan siyahısı boşdur, «Kartı yoxdur» bütün şagirdləri göstərir, yeni kart qəbul olunur.

---

## Əlavə tələb 1: «Skan edəndə bir şagird bitməmiş digəri gəlməsin, bal görünsün, sonra növbəti»
Ardıcıl skan (`scanCamera.tsx`) – **bir şagird, bir nəticə**:
1. Kart çəkilir, sonra «Göndərilir…» → «Kart oxunur… N san.» (şagirdin adı ilə). Bu müddətdə «📷 Çək» düyməsi və QR ilə
   avtomatik çəkiliş **bağlıdır**, ikinci kart qəbul edilmir.
2. Oxunuş bitəndə ekranda böyük nəticə görünür: ad, **bal**, düz say (məs. 22/30), sarı xana sayı («şəkilə baxıb yoxlayın»).
   Titrəmə siqnalı verilir.
3. Növbəti kart yalnız **«Növbəti şagird ▶»** basılandan sonra çəkilir; avtomatik çəkiliş 3 saniyə sonra açılır.
   Bal səhv görünürsə, **«↻ Bu kartı yenidən çək»** köhnə skanı əvəz edir.
4. Mənim əlavələrim:
   - Oxunuş 30 saniyədən uzun çəkərsə, və ya bütün açarlar limitdədirsə (səbəb müəllimin dilində göstərilir),
     **«Keç – sonra oxunsun»** düyməsi çıxır. Kart qəbul olunub, nəticə siyahıda görünəcək, müəllim ilişib qalmır.
   - Alt sətirdə «qalıb: N şagird» göstərilir (variantı olub skanı olmayanlar).
   - Bir şəkildə bir neçə kart varsa, hamısının nəticəsi birlikdə göstərilir.
   - `aiErrorText` ortaq moduldadır (`scanCamera.tsx`) – skan siyahısı və kamera eyni mətni göstərir.

## Əlavə tələb 2: «Hər şagirdin nəticəsi şəkil olaraq özünə getsin (dəqiqlik üçün) və sistemdəki düz cavablar da»
Şagird portalı → «Nəticələr» → imtahan sətri → **«🧾 Kartım»**:
1. Öz cavab kartının şəkli: `GET /api/portal/exam-card/{scan_id}/image`. Yalnız öz kartı, yalnız qiymətləndirilmiş kart;
   başqasınınkı üçün 404.
2. Cədvəl:
   | № | Sənin cavabın (sistemin oxuduğu) | Düz cavab (sistemdəki açar) | ✓ / ✗ |
   |---|---|---|---|
   - Ləğv edilmiş və vərəqə düşməyən (⊘) suallar boz göstərilir: «sayılmır».
3. Açıqlama: «Kartındakı cavabı sistemin oxuduğu ilə tutuşdur. Fərq görsən – müəllimə de, müəllim düzəldəcək.»
   Bunun məqsədi oxunuşun dəqiqliyini şagirdin özünün də yoxlamasıdır.
4. Bildiriş (7 gün): «KSQ-1 – kartının şəkli və nəticəsi · 78 bal · cavablarını düz cavablarla yoxla» → `/results`.
   Kart yenidən oxunanda / düzəldiləndə yeni bildiriş gəlir (açar `card-{id}-{updated_at}`).
5. Onlayn yazıda şəkil yoxdur: «Onlayn yazmısan – cavabların ekrandan götürülüb». Cədvəl eynidir.
6. Təhlükəsizlik: hər şagirdin öz variantı var (suallar fərqlidir), ona görə açarı görmək başqasına cavab vermir.
   Kart yalnız müəllim skan edib qiymətləndirəndən sonra görünür.
7. Mətnlər AZ/EN/RU (bildiriş – şagirdin dilində).

## İcra qeydi
- Silmə endpoint-i kəsik şəkillərini **silmir**. Avtomatik təhlükəsizlik yoxlaması blob silməni blokladı, və bu daha
  təhlükəsizdir: şəkillər ehtiyat kimi qalır, sonra ayrıca təmizlənir.
