# «Analitika və hesabat» – audit və vahid bölmə promtu (20.10.2026)

**Sifarişçi:** müəllim: «analitika/hesabat bölməsinə aid funksiyaları ora keçirin, tam dərin audit, peşəkar promt, icra».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Kart:** `docs/tasks/analitika-bolmesi.md`
**Ardıcıllıq:** «İşlənməyənlər hesabatı» (`docs/islenmeyenler-hesabati-promtu.md`) main-ə birləşəndən SONRA başlanır (eyni fayllar).
**Qaydalar:** CLAUDE.md – AZ/EN/RU, `npm run build`; funksiya silinmir – yalnız yeri dəyişir, köhnə keçidlər yeni yerə yönəlir.

## 1. Audit nəticəsi (kod üzrə, 20.10.2026)
| # | Tapıntı | Yer | Problem |
|---|---|---|---|
| A1 | Analitika iki bölməyə səpələnib | `/reports` (Reports.tsx: İcmal, Dərs sayı, Müvəffəqiyyət, Reytinq, Səviyyələr, Risk, Davamiyyət, Çap/PDF, Məktəb üzrə, Sertifikatlar) və `/tests → «📊 Nəticələr və reytinq»` (ResultsCenter.tsx: Reytinq, Yazmayanlar, Şagird, Sinif və qrup, Ümumi + ClassMatrix, StudentReport) | müəllim eyni növ məlumatı iki yerdə axtarır |
| A2 | **İki «Reytinq»** | Reports «Reytinq» (qiymət 40% · KSQ 30% · ev tap. 15% · davamiyyət 15%) və ResultsCenter «Reytinq» (test nəticələri) | eyni ad – fərqli məna; çaşqınlıq |
| A3 | **İki «yazmayanlar» hesablaması** | `/api/results-center/missing` (chronic) və `student_report.class_missing` (matris) | saylar fərqlənə bilər – tək mənbə pozulur (işlənməyənlər kartında həll olunur) |
| A4 | Çap formaları dağınıqdır | Reports «Çap/PDF», Journal «Çap/PDF», Classes «Çap/PDF», Plan «Çap/PDF», ClassMatrix (matris, yazmayanlar), StudentReport (hesabat, vərəqə), Exams (nəticə paketləri, hesabat) | «hansı sənəd harada?» – vahid siyahı yoxdur |
| A5 | Şagird hesabatına giriş yolu uzundur | `/tests?s=netice&v=student&student=ID` | analitik səhifə «Testlər» altında |
| A6 | Əsas səhifə keçidləri | Home.tsx: `/tests?s=netice&v=class`, `/reports` | yeni quruluşa yönəlməlidir |
| A7 | Testlər bölməsi qarışıqdır | TestsHub: yaratma/təyin/skan (əməliyyat) + nəticə analitikası | əməliyyat və analitika bir yerdə |

Yerində qalanlar (əməliyyat və ya rəsmi sənəd, keçid «Çap mərkəzi»ndən): Jurnal çapı, perspektiv plan çapı, sinif siyahısı çapı,
KSQ/BSQ cavab kartları və nəticə paketləri (sınaq iş axını), sinif rəhbəri davamiyyəti (rola aid). Şagird tərəfi (`/analytics`) dəyişmir.

## 2. Hədəf quruluş – «Analitika və hesabat» (`/reports`)
Yuxarıda: sinif seçimi (+ «Bütün siniflərim»), dövr (yarımil / ay / aralıq) – bütün tablar üçün ortaq.
| Qrup | Tablar (alt bölmələr) | Mənbə (köçürülür) |
|---|---|---|
| **İcmal** | Sinif icmalı (göstəricilər, paylanma, səviyyə/risk xülasəsi, «diqqət» siyahısı) | Reports İcmal |
| **Akademik nəticələr** | Müvəffəqiyyət · **Ümumi reytinq** (köhnə Reports «Reytinq») · Səviyyələr · Dərs sayı | Reports |
| **Testlər və sınaqlar** | **Test reytinqi** (köhnə ResultsCenter «Reytinq») · Kim nəyi işləyib (matris) · **Yazmayanlar** (yeni peşəkar hesabat) · Sinif və qrup · Ümumi | ResultsCenter, ClassMatrix |
| **Şagird** | Şagird hesabatı (axtarış + kart) · Risk | StudentReport, Reports Risk |
| **Davamiyyət** | Davamiyyət | Reports |
| **Çap mərkəzi** | Bütün sənədlərin vahid siyahısı: ad, təsvir, format (PDF/Excel), «Yarat» – bu bölmədəkilər birbaşa, digərləri öz səhifəsinə keçid | Reports Çap/PDF + A4 siyahısı |
| **Məktəb üzrə** (admin/müavin) | Məktəb hesabatı, Sertifikatlar | SchoolReport, CertificatesPanel |

- Tab adları dəqiq: «Ümumi reytinq (qiymət+KSQ+ev+davamiyyət)» və «Test reytinqi (onlayn+sınaq)» – alt yazı ilə formulu göstər.
- URL: `/reports?g=tests&t=missing&ta=…` (paylaşıla bilən, geri düyməsi işləyir); son açılan tab yadda (localStorage, try/catch).
- Telefonda: qruplar açılan siyahı (mövcud `Disclosure`/`Seg` üslubu), cədvəllər üfüqi sürüşür.
- **TestsHub** yalnız əməliyyat: Mövzu testləri · Sınaqlar · Yazılı iş. «📊 Nəticələr» bölməsi əvəzinə düymə «📊 Nəticələr → Analitika» (`/reports?g=tests`).
- **Köhnə keçidlər:** `/tests?s=netice&v=X[&student=ID]` → `/reports?g=tests&t=X` (student → `g=student&student=ID`) – `Navigate replace`;
  Home.tsx və digər daxili keçidlər birbaşa yenisinə.
- Menyu: «Analitika və hesabat» Qiymətləndirmə qrupunda qalır; ad dəyişmir.

## 3. Qəbul meyarları
1. A1–A7 həll olunub; heç bir funksiya itməyib (köhnə hər tab yeni yerdə açılır – yoxlama siyahısı hesabatda).
2. Bir səhifədə iki eyni adlı «Reytinq» yoxdur; yazmayanlar – tək mənbə.
3. Köhnə URL-lər yönəlir (test: router-də redirect), Home keçidləri yeni yerə.
4. AZ/EN/RU – bütün yeni ad və izahlar; `npm run build` ✅; aid pytest (backend dəyişirsə).
5. Kompüter (1366) və telefon (390) eni – Rəhbər ekran şəkli ilə yoxlayır.

## 4. İcra ardıcıllığı
1) İşlənməyənlər hesabatı merge → 2) kart → `kodcu` (worktree) → 3) review + build + Chrome yoxlaması → 4) merge → push → Render → audit sətri.
