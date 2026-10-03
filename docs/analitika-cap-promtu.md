# Analitika, hesabat və çap – təkmilləşdirmə promtu

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi, məktəb metodisti (təhsil statistikası) və rəsmi sənəd redaktorusan.
Məqsəd: müəllimin, sinif rəhbərinin və direktor müavininin **eyni rəqəmləri** gördüyü, ilin istənilən günündə düzgün işləyən,
telefonda rahat oxunan və məktəbə təqdim ediləcək **rəsmi A4 sənədlər** verən analitika bölməsi.

**Əsas sənəd:** `docs/analitika-cap-auditi.md` (A1–A9, P1–P10 tapıntıları). Hər tapıntını bu promtun bəndinə bağla,
düzəlt, test yaz, brauzerdə (kompüter 1366 px və telefon 360 px) yoxla, ayrıca commit et.

## 0. Sabit qaydalar (istifadəçinin qərarları – dəyişmə)
- KSQ/BSQ: bal → faiz → qiymət 0–30 → 2, 31–60 → 3, 61–80 → 4, 81–100 → 5; yarımil = (KSQ ortası)×0,4 + BSQ×0,6, adi yuvarlaqlaşdırma.
- Reytinq çəkiləri: qiymət 40 · KSQ 30 · ev tapşırığı 15 · davamiyyət 15; olmayan komponentin çəkisi qalanlara bölünür;
  yalnız davamiyyət/ev tapşırığı ilə reytinq verilmir. Davamiyyət xəbərdarlığı – 25%-dən çox.
- Sınaq imtahanları formativ qiymətə və fənn reytinqinə **daxil deyil** (ayrıca göstərilir).
- Çap: A4 portret (geniş cədvəllər – albom), ağ-qara (Canon), Times New Roman, rəsmi sənəd yalnız Azərbaycan dilində,
  ondalıq vergül (3,53), tarix gg.aa.iiii. Məxfilik: şagird yalnız özünü və adsız sinif ortasını görür.
- Bütün hesablamalar serverdə, `domain/rules.py`-dakı funksiyalarla; interfeys yalnız göstərir. «Bu gün» – Asia/Baku.

## 1. Hesablamanın düzgünlüyü (əvvəl bu)
1. **İrəliləyiş (A1).** Dövrü təqvim ortasından deyil, **faktiki məlumatdan** böl: `[p.a, min(p.b, bu gün)]` aralığında
   yazılmış dərsləri (və ya qiymətləri) say, iki bərabər yarıya ayır; hər yarıda ən azı 2 nəticə yoxdursa – `None` və
   interfeysdə «məlumat azdır» izahı. Test: 15.09–03.10 arası qiymətlər, dövr I yarımil → irəliləyiş hesablanır.
2. **Avtomatik jurnal yazısı (A2).** Onlayn testin yaratdığı `JournalEntry`-ni işarələ (məs. `auto_from_task`
   və ya «davamiyyət yoxdursa və müəllim saxlamayıbsa»). «Dərs sayı → yazılıb», «yazılmamış dərslər», sinif rəhbərinin
   cəmi və davamiyyət xəritəsi bunu **yazılmamış** saysın; jurnalda həmin dərs «test qiymətləri var, dərs yazılmayıb» kimi görünsün.
   Miqrasiya mövcud yazıları düzgün işarələsin. Test: yalnız test qiyməti olan dərs → `written` artmır, `missing`-də qalır.
3. **Fənnə uyğun IX balı (A3).** `levels._exam_score` məntiqini ümumi funksiyaya çıxar (riyaziyyat/cəbr/həndəsə → riyaziyyat,
   Azərbaycan dili/ədəbiyyat → dil, ingilis/rus/… → xarici dil, uyğun gəlməyən fənn → balsız). `analyze()`, risk, Excel
   («IX bal» başlığı fənnə görə) bunu istifadə etsin. Test: dil fənni üzrə ilkin səviyyə dil balından gəlir.
4. **Vahid səviyyə (A4).** Səviyyənin tək mənbəyi: «Səviyyə qrupları» bölgüsü varsa o, yoxdursa analitikanın avtomatik
   səviyyəsi. Analitikada mənbə nişanı (bölgü / müəllim / nəticələr / IX balı) və bölgüyə keçid. İzah mətnini düzəlt.
5. **Minimal qiymət sayı (A5).** Formativ ortadan fənn qiyməti çıxarmaq üçün ən azı **3 qiymət** (sabit `MIN_MARKS`);
   az olanlar «qiymətləndirilməyib (az qiymət)» sayılır və ayrıca göstərilir. Müvəffəqiyyət ekranında xəbərdarlıq zolağı.
   *(İstifadəçi qərarı lazımdır: hədd 3 olsun?)*
