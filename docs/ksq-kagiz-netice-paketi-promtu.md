# Kağız KSQ/BSQ skanından sonra şagirdə nəticə paketi – cavab kartı + öz testi (altmövzu və № ilə) · audit + promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi, qiymətləndirmə mütəxəssisi və məxfilik auditorusan. Məqsəd: kağız KSQ/BSQ
(və yazılı TEST/SINAQ) cavab kartları skan ediləndən sonra hər şagirdə **bir paket** çatsın:
1) **cavab kartının skanı** (öz kartının şəkli + sistemin oxuduğu cavablar);
2) **öz testi** – şagirdin yazdığı variant kağızdakı kimi (sual mətni, şəkil, variantlar, «öz rəqəmləri» varsa onun rəqəmləri),
   hər sualın **altında**: «Altmövzu: … · №n» (n – sualın altmövzu faylındakı nömrəsi), öz cavabı, düz cavab, bal.
Paket portalda bir ekranda, bildiriş və çatda keçidlə, PDF kimi yüklənə bilən olsun.

## 0. Sabit qaydalar
- **Nəşr qaydası qalır**: düz cavab, ✓/✗, bal, altmövzu yalnız müəllim «📤 Nəticələri göndər» edəndən sonra (və ya aşağıdakı
  «skan olunan kimi göndər» rejimində həmin şagird üçün). Nəşrdən əvvəl şagird yalnız öz kartının şəklini və oxunuşu görür (indiki kimi).
- Başqa şagirdin kartı/testi heç vaxt (404). Texniki ünvan (`B<id>`, file_id, mənbə yolu) şagirdə getmir – yalnız «altmövzu · №n».
- Yazmayan şagirdə sual və düz cavablar göstərilmir (indiki qayda).
- Mətnlər AZ/EN/RU (`t()`, `ml()`, `label_ml()`); PDF – şagirdin dilində, rəsmi çap AZ.
- Aid pytest + `npm run build`; canlı DB-yə əl ilə yazı yoxdur.

## 1. Audit (kod, 19.10.2026)
| # | Var | Çatışmır |
|---|---|---|
| K1 | Portal: `GET /portal/exams` → `_card` – kartın şəkli (`/portal/exam-card/{scan_id}/image`) və oxunuş; nəşrdən sonra düz cavab, ✓/✗ | Şəkil və test **ayrı yerlərdədir** (Results.tsx-də `ExamCard` və ayrıca «Cavab kartı» modalı) – bir paket yoxdur |
| K2 | `GET /portal/exams/{id}/card` (`exam_cards.exam_card`): sual mətni, şəkil, variantlar, açar, bal, izah, **altmövzu adı** | Sualın altmövzudakı **№-si** şagirdə silinir (`q.pop('ref')` – B-id ilə birlikdə); kağızdakı sıra/görünüş (blok, sual nömrəsi) təkrarlanmır |
| K3 | Nəşr: `PUT /exams/{ta}/{exam}/publish` | Skan qiymətləndiriləndə şagirdə heç nə **göndərilmir** – bildiriş (`/portal/notifications`) yalnız onlayn sınaq nəticəsini sayır; çat mesajı yoxdur |
| K4 | Müəllim üçün «🖨 Cavab kartlarını çap et» | Şagird/valideyn üçün paketin PDF-i yoxdur |
| K5 | «Öz rəqəmləri» variantı (`reqem_variantlari`, `avto_reqem`) | Paketdə şagirdin **öz rəqəmləri ilə** sual mətni göstərildiyi yoxlanmayıb |

## 2. Həll
### 2.1 Paket – `app/exam_cards.py` → `student_package(db, e, sid, lang, published)`
`{exam: {title, date, subject, kind}, scan: {scan_id, image, read_by, at}, questions: [{n (kağızdakı №), slot, text, image, options,
my_answer, key, ok, points, earned, void, topic (şagirdin dilində), topic_no («№7»), explanation}], total: {points, max, pct, grade},
appeal_until, appeals}` – nəşrdən əvvəl `key/ok/earned/topic/topic_no/explanation` boş. Mənbə: mövcud `exam_card` + `_card` (bir funksiya,
təkrar yox); `topic_no` – `ref_of(...)`-dan yalnız № hissəsi (B-id yox).

