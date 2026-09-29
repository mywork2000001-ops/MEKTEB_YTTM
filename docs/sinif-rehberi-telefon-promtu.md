# Promt: «Sinif rəhbəri» bölməsinin telefon rejimində auditi və təkmilləşdirilməsi

## Rol
Sən mobil interfeys (UX) mütəxəssisi və bu tətbiqin (React + Vite) proqramçısısan. Sinif rəhbərinin gününü bilirsən:
səhər dəhlizdə və ya sinifdə telefonla davamiyyət qeyd edir, dərs arasında valideynə zəng edir, iclasdan sonra qeyd yazır.
Hər əməliyyat **bir əllə, 2–3 toxunuşla, sürüşdürmədən** edilməlidir.

## Yoxlanılan ekranlar (360 px və 412 px en, toxunma rejimi)
İcmal · Dərslər · Qiymət cədvəli · Davamiyyət (Gündəlik qeyd, Aylıq cədvəl, Dövr üzrə) · Dərs cədvəli · Valideynlər
(redaktə pəncərəsi) · Rəhbərin jurnalı (yeni qeyd pəncərəsi) · Çap / PDF.

## Meyarlar
1. **Ekran eni:** heç bir ekran enə daşmır. Geniş cədvəl yalnız öz sürüşən qutusunda olur və ad sütunu sabit qalır.
2. **Toxunma hədəfi:** düymə, seçim və sahə ən azı 40–44 px hündürlükdə; qonşu hədəflər arasında boşluq var.
3. **Əsas əməliyyat ilk ekranda:** gündəlik davamiyyətdə şagird siyahısı dərhal görünür. «Yadda saxla» həmişə əlçatandır
   (aşağıda, menyu zolağının üstündə sabit).
4. **Telefon görünüşü:** geniş cədvəl əvəzinə kart və ya siyahı. Davamiyyətdə əvvəl **dərs saatı** seçilir, sonra şagirdlər
   üzrə iri V / Q / Ü / G düymələri gəlir. Bütün gün üçün tez əməliyyat var.
5. **Oxunaqlılıq:** əsas mətn ≥ 14 px, köməkçi mətn ≥ 12 px, rəng təzadı kifayət qədərdir.
6. **Pəncərələr:** alt menyunun üstündə açılır, «Yadda saxla» görünür, klaviatura açılanda sahə görünür qalır.
7. **Məzmun eynidir:** telefon görünüşü kompüter görünüşü ilə eyni məlumatı və eyni qaydaları verir
   (jurnal kilidi 🔒, üzrlü səbəb, gələcək gün yoxdur).
8. **Xəta yoxdur:** JS xətası və uğursuz sorğu yoxdur.

## İcra
- Avtomatik yoxlama (Playwright, 360/412 px, isMobile + hasTouch): enə daşma, kiçik hədəflər, kiçik mətn, JS xətaları.
- Ekran görüntüləri ilə əl ilə yoxlama (avtomatik tapıntı ekranla təsdiqlənmədən səhv sayılmır).
- Düzəliş → `tsc` + `vite build` + `pytest` → təkrar yoxlama → `docs/sinif-rehberi-telefon-auditi.md` → commit + push.
