# Sinif, qrup, bölünmə qrupu + mövzu icrası (irəliləyiş / geriləmə) – audit və peşəkar promt

**Rol:** məktəb İKT mütəxəssisi + riyaziyyat metodisti + tədris hissə müdiri baxışı.
**Məqsəd:** müəllim (1) sinif, sərbəst tədris qrupu və sinif daxilində bölünmə qrupunu özü yarada və redaktə edə bilsin;
(2) keçdiyi mövzuları qeyd edib perspektiv plana nisbətən **faktiki** irəliləyişi və ya geriləməni rəqəm, faiz və qrafiklə izləsin.

---

## 1. Audit – mövcud vəziyyət (01.10.2026, `def2f7a`)

### 1.1 Sinif / qrup
| Var | Çatışmır / problem |
|---|---|
| Sinif yaratmaq (TOM, adi), dublikat adına 409 – «qoşul» | Sinfin **növünü** (TOM ↔ adi) sonradan dəyişmək olmur (`ClassPatch`-da `kind` yoxdur) |
| Bölünmə qrupu (`kind='qrup'` + `parent_id`), şagirdlər ana sinifdən seçilir, paralel fənn (`split_with`) | **Sərbəst tədris qrupu yoxdur**: `qrup` üçün ana sinif məcburidir (400). Müxtəlif siniflərdən yığılan qrup (olimpiada, hazırlıq, dərnək, IX-lardan riyaziyyat qrupu) yaratmaq mümkün deyil – `GroupMember` docstring-i bunu vəd edir, kod etmir |
| Ad, UTİS sinfi, imtahan tarixi redaktəsi | Sinfin **öz zəngi** (`bells`, məs. XI peşə 08:00) API-də var, interfeysdə redaktə yoxdur |
| Arxiv → bərpa → həmişəlik silmə | «Siniflər» səhifəsində qrup növü fərqlənmir («qrup» yazılır), redaktəyə keçid yoxdur |
| Qrup jurnalı `roster()` ilə üzvlər üzrə işləyir | Qrupun şagird kartı (`/students/{id}/contacts`, `plans`) ana sinif yoxlaması ilə 403 verər – sərbəst qrupda üzv başqa sinifdəndir |
| | Sinif çatı: sərbəst qrup üçün otaq yaranar, amma şagirdlər ora girə bilməz (yoxlama `class_id` ilədir) |

### 1.2 Mövzu icrası və geriləmə
| Var | Çatışmır / problem |
|---|---|
| Rəsmi plan dəyişmir; «Mövzunu saxla» işçi planı sürüşdürür | **Geriləmə yalnız «saxla» düyməsi ilə ölçülür** (`shift`). Müəllim dərsi keçməyibsə, jurnal yazmayıbsa, və ya iki mövzunu bir dərsdə keçibsə – rəqəm reallığı göstərmir |
| Jurnal → Mövzular: `keçilib / gecikir / gözlənilir` (yalnız jurnal əsasında) | Mövzunu **birbaşa «keçildi» kimi qeyd etmək** olmur (jurnal yazmadan, keçmiş tarixlə, toplu) |
| `performance.lesson_counts.covered` | `covered` = «tarixi keçmiş işçi plan yuvaları» – faktiki deyil, fərziyyədir |
| | «Qismən keçildi», «keçildi, amma təkrar lazımdır» kimi metodik qeyd yoxdur |
| | Rəsmi plana nisbətən **irəlidə / geridə N dərs (≈ həftə)**, bölmələr üzrə icra, zaman üzrə qrafik, ilin sonuna **proqnoz** yoxdur |
| | Gündəlik plan (AI) təkrar tələb edən mövzuları bilmir |

---

## 2. Qaydalar (pozulmaz)
1. **Rəsmi plan dəyişmir.** Qeyd ayrıca cədvəldə saxlanılır (`topic_progress`); planın yenidən yüklənməsi qeydləri silmir (sıra № üzrə yenilənir, `plan_lesson_id` qorunur).
2. **Mənbə ierarxiyası:** müəllimin əl ilə qeydi > jurnal (`JournalEntry.plan_lesson_id`). Qeyd silinərsə, jurnal yenə «keçildi» deyir.
3. **Geriləmə rəsmi tarixə görə** ölçülür: `fərq = keçilən − (rəsmi tarixi bu günə qədər olan mövzular)`; mənfi – geriləmə, müsbət – irəliləmə. Həftəyə çevrilmə: `fərq ÷ həftəlik saat`.
4. Statuslar: **keçildi** (sayılır), **təkrar** – keçildi, mənimsəmə zəifdir (sayılır + AI planına təkrar kimi gedir), **qismən** (sayılmır, ayrıca göstərilir).
5. Sinif/şagird **məktəbə** aiddir: sərbəst qrup yeni şagird yaratmır, yalnız mövcud şagirdləri üzv edir. Şagirdin şəxsi məlumatını yenə yalnız öz sinfinin müəllimləri redaktə edir; qrup müəllimi kartı (əlaqə, fərdi plan) görür.
6. Bölünmə qrupunun üzvləri yalnız ana sinifdən; sərbəst qrupun üzvləri məktəbin istənilən aktiv sinfindən.
7. Növ dəyişmə: yalnız TOM ↔ adi. Sinif ↔ qrup çevrilməsi qadağandır (jurnal/üzvlük pozular).
8. Hər dəyişiklik audit jurnalına düşür; məxfilik qaydaları (Uşaq İD, PIN və s.) toxunulmur.

