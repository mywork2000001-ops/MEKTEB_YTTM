# Sertifikat və şagird motivasiyası – «Müəllim köməkçisi» (06.10.2026)

## 0. Kontekst və sabit qaydalar
- Mənbə: hub-dakı `Documents/Claude/Projects/_Shared_Core/certificate.js` (EduCert v1.0): A4 albom, IEN brendi, platforma nişanı,
  ad, nailiyyət, faiz dairəsi, «Uğurla keçdiniz / İştirak etdiniz» (≥ 60 %), tarix, ID. Çatışmazlıqlar: ID təsadüfidir
  (yoxlanılmır), `window.open` popup-a ilişir, məktəb/müəllim yoxdur, hər kəs istənilən ad yaza bilər.
- Tətbiqdə sertifikat **yalnız serverdəki faktiki nəticədən** yaranır (şagird ad/bal dəyişə bilməz), hər sertifikatın
  yoxlanıla bilən nömrəsi var. Dizayn EduCert-dən götürülür (rənglər, quruluş), kod React + mövcud `print.ts` ilə yazılır,
  hub faylı dəyişmir.
- Məxfilik: şagird yalnız öz sertifikatlarını və öz yerini görür; reytinqdə başqalarının adı göstərilmir (mövcud qayda).
  Valideyn – övladınınkıları. Testlər yazılmır (istifadəçinin qərarı); `pytest`, `tsc -b` təmiz.

## 1. Sertifikat növləri (avtomatik verilir)
| Növ | Şərt (müəllim tənzimləyə bilər) | Mətn |
|---|---|---|
| Mövzu ustası | mövzu testi ≥ 90 % (ilk cəhd) | «… mövzusunu əla mənimsəmişdir» |
| Sınaq nəticəsi | sınaqda ≥ 80 % və ya sinifdə 1–3-cü yer | «Sınaq imtahanı – N bal, sinifdə X-ci yer» |
| Fəsil / bölmə | fəslin bütün testləri ≥ 75 % (P007 fəsil faizi, §4.5) | «Natural ədədlər fəslini tamamlamışdır» |
| Seriya | sınaq seriyasının (exam_series) ≥ 80 %-nə qatılıb | «Həftəlik sınaq seriyası iştirakçısı» |
| Yarımil / il | formativ ortası ≥ 4,5 və ya irəliləyiş ≥ +15 % | «Yarımilin ən çox irəliləyən şagirdi» |
| Müəllim verir | əl ilə, sərbəst mətnlə | məs. «Olimpiadada iştiraka görə» |

## 2. Məlumat modeli
- `certificates`: id, `code` (12 simvol, unikal, məs. `MK-26-7F3K9Q2A`), student_id, assignment_id, kind, title, details (JSON:
  bal, faiz, yer, mövzu/fəsil, test/sınaq id), issued_at, issued_by (None – avtomatik), revoked_at.
- `cert_rules` (sinif/qrup üzrə, default yuxarıdakı cədvəl): kind, threshold, enabled.
- Unikal: (student_id, kind, mənbə id) – təkrar verilmir.

## 3. Backend
1. `app/certificates.py::issue_due(db)` – scheduler (15 dəq.) + test/sınaq təhvil veriləndə: şərtə uyğun nəticələrdən sertifikat.
2. API: şagird `GET /api/portal/certificates`, `GET /api/portal/certificates/{code}`; müəllim `GET /api/certificates?ta=`,
   `POST /api/certificates` (əl ilə), `POST /{id}/revoke`, `PUT /api/certificates/rules/{ta}`.
3. **Açıq yoxlama:** `GET /api/verify/{code}` (girişsiz) → ad (qısaldılmış: «Əli H.»), sertifikat, tarix, məktəb, etibarlıdır / ləğv edilib.
   Səhifə `/verify/:code`. Sertifikatda QR kod (kitabxanasız SVG generator və ya mövcud asılılıq) → bu səhifə.

## 4. Frontend
- **Sertifikat görünüşü** (`Certificate.tsx`): EduCert-in quruluşu – yuxarı rəng zolağı, künc bəzəkləri, «SERTİFİKAT», ad,
  nailiyyət, faiz dairəsi, bal/yer, məktəb (`header_school`), müəllim imzası xətti, tarix, kod + QR. A4 albom çap və
  «PDF kimi saxla» (`printDoc`), popup yoxdur. Rəng növə görə (mövzu – yaşıl, sınaq – bənövşəyi, fəsil – mavi, müəllim – qızılı).
