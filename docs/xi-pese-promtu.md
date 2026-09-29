# XI peşə sinfinin tətbiqə əlavə olunması – peşəkar promt və icra ardıcıllığı

**Rol:** məktəb İKT mütəxəssisi + riyaziyyat metodisti. **Məqsəd:** XI peşə sinfinin şagirdlərini UTİS-dən dəqiq, məxfiliyi qoruyaraq tətbiqə köçürmək, sinfin səviyyəsini qeyd etmək və planlaşdırmanı (gündəlik plan, onlayn test) bu sinfin real vəziyyətinə uyğunlaşdırmaq.

## Mənbə
- UTİS ixracı: `Şagird 27092026 Utis.pdf` (27.09.2026) – «Tədris sinfi» = **11 p** (14 şagird).
- Müəllimin məlumatı (30.09.2026): **yalnız Axundzadə Tural 60 baldan yuxarı** toplayıb, qalanları zəifdir.
- Sinif: «XI peşə sinfi», adi sinif (TOM deyil), həftədə 4 saat (B.e. 1, 2; Ç.a. 1; Ç. 1), öz zəngi (1-ci saat 08:00–08:45). Başlıqda məktəb – «Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi».

## Qaydalar (pozulmaz)
1. **Məxfilik:** UTİS PIN-kodu, şəxsiyyət vəsiqəsinin seriya/nömrəsi, Uşaq İD tətbiqə **yazılmır**. Yalnız: soyad, ad, ata adı, doğum tarixi, cins (ata adındakı «oğlu/qızı», «-oviç» → oğlan).
2. Şəxsi məlumat **repoya (GitHub) düşmür** – idxal müəllimin fayl yükləməsi ilə olur.
3. Təkrar idxal eyni şagirdi ikinci dəfə yaratmır (ad + doğum tarixi).
4. Yalnız tətbiqdə UTİS sinfi ilə bağlanmış siniflər idxal olunur (XI peşə sinfi ↔ «11 p»); faylda digər siniflər (0–10, 11 a) ötürülür.
5. Səviyyə müəllimin fənni üzrə əl ilə təyin olunur (LevelOverride) və qeyd saxlanılır; müəllim sonra dəyişə bilər.

## İcra ardıcıllığı
| № | İş | Harada | Yoxlama |
|---|---|---|---|
| 1 | «XI peşə sinfi» ↔ UTİS «11 p» bağlantısı (yeni quraşdırmada və canlıda avtomatik – başlanğıc doldurması boş bağlantını tamamlayır) | `domain/calendar.py`, `seed.py` | test |
| 2 | UTİS idxalı **PDF** faylını da qəbul edir (xlsx kimi): sətirlər «№ Soyad Ad Ata adı Uşaq İD dd/mm/yyyy sinif Seriya Pinkod» | `importers/utis.py`, interfeys «UTİS faylı (.xlsx / .pdf)» | test + real faylla quru yoxlama (14 şagird) |
| 3 | İdxal: portal kodu XIP-001…XIP-014, ilkin PIN avtomatik, giriş vərəqələri çapa hazır | Tənzimləmələr → Şagirdlər → İdxal | canlıda |
| 4 | Səviyyə: Axundzadə Tural – **Orta** (60+ bal; dəqiq bal ≥ 70 olarsa «Güclü» edilməlidir), qalan 13 şagird – **Zəif**; qeyd: «UTİS 27.09.2026 / müəllim, 30.09.2026» | Səviyyə (müəllim) | canlıda |
| 5 | Gündəlik plan promtu sinfin tərkibini bilir: «14 şagird: 1 orta, 13 zəif» → diferensial yanaşma, addım-addım nümunə, əsas bacarıqlar | `lessonplans._context`, `daily_plan.user_prompt` | test |
| 6 | Giriş vərəqələri (ID + PIN + QR) çap olunur və paylanır | Tənzimləmələr → Şagirdlər → «Giriş vərəqələri» | müəllim |

## Metodist tövsiyəsi (zəif sinif üçün)
- Hər dərsdə 5–7 dəqiqəlik **əsas bacarıq təkrarı** (hesablama, sadə tənlik, faiz).
- Tapşırıqlar üç pillədə: nümunə üzrə → oxşar → tətbiq; ev tapşırığı qısa və məcburi hissə + könüllü hissə.
- Formativ qiymətləndirmə tez-tez, qısa (3–5 sual); onlayn testlərdə «göstərici izah» açıq.
- Axundzadə Tural – «köməkçi şagird» (cüt işində lider), əlavə çətin tapşırıq.
