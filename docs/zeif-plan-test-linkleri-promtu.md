# Zəif qrup planı (X e) – mövzunun altındakı test linkləri səhvdir (13.10.2026)

## Tələb
«X e zəif planlamada mövzunun altındakı testlərin linkləri səhvdir. Peşəkar promt hazırla və ardıcıl, sistemli icra et.»

## Diaqnoz
1. **Köhnə əl seçimləri yeni mövzulara keçib.** `programs.apply` dərsləri sıra № ilə yeniləyir (id qorunur). `lesson_bank_links`
   isə `plan_lesson_id`-yə bağlıdır. Ona görə köhnə planda N-ci dərsə seçilmiş test faylı yeni planın N-ci dərsində qalıb –
   tamam başqa mövzunun altında görünür (müəllimin seçimi avtomatikdən üstündür).
2. **Zəif tempin törəmə dərsləri səhv uyğunlaşır.** «Məşq və möhkəmləndirmə: X», «Təkrar və bərpa: X», «Bölmə təkrarı: …»,
   «Spiral təkrar: …», «KSQ-yə hazırlıq: …» adları Matcher-ə olduğu kimi gedir. «Məşq», «təkrar», «bərpa» sözləri və
   «Bazanın bərpası» / «Təkrar» bölmə adları uyğunluğu təsadüfi fayllara yönəldir.
3. **KSQ aralığı.** Eyni törəmə dərslər KSQ-nin mövzu siyahısına ayrıca mövzu kimi düşür: məşq dərsi əsas mövzunu təkrarlayır,
   qarışıq təkrar dərslərinin isə uyğun faylı yoxdur.

## Qərar
1. `bank/match.py` – `lesson_query(topic, section)`:
   - «Məşq və möhkəmləndirmə: X», «Təkrar və bərpa: X» → mövzu **X** (əsas mövzunun testi). «Bazanın bərpası» və «Təkrar»
     bölmələri nəzərə alınmır.
   - «Bölmə təkrarı», «Spiral təkrar», «KSQ-yə hazırlıq», yarımil «Təkrar: … yekunlaşdırıcı», KSQ/BSQ → **link yoxdur**.
     Bunlar qarışıq təkrar dərsləridir, tək mövzu faylı səhv olardı. Müəllim istəsə, planda faylı özü seçir.
   - `Matcher.matches` bu qaydanı özü tətbiq edir. Bununla plan, gündəlik plan, portal, mövzu testi və KSQ eyni nəticəni verir.
2. `programs.apply`: dərsin mövzusu və ya bölməsi dəyişəndə həmin dərsin `lesson_bank_links` sətri silinir
   (köhnə seçim yeni mövzuya keçmir).
3. KSQ aralığı (`_range_lessons`, `_range_topics`): törəmə dərslər (məşq, bərpa, təkrar) atlanır. Mövzular yalnız əsas dərslərdən götürülür.
4. Miqrasiya: zəif qrup tempi tətbiq olunmuş planlarda (proqram mənbəyi «Zəif qrup tempi (2 il)») 13.10.2026-dan sonrakı
   dərslərin köhnə əl seçimləri silinir və dərslər avtomatik uyğunluğa qayıdır.

## Yoxlama
- pytest: `lesson_query` qaydaları; apply mövzunu dəyişəndə link silinir, dəyişməyəndə qalır; mövcud testlər.
- Canlı: X e perspektiv planı → 14.10-dan sonra məşq dərsinin linki əsas mövzunun linki ilə eynidir, təkrar dərslərində link yoxdur.