- Şagird: yeni bölmə **«Uğurlarım»** – sertifikatlar qalereyası (kartlar), aç → tam görünüş, çap, paylaş (WhatsApp linki yoxlama səhifəsinə).
- Müəllim: Analitika → «Sertifikatlar» – verilənlər, əl ilə vermək, ləğv, qaydalar (hədlər).

## 5. Şagird üçün cəlbedicilik (motivasiya)
1. **Təbrik anı:** test/sınaq təhvil veriləndə nəticə ekranında animasiya (CSS konfetti, `prefers-reduced-motion`-a hörmət),
   «Yeni sertifikat!» kartı.
2. **Nişanlar** (sertifikatdan kiçik, çoxlu): «5 test ardıcıl ≥ 80 %», «Həftəlik sınaqların hamısı», «Həll şəkillərini göndərdi»,
   «Erkən təhvil», «İrəliləyiş +20 %». Profil başlığında son 3 nişan.
3. **Seriya (streak):** ardıcıl neçə test/sınaq vaxtında yazılıb – «🔥 6»; buraxanda sıfırlanır, amma «ən yaxşı seriya» qalır.
4. **Səviyyə/XP:** hər test – XP (düz cavab × 10, ilk cəhd bonusu); səviyyələr (Başlanğıc → Bilici → Usta → Ekspert); XP yalnız
   şagirdin özünə görünür (rəqabət stresi olmasın), sinif reytinqi mövcud qaydada qalır.
5. **Proqres xəritəsi:** perspektiv plan fəsilləri/bölmələri kart kimi – faiz rəngi (qırmızı → yaşıl), «növbəti hədəf: Kəsrlər 62 % → 75 %».
6. **Həftəlik hədəf:** «Bu həftə: 2 test, 1 sınaq» – tamamlananda nişan.
7. Bildirişlər (mövcud `/api/portal/notifications`): «Sertifikat qazandınız», «Seriyanız 5-ə çatdı».
8. Mobil birinci: 360 px, iri toxunma sahələri, qaranlıq rejim, şəkillər lazy.

## 6. Mərhələlər
1. Model + avtomatik vermə + şagird «Uğurlarım» + çap (sertifikat dizaynı).
2. Yoxlama səhifəsi + QR + müəllim paneli (əl ilə, ləğv, qaydalar).
3. Motivasiya: təbrik, nişanlar, seriya, XP/səviyyə, proqres xəritəsi, həftəlik hədəf.

## 7. Qəbul
Şagird mövzu testində 92 % alır → «Uğurlarım»da sertifikat görünür, çap olunur (A4 albom, məktəb və müəllim adı ilə), QR
yoxlama səhifəsini açır və «etibarlıdır» göstərir; müəllim sertifikatı ləğv edəndə yoxlama «ləğv edilib» deyir; nəticə
ekranında təbrik və nişan; heç bir şagird başqasının adını/balını görmür.

## 8. Götürülən qərarlar (icra, 06.10.2026)
- Avtomatik növlər: movzu (≥ 90 %, təhvil anında), sinaq (bağlanandan sonra ≥ 80 % və ya ilk 3 yer), seriya (≥ 4 sınaq
  göndərilib, ≥ 80 % iştirak), manual. «Fəsil» və «yarımil» sertifikatları sonraya (şagird üzrə etibarlı məlumat yoxdur).
- Hədlər sinif/qrup üzrə (`teaching_assignments.cert_rules`), default `DEFAULT_RULES`; miqrasiya e4a6c8d0f2b3.
- Sertifikat şagirdin hesabına bağlıdır: ad tətbiqdəki addan avtomatik, şagird ID-si sertifikatda çap olunmur (istifadəçi:
  «не на сертификат – свяжи»); yeni sertifikat tətbiq açılanda özü göstərilir (CertNudge + konfetti), sonra «görüldü».
- Kod `MK-YY-XXXXXXXX` (0/O, 1/I yoxdur), QR → `/v/:code` (girişsiz), yoxlamada ad qısaldılır.
- Nişan/XP/səviyyə/seriya/həftəlik hədəf/bölmə proqresi saxlanılmır – `GET /api/portal/achievements` nəticələrdən hesablayır.
- Şagird: «Uğurlarım» (/achievements); müəllim: Hesabatlar → Performans → «Sertifikatlar» (siyahı, əl ilə, ləğv, hədlər).
