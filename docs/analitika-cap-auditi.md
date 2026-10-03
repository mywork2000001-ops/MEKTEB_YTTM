# Analitika, hesabat və çap – audit (03.10.2026)

**Üsul.** Kod oxunuşu (backend: `analytics.py`, `performance.py`, `api/analytics.py`, `api/homeroom.py`, `task_journal.py`,
`levels.py`, `api/printing.py`; frontend: `Reports.tsx`, `print.ts`, `student/Analytics.tsx`, `student/Results.tsx` və
`printDoc` çağırılan 25 yer), demo bazada (6 sinif/qrup, real perspektiv planlar, uydurma şagirdlər) API sorğuları,
canlı saytda (1f31e93) jurnal və çat sorğularının yoxlanması. 162 avtomatik test keçir.

Ciddilik: **K** – kritik (səhv rəqəm/rəsmi sənəd), **Y** – yüksək, **O** – orta, **A** – aşağı / kosmetik.

## 1. Analitika: hesablama səhvləri

| № | Ciddilik | Tapıntı | Sübut | Nəticə |
|---|---|---|---|---|
| A1 | **K** | «İrəliləyiş» heç vaxt hesablanmır | `analyze()` dövrü **təqvim ortasından** bölür (`mid = p.a + (p.b-p.a)/2`). I yarımil 15.09–26.01 → orta 21.11; bu gün 03.10 → ikinci yarı boşdur. Demo: 6 sinifdə `progress != None` – **0 şagird** | «Reytinq → İrəliləyiş» sütunu və irəliləyiş reytinqi boşdur; il boyu yalnız dövrün sonunda işləyir |
| A2 | **Y** | Onlayn testin avtomatik yaratdığı jurnal yazısı «yazılmış dərs» sayılır | `write_topic_marks()` yazı yoxdursa `JournalEntry` yaradır (davamiyyətsiz). Demo: X c – müəllim heç nə yazmayıb, «yazılmış dərs: 1» | «Dərs sayı», «yazılmamış dərslər», sinif rəhbərinin «yazılıb» rəqəmləri şişir; davamiyyət xəritəsində boş sütun |
| A3 | **Y** | IX sinif balı fənndən asılı olmayaraq **riyaziyyat** götürülür | `analyze()`: `level(s.score_math)`, `RiskInput(ix_math=s.score_math)`; Excel başlığı «IX riy.» | Azərbaycan dili / xarici dil müəllimində ilkin səviyyə və risk səhvdir (`levels.py` isə fənnə uyğun seçir – iki sistem fərqli) |
| A4 | **Y** | Səviyyənin iki fərqli tərifi | Analitika: reytinq ≥70/40 (IX bal ehtiyat); «Səviyyə qrupları»: buraxılış 30 + sınaq 40 + reytinq 30 + diaqnostik 30, histerezis 5. Bölgü `LevelOverride(source='auto')` kimi analitikanı üstələyir | Müəllim «Güclü/orta/zəif» tabında bir şey, «Səviyyə qrupları»nda başqa şey görür; izah mətni (Reports.tsx:94) bölgünü qeyd etmir |
| A5 | **O** | Bir neçə qiymətlə «fənn qiyməti» | `subject_grades()`: yarımil qiyməti yoxdursa formativ orta → yuvarlaqlaşdırılmış qiymət, **minimal say yoxdur**. Demo: tək onlayn testdən 15 şagird «qiymətləndirilib», müvəffəqiyyət 73,3% | Müvəffəqiyyət/keyfiyyət/SOU ilin əvvəlində yanıldıcıdır; mənbə «formativ» göstərilir, amma xəbərdarlıq yoxdur |
| A6 | **O** | Defolt yarımil həmişə «I» | `Reports.tsx:15` `useState('1')` | Fevraldan sonra hər açılışda köhnə yarımil görünür |
| A7 | **O** | Onlayn cəhdlər dövrə UTC tarixi ilə düşür | `_collect`: `a.submitted_at.date()` (UTC) | 00:00–04:00 Bakı vaxtı təhvil verilən test əvvəlki günə/dövrə düşə bilər |
| A8 | **A** | «Orta qiymət» üç yerdə üç cür | İcmal: bütün formativ qiymətlərin ortası; Müvəffəqiyyət: şagird qiymətlərinin ortası; şagird portalı: öz ortası | Eyni ekranda 3,53 və başqa rəqəm görünə bilər – izah lazımdır |
| A9 | **A** | Şagird analitikasında orta qiymət zolağı 0-dan başlayır | `Compare max=5`: «2» zolağın 40%-ni tutur | Vizual olaraq zəif qiymət yaxşı görünür (2–5 şkalası olmalıdır) |

## 2. Analitika ilə modulların əlaqəsi