6. **Defolt dövr (A6):** bu gün hansı yarımildədirsə o; tətildə – sonuncu bitmiş yarımil.
7. **Vaxt zonası (A7):** onlayn cəhdin tarixi `submitted_at` Bakı vaxtına çevrilərək dövrə salınsın.
8. **«Orta qiymət» terminləri (A8):** hər kartda nəyin ortası olduğunu yaz («bütün formativ qiymətlərin ortası» /
   «şagirdlərin fənn qiymətlərinin ortası»); şagird portalında eyni ad.
9. **Şagird müqayisə zolağı (A9):** orta qiymət şkalası 2–5.

## 2. Modullarla əlaqələndirmə
1. **Sınaq imtahanları → analitika (ayrıca blok, reytinqə qarışmadan):** şagird sətrində «sınaq ortası %», son sınaq,
   dinamika (▲/▼); sinif üzrə orta; riskə yeni amil – «son 2 sınaq < 40%» (çəkisi `RISK_WEIGHTS`-də, izahlı).
2. **Əlavə məşğələ:** risk və şagird kartında «məşğələyə yazılıb / davamiyyəti %»; zəif şagird məşğələyə yazılmayıbsa təklif
   («Zəif qrupa əlavə et»). Məşğələ qiyməti jurnala yazılmır – yalnız göstərici.
3. **Davamiyyət:** fənn analitikasında iki rəqəm – «mənim dərslərim» və «bütün dərslər (sinif rəhbərinin birləşmiş qeydi)»;
   25% xəbərdarlığı hansına görədirsə, aydın yaz. Sinif rəhbəri ekranı ilə eyni funksiya (`homeroom_att.merged`).
4. **Risk → hərəkət:** risk siyahısında hər şagird üçün «Valideynlə əlaqə yaz», «Fərdi plan aç», «Mövzu testi təyin et»
   düymələri (mövcud API-lər); fərdi planı olan şagirddə nişan.
5. **Məktəb üzrə hesabat (admin / direktor müavini):** yeni `GET /api/school/performance?semester=` – bütün siniflər və
   fənlər üzrə müvəffəqiyyət, keyfiyyət, SOU, «2»-lilər siyahısı, yazılmamış dərslər, 25%+ buraxanlar; paralel üzrə
   (X a/b/c…) müqayisə. Yalnız admin; müəllim yalnız öz siniflərini görür. Mövcud `subject_grades`/`metrics`/`lesson_counts`.
6. **Bildiriş:** həftəlik (bazar ertəsi) müəllimə xülasə – yeni qırmızı risk, 25%-i keçən, 3+ yazılmamış dərs (mövcud
   bildiriş sistemi; Web Push varsa ora da).

## 3. Çap və ixrac
1. **Vahid sənəd şablonu (`print.ts`):**
   - məktəb adı **bazadan** (`School.name`; `/api/auth/me` və ya `/api/school` ilə gəlsin) – `SCHOOL` sabiti və
     gündəlik planın ayrıca `header_school`-u bir mənbəyə birləşsin (gündəlik planda fərdi dəyişmə saxlanılırsa, defolt `School.name`);
   - başlıq: məktəb → sənədin adı → sinif · fənn · dövr · tədris ili;
   - altbilgi: «Tərtib edildi: gg.aa.iiii · Müəllim köməkçisi» və **«Səhifə X / Y»** (server PDF: Chromium `displayHeaderFooter`
     + `footerTemplate`; brauzer çapı üçün CSS `@page` altbilgisi mümkün olduğu qədər);
   - imza bloku parametrlə: `signers: ['Fənn müəllimi', 'Sinif rəhbəri', 'Direktor müavini (tədris işləri üzrə)']` – ad və «____»;
   - cədvəl başlığı hər səhifədə təkrarlansın (`thead{display:table-header-group}`), sətir bölünməsin.
2. **Analitika çap mərkəzi** (Reports «Çap / PDF» tabı) – checkbox-larla bir sənəddə seçilən bölmələr:
   Müvəffəqiyyət (rəsmi forma: say, «5/4/3/2», müvəffəqiyyət %, keyfiyyət %, SOU, qiymətləndirilməyənlər – P1),
   Reytinq, Dərs sayı və yazılmamış dərslər, Davamiyyət (25%+ qalın), Güclü/orta/zəif. **Risk** defolt **söndürülmüş**,
   işarələnəndə «Daxili istifadə üçün» damğası (P4).
