# KSQ/BSQ: suallar YALNIZ keçilmiş mövzulardan + peşəkar dizayn (13.10.2026)

**İstifadəçi tələbi:** «testlərə fikir ver – mövzular üzrə olmalı, KSQ-yə qədər olan mövzularda; dizayn gözə yatımlı olsun;
əvvəlki məlumatları da qeyd et; ardıcıl icra et».
**Qayda:** uğursuz test → düzəliş → pytest → `npm run build` → brauzer (390/1280) → commit → push → Render `success`. AZ/EN/RU.

## 0. Əvvəlki vəziyyət (12–13.10.2026, hamısı canlı saytda)
- Mərhələ 1–5 hazırdır: slot planı (n sual, cəmi 100 bal, ~30 % test / ~70 % açıq), `exam_variants`, sinifdə təkrarsız generator,
  20 parametrli şablon, A4 iki üzlü çap + cavab kartı (imzalı QR), skan (zxing-cpp), Claude oxunuşu, telefonla ardıcıl skan.
- Müəllim sual sayını seçir (10–30); başqa siniflərlə ≤ 20 % təkrar; KSQ redaktə/silmə; ZIP arxiv (Google Drive üçün).
- Test mənbəyi: hər plan dərsinin öz faylları (planda seçilən fayl üstündür) və ya «Özüm seçirəm».
- 06475ec-də çatışmazlıq üçün **ümumi şablonlar** son çarə kimi əlavə olunub – bu, mövzudan kənar sual verə bilər (**ləğv olunur**).

## A. Audit
| № | Tapıntı | Risk | Qərar |
|---|---|---|---|
| 1 | Ümumi şablon ehtiyatı (`tpls or T.TEMPLATES`) | KSQ-də keçilməmiş mövzudan sual | **Ləğv.** Yalnız aralıq mövzularına uyğun şablonlar |
| 2 | «Özüm seçirəm» planın fayllarını **əvəz edir** | müəllim bir test seçəndə mövzular itir | Seçilən testlər plana **əlavə olunur**; «yalnız seçdiklərim» ayrıca seçim |
| 3 | Çatışmazlıq yalnız yaradanda bilinir | müəllim nə edəcəyini bilmir | **Hazırlıq paneli** – yaratmazdan əvvəl mövzu üzrə hovuz və tövsiyə |
| 4 | Sual hansı mövzudandır – vərəqdə görünmür | şagird/müəllim üçün qeyri-şəffaf | Vərəqdə sualın yanında kiçik mövzu nişanı, açarda mövzu sütunu |
| 5 | Hovuz kiçik sinifdə çatmır, alternativ yoxdur | KSQ keçirilə bilmir | Müəllimin seçimi: (a) sual sayını azalt (maks. mümkün n göstərilir), (b) «hər sual ən çox 2 şagirdə» (qonşu partalara düşməsin – variant kodları uzaq), (c) test əlavə et |
| 6 | Vərəq sadədir | gözə yatımlı deyil | Peşəkar şablon: başlıq zolağı, bal/qiymət xanası, sual nömrə nişanları, mövzu çipləri, səliqəli kart |
| 7 | Pəncərə uzun mətndir | müəllim üçün ardıcıllıq aydın deyil | 4 addımlı panel: **1 Hazırlıq → 2 Variantlar → 3 Çap → 4 Skan** |

## B. Mövzu qaydası
1. Aralıq: KSQ – əvvəlki KSQ/BSQ-dən bu KSQ-yə qədər keçilmiş plan dərsləri; BSQ – yarımilin bütün mövzuları (dəyişmir).
2. Hər sualın mövzusu: bank faylının bağlı olduğu plan dərsi; şablonun açar sözləri həmin dərsin mövzusu ilə üst-üstə düşməlidir.
3. Slotlar mövzulara bərabər paylanır (hər mövzuya ən azı 1), mövzu daxilində asandan çətinə.
4. Heç vaxt aralıqdan kənar mövzu yoxdur; çatmırsa – B5.
5. Çatışmazlıqda müəllimə 3 yol (A5) – səssiz həll yoxdur.

## C. Hazırlıq paneli (yaratmazdan əvvəl)
- Cədvəl: № · mövzu · testlər (fayllar) · bankda test/açıq sual · şablon · vəziyyət ✓/⚠.
- Üstdə: «N şagird × n sual = X sual lazımdır · hovuz Y» və **maksimal mümkün sual sayı** (sınaq generasiyası ilə).
- Düymə «Variantları yarat» yalnız ✓ olanda aktiv; ⚠-də üç yol düyməsi.

## D. Dizayn
- **Vərəq (A4):** yuxarıda rəngli (çapda boz) zolaq: məktəb · fənn · sinif · KSQ-n · tarix; sağda «Bal ___/100 · Qiymət ___» xanası;
  ad və variant kodu ayrıca sətirdə; suallar dairəvi nömrə nişanı ilə, balı sağda kiçik çipdə, mövzu boz kiçik yazı;
  sütun xətti incə; kartda başlıq «CAVAB KARTI», nümunə xanalar.
- **Pəncərə:** 4 addım kartı (nömrəli dairə + başlıq + vəziyyət), aktiv addım vurğulanır; telefonda sütun.

## E. Testlər
- Aralıqdan kənar mövzu heç vaxt seçilmir (mövzuya uyğun şablon yoxdursa – çatışmazlıq, ümumi şablon yox).
- «Özüm seçirəm» planı əvəz etmir; «yalnız seçdiklərim» əvəz edir.
- Hazırlıq: kiçik hovuzda `ok=false`, `max_n` düzgün; «2 şagirdə» rejimində eyni şagirdə təkrar yoxdur, hər sual ≤ 2 dəfə.
- Vərəqdə mövzu nişanı; açarda mövzu.