| Mənbə | Analitikaya düşür? | Qeyd |
|---|---|---|
| Jurnal: formativ qiymət, davamiyyət, ev tapşırığı | ✔ | reytinq: qiymət 40 · KSQ 30 · ev tap. 15 · davamiyyət 15 |
| KSQ / BSQ | ✔ | KSQ reytinqdə; BSQ yalnız «Müvəffəqiyyət»də (yarımil qiyməti) |
| Mövzu testi (onlayn) | ✔ ikiqat yox | jurnala «test» qiyməti kimi düşür, `online_pct` ayrıca göstərilir (reytinqə daxil deyil) – düzgün, amma ekranda izah yoxdur |
| **Sınaq imtahanları** | ✘ | yalnız «Sınaq imtahanları → Reytinq»də; fənn analitikasında, riskdə, çapda yoxdur (bölgüdə 40% çəki ilə var) |
| **Əlavə məşğələ** | ✘ | öz statistikası; zəif şagirdin məşğələyə gəlib-gəlmədiyi riskdə/şagird kartında görünmür |
| **Sinif rəhbərinin davamiyyəti** | ✘ (fənn analitikasında) | sinif rəhbəri ekranı birləşmiş davamiyyəti göstərir, fənn müəllimi yalnız öz jurnalını – iki fərqli «davamiyyət %» |
| Səviyyə qrupları | qismən | bölgü analitikadakı səviyyəni üstələyir (A4) |
| Valideynlə əlaqə, fərdi plan | ✔ (şagird kartı) | risk siyahısından birbaşa «plan aç / əlaqə yaz» keçidi yoxdur |
| Məktəb üzrə (admin) | ✘ | `/api/overview` yalnız müəllimin öz sinifləri; direktor müavini üçün məktəb/paralel üzrə müvəffəqiyyət hesabatı yoxdur |

## 3. Çap / PDF

25 çap nöqtəsi vahid `print.ts` modulundan istifadə edir (A4, ağ-qara, Times New Roman, server PDF – Chromium, JS söndürülüb,
xarici sorğu bloklanır) – əsas yaxşıdır. Tapıntılar:

| № | Ciddilik | Tapıntı | Sübut |
|---|---|---|---|
| P1 | **K** | «Müvəffəqiyyət» (rəsmi hesabat forması) **fənn müəllimi üçün çap olunmur** | Reports «Çap / PDF» yalnız reytinq cədvəlini çap edir; müvəffəqiyyət çapı yalnız sinif rəhbərində (fənlər üzrə) var |
| P2 | **Y** | Önbaxış çapdan fərqlidir | Reports.tsx:140–151 ekranda 8 sütun, `printDoc` isə 9 (Risk əlavə); önbaxışda məktəb adı ayrıca sabit yazılıb |
| P3 | **Y** | Məktəb adı sabit koddadır | `print.ts:9 SCHOOL`, Reports.tsx:141; halbuki `School.name` bazada var, gündəlik plan isə öz `header_school` ayarını saxlayır – üç mənbə |
| P4 | **Y** | Rəsmi sinif hesabatında «Risk» (Qırmızı/Sarı) çap olunur | Reports.tsx:136 | Şagirdi damğalayan daxili göstərici kağıza çıxır; ən azı seçimə bağlı olmalıdır |
| P5 | **O** | Şagirdin «Hesabatım» çapında **şagirdin adı yoxdur** | student/Analytics.tsx:25 | Kağız kimin olduğu bilinmir |
| P6 | **O** | Sənəddə tarix, səhifə nömrəsi, imza blokları yoxdur | `docHtml` – altbilgi yoxdur; yalnız «Müəllim: ____» | Direktor müavini / sinif rəhbəri imzası, «tərtib tarixi», «Səhifə 1/2» standart deyil |
| P7 | **O** | Excel-də məktəb adı, imza, dövrün yarımil adı yoxdur; müvəffəqiyyət və davamiyyət üçün Excel yoxdur | `export_xlsx` |
| P8 | **O** | Server PDF-də şrift | Render (Linux) Times New Roman yoxdur → «Liberation Serif»; «ə, ğ, ı, ş» glifləri canlı PDF-də yoxlanmayıb |
| P9 | **A** | Telefonda çap pəncərəsi `window.open` – popup bloklananda `alert()` | print.ts:72 – in-app bildiriş olmalıdır |
| P10 | **A** | Davamiyyət xəritəsi, Risk, Güclü/orta/zəif, Dərs sayı tablarının öz çapı yoxdur | Reports.tsx |

## 4. Telefon görünüşü (analitika)
- Reytinq və müvəffəqiyyət cədvəlləri telefonda üfüqi sürüşür (7–6 sütun) – kart görünüşü yoxdur.
- Davamiyyət xəritəsində şagird adı sabit deyil (`sticky-first` istifadə olunmur), sütunlar çox olanda ad itir.
- Tablar (8 ədəd) sürüşür, sonuncular görünmür – qruplaşdırma lazımdır.

