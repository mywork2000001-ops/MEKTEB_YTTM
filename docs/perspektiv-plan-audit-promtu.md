# Perspektiv plan – müəllim və şagird hissəsinin auditi (14.10.2026)

## Rol və məqsəd
Sən «Müəllim köməkçisi» tətbiqinin (FastAPI + React/TS, Render + Neon) baş mühəndisisən. Perspektiv plan
funksiyasını uçdan-uca yoxla – müəllim (Perspektiv plan, Proqramlar) və şagird (Plan, Dərs, Keçilən mövzular)
tərəfi – tapılan səhvləri düzəlt, testlə və build ilə yoxla, deploy et.

## Əhatə
| Hissə | Fayl | Yoxlanılan |
|---|---|---|
| Müəllim – plan | `frontend/src/pages/teacher/Plan.tsx`, `backend/app/api/plan.py` | görünüşlər (gün/həftə/ay/I–II yarımil/il), geriləmə, sığmayan dərslər, test faylı (P0010/P007/P013) seçimi, avtomatik mövzu testi, Word ixracı |
| Müəllim – proqramlar | `pages/teacher/Programs.tsx`, `app/programs.py`, `app/slow_plan.py` | proqramın tətbiqi, zəif qrup tempi, köhnə test bağlantıları |
| Şagird | `pages/student/Plan.tsx`, `Lesson.tsx`, `Extra.tsx`, `app/api/portal.py` | plan, test yalnız dərs başlayanda açılır, keçilən mövzular, dil (AZ/EN/RU) |
| İmtahan aralığı | `app/api/exams.py` `_range_topics/_range_lessons` | KSQ/BSQ mövzu siyahısı |

## Qaydalar
- Hər yeni/dəyişən interfeys mətni AZ/EN/RU (`t()`/`tt()`, lüğət `frontend/src/i18n.ts`, təkrar açar olmasın).
- Rəsmi sənədlər (Word perspektiv plan, plan çapı) – yalnız AZ.
- Yoxlama: `backend/.venv` ilə pytest (plan/portal/programs/slow_plan), `frontend`-də `npm run build`.
- Deploy: push → Render statusunu `gh api` ilə yoxla.

## Tapılanlar və düzəlişlər
1. **Zəif tempdə səhv test linkləri** (docs/zeif-plan-test-linkleri-promtu.md): proqram yenidən tətbiq olunanda
   mövzusu dəyişən dərsin köhnə `lesson_bank_links` seçimi qalırdı → `programs.apply` onu silir; miqrasiya
   `b4d6f8a0c2e4` canlı bazada köhnələri təmizləyir. «Məşq/Bərpa» dərsləri əsas mövzunun testini alır,
   «Bölmə/Spiral təkrar, KSQ-yə hazırlıq, yekun təkrar» – test linki yoxdur (`bank/match.lesson_query`).
2. **KSQ/BSQ aralığı**: törəmə (məşq/təkrar) dərslər ayrıca mövzu sayılırdı → `_range_topics/_range_lessons`-da çıxarıldı.
3. **Müəllimin «Perspektiv plan» səhifəsi tərcümə olunmurdu** (rusdilli müəllim hər şeyi AZ görürdü) →
   bütün mətnlər, bildirişlər, test statusları `t()/tt()` ilə; 50-dək yeni lüğət açarı.
4. **Şagirddə həftə günü** serverdən «B.e./Ç.a.» gəlirdi və rus/ingilis dilində tərcümə olunmurdu → Plan, Dərs,
   Əlavə dərslər səhifələrində `t(weekday)`; lüğətə qısa və tam gün adları əlavə edildi.
5. Görünüş siyahısının aria-label-i «Görünüş» (= tema, «Внешний вид») idi → «Dövr».

## Qəbul meyarları
- pytest: plan/portal/programs/slow_plan testləri keçir (55 passed, 2 skipped).
- `npm run build` uğurlu.
- Canlıda: X e planında məşq/bərpa dərsləri əsas mövzunun testini göstərir, təkrar dərslərində test linki yoxdur;
  RU dilində müəllim planı və şagird planındakı gün adları rusca.

## Növbəti addım (açıq)
- `Programs.tsx` (proqram kitabxanası, tətbiq pəncərələri) hələ yalnız AZ – eyni üsulla tərcümə.
- Şagirdin öz çapı (`studentPrint.ts` – «Dərs planım») AZ-dır; rəsmi sənəd deyil – istəyə görə tərcümə.
