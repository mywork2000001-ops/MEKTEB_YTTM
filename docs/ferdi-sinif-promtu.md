# Fərdi (repetitor) siniflər – məktəbdən ayrı şəxsi məkan · promt (04.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və məxfilik auditorusan. Məqsəd: müəllim məktəbə aid olmayan öz hazırlıq
(repetitor) siniflərini və qruplarını yarada bilsin; bu siniflər, şagirdlər, jurnal, testlər və nəticələr **məktəbin hesabatlarına,
məktəb siyahılarına, adminə və digər müəllimlərə heç vaxt düşməsin**, amma müəllim tətbiqin bütün imkanlarından (jurnal, perspektiv
plan proqramları, onlayn testlər, sınaqlar, analitika, çap, çat, şagird portalı) burada da istifadə etsin.

## 0. Sabit qaydalar (dəyişmə)
- Məktəbin bütün mövcud qaydaları, məlumatları və hesabatları olduğu kimi qalır; mövcud siniflər məktəbdə qalır.
- Məxfilik: fərdi məkanı yalnız onu yaradan müəllim görür (məktəb admini də görmür); fərdi şagird yalnız öz müəllimini görür.
- Uşaq İD, pinkod, şəxsiyyət vəsiqəsi saxlanmır (mövcud qayda); şagird girişi – giriş kodu + PIN.
- Sınaq/test bankı, DİM «Sinif testləri» proqramları, çap şablonu – ortaq resurslardır, məkan fərqi yoxdur.

## 1. Həll: «məkan» (workspace)
Tətbiqdə məlumatların demək olar hamısı `school_id` ilə ayrılır (siniflər, şagirdlər, tədris ili, bayramlar, zənglər, çat otaqları,
əlavə məşğələ, məktəb hesabatı). Ona görə fərdi siniflər **ayrıca şəxsi məkanda** saxlanılır:
- `schools.kind`: `school` (adi məktəb) | `private` (fərdi məkan); `schools.owner_id` – fərdi məkanın sahibi.
- Fərdi məkan ilk dəfə «Fərdi sinif yarat» deyiləndə avtomatik yaranır: ad «{Müəllim} – fərdi hazırlıq» (dəyişmək olar), öz tədris ili
  (defolt – əsas məktəbin təqvimi və bayramları köçürülür, sonra müəllim dəyişə bilər), öz dərs vaxtları (zənglər).
- Müəllimin **aktiv məkanı**: `users.active_school_id` (əsas məktəb – `users.school_id`). Bütün mövcud sorğular aktiv məkanla işləyir –
  beləliklə fərdi siniflər avtomatik olaraq məktəb sorğularından ayrılır, mövcud kodun əksəriyyəti dəyişmədən işləyir.
- Fərdi məkan **məktəb axtarışında görünmür**, başqa müəllim ona qoşula bilmir, admin siyahısında yoxdur.

## 2. İnterfeys
- **Sinif yaradanda məkan seçimi:** Tənzimləmələr → Siniflər → «Yeni sinif / qrup» formasında «Harada»:
  ○ Məktəb – {məktəbin adı} ○ Fərdi (hazırlıq / repetitor) – məktəbə aid deyil. Fərdi seçiləndə izah: «Məktəbin hesabatlarına,
  siyahılarına və adminə düşmür».
- **Məkan dəyişdiricisi** yuxarı paneldə (yalnız fərdi məkanı olan müəllimdə): «Məktəb · Fərdi hazırlıq». Aktiv məkan rəng nişanı ilə
  (fərdi – fərqli rəngli zolaq və «Fərdi» nişanı), seçim yadda qalır. Bütün səhifələr (Əsas, Siniflər, Jurnal, Plan, Tapşırıqlar,
  Analitika, Çat, Tənzimləmələr) aktiv məkana görə göstərir.
- Tənzimləmələr → **Fərdi məkan**: ad, tədris ili tarixləri, bayramlar, dərs vaxtları; «Məktəbin təqvimini yenidən köçür».
- Fərdi şagird: ad, soyad (ata adı istəyə görə), sinfi (məs. «IX hazırlıq»), valideyn telefonu; giriş kodu prefiksi fərqli (məs. `F-`),
  giriş vərəqəsi çapı mövcud qaydada.
- Çap sənədlərinin başlığında məktəbin adı əvəzinə fərdi məkanın adı; «Direktor müavini» imzası çıxmır (yalnız müəllim).

## 3. Məlumat və hesabatların ayrılması (yoxlanılmalı yerlər)
| Yer | Qayda |
|---|---|
| Məktəb üzrə hesabat (`/api/school/performance`), sinif rəhbəri, admin siyahıları | yalnız `kind = school` məkan; fərdi siniflər heç vaxt |
| Müəllimin öz analitikası, həftəlik xülasə, Əsas səhifə | aktiv məkan; fərdi məkanda ayrıca |
| Müəllim otağı (staff çat), məktəb kontaktları | fərdi məkanda yoxdur; çat – yalnız müəllim ↔ fərdi şagirdlər və fərdi sinif söhbəti |
| Sınaq imtahanları (çoxsinifli) | sinif seçimi aktiv məkanla məhdud; məktəb və fərdi sinif bir sınaqda qarışmır |
| Perspektiv plan proqramları | kitab proqramları ortaq; müəllimin öz proqramları hər iki məkanda görünür (sinfə tətbiq aktiv məkanda) |
| Əlavə məşğələ, materiallar | aktiv məkan |
| Audit jurnalı | fərdi məkanın yazıları məktəb adminin audit siyahısında görünmür |
| Şagird portalı | fərdi şagird yalnız öz siniflərini, öz müəllimini görür |