## 5. Yaxşı olanlar
- Qiymət/faiz qaydaları bir yerdədir (`domain/rules.py`), yarımil qiyməti `Decimal` + adi yuvarlaqlaşdırma.
- Reytinqdə olmayan komponentin çəkisi qalanlara bölünür; yalnız davamiyyətlə reytinq verilmir.
- Mövzu testi jurnala yazılarkən müəllimin əl ilə yazdığı «test» qiyməti üstələnmir, boş avtomatik təhvilə «2» qoyulmur.
- PDF serverdə təhlükəsiz qurulub (JS yox, şəbəkə yox, kilid, ölçü limiti, audit).
- Excel A4 portret, sığdırma, başlıq sətri təkrarlanır.

## 6. İcra vəziyyəti (03.10.2026, `docs/analitika-cap-promtu.md` üzrə)

| Tapıntı | Vəziyyət | Necə |
|---|---|---|
| A1 İrəliləyiş | ✔ düzəldildi | dövr faktiki nəticə günlərinin ortasından bölünür; < 4 nəticə günü – «məlumat azdır» izahı |
| A2 Avtomatik jurnal yazısı | ✔ | `journal_entries.auto` (miqrasiya b8d3f1a6c2e4, mövcud yazılar işarələnir); dərs sayı, davamiyyət xəritəsi, sinif rəhbəri, jurnal səhifəsi – yazılmamış; jurnalda «dərs hələ yazılmayıb», davamiyyət defolt «var» |
| A3 IX balı | ✔ | `services.ix_score` – fənnə uyğun, yalnız X–XI; risk etiketi fənnə görə; Excel «IX bal» |
| A4 Səviyyə | ✔ | mənbə nişanı (bölgü / müəllim / nəticələr / IX), izah – bölgü əsasdır |
| A5 Az qiymət | ✔ | `MIN_MARKS = 3`; «az qiymət» ayrıca sayılır (müvəffəqiyyət, sinif rəhbəri, məktəb hesabatı eyni funksiya) |
| A6 Defolt yarımil | ✔ | `/api/my/lessons` → `semester` |
| A7 Vaxt zonası | ✔ | onlayn cəhd tarixi Bakı vaxtı ilə |
| A8 Terminlər | ✔ | hər kartda nəyin ortası olduğu yazılır |
| A9 Şagird zolağı | ✔ | 2–5 şkalası |
| Sınaq → analitika | ✔ | sınaq ortası/son/dinamika sütunu, icmal; risk amili «son 2 sınaq < 40%» (+20) |
| Əlavə məşğələ | ✔ | şagird sətrində kurs və davamiyyət; riskdə göstərilir |
| Bütün dərslər üzrə davamiyyət | ✔ | sinif rəhbərinin birləşmiş qeydindən ayrıca sütun |
| Risk → hərəkət | ✔ | valideynlə əlaqə, fərdi plan, test təyin et |
| Məktəb hesabatı | ✔ | `GET /api/school/performance` (yalnız admin), Analitika → «Məktəb üzrə», albom çap, direktor müavini + direktor imzası |
| Həftəlik xülasə | ✔ | `GET /api/my/weekly`, Əsas səhifədə «Bu həftə diqqət» (həftə ərzində «Oxudum») |
| P1 Müvəffəqiyyət çapı | ✔ | çap mərkəzi (seçilən bölmələr bir sənəddə) |
| P2 Önbaxış = çap | ✔ | iframe `srcdoc = docHtml()` |
| P3 Məktəb adı | ✔ | `School.name` → `/api/auth/me`; gündəlik planın defoltu da oradan |
| P4 Risk çapda | ✔ | defolt söndürülüb; seçiləndə «Daxili istifadə üçün» |
| P5 Şagird hesabatı | ✔ | ad, sinif, kod, KSQ/BSQ, onlayn testlər, sınaqlar |
| P6 Tarix, səhifə, imza | ✔ | `@page` altbilgisi «Tərtib edildi … · Səhifə X / Y»; `signers`; Tənzimləmələr → Məktəb: direktor müavini, direktor |
| P7 Excel | ✔ | 4 vərəq, məktəb adı, imzalar, «Səhifə &P / &N» |
| P8 Server şrifti | ✔ (kod) | Dockerfile: fonts-liberation, fonts-dejavu-core; **canlıda PDF yoxlanmalıdır** |
| P9 Popup | ✔ | bloklananda PDF birbaşa yüklənir |
| P10, §4 Telefon | ✔ | reytinq/müvəffəqiyyət/məktəb – kartlar; davamiyyətdə ad sabit; tablar iki sırada; 360 px-də daşma yoxdur |

**Götürülmüş qərarlar (istifadəçi «bütün icazələri verirəm» dedi – təklif olunan variantlar):** minimal 3 qiymət;
imza – fənn müəllimi + direktor müavini (adı Tənzimləmələrdə, boşdursa xətt); risk çapa yalnız seçimlə; sınaq riskdə;
məktəb hesabatı – yalnız admin.
