# Kart: kod düzəlişləri 20.10.2026 (qalan işlər §3, 6–9)

**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Qaydalar:** CLAUDE.md (AZ/EN/RU, `npm run build`).
Canlı DB, miqrasiya, deploy – YOX. Commit öz budağında; main-ə Rəhbər birləşdirir.

## 1. İştirak 100% xətası – `backend/app/api/results_center.py` (~352, 373, 403; `GIVEN` – `app/timing.py`)
Heç bir test yazmayan şagirdə iştirak 100% görünür. Gözlənilən: tapşırıq var, yazılmayıb → **0%**; heç tapşırıq yoxdursa → `None`
(frontend «—» göstərir). Məxrəc = şagirdə təyin olunmuş (vaxtı keçmiş və ya bitmiş) tapşırıqlar sayı. Test: yazmayan şagird → 0.

## 2. «Yenidən göndər» (`copy_task`, `backend/app/api/tasks.py:445`, `CopyIn`) – müddətsiz rejim
Mənbə tapşırıq müddətsizdirsə (`timing.is_unlimited`) və ya `CopyIn`-də müddətsiz seçilibsə, kopyada da eyni qayda
(`closes_at`/`duration_min` – `timing.py`-dakı kimi). KSQ/BSQ 45 dəq. qalır. Frontend-də «Yenidən göndər» formasında
müddətsiz seçimi yoxdursa – əlavə et (mətn `t()` + i18n.ts AZ/EN/RU). Test: müddətsiz mənbə → müddətsiz kopya; KSQ → 45.

## 3. `exam_series` testləri – `backend/app/api/exam_series.py`
Yeni `backend/tests/test_exam_series.py`: ən azı 3 test əsas axın üçün (yaratma, siyahı/oxu, icazəsiz istifadəçi rədd).
Mövcud testlərdəki fixture-lardan istifadə et (`tests/conftest.py`).

## 4. Tərcümə boşluqları (görünən server mətnləri)
- `backend/app/api/extra.py:36` `DAYS` (yalnız AZ qısa adlar) – cavabda `weekday` indeksini də qaytar
  (`weekday_i`), frontend gün adını `t()` ilə göstərsin; AZ mətn sahəsi geriyə uyğunluq üçün qalsın.
  138-ci sətirdəki toqquşma mesajı – istifadəçinin dilinə uyğun (mövcud server i18n köməkçisi varsa onu işlət).
- `backend/app/programs.py` `lessons_for` xəbərdarlıqları – EN/RU qarşılığı (mövcud server mesaj modeli ilə).
- Məşğələ mövzu mətni yalnız AZ – əgər sxem `{az,ru,en}` dəstəkləyirsə `ml()` ilə göstər; yoxdursa toxunma, hesabatda yaz.
Rəsmi sənədlər (`plan_docx.py`, jurnal) – yalnız AZ, toxunma.

## Yoxlama (icraçı)
`cd backend && python -m pytest tests/test_exam_series.py <aid testlər> -q 2>&1 | tail -5`;
`cd frontend && npm run build 2>&1 | tail -5`. i18n.ts-də təkrar açar olmasın. Hesabat: dəyişən fayllar, test sayı, build, açıq qalanlar.
