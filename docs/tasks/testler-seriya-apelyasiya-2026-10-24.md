# Tapşırıq: Testlər/Sınaqlar bölməsi, Avtomatik seriyalar (sözlə), Apelyasiya — audit + icra
- Tarix: 2026-10-24   Müəllif: Rəhbər (Claude)   İstifadəçi tələbi: 24.10 («интервал не цифрами а словами», «учитель не видит вопрос и текст апелляции»)
- İcraçı: `kodcu` × 2 paralel (worktree): **A** = Seriya + Testlər UI, **B** = Apelyasiya. Birləşdirmə, i18n konflikti, build/pytest — Rəhbər
- Əlaqəli: `docs/metodik-audit-2026-10-24.md` (M1, M5 burada icra olunur)

## 0. Audit nəticəsi (nə tapıldı)
| № | Bölmə | Tapıntı | Fayl |
|---|---|---|---|
| T1 | Seriya | Tezlik rəqəmlə: «Dövr» + «Hər neçə dövrdən bir: [2]»; siyahıda «hər 2 həftə» | `ExamSeries.tsx:21-22,122-123` |
| T2 | Seriya | «Açıq qalır (saat): 48», «Həll müddəti (dəq): 60» — müəllim saatı/dəqiqəni hesablamalıdır | `ExamSeries.tsx:130-131` |
| T3 | Seriya | Xülasə sətri rəqəm yığını: «· növbədə 5 · göndərilib 2»; seriyanın nə vaxta qədər çatacağı görünmür | `ExamSeries.tsx:44` |
| T4 | i18n | Tərcüməsiz: `'Hər həftə'`, `'işləyir'`, `'dayandırılıb'`, `'Davam et'`, `hint="ən azı 45"`, `toast('Xəta')`, həftə günləri `WD` | `ExamSeries.tsx:18,28,42,48,122,131`, `OnlineExams.tsx:272` |
| T5 | Testlər | Müddət rəqəmlə (45–300 dəq) | `OnlineExams.tsx:272`, `AssignTests.tsx:64` |
| T6 | Testlər | Müddətsiz mövzu testində cavablar «bağlanandan sonra» → bağlanma 2100-cü il → şagird izahı görmür (metodik M1) | `backend/app/plan_tests.py:~440` |
| T7 | Şagird | «Cavab ver» tərcüməsiz (M5) | `pages/student/Surveys.tsx:36` |
| A1 | Apelyasiya | Müəllim apelyasiyanı yalnız «Jurnal → KSQ → imtahan → ⚖» içində görür; ana səhifə düyməsi yalnız **birinci** imtahana aparır | `Home.tsx:79`, `Exams.tsx:258` |
| A2 | Apelyasiya | Kartda sualın **variantları yoxdur** — «Şagirdin cavabı: C» nə demək olduğu görünmür | `Exams.tsx:~416` (`a.question.options` göstərilmir) |
| A3 | Apelyasiya | Sual mətni `String(ml(...))` — düsturlar KaTeX-siz, xam `$...$` | `Exams.tsx:~416` |
| A4 | Apelyasiya | Şagirdin **mətni** (reason) kiçik «💬» sətirdə, aşağıda — gözdən qaçır | `Exams.tsx:~421` |
| A5 | Apelyasiya | Sual yalnız `ExamVariant`-dan oxunur; variant sonradan yenidən yaradılsa (retake) sual itir/dəyişir — apelyasiyada snapshot yoxdur | `api/exam_appeals.py:_out`, `api/portal.py:695-706` |

## Ümumi qaydalar
- Hər yeni/dəyişən UI mətni AZ/EN/RU (`t()`/`tt()`, `frontend/src/i18n.ts`; təkrar açar = build xətası). Server mesajı — `_L`.
- Test təyini məntiqi — yalnız `backend/app/plan_tests.py` (CLAUDE.md «tək mühərrik»).
- Miqrasiya YOX (A5 üçün mövcud JSON sahəsi `bank_ref` istifadə olunur).
- Yoxlama: aid pytest + `npm run build` (frontend). Commit etmə — Rəhbər birləşdirir.

