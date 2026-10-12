# «Testlər və sınaqlar» – üç bölmənin bir bölməyə birləşdirilməsi (promt)

**İstək (12.10.2026):** «Onlayn tapşırıqlar», «Sınaq imtahanları» və «Test nəticələri» menyuda bir bölmə olsun; içəridə
seçimlər açılan siyahı ilə: əvvəl sinif, sonra mövzu testi / sınaq / nəticələr. Səliqəli, gözə xoş.

## Qaydalar
- Menyuda üç bənd əvəzinə **bir bənd: «Testlər və sınaqlar»** (`/tests`).
- Səhifənin başında bir sırada üç açılan siyahı (etiketli, böyük, telefonda alt-alta):
  1. **Bölmə:** Mövzu testləri (onlayn tapşırıqlar) · Sınaq imtahanları · Nəticələr və reytinq
  2. **Sinif:** Bütün siniflərim · X e · …
  3. **Görünüş** (bölməyə görə): sınaqda – Sınaqlar / Avtomatik seriyalar; nəticələrdə – Reytinq / Yazmayanlar /
     Şagird / Sinif və qrup / Ümumi. Mövzu testlərində yoxdur.
- Bölmənin içində öz başlığı, öz sinif seçimi və öz bölmə düymələri təkrarlanmır – hamısı yuxarıdakı siyahılardadır.
- Sinif seçimi hər üç bölməyə tətbiq olunur (sınaqlar – həmin sinfə verilənlər; nəticələr – həmin sinif).
- Seçim URL-də (`/tests?s=sinaq&v=series`) – keçid paylaşılır, «geri» düyməsi işləyir; sinif – sessiyada yadda qalır.
- Köhnə ünvanlar (`/tasks`, `/exams-online`, `/results-center?…`) yeni bölməyə yönlənir (jurnal, hesabat, şagird
  profili keçidləri qırılmır); jurnaldan «Onlayn test təyin et» – sinif seçilmiş açılır.
- Server: sınaq siyahısına `ta_ids` (sinif filtri üçün).

## Yoxlama
- `tsc`, build, backend testləri; brauzer: üç bölmə × sinif × görünüş, köhnə keçidlərin yönləndirilməsi, şagird profili keçidi.

## Əlavə (12.10.2026): köhnə testlərin səliqəsi, 45 dəqiqə, təkrarlar
- [x] **Həll müddəti ən azı 45 dəq:** mövzu testi, sınaq, yenidən göndərmə, redaktə, seriya, avtomatik mövzu testi
      (az yazılsa – 45-ə qaldırılır; açıq qalma aralığı 45 dəqiqədən qısadırsa – xəbərdarlıq). Məşğələ testləri – dəyişmir.
- [x] **Miqrasiya f7b9d1e3a5c8 (canlıda bir dəfə):** bağlanmamış mövzu testi/sınaqlarda müddət 45 dəqiqəyə (aralıq imkan
      verdikcə), seriyalarda da; **təkrarlar** – eyni sinif, növ, mövzu, ad, suallar və şagirdlər: heç kimin başlamadığı
      surətlər silinir, boş paket də; **nəticəsi olan test heç vaxt silinmir**. Nəticə Render logunda: «test tidy: {...}».
- [x] **Mövzu testləri səliqəsi:** eyni test bir neçə sinfə verilibsə – bir kart («N sinif»), içində sinif sətirləri
      (vəziyyət, vaxt, təhvil, orta, əməllər); ümumi təhvil və orta kartın başında.
