# Fərdi hazırlıq – 90 dəqiqəlik dərs günləri və «Sinif testləri» üzrə avtomatik perspektiv plan · promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən. Fərdi (repetitor) məkanda planlaşdırmanı
səliqəyə sal: hazırlıq dərsi **gün** üzrə keçir və bir görüş **90 dəqiqədir = 2 akademik saat (2 × 45 dəq.)**. Hər qrupun öz
günləri/saatları qeyd olunan kimi perspektiv plan **avtomatik** yenidən hesablanmalı, mövzular DİM «Riyaziyyat. Sinif testləri»
kitabının ardıcıllığı ilə (V → VI → … → IX/XI) düzülməlidir. Eyni hesablama Python skripti ilə tətbiqdən kənarda da işləməlidir.

İstinad: docs/ferdi-sinif-promtu.md (məkan), docs/repetitor-proqramlar-promtu.md (kurs formatı, mərhələ 2/3/6/7).

## 0. Sabit qaydalar (pozulmur)
- Məktəb məkanı, məktəb zəngləri, məktəb planları **dəyişmir**; hər şey yalnız `schools.kind = private` məkanda.
- Proqramlar qarışdırılmır; jurnalda yazılmış (keçilmiş) mövzular dondurulur – yenidən hesablama yalnız **gələcək** yuvaları dəyişir.
- Jurnal yazıları `(tarix, sıra)` ilə bağlıdır: mövcud vaxtların sırası saxlanılır (`private_times` qaydası).
- İnterfeys mətnləri AZ/EN/RU (`t()`/`tt()`), rəsmi çap (perspektiv plan) – yalnız AZ.
- Yoxlama: aid pytest + `npm run build` (frontend). Canlı DB-yə yazma/miqrasiya – yalnız istifadəçinin razılığı ilə.

## 1. Hazırkı vəziyyət (problem)
- `private_times` hər vaxt sətrini (məs. Ç.a. 17:00–18:30) **bir** yuva sayır → 90 dəqiqəlik görüş planda 1 dərs, həftəlik
  saat yarıya enir, kurs proqramı yuvaya sığmır və ya mövzular 1 dərsə sıxılır.
- `expand_course` mövzunu «dərs» vahidi ilə açır, amma görüş (gün) anlayışı yoxdur: eyni gündə iki hissənin məzmunu
  bir-birinə bağlanmır (məs. 1-ci saat izah, 2-ci saat həmin mövzunun sinif testi).
- Qrupun vaxtı dəyişəndə plan avtomatik yenilənmir – müəllim proqramı yenidən tətbiq etməlidir.

## 2. Vahid: görüş = N akademik saat
- `teaching_assignments.times` formatı geriyə uyğun genişlənir: hər vaxt sətri **görüşdür**, onun saat sayı
  `units = round(müddət / 45)` (60 dəq. → 1, 90 → 2, 135 → 3; 20–44 dəq. → 1). Akademik saat uzunluğu – fərdi məkan
  tənzimləməsi `lesson_minutes` (defolt 45).
- Daxildə görüş `units` qədər ardıcıl sıraya (period) açılır: 17:00–18:30 → `0: 17:00–17:45`, `1: 17:45–18:30`
  (fasilə: `break_minutes`, defolt **5** – istifadəçi qərarı 19.10.2026; 17:00 + 2 saat → 17:00–17:45, 17:50–18:35;
  `units = round((müddət + fasilə) / (45 + fasilə))`). Beləliklə `slots`, `weekly_hours`, `capacity`, jurnal, portal, cədvəl
  mövcud mexanizmlə işləyir – yeni məntiq yalnız `private_times` və `times_out`-da.
- `times_out` görüşü bir sətir kimi qaytarır: `{weekday, start, end, units, periods:[0,1]}`; UI görüş göstərir, saat yox.
- **Miqrasiya**: mövcud fərdi qrupların 90 dəq.-lik vaxtları 2 sıraya açılır; köhnə sıra (birinci hissə) jurnal yazılarını saxlayır,
  ikinci hissə yeni sıra alır. Əvvəl quru rejim (`--dry-run`) hesabatı: hansı qrup, neçə yuva əlavə olunur → istifadəçi təsdiqi.