3. **Önbaxış = çap (P2):** ekrandakı önbaxış `docHtml()` nəticəsini iframe-də (`srcdoc`) göstərsin – ayrıca React maketi silinsin.
4. **Şagird hesabatı (P5):** ad, sinif, giriş kodu, dövr; KSQ/BSQ, onlayn testlər, sınaq dinamikası; sinif ortası adsız.
5. **Excel (P7):** başlıqda məktəb adı və dövr, sonda imza sətirləri; ayrıca vərəqlər – «Müvəffəqiyyət», «Reytinq»,
   «Davamiyyət» (xəritə: q/ü/g), «Dərs sayı». Ağ-qara, A4, sığdırma.
6. **Server PDF şrifti (P8):** Docker-ə `fonts-liberation` (və ya Times-uyğun açıq şrift) açıq quraşdırılsın; canlıda
   «Əə Ğğ Iı İi Şş Çç Öö Üü» sınaq səhifəsi PDF-ə çevrilib yoxlansın; sənəd CSS-də şrift ardıcıllığı
   `"Times New Roman","Liberation Serif","Tinos",serif`.
7. **Telefonda çap (P9):** popup bloklananda `alert` yox – tətbiq daxilində bildiriş və «PDF yüklə» düyməsi (server PDF
   birbaşa yüklənsin, pəncərəsiz).

## 4. Telefon görünüşü (analitika)
- Reytinq, Müvəffəqiyyət, Risk – telefonda kart siyahısı (yer, ad, reytinq, ▲/▼, səviyyə nişanı); kompüterdə cədvəl.
- Davamiyyət xəritəsində şagird adı sabit (`sticky-first`), telefonda ad + son 10 dərs, qalan sürüşmə ilə.
- 8 tab → telefonda 2 sıra və ya «Göstəricilər / Şagirdlər / Davamiyyət / Çap» qruplaşdırması.
- Yoxlama: 360 px-də səhifə üfüqi daşmır (`document.scrollingElement.scrollWidth === innerWidth`).

## 5. Testlər (pytest, minimum)
- irəliləyiş dövrün ortasında (bu gün < dövr ortası) hesablanır; məlumat az olanda `None`;
- avtomatik test yazısı `written`-ə düşmür, `missing`-dədir; müəllim saxlayanda «yazılıb» olur;
- dil fənnində IX balı dil balından; uyğun fənn yoxdursa balsız;
- bölgü varsa analitikanın səviyyəsi bölgüdəndir, mənbə «bölgü»;
- 2 qiymətli şagird müvəffəqiyyətə daxil deyil (hədd 3);
- sınaq ortası şagird sətrində, reytinq dəyişmir;
- məktəb hesabatı: admin görür, müəllim 403; rəqəmlər sinif rəhbəri cəmi ilə eynidir;
- PDF: altbilgidə səhifə nömrəsi, məktəb adı bazadan; Excel-də 4 vərəq.

## 6. Qəbul meyarları
- Eyni sinif/fənn/dövr üçün **müəllim analitikası, sinif rəhbəri cədvəli, məktəb hesabatı, Excel və PDF eyni rəqəmləri** verir.
- 3 oktyabrda (yarımilin əvvəli) bütün tablarda boş/yanıldıcı rəqəm yoxdur – ya rəqəm, ya «məlumat azdır» izahı.
- Hər çap sənədində: məktəb adı (bazadan), dövr, tərtib tarixi, səhifə nömrəsi, imza yerləri; önbaxış çapla eynidir.
- Telefon 360 px: heç bir analitika tabında üfüqi daşma yoxdur.
- Bütün testlər keçir; dəyişikliklər `docs/analitika-cap-auditi.md`-də «Düzəldildi» sütunu ilə qeyd olunur.

## 7. İstifadəçinin qərarı lazım olanlar (başlamazdan əvvəl soruş)
1. Fənn qiyməti üçün minimal formativ qiymət sayı – 3 (təklif) və ya başqa?
2. Rəsmi hesabatda imza verənlər: «Direktor müavini (tədris işləri üzrə)» adı kim yazılsın, Tənzimləmələrdə saxlansın?
3. Risk göstəricisi ümumiyyətlə çapa çıxsınmı (təklif: yalnız «daxili istifadə» seçimi ilə)?
4. Sınaq nəticələri riskə amil kimi daxil olsunmu (təklif: bəli, son 2 sınaq < 40%)?
5. Məktəb hesabatını admindən başqa kim görsün (direktor müavini rolu yoxdur – yeni rol və ya admin)?

## 8. İş ardıcıllığı
§1 (A1 → A2 → A3 → A4 → A5–A9) → §3.1–3.3 (şablon, çap mərkəzi, önbaxış) → §2.1–2.4 → §3.4–3.7 → §4 → §2.5–2.6.
Hər addım: test → `npm run build` → demo bazada telefon/kompüter skrinşotu → commit (AZ dilində, qısa).