## 4. Təhlükəsizlik
- Hər endpoint-də məkan yoxlaması: istifadəçi yalnız öz əsas məktəbinə və ya **özünə məxsus** fərdi məkana keçə bilər
  (`active_school_id` dəyişdiriləndə server yoxlayır); başqasının fərdi məkanına sorğu – 404.
- Admin rolu fərdi məkanda qüvvədə deyil: məktəbin admini başqa müəllimin fərdi məkanını görmür; müəllimin öz fərdi məkanında
  o, «sahib»dir (sinif yaratma, şagird əlavə etmə, Tənzimləmələr).
- Fərdi şagird məktəbin şagirdi ilə eyni şəxsdirsə – ayrıca qeyd (birləşdirilmir), məlumat sızmasın.

## 5. Miqrasiya
`schools.kind` (defolt `school`), `schools.owner_id`, `users.active_school_id` (defolt = `school_id`). Mövcud məlumatlar dəyişmir.

## 6. Testlər
- fərdi sinif yaradılır → məktəb hesabatında, sinif rəhbəri siyahısında, admin siniflərində, məktəb axtarışında **yoxdur**;
- admin və başqa müəllim fərdi sinif/şagird/jurnal/çata sorğu edir → 404/403;
- aktiv məkan dəyişir → Siniflər, Jurnal, Analitika yalnız həmin məkanı göstərir; başqasının məkanına keçmək – 404;
- fərdi şagird portalı: yalnız öz sinfi; çatda yalnız öz müəllimi;
- sınaq imtahanında məktəb və fərdi sinif qarışmır; çap başlığında fərdi məkanın adı, direktor müavini imzası yoxdur;
- mövcud bütün testlər keçir.

## 7. Qəbul meyarları
Müəllim sinif yaradanda «Məktəb / Fərdi» seçir; fərdi sinif tam işləyir (jurnal, plan, test, analitika, çap, portal), amma məktəbin heç
bir hesabatında, siyahısında və adminin görünüşündə yoxdur; məkanlar arasında bir kliklə keçid; məlumat sızması testlərlə yoxlanılıb.

## 8. İstifadəçidən soruşulacaq (başlamazdan əvvəl)
1. Fərdi məkanın tədris ili məktəbinki ilə eyni olsun, yoxsa öz tarixləri (məs. yay hazırlığı)?
2. Fərdi şagirdlərin portala girişi lazımdırmı (onlayn test, nəticələr), yoxsa yalnız müəllim jurnalı?
3. Fərdi sinifdə KSQ/BSQ (summativ) lazımdırmı, yoxsa yalnız formativ və sınaqlar?
4. Fərdi məkan bir dənə olsun, yoxsa bir neçə (məs. «Hazırlıq kursu», «Olimpiada»)?

## 9. İcra vəziyyəti (04.10.2026)
Götürülən qərarlar (istifadəçi «başlayaq» dedi, suallara cavab vermədi): tədris ili məktəbdən köçürülür; fərdi şagirdlərin portalı açıqdır;
fərdi sinifdə KSQ/BSQ defolt söndürülüdür (qoşulma formasında yandırılır); bir fərdi məkan.
- miqrasiya `e1f5b8c3a9d2`: `schools.kind/owner_id`, `users.active_school_id`, `audit_log.school_id`;
- `workspaces.py`: aktiv məkan sorğu boyu `school_id`-yə tətbiq olunur (`set_committed_value` – bazaya yazılmır); `ensure_private`;
- `/api/workspaces` (siyahı, yaratma, aktiv, ad/zənglər); sinif yaratmada `private: true`;
- məktəb axtarışı, məktəbə qoşulma, admin redaktəsi – fərdi məkan yoxdur; admin audit jurnalında fərdi yazılar yoxdur;
- müəllimin bütün «mənim siniflərim» siyahıları (`ws_cond`) aktiv məkanla məhdud; çatda fərdi məkanda «Müəllim otağı» yoxdur,
  fərdi şagird öz müəllimi ilə yazışır; çapda fərdi məkanın adı, rəhbərlik imzası yoxdur;
- interfeys: «Harada: Məktəb / Fərdi», yuxarıda «Məktəb · Fərdi» keçidi (fərdi – bənövşəyi zolaq), Tənzimləmələr → «Fərdi məkan».
Qalan: fərdi məkanın tədris ili və bayramlarını interfeysdən dəyişmək (hazırda məktəbdən köçürülmüş təqvim).
