# Hesabat çapı – qruplar və genişləndirmə promtu (03.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və rəsmi sənəd redaktorusan. Məqsəd: hesabat hissəsində **hər sinif və
hər qrup** (bölünmə qrupu, tədris qrupu, səviyyə qrupu) kağıza düzgün, tam və eyni üslubda çıxsın; müəllim, sinif rəhbəri və
admin lazım olan sənədi bir kliklə, lazım olarsa hamısını birdən çap etsin.

**Sabit qaydalar:** `docs/analitika-cap-promtu.md` §0 (A4, ağ-qara, Times, AZ dili, ondalıq vergül, məktəb adı bazadan,
altbilgidə tarix və «Səhifə X / Y», imza bloku `signers`). Hesablamalar serverdə; çap yalnız göstərir.

## 1. Audit – tapıntılar

| № | Ciddilik | Tapıntı | Sübut |
|---|---|---|---|
| Q1 | **K** | Məktəb hesabatında qruplar yoxdur | `school_performance` yalnız `kind != 'qrup'` siniflər; bölünmə və tədris qruplarının fənn göstəriciləri heç yerdə çap olunmur |
| Q2 | **K** | Sinif rəhbəri hesabatlarına **tədris qrupları** düşmür | `homeroom._assignments` yalnız `parent_id == sinif` qruplarını götürür; paralel siniflərdən yığılan qrupda oxuyan şagirdin həmin fənn qiyməti cədvəldə yoxdur |
| Q3 | **Y** | Səviyyə qrupları (Zəif / Orta / Güclü bölgüsü) hesabat çapında yoxdur | Çap mərkəzindəki «Güclü / orta / zəif» analitika səviyyəsidir, bölgünün balı, komponentləri, «təyin edilməyib» yoxdur |
| Q4 | **Y** | Bölünən sinifdə eyni fənn iki sütun olur | Sinif rəhbərinin «Qiymət cədvəli»ndə «Riyaziyyat (X b qrup 1)» və «(qrup 2)» – hər sütunun yarısı boş |
| Q5 | **Y** | Bütün sinif və qruplarımı birdən çap etmək olmur | Çap mərkəzi yalnız seçilmiş bir sinif/qrup üçündür |
| Q6 | **O** | Köhnə çaplar yeni şablonda deyil | `<p class="sign">Müəllim: ____</p>` – Səviyyə qrupları, jurnal yarımil, KSQ/BSQ, sinif rəhbəri, sınaq, əlavə məşğələ; imza bloku/vəzifələr fərqli |
| Q7 | **O** | Səviyyə qrupları çapında başlıq/alt sətir zəifdir | `<h3>` (şablonda üslubu yoxdur), sinif · fənn · tarix yoxdur, komponentlər və «təyin edilməyib» yoxdur |
| Q8 | **O** | Valideyn üçün fərdi hesabat kartı yoxdur | Sinif rəhbəri yalnız cədvəllər çap edir |
| Q9 | **O** | Davamiyyət xəritəsi (tarix × şagird) analitikadan çap olunmur | Yalnız yekun cədvəl |
| Q10 | **A** | Analitika çapında hansı qrup olduğu yazılmır | başlıqda «X b (riyaziyyat qrupu) sinfi» – qrupun növü (bölünmə / tədris) və ana sinif yoxdur |

## 2. Tapşırıqlar

### 2.1 Qruplar (Q1–Q4, Q10)
1. **Məktəb hesabatı:** yeni blok `groups` – məktəbin bütün qrupları (bölünmə + tədris): ad, növ, ana sinif / üzvlərin sinifləri,
   fənn, müəllim, şagird, «5/4/3/2», müvəffəqiyyət, keyfiyyət, SOU, yazılmamış dərs. Ekranda və çapda ayrıca bölmə.
2. **Sinif rəhbəri:** `_assignments` – sinfin şagirdlərinin üzv olduğu **tədris qrupları** da (yalnız həmin şagirdlər hesablanır).
3. **Bölünən fənn bir sütun:** sinif rəhbərinin qiymət cədvəlində eyni fənnin qrupları bir sütunda (şagird hansı qrupdadırsa, o qiymət);
   müvəffəqiyyət və dərs sayı cədvəllərində qruplar ayrıca sətir qalır (müəllim fərqlidir).
4. **Səviyyə qrupları:** analitika çap mərkəzinə «Səviyyə qrupları (bölgü)» bölməsi – `/api/levels/{ta}`: hər qrup, bal, komponentlər,
   mənbə (bölgü / müəllim 🔒), «təyin edilməyib».
5. **Başlıq:** qrupun növü və ana sinfi (məs. «X b (riyaziyyat qrupu) – bölünmə qrupu, X b sinfi»).

### 2.2 Toplu çap (Q5)
Analitika → Çap / PDF → «Bütün sinif və qruplarım»: seçilən bölmələr hər sinif/qrup üçün ayrıca səhifədən başlayır, bir sənəd
(və ya bir PDF). Yüklənmə göstəricisi; hər birində öz imza bloku.

### 2.3 Vahid şablon (Q6, Q7)
Bütün hesabat çaplarında `signers` (fənn müəllimi / sinif rəhbəri / direktor müavini), `<p class="sign">` qalmasın; `h3` → `h2`.

### 2.4 Yeni sənədlər (Q8, Q9)
1. **Valideyn üçün hesabat kartı** (sinif rəhbəri): hər şagird ayrıca səhifə – fənlər üzrə qiymət, orta, kateqoriya, davamiyyət
   (dərs / buraxıb / üzrsüz / gecikmə), sinif rəhbərinin və valideynin imzası. Bütün sinif bir sənəddə.
2. **Davamiyyət xəritəsi** (analitika çap mərkəzi): albom A4, sətir – şagird, sütun – dərs tarixi, xanada q / ü / g; seçiləndə sənəd albom olur.

## 3. Testlər
- məktəb hesabatında bölünmə və tədris qrupları, admin-only;
- sinif rəhbəri cəmində tədris qrupunun fənni (yalnız sinfin şagirdləri);
- build, telefon 360 px və kompüterdə çap mərkəzi, PDF (altbilgi, imza).

## 4. Qəbul meyarları
Hər qrup ən azı bir rəsmi sənəddə görünür (məktəb, sinif rəhbəri, analitika); bölünən fənn sinif cədvəlində bir sütundur;
bütün hesabat çapları eyni şablondadır; toplu çap işləyir; bütün testlər keçir.
