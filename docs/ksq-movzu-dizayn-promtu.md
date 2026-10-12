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

## F. MƏNBƏ QAYDASI (istifadəçi, 13.10.2026 – dəyişməz)
- **X–XI sinif KSQ/BSQ sualları YALNIZ P0010 «Blok İmtahan» fayllarındandır** – perspektiv planda dərslərə təyin olunan həmin fayllar
  (planda ✎ ilə seçilən fayl üstündür). IX sinif – DİM 9 (P007).
- Parametrli şablon suallar **standart olaraq söndürülüb**; yalnız müəllim «Parametrli şablon suallar da» qutusunu işarələsə.
- P0010 çatmasa: «bir sual ən çox 2 şagirdə» və ya sual sayını azaltmaq (hazırlıq paneli göstərir); səssiz əvəzetmə yoxdur.
- Gələcək üçün başqa platformalar (layihələr) seçimi saxlanılır: «Test layihələri» sətrində qoşulur.
- Audit 13.10 (X-b, X-c, X-e, XI-a): «ədədi silsilə» KSQ-1-ə şablondan düşürdü (açar «ədədi» ← «ədədin») – düzəldildi; köhnə variantlar üçün
  «🧹 Uyğunsuz sualları düzəlt» – bütün şablon sualları və planın fayllarından kənar sualları P0010 sualları ilə əvəz edir.

## G. Xüsusi audit (13.10.2026, Bayramlı Zeynəb – X-b, «ədədi silsilə» yenə)
| № | Tapıntı | Qərar (icra olundu) |
|---|---|---|
| 1 | «Düzəlt» basılanda boş P0010 sualı tapılmayıb, sual qalıb, amma variant «yeni» işarələnib – xəbərdarlıq itib | Versiya yalnız uyğunsuz sual qalmayanda yenilənir; yoxlama əvəzdən sonra yenilənmiş fayl siyahısı ilə |
| 2 | P0010-da sualların çoxu testdir, KSQ-də ~70 % açıq → açıq slotlar şablonla dolurdu | Düzgün variantı ƏDƏD olan P0010 test sualı açıq sual kimi də verilir (variantsız, cavab karta) – sual yenə P0010-dandır |
| 3 | Şablon suallar (istifadəçi: «ümumiyyətlə sil») | KSQ-də şablon **yoxdur**: generatorda, əvəzetmədə, pəncərədə söndürülüb; köhnə variantlardakı şablon sualları fon işi (hər 10 dəq) və «🧹 Düzəlt» P0010 sualları ilə əvəz edir |
| 4 | Təkrar müəllimin seçimi idi | **Sistem özü** ən az təkrarı seçir: əvvəl hamıya fərqli, çatmasa «bir sual ən çox k şagirdə» (k = 2, 3, …, ən kiçik mümkün); şagirdin öz variantında təkrar heç vaxt yoxdur |
| 5 | Nəticəsi yazılmamış köhnə variantlar | Fon işi avtomatik təmizləyir (müəllimin düyməyə basması lazım deyil); nəticəli imtahanlarda – «🧹 Düzəlt» düyməsi |

## H. Səhvlər birdə yaranmasın + gələcək illər üçün KSQ bazası (13.10.2026)
- **Məcburi yoxlama** (`ksq_base.validate`, `_guard`): variant bazaya yazılmazdan əvvəl – şablon sualı, layihədən kənar sual, aralıqdan kənar fayl,
  variantda təkrar → variant yazılmır.
- **KSQ bazası** (`ksq_bases`, açar: fənn|sinif|KSQ/BSQ|nömrə|yarımil): mövzular, P0010 faylları, müəllimin düzəlişləri (redaktə) və
  istisnalar (əvəz edilən / bankda gizlədilən suallar). Gələn il eyni KSQ hazırlananda avtomatik tətbiq olunur.
- **Kart ↔ variant bağlılığı**: QR-da variantın barmaq izi (`code~rev`); çapdan sonra sual/açar dəyişibsə köhnə kart qəbul olunmur
  («köhnə çapdır – yenidən çap edin»). Versiyasız köhnə kartlar (13.10-dan əvvəlki çaplar) qəbul olunur.
- **Çap olunmuş variantlar qorunur** (`exam_variants.printed_at`): fon işi toxunmur; 13.10-a qədərki bütün variantlar çap olunmuş sayılır
  (müəllim X b, X c, X e, XI a-nı çap edib).
- Canlı yoxlamada tapılan səhvlər üçün reqressiya testləri: «ədədi» → silsilə, ortaq fayl 0, siniflərarası limit k-nı bloklayırdı,
  hazırlıq asılırdı, «Düzəlt» variantı səhv işarələyirdi.