## 3. Jurnal və davamiyyət – görüş bir dəfə
- Jurnal günündə eyni görüşün hissələri **bir kartda**: «Ç.a. 17:00–18:30 · 2 saat»; davamiyyət **bir dəfə** qeyd olunur və hər iki
  hissəyə yazılır (hissə üzrə fərqli davamiyyət – «Ətraflı» altında). Ev tapşırığı görüşə bir dəfə.
- Qiymət hər hissəyə ayrıca qoyula bilər (məs. 2-ci hissə – sinif testi balı).
- Görüş ləğv olunursa («Dərs olmadı» / bayram) – hər iki hissə boşalır və plan sürüşür (bölmə 5).

## 4. Plan: «Sinif testləri» ardıcıl – görüş şablonu
`expand_course` görüş bilir: yuvalar `(tarix, sıra)` siyahısı əvəzinə görüşlərə qruplaşdırılmış verilir. Mövzu açılışı:
- Ardıcıllıq: `sinif_testleri.json` → V, VI, VII, VIII, IX (XI kursunda X, XI də), sinif daxilində kitabdakı bölmə/mövzu sırası;
  «Təkrar» bölmələri atılır (indiki `_prep_template` kimi). Bölmə seçimi (mərhələ 4) qüvvədə qalır.
- **90 dəqiqəlik görüş (2 saat) üçün defolt şablon** – bir mövzu bir görüşə:
  1-ci saat: «{mövzu}. Nəzəri xülasə və nümunə məsələlər»; 2-ci saat: «{mövzu}. Sinif testi (variant A) və təhlil».
  Mövzuya 2 görüş düşürsə: 1-ci görüş – izah + məsələ həlli, 2-ci görüş – möhkəmləndirmə + sinif testi.
- Yuva bölgüsü: mövzuya düşən saat **cüt** ədəd olur (görüş bölünmür); artıq yuvalar ağır bölmələrə (mövzu sayı çox olan)
  üstünlüklə verilir, qalanı «Ümumi təkrar».
- Aralıq sınaq: hər `mock_every` **görüşdən** bir (defolt 4 görüş = 8 saat) – bütöv görüş (90 dəq.); bölmə/sinif sonunda
  «Sınaq: V sinif materialı» (istəyə görə); sonda «Yekun sınaq». Yuva azdırsa kəsilmə sırası indiki kimidir.
- Resurs sütunu: «DİM «Riyaziyyat. Sinif testləri», {sinif}, «{mövzu}», variant A/B» – variant A dərsdə, B ev tapşırığı /
  təkrar yazı üçün.

## 5. Avtomatik yenidən hesablama
- Qrupun vaxtları, kurs müddəti (`starts_on/ends_on`), fərdi məkanın bayramları və ya bölmə seçimi dəyişəndə: proqram tətbiq
  olunubsa plan **avtomatik** yenidən açılır (`programs.apply` – keçilmiş dərslər dondurulmuş, qalanlar yeni yuvalara).
- Görüş olmayıbsa (ləğv/xəstəlik) keçilməyən mövzu növbəti görüşə sürüşür; kurs sonunda yer çatmırsa xəbərdarlıq.
- Cavabda və UI-da **büdcə xülasəsi** (AZ/EN/RU): «Kurs: 20.10.2026 – 31.05.2027 · 58 görüş · 116 saat · plan tələb edir 112 saat ·
  ehtiyat 4 saat» və ya «… çatmır: 18 saat. Həftəyə 1 görüş əlavə edin və ya bölmələri azaldın».

