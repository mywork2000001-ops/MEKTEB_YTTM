# Jurnal → «Gündəlik»: səliqəli görünüş, dərs seçimi, davamiyyətin 1-ci dərsdən 2-ci dərsə köçürülməsi

**Rol:** baş mühəndis + UX dizayner. **Obyekt:** `frontend/src/pages/teacher/Journal.tsx` (`DayView`, `LessonCard`),
`pages/teacher/common.tsx` (`ATT`, `LessonSelect`), `backend/app/api/journal.py` (`GET /{ta}/day`, `PUT /{ta}/entry`, `JournalEntry.auto`).
**İstifadəçi tələbi (12.10.2026):** jurnal səliqəli olsun; açılan siyahı ilə seçim; bir gündə iki dərs varsa – filtrlə
seçilsin; **birinci dərsdə qoyduğum davamiyyət ikinciyə avtomatik köçsün**, müəllim yalnız dəyişəni düzəltsin
(şagird 2-ci dərsdə yoxdursa və ya sonradan gəlibsə).
**Qayda:** əvvəl uğursuz test → düzəliş → bütün testlər → `tsc` + `vite build` → brauzer (telefon 390 px və kompüter) →
commit → push. Hər yeni mətn AZ/EN/RU (CLAUDE.md). Rəsmi jurnal çapı dəyişmir.

## A. Audit (kod, 12.10.2026)
| № | Tapıntı | Qərar |
|---|---|---|
| 1 | `DayView` günün bütün dərslərini alt-alta uzun kartlar kimi göstərir (`day.lessons.map(LessonCard)`); telefonda 2 dərs = çox sürüşdürmə | Günün dərsləri **açılan siyahı** (seçici) ilə: «2-ci saat · 09:40 – Kvadrat tənliklər». Bir dərs varsa – seçici gizli |
| 2 | `LessonCard` davamiyyəti hər dərsdə sıfırdan `var` ilə başladır (`e.exists && !e.auto ? … : hamısı var`) – 1-ci dərsdəki «q/ü/g» 2-ci dərsə keçmir | **Köçürmə:** 2-ci dərs hələ yazılmayıbsa (`!exists \|\| auto`), davamiyyət 1-ci dərsdən götürülür; müəllim yalnız fərqi dəyişir |
| 3 | 2-ci dərs artıq saxlanıbsa, 1-ci dərsdə sonradan edilən dəyişiklik ona toxunmamalıdır | Köçürmə **yalnız yazılmamış** dərsə; yazılmışa heç vaxt yazılmır |
| 4 | Jurnalın 8 tabı (`Gündəlik … Xülasə`) telefonda bir sətrə sığmır | Dar ekranda tablar **açılan siyahıya** çevrilir (≤ 640 px), kompüterdə tab qalır |
| 5 | Gün naviqasiyası: «‹ Əvvəlki gün / Növbəti gün ›» – dərs olmayan günlərə də keçir | «‹ / ›» düymələri **növbəti dərs gününə** keçir (cədvəl + bayramlar `day` API-dən); tarix seçicisi qalır |
| 6 | Qiymət və ev tapşırığı yoxlaması dərsə məxsusdur | **Köçürülmür** – yalnız davamiyyət (qiymət hər dərsdə ayrıca) |

## B. Davranış
1. **Dərs seçimi (filtr).** Gündə ≥ 2 dərs varsa yuxarıda açılan siyahı: `1-ci dərs – 2-ci saat (09:40)`, `2-ci dərs – 5-ci saat (12:10)`.
   Standart seçim: indiki saata ən yaxın dərs (dərs zamanı – həmin dərs; gün bitibsə – sonuncu yazılmamış dərs).
   Seçim URL-də saxlanır (`?date=…&p=5`) – səhifə yenilənəndə itmir. Siyahıda hər dərsin yanında vəziyyət: ✓ yazılıb / ● yazılmayıb.
2. **Davamiyyətin köçürülməsi.**
   - 2-ci dərs açılanda: o dərs yazılmayıbsa və həmin gün əvvəlki dərs (eyni sinif/fənn) yazılıbsa → davamiyyət ondan götürülür.
   - Yuxarıda məlumat zolağı: «Davamiyyət 1-ci dərsdən köçürüldü – yalnız dəyişəni düzəldin». Düymə: «Hamısını *var* et».
   - Köçürülmüş, amma hələ saxlanmamış dəyər fərqli rəngdə (açıq çərçivə); müəllim dəyişdikcə adi rəngə keçir.
   - Tipik düzəlişlər bir toxunuşla: 1-ci dərsdə «q» olan, 2-ci dərsə gələn → «var» (və ya «g»); 1-ci dərsdə olan, 2-ci dərsdə yoxdur → «q».
   - Saxlananda adi `PUT /entry` – heç bir gizli avtomatik yazı yoxdur (müəllim «Yadda saxla» basmasa, 2-ci dərs yazılmamış qalır).
   - 2-ci dərs artıq yazılıbsa – köçürmə olmur; 1-ci dərsi sonradan dəyişəndə 2-ciyə toxunulmur.
3. **Səliqə.**
   - Dərs kartında bölmələr ardıcıllıqla və yığılan (accordion): *Mövzu və ev tapşırığı* → *Davamiyyət* → *Qiymətlər* → *Ev tapşırığının yoxlanması* → *Qeyd*.
   - Şagird sətri: ad (tam en, sıxılmır) · davamiyyət düymələri · qiymət; telefonda düymələr ikinci sətrə keçir, mətn kəsilmir.
   - Yuxarıda xülasə: «Sinifdə 24 · gəlib 22 · qayıb 1 · üzrlü 1 · gecikib 0».
   - «Yadda saxla» düyməsi aşağıda sabit (sticky); saxlanmamış dəyişiklik varsa başqa dərsə / günə keçəndə xəbərdarlıq.
   - Tablar telefonda açılan siyahı (A4).

## C. Backend
- `GET /api/journal/{ta}/day` cavabına hər dərs üçün `prev_attendance` (həmin gün əvvəlki yazılmış dərsin davamiyyəti, yoxdursa `null`)
  və `copied: bool` əlavə olunur. Hesablama serverdə – frontend sadə qalır, oflayn növbə (outbox) dəyişmir.
- Yeni cədvəl / miqrasiya lazım deyil.

## D. Testlər
- Backend: gündə 2 dərs; 1-ci yazılıb (`A=q, B=g`) → 2-ci üçün `prev_attendance` = həmin dəyərlər; 2-ci yazılıbsa – `prev_attendance` yoxdur;
  fərqli sinif/fənn dərsindən köçmür; 1-ci dərs yazılmayıbsa – köçmür; qiymətlər köçmür.
- Brauzer (390 px və 1280 px): 2 dərslik gün → seçici görünür, standart seçim düzgündür; 2-ci dərsdə davamiyyət 1-cidən gəlib,
  bir şagirdi «var» edib saxla → jurnal səhifəsində hər iki sütun düzgün; tablar telefonda siyahıdır; heç bir mətn sıxılmır, üfüqi sürüşmə yoxdur.

## E. Mərhələlər
1. Backend `prev_attendance` + testlər.
2. `DayView`: dərs seçicisi (URL ilə), növbəti dərs gününə keçid.
3. `LessonCard`: köçürmə, məlumat zolağı, «Hamısını var et», saxlanmamış dəyişiklik xəbərdarlığı, sticky «Yadda saxla».
4. Səliqə: yığılan bölmələr, xülasə sətri, telefonda tablar → açılan siyahı.
5. Brauzer yoxlaması, commit, push.