---
## A. Seriya və testlər — «sözlə» (kodcu A)
### A.1 Köməkçi: `frontend/src/humanTime.ts` (yeni)
- `numWord(n, lang)`: 1–12 sözlə — az: bir, iki, üç, dörd, beş, altı, yeddi, səkkiz, doqquz, on, on bir, on iki; ru: один/одна… (cins: неделя/минута — qadın), en: one…twelve. 12-dən böyük — rəqəm.
- `everyText(period, every, lang)`: az: «hər gün / iki gündən bir / hər həftə / iki həftədən bir / hər ay / üç aydan bir»; ru: «каждый день / раз в два дня / каждую неделю / раз в две недели / каждый месяц / раз в три месяца»; en: «every day / every two days / every week / every two weeks / every month / every three months».
- `spanText(hours | minutes, lang)`: «45 dəqiqə» → «bir dərs (45 dəq)», 90 → «iki dərs (90 dəq)», 60 → «bir saat», 120 → «iki saat», 24 saat → «bir gün», 48 → «iki gün», 168 → «bir həftə», 336 → «iki həftə»; qalan — «N saat»/«N dəq» rəqəmlə.
- Dil `useT`/`prefs` ilə alınır; az/ru/en sözlükləri faylın içində (i18n.ts-ə 50 açar əlavə etməmək üçün) — CLAUDE.md istisnası deyil: bu, mətn deyil, ədəd sözlüyüdür.
- Kiçik vahid test yoxdur (frontend testi yoxdur) — `tsc -b` + əl ilə 3 dildə yoxlama.

### A.2 `ExamSeries.tsx` — forma
1. «Dövr» + «Hər neçə dövrdən bir» əvəzinə **bir seçim «Tezlik»**: hər gün · iki gündən bir · hər həftə · iki həftədən bir · üç həftədən bir · dörd həftədən bir · hər ay · iki aydan bir. Backend sahələri eyni (`period`, `every`) — yalnız UI.
2. «Açıq qalır (saat)» → seçim: bir gün · iki gün · üç gün · bir həftə · iki həftə · (növbəti sınağa qədər = `every`-ə uyğun hesablanır). Dəyər saatla göndərilir (24/48/72/168/336).
3. «Həll müddəti (dəq)» → seçim: bir dərs (45 dəq) · bir saat · iki dərs (90 dəq) · iki saat · üç saat. Dəyər dəqiqə (45/60/90/120/180).
4. «Ayın günü» rəqəm qalır (tarix), amma etiket: «Ayın neçəsi».
5. Formanın altında **canlı cümlə** (müəllim nə qurduğunu oxusun): «Hər iki həftədən bir, cümə günü saat 15:00-da açılır, iki gün açıq qalır, həll müddəti bir saat. Növbədə beş sınaq var — təxminən on həftəyə çatar (son: 26 dekabr).» (3 dildə, `everyText`/`spanText`/`numWord`).

### A.3 `ExamSeries.tsx` — siyahı
- Xülasə sətri (`:44`) A.2.5 cümləsinin qısa forması: «Hər həftə, cümə 15:00 · iki gün açıq · bir saat · növbədə beş sınaq, göndərilib iki». Növbə bitəcək tarix: «növbə ~26 dekabrda bitir» (`preview`/`next_at` + `every` ilə hesabla; `auto_new` açıqdırsa «yeni sınaqlar gəldikcə davam edir»).
- T4 sətirləri `t()`-yə: `'Hər həftə'`, `'işləyir'`, `'dayandırılıb'`, `'Davam et'`, `'ən azı 45'`, `'Xəta'`; `WD` həftə günləri — `t()` ilə (açarlar i18n.ts-də varsa təkrar etmə: əvvəl grep).

### A.4 Digər testlər
- `OnlineExams.tsx:272`, `AssignTests.tsx:64`: müddət seçimi A.2.3 ilə eyni (köməkçi komponent `DurationSelect` — `humanTime.ts`-də və ya `ui.tsx`-də), hint tərcümə.
- **T6/M1** `plan_tests.py`: mövzu testi + `NO_DEADLINE` → `show_answers='after_submit'`; müddətli/KSQ/BSQ/sınaq — dəyişmir. Portal `after_submit`-i artıq dəstəkləyir (ExamSeries-də seçim var) — yoxla. Test: `backend/tests/test_plan_tests.py` +2 hal.
- **T7/M5** `Surveys.tsx:36` → `tt('Cavab ver')` + i18n `['Answer', 'Ответить']`.
- `auto_tests.py:1-6` docstring-i real defoltlara uyğunlaşdır (M4) — davranış dəyişmir.

**A qəbul:** formada heç bir saat/dəqiqə/dövr rəqəm sahəsi yoxdur (ayın günü istisna); siyahı və canlı cümlə üç dildə düzgün («раз в две недели», «every two weeks»); köhnə seriyalar düzgün göstərilir (every=3 → «üç həftədən bir»; preset olmayan dəyər — «N saat» kimi, itmir); build ok; `test_plan_tests.py` ok.