## 6. Python skripti – `backend/scripts/ferdi_plan.py`
Tətbiqin **eyni funksiyalarını** idxal edir (`private_times` məntiqi, `lesson_slots`, `expand_course`) – ayrıca alqoritm yazılmır.
```
python scripts/ferdi_plan.py --program buraxilis9 --from 2026-10-20 --to 2027-05-31 \
    --time "1 17:00-18:30" --time "5 10:00-11:30" [--holidays tetil.txt] [--sections "V sinif*,VI sinif*"] \
    [--mock-every 4] [--out plan.csv|plan.docx|plan.json]
python scripts/ferdi_plan.py --class-id 123 --dry-run      # DB-dən: qrupun vaxtı, bayramlar, proqram; yazmır
python scripts/ferdi_plan.py --all-private --report        # bütün fərdi qruplar: görüş/saat büdcəsi, çatışmazlıq
```
- Çıxış: büdcə xülasəsi + cədvəl (№, tarix, gün, vaxt, saat 1/2, bölmə, mövzu, resurs, qiymətləndirmə). `.docx` – rəsmi
  perspektiv plan forması (AZ), `.csv` – Excel üçün.
- `--class-id` DB-yə yazmır; `--apply` yalnız açıq bayraqla və təsdiq sualı ilə (canlı DB – istifadəçinin razılığı).
- Testlər: `tests/test_ferdi_plan.py` – (a) 90 dəq. → 2 saat; (b) 2 görüş/həftə, 1 bayram → yuva sayı düzgün; (c) mövzular
  kitab ardıcıllığında, saat sayı cüt; (d) vaxt dəyişəndə yalnız gələcək dərslər dəyişir; (e) skript və API eyni nəticə verir.

## 7. İnterfeys (fərdi məkan)
- Qoşulma forması «Dərs günləri»: gün + başlama + **müddət** seçimi (45 / 60 / 90 / 135 dəq., defolt 90) → bitmə avtomatik;
  altda «Həftədə 2 görüş · 4 saat · kursda ≈ 58 görüş».
- Qrup kartında: «Ç.a., Ş. · 90 dəq.», büdcə nişanı (yaşıl – sığır, sarı – ehtiyat < 5%, qırmızı – çatmır).
- Plan səhifəsində görüş sətirləri birləşmiş: «20.10 Ç.a. 17:00–18:30 | 1-ci saat … | 2-ci saat …».
- Həftəlik cədvəldə fərdi görüş bir blok (90 dəq.).

## 8. Əlavələr (metodist təklifi – hər biri ayrıca seçilə bilər)
1. **Giriş diaqnostikası**: ilk görüş – V–IX üzrə qısa diaqnostik test; nəticəyə görə zəif bölmələrə əlavə görüş təklifi.
2. **İmtahan tarixinə geri sayım**: qrupa imtahan tarixi (müəllim yazır, uydurulmur) → kurs sonu ondan 1 həftə əvvəl,
   son 2–4 görüş – tam sınaqlar.
3. **Spiral təkrar**: hər 3-cü görüşün 2-ci saatının ilk 10 dəqiqəsi – əvvəlki bölmədən 3 tapşırıq (planda resurs qeydi).
4. **Əvəz görüşü**: ləğv olunan görüş üçün «Əvəz görüşü əlavə et» – plan geri sürüşmür.
5. **Şagird portalı**: şagird öz qrafikini görür – «növbəti görüş: Ş. 10:00, mövzu …, ev tapşırığı: variant B».
6. **Valideyn hesabatı** (ayda bir, AZ/RU): keçilən mövzular, sinif testi balları, davamiyyət.

## 9. Qəbul meyarları
- Ç.a. + Ş. 90 dəq., 20.10.2026–31.05.2027 → hər görüş 2 saat; `weekly_hours = 4`; plan V→IX ardıcıl, mövzu saatları cüt.
- Vaxt dəyişəndə plan özü yenilənir, keçilmiş mövzular toxunulmaz; məktəb məkanında heç bir nəticə dəyişmir.
- Skript (`--program` və `--class-id`) ilə API eyni dərs siyahısını verir; bütün aid testlər + `npm run build` keçir.
- Yeni mətnlər AZ/EN/RU; rəsmi çap AZ.

**İcra ardıcıllığı (kodcu, ayrıca commit-lər):** 2 (vahid + miqrasiya quru rejim) → 4 (plan şablonu) → 6 (skript + testlər) →
5 (avtomatik yenilənmə) → 3 (jurnal kartı) → 7 (UI) → 8 (seçilən əlavələr). Miqrasiyanın canlıda tətbiqi və deploy – Rəhbər,
istifadəçinin razılığı ilə.