---

## 3. Peşəkar promt (icraçı üçün)

> Sən FastAPI + SQLAlchemy + React (TS) tətbiqində işləyən baş proqramçısan. Mövcud kod üslubunu (Azərbaycan dilində
> şərhlər, `audit()`, `settings_unlocked`, `own_assignment`, `plan_ctx`, `useLoad`, `Drawer`, `Pill`) saxla.
>
> **A. Siniflər və qruplar**
> 1. `kind='qrup'` + `parent_id=None` = **sərbəst tədris qrupu**; `parent_id` dolu = **bölünmə qrupu**. Yaradılışda ana sinif məcburiliyini götür.
> 2. `PUT /classes/{id}/members`: bölünmə – yalnız ana sinifdən; sərbəst – məktəbin aktiv şagirdləri (başqa məktəb → 400).
> 3. `GET /classes/{id}/candidates?class_id=` – sərbəst qrupa üzv seçmək üçün istənilən sinfin siyahısı (yalnız ad, sinif; qrupu redaktə edə bilən müəllim).
> 4. `PATCH /classes/{id}`: `kind` (TOM ↔ adi), `bells` (sinfin öz zəngi); qrupa növ dəyişmək → 400.
> 5. `can_see_student()` – şagird kartı üçün: öz sinfi **və ya** müəllimin dərs dediyi qrupun üzvü.
> 6. Çat: sərbəst qrup üçün sinif otağı yaradılmır.
> 7. İnterfeys: Tənzimləmələr → Siniflər: «Yeni» formasında 4 növ (TOM sinif, adi sinif, bölünmə qrupu, tədris qrupu); redaktədə növ və zəng; sərbəst qrupda «Üzvlər» (sinif seç → işarələ, seçilənlər siyahısı). «Siniflər» səhifəsində növ adları və «Redaktə» keçidi.
>
> **B. Mövzu icrası**
> 1. Model `TopicProgress(assignment_id, plan_lesson_id, status, done_on, note, updated_by, updated_at)`, unikal (assignment, plan_lesson); Alembic miqrasiyası.
> 2. `app/progress.py`: `topic_progress(db, ctx, today)` → mövzular (status, tarix, mənbə, rəsmi tarix, işçi plan tarixi, gecikmə günü), xülasə (cəmi, keçilib, qismən, təkrar, gözlənilən, fərq, həftə, faiz, plan faizi), bölmələr, həftəlik seriya (plan və faktiki kumulyativ), proqnoz (qalan mövzu, qalan dərs saatı, sığmayan, son 4 həftənin tempi vs lazım olan temp).
> 3. API: `GET /plan/{ta}/progress`, `PUT /plan/{ta}/topics/{pl}`, `DELETE /plan/{ta}/topics/{pl}`, `POST /plan/{ta}/topics/bulk` (məs. «№1–№12 keçildi»), `GET /my/progress` (bütün dərslərim üzrə icmal).
> 4. Gündəlik plan promtuna «təkrar tələb olunan əvvəlki mövzular» sətri.
> 5. İnterfeys: Jurnal → **Mövzular** tabı «İrəliləyiş» panelinə çevrilir: KPI (keçilib/cəmi, irəlidə/geridə N dərs ≈ həftə, proqnoz), plan-fakt qrafiki, bölmələr üzrə zolaqlar, hər mövzuda status düymələri + tarix + qeyd, toplu qeyd, çap. Ana səhifədə hər sinif üzrə qısa icmal.
> 6. Testlər: qrup növləri və üzvlük qaydaları, növ dəyişmə, mövzu qeydi (jurnal ierarxiyası, toplu, fərq hesabı, proqnoz), icazələr (başqa müəllim → 404).

---