---
## B. Apelyasiya — müəllim sualı və mətni tam görsün (kodcu B)
### B.1 Snapshot (A5) — miqrasiyasız
- `api/portal.py:create_appeal`: `bank_ref` JSON-a `q` açarı əlavə et: `{'text', 'options', 'image', 'kind', 'key'}` (variantdakı sualın o anki surəti; `key=key_value(q)`).
- `api/exam_appeals.py:_out`: `question` = variantdan tapılan `q`, **yoxdursa** `bank_ref['q']`; əlavə `question_changed: bool` (variantdakı mətn snapshot-dan fərqlidirsə).
- Köhnə apelyasiyalar (snapshot yoxdur) — indiki kimi variantdan.

### B.2 Bütün apelyasiyalar bir yerdə (A1)
- Backend: `GET /api/exam-appeals/inbox?status=open|all` — müəllimin bütün imtahanları üzrə (`own_assignment` hüququ ilə, admin — öz sinifləri): hər sətir `_out(...)` + `exam: {id, title, kind (KSQ/BSQ), date, ta_id, class_name}`, `appeal_until`. Sıralama: əvvəl `open`, köhnədən yeniyə.
- Frontend: yeni səhifə/çəkməcə **«⚖ Apelyasiyalar»** — ana səhifədəki düymə (`Home.tsx:79`) artıq birinci imtahana yox, buraya aparır; filtr «Gözləyənlər / Hamısı», qrup — imtahan üzrə başlıq («X e · KSQ-2 · 18.10 · apelyasiya 26.10-dək»). Kart komponenti **Exams.tsx-dəki ilə eyni** (ortaq `AppealCard` çıxar, kopya yox); qərar düymələri eyni endpoint-lər.
- Menyuda «Testlər və sınaqlar» və ya «Qiymətləndirmə» qrupunda «Apelyasiyalar (N)» bəndi (N = gözləyən).

### B.3 Kart (A2–A4) — `AppealCard`
Yuxarıdan aşağı:
1. Başlıq: şagird · sual №· mənbə (Onlayn/Yazılı) · status · tarix.
2. **Şagirdin apelyasiya mətni** — iri, çərçivəli blok, başlıq «Şagirdin yazdığı» (A4), ilk göstərilən məzmun.
3. Sual: `MathText` ilə (KaTeX), şəkil; **variantlar A–E** siyahısı: şagirdin seçdiyi — narıncı çərçivə + «şagird», açar — yaşıl + «açar»; açıq (input) sualda: «Şagirdin cavabı» / «Açar».
4. `question_changed` → xəbərdarlıq «Sual apelyasiyadan sonra dəyişib – şagirdin gördüyü variant göstərilir».
5. Skan kəsiyi (varsa), altmövzu, bank ünvanı (indiki kimi), «Bankda indi».
6. Cavab sahəsi + düymələr (indiki kimi). Rədd üçün cavab məcburidir — yazılmayıbsa düymə aktiv deyil (indi server 400 qaytarır).
- Şagird tərəfi (`ResultPackage.tsx`/`Results.tsx`): öz apelyasiyasının yanında müəllimin cavabı və statusu artıq var — yoxla, yoxdursa göstər.

### B.4 Testlər
- `backend/tests/test_exam_appeals.py` (varsa genişləndir, yoxdursa yarat): create → snapshot `bank_ref['q']` var; variant silinəndən sonra `_out.question` snapshot-dan gəlir; inbox başqa müəllimin apelyasiyasını göstərmir; inbox `open` sayı = `open-count`.

**B qəbul:** müəllim ana səhifədən bir kliklə bütün gözləyən apelyasiyaları görür; hər kartda şagirdin mətni, düsturlu sual, variantlar (şagirdin seçimi və açar işarəli); köhnə apelyasiyalar da açılır; bütün yeni mətnlər 3 dildə; pytest + build ok.

## Toxunma
Apelyasiya qərar məntiqi (`_decide_core`, `regrade_for`, `apply_all`), KSQ/BSQ şkalası, seriya backend planlaşdırıcısı (`exam_series.py` — yalnız oxu), rəsmi çap formaları.

## Cavab formatı
docs/agent-sistemi-promtu.md §7: dəyişən fayllar, yeni i18n açarları siyahısı, pytest (keçən/ümumi), build, açıq suallar.
