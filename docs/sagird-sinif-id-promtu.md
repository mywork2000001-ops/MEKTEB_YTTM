# Prompt: şagird əlavə etmə, sinif ID-si, bölünmədə şagird seçimi və şagird səhifəsinin auditi

**Kontekst.** «Müəllim köməkçisi» (FastAPI + React). Siniflər `classes` (kind: TOM | adi | qrup; bölünmə qrupu –
`parent_id` olan qrup), şagirdlər `students` (ana sinifdə), qrup üzvlüyü `group_members`. Müəllimin şikayəti (03.10.2026):
«sinfə şagird əlavə edə bilmirəm», «hər sinfə ID təyin edin ki, bölünmədə sinfin bölünən şagirdlərini ayrıca qrupa seçə bilim»,
«şagird səhifəsini audit edib düzəldin».

## Diaqnoz (canlıda yoxlanıb)
- API ilə əlavə etmə işləyir (test şagirdi yaradılıb, dərhal silinib).
- **Səhv – interfeys:** «+ Şagird» pəncərəsində «Şagirdi əlavə et» basılan kimi pəncərə **dərhal bağlanır**, giriş kodu
  və PIN göstərilmir – müəllim əlavə olunmadığını düşünür, PIN də itir.
- «Siniflər və qruplar» səhifəsində şagird əlavə etmək düyməsi yoxdur (yalnız Tənzimləmələrə keçid).
- Arxivdə (passiv) eyni adlı şagird varsa, 409 xətası çıxır, amma geri qaytarmaq yolu göstərilmir.
- Bölünmə qrupunda üzv seçimi var, amma şagirdlərin ID-si görünmür, axtarış yoxdur, sinfin ID-si görünmür.

## 1. Şagird əlavə etmə
- Əlavə edəndən sonra pəncərə açıq qalır: yaşıl blokda ad, **giriş kodu (ID)** və **PIN**, «Giriş vərəqəsini çap et»;
  forma təmizlənir – növbəti şagirdi dərhal yazmaq olur; siyahı və say yenilənir.
- Təkrar şagird (eyni ad + doğum tarixi): aydın mesaj; şagird arxivdədirsə – «Arxivdən geri qaytar» düyməsi.
- Doğum tarixi gələcəkdə ola bilməz; ad boşluqları normallaşdırılır; ən az ad + soyad (2 söz).
- Giriş kodu yaradılarkən həm şagird kodları, həm də istifadəçi loginləri ilə toqquşma yoxlanır (növbəti boş nömrə).
- «Siniflər və qruplar» səhifəsində seçilmiş sinifdə **«+ Şagird»**; bölünmə qrupunda – şagird ana sinfə yazılır və
  dərhal qrupa üzv edilir.

## 2. Sinif ID-si
- Hər sinfin/qrupun **ID-si** (qısa kod: `XB`, `XBQ`) bütün siyahılarda görünür («ID: XB»).
- Müəllim/admin ID-ni redaktə edə bilər (hərf, rəqəm; 1–8 simvol; məktəb + tədris ilində unikal). Mövcud şagird kodları
  dəyişmir, yeni şagirdlər yeni ID ilə nömrələnir.
- Şagird ID-si (giriş kodu, məs. `XB-007`) sinif ID-si + sıra nömrəsidir.

## 3. Bölünmədə şagird seçimi
- «Bölünmə / şagird» pəncərəsində: sinfin ID-si, hər şagirdin ID-si, axtarış (ad və ya ID), sayğaclar.
- **ID ilə seçim:** «XB-001, XB-005 …» yazıb/yapışdırıb «Qrupa əlavə et» – həmin şagirdlər qrupa keçir; tanınmayan ID-lər
  göstərilir. «Hamısı», «Heç biri», «Tək nömrələr / cüt nömrələr» (sürətli yarıya bölmə).
- «Siniflər və qruplar»da bölünmə qrupu seçiləndə yalnız qrupun üzvləri görünür (ID-ləri ilə).

## 4. Şagird səhifəsinin auditi (düzəlişlər)
- Axtarış Azərbaycan hərfləri ilə düzgün işləsin (İ/i, I/ı) – `toLocaleLowerCase('az')`; ID ilə də axtarılsın.
- Şagird siyahısında ID sütunu, IX balları, səviyyə; boş sinifdə izah və «+ Şagird».
- Şagird kartında ID və sinif ID-si; redaktə Tənzimləmələrdən.

## 5. Qəbul meyarları
- Müəllim şagird əlavə edəndə ID və PIN-i görür, siyahıda şagird dərhal görünür.
- Arxivdəki təkrar şagird bir kliklə geri qaytarılır.
- Sinif ID-si görünür və redaktə olunur; bölünmədə ID ilə və siyahıdan seçim işləyir.
- Backend testləri keçir, frontend yığılır.