## 4. İcra ardıcıllığı
| № | İş | Harada | Yoxlama |
|---|---|---|---|
| 1 | Sərbəst qrup + üzvlük qaydaları + `candidates` | `api/classes.py` | test |
| 2 | Növ (TOM↔adi) və zəng redaktəsi | `api/classes.py`, `SettingsRoster.tsx` | test |
| 3 | `can_see_student` (kart), çat otağı istisnası | `api/common.py`, `api/analytics.py`, `api/chat.py` | test |
| 4 | `TopicProgress` modeli + miqrasiya | `models.py`, `migrations/versions/b7c1d2e3f4a5_movzu_icrasi.py` | `alembic upgrade head` |
| 5 | İcra hesabı (fərq, bölmə, seriya, proqnoz) | `app/progress.py` | test |
| 6 | API: progress, qeyd, toplu, icmal | `api/plan.py` | test |
| 7 | AI gündəlik plan: təkrar mövzular | `api/lessonplans.py`, `domain/daily_plan.py` | test |
| 8 | Interfeys: Siniflər (forma, üzvlər), Jurnal → Mövzular, Ana səhifə | `SettingsRoster.tsx`, `Classes.tsx`, `Journal.tsx`, `Home.tsx` | `tsc`, `vite build` |
| 9 | Şagird əlavə etmə: sinfə «+ Şagird»; bölünmədə «+ Yeni şagird» → bu qrup və ya paralel; tədris qrupuna siniflərdən seçim | `SettingsRoster.tsx` (`NewStudent`, `Members`, `StudyMembers`) | `tsc` |
| 10 | Telefonlar (bax §6) | `domain/phones.py`, `api/phones.py`, miqrasiya `c9d3e4f5a6b7`, `Homeroom.tsx` | test |
| 11 | Şagird portalı: Plan → «Keçilən mövzular» (fənn üzrə keçilib/cəmi, plana nisbətən fərq, təkrar tövsiyəsi, növbəti mövzular); qrup dərsində qrupun adı | `api/portal.py` (`/portal/progress`), `student/Plan.tsx` | test |

## 6. Əlavə istək: şagird və valideyn telefonları
**Audit:** valideyn (ad, qohumluq, telefon) yalnız şagird-şagird pəncərədə yazılırdı; şagirdin öz telefonu, toplu daxil etmə, Excel idxalı, vahid format yox idi.
**Qaydalar:** telefonları yalnız sinif rəhbəri və admin görür (fənn müəllimi, şagird portalı – yox); nömrələr audit jurnalına yazılmır;
istənilən yazılış (`050 123 45 67`, `994…`, `+994 (50)…`) → `+994 50 123 45 67`; səhv nömrə rədd edilir; xarici nömrə `+` ilə qəbul olunur.
**İcra:** Sinif rəhbəri → Valideynlər:
- **Siyahı** – şagirdin və valideynlərin nömrəsi, zəng (`tel:`) və WhatsApp keçidi; redaktə pəncərəsində şagirdin öz telefonu;
- **Cədvəldə daxil et** – bütün sinif bir ekranda (şagird, ana, ata: ad + telefon), bir düymə ilə saxlanır; digər qəyyumlar qorunur;
- **Excel / CSV idxalı** – sinfin adları ilə hazır şablon (.xlsx), «Yoxla» (heç nə yazılmır, sətir-sətir hesabat) → «Təsdiq et»; ad «oğlu/qızı»suz da eşləşir; boş xana mövcud nömrəni silmir;
- çap: «Valideynlərin siyahısı»na şagirdin telefonu sütunu.

## 7. İcra nəticəsi (01.10.2026)
- Backend: 148 test keçdi (yeni: `test_api_groups_progress.py`, `test_api_phones.py`); miqrasiyalar `upgrade → downgrade → upgrade` yoxlanıb.
- Frontend: `tsc` və `vite build` xətasız.
- Brauzerdə əl ilə yoxlama hələ aparılmayıb (telefon eni 360 px daxil) – canlıya çıxmazdan əvvəl lazımdır.

## 5. Metodist tövsiyəsi
- Hər həftənin sonunda «Mövzular» panelinə baxın: **−2 dərsdən** çox geriləmə – «Mövzunu saxla»nı azaldın, KSQ-dan əvvəl təkrar dərsini birləşdirin.
- «Təkrar» statusu zəif sinifdə (XI peşə) dərsin əvvəlinə 5 dəqiqəlik təkrar kimi avtomatik daxil olur.
- Proqnoz «sığmır» deyirsə, ilin sonuna qədər lazım olan temp (dərs/həftə) həftəlik saatdan çoxdur – tədris hissəsi ilə əlavə saat və ya birləşdirmə razılaşdırılmalıdır.