### 2.2 Göndərmə
- **Defolt**: «📤 Nəticələri göndər» → paket bütün yazan şagirdlərə açılır + bildiriş «KSQ-1 nəticən hazırdır: cavab kartı və testin»
  (+ çat mesajı keçidlə, çat varsa; serverdə idempotent – təkrar nəşrdə ikinci mesaj yox).
- **Seçim** `Exam.send_on_scan` (miqrasiya – yeni sütun, defolt False; imtahan formasında «Skan olunan kimi şagirdə göndər»): kart
  `graded` olanda həmin şagird üçün paket açılır (şagird üzrə `published_for`), bildiriş gedir. **Qoruma**: imtahan başqa sinifdə/gündə
  hələ keçirilməyibsə (eyni `ExamSeries`/eyni variant digər sinifdə gələcək tarixli) – rejim bloklanır, xəbərdarlıq.
- Müəllim ekranında hər şagird sətrində status: «göndərilməyib / göndərildi 19.10 14:20 / baxıb».

### 2.3 Portal UI (`pages/student/Results.tsx`)
KSQ/BSQ sətrində «📄 Nəticə paketi» → bir səhifə: yuxarıda kartın şəkli (böyüdülə bilən) və bal; altında test kağızdakı sıra ilə:
№, sual (MathText, şəkil), variantlar – öz cavabı (qırmızı/yaşıl), düz cavab; sualın **altında** kiçik şriftlə «Altmövzu: … · №n»;
«⚖ Apelyasiya» (mövcud). «⬇ PDF» düyməsi.

### 2.4 PDF – `GET /portal/exams/{id}/package.pdf` (şagird) və `GET /exams/{ta}/{exam}/packages.pdf` (müəllim: bütün sinif, hər şagird
ayrıca səhifədən başlayır). Mövcud çap/PDF mexanizmi; A4; formul və şəkillər.

## 3. Testlər (`tests/test_exam_package.py`)
1. Nəşrdən əvvəl: şəkil + oxunuş var; açar, ✓/✗, altmövzu, № yoxdur.
2. Nəşrdən sonra: hər sualın altında altmövzu və №; `B<id>`/file_id cavabda yoxdur.
3. Başqa şagirdin paketi/şəkli/PDF-i – 404; yazmayan şagird – 404.
4. `send_on_scan`: kart graded → yalnız həmin şagird üçün açılır; digər sinifdə gələcək tarixli eyni imtahan varsa – 409.
5. Öz rəqəmləri variantı – paketdə şagirdin öz rəqəmləri.
6. Təkrar nəşr – ikinci bildiriş/çat mesajı yox.

## 4. Əlavələr (metodist təklifi)
1. **Səhv analizi**: paketdə «Ən çox səhv etdiyin altmövzular» (2–3) + hər birinə «Məşq testi» düyməsi (bankdan həmin altmövzu, plan_tests mühərriki ilə).
2. **Valideyn nüsxəsi**: PDF-in qısa forması (bal, qiymət, zəif altmövzular) – AZ/RU.
3. **Oxunuş şübhəsi**: şagird «kartımda başqa cavab yazmışam» düyməsi → müəllimə skan kəsiyi ilə sorğu (apelyasiyanın «oxunuş» növü).
4. **Sinif üzrə altmövzu xəritəsi** müəllimə: hansı altmövzuda sinfin 50%-dən çoxu səhv edib.

## 5. Qəbul meyarları
- Skan + nəşrdən sonra (və ya `send_on_scan` ilə) şagird bir ekranda kart şəklini və öz testini görür, hər sualın altında altmövzu və №.
- Məxfilik testləri keçir; nəşrdən əvvəl heç bir açar/altmövzu sızmır.
- PDF yüklənir; bildiriş gəlir; mətnlər AZ/EN/RU; aid testlər + `npm run build` keçir.

**İcra (kodcu):** 2.1 → 3 (1–3, 5) → 2.3 → 2.2 (miqrasiya + 4, 6) → 2.4. Əlavələr – istifadəçi seçəndə.
