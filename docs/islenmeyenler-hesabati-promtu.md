# Onlayn testləri yazmayanlar – peşəkar hesabat (20.10.2026)

**Sifarişçi:** müəllim (istifadəçi): «onlayn testləri yazmayan şagirdlər üzrə hər şagirdin və sinif daxili peşəkar, konkret
hesabatı; lazım olanda çap edib qrupa göndərsin; səliqəli, təkrarsız sətirlər».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Kart:** `docs/tasks/islenmeyenler-hesabati.md`
**Qaydalar:** CLAUDE.md – interfeys AZ/EN/RU; rəsmi sinif hesabatı yalnız AZ; şagird vərəqəsi şagirdin dilində (AZ və ya AZ|RU);
tək mənbə – `student_report.class_matrix` → `class_missing` (yeni hesablama məntiqi yazılmır, yalnız genişlənir).

## 1. Hazırkı vəziyyət
- `GET /api/results-center/class/{ta}/missing-list` (json / pdf / xlsx, `per_student=1`), `…/student/{sid}/missing-list`;
  çap – `backend/app/missing_list_print.py`; ekran – `ClassMatrix.tsx` («İşlənməyənlər» rejimi), `StudentReport.tsx`.
- Çatışmayanlar: yalnız «kim nəyi yazmayıb» siyahısı; göstərici, icra faizi, risk səviyyəsi, test üzrə kəsik, tövsiyə,
  dövr seçimi, bütün siniflər üzrə xülasə, «qrupa göndər» (WhatsApp/Telegram) yoxdur; təkrar göndərilmiş test ayrı sətir ola bilər.

## 2. Metodiki əsaslar (hesabatın məntiqi)
1. **İcra (iştirak) əmsalı** = işlədiyi testlər / ona verilmiş və hesabat tarixinə qədər açılmış testlər × 100%.
   Məxrəcə yalnız şagirdə həqiqətən təyin olunmuş testlər düşür (sonradan gələn şagird – gəlişindən sonrakılar).
2. **Status ayrımı** (ədalətli qiymətləndirmə):
   - *Yazmayıb* – son tarix keçib, təhvil yoxdur;
   - *Gözlənilir* – test açıqdır/müddətsizdir, hələ yazılmayıb (borc kimi sayılır, amma ayrıca göstərilir);
   - *Üzrlü* – müəllim qeydi (xəstəlik və s.) varsa, məxrəcdən çıxır (sxemdə varsa; yoxdursa – P3).
3. **Risk səviyyəsi** (şagird üzrə, dövr üçün): 🔴 *Kritik* – icra < 50% və ya ardıcıl ≥ 3 buraxma;
   🟠 *Diqqət* – 50–79%; 🟢 *Normal* – ≥ 80%. Hədlər bir yerdə sabit kimi (`MISSING_RISK`), sonra tənzimlənə bilər.
4. **Tövsiyə sütunu** (avtomatik, qısa): Kritik → «Valideynlə əlaqə + fərdi söhbət»; Diqqət → «Xatırlatma, təkrar imkan»;
   yalnız *gözlənilir* → «Son tarixi xatırlat». Müəllim çapdan əvvəl qeyd sətri əlavə edə bilər (sərbəst mətn, yadda saxlanmır).
5. **Təkrarsızlıq qaydaları:**
   - bir şagird = bir sətir (paralel qrup, iki sinifdə olan, birləşdirilmiş dublikat – `student_id` üzrə bir dəfə);
   - bir məntiqi test = bir sütun/sətir: «Yenidən göndər» surətləri və orijinal bir test sayılır; şagird hər hansı
     variantı işləyibsə – *işləyib* (təkrar göndərişlər qrupu məntiqi mövcud koddan götürülür);
   - onlayn + kağız (nəşr olunmuş skan) eyni testdirsə – bir dəfə (matrisin mövcud qaydası).
6. **Etika:** qrupa göndəriləcək variantda ad göstərmə rejimi seçilir – «Tam ad» / «Ad + soyadın baş hərfi» / «Adsız (yalnız say)».
   Ekranda qısa xatırlatma: «Valideyn qrupunda adsız və ya qısa ad tövsiyə olunur; fərdi vərəqəni şəxsən göndərin».

## 3. Hesabat formaları (qəbul meyarları)
| # | Forma | Məzmun | Format |
|---|---|---|---|
| H1 | **Sinif hesabatı** (rəsmi, AZ, A4) | Başlıq bloku (məktəb, sinif, fənn, müəllim, dövr, tarix); **göstəricilər**: şagird sayı, test sayı, sinif üzrə orta icra %, tam icra edən, kritik/diqqət sayı; **Cədvəl 1 – şagird üzrə** (bir şagird bir sətir: №, ad, verilib, işləyib, yazmayıb, gözlənilir, icra %, risk, işlənməyən testlər qısa №-lərlə, tövsiyə); **Cədvəl 2 – test üzrə** (tarix, test, verilib, işləyib, icra %, yazmayanların sayı); şərti işarələr; imza bloku | PDF, Excel |
| H2 | **Şagirdin fərdi vərəqəsi** | Ad, sinif, dövr, icra %, işləməli olduğu testlər (tarix, status, «necə tapmaq»: Tapşırıqlar bölməsi), müəllim qeydi sətri, valideyn imzası sətri | PDF; şagird dili ru → AZ|RU |
| H3 | **Bütün siniflərim – xülasə** | Hər sinif bir sətir: şagird, test, icra %, kritik/diqqət sayı; sonra hər sinfin H1-i ayrıca səhifədə | PDF |
| H4 | **«Qrupa göndər»** | Qısa mesaj mətni (seçilmiş dildə, ad rejimi ilə): dövr, açıq testlər və son tarix, yazmayanlar; «📋 Mətni kopyala»; telefonda «Paylaş» (Web Share API – PDF faylı ilə, dəstək yoxdursa yükləmə) | mətn + PDF |

Ümumi: dövr seçimi (bu həftə / bu ay / semestr / tarix aralığı), növ (mövzu / sınaq / hamısı), «yalnız yazmayıb» / «gözlənilir də».
Sıralama: risk → icra % → ad. Boş nəticə – «Bu dövrdə bütün şagirdlər testləri işləyib 👏».

## 4. İcra ardıcıllığı
1. Kart → `kodcu` (worktree). 2. Review: aid pytest, `npm run build`, PDF-lərin şəkli (Rəhbər baxır).
3. Merge → push → Render success → canlıda bir sinifdə PDF yoxlaması. 4. Audit sətri.

## 5. Əlavə tələblər (istifadəçi, 20.10.2026 – sonradan)
### 5.1 «Dərs planına uyğun günə yazmayıb qalanlar»
- Hər testin **plan günü** = bağlı plan dərsinin tarixi (`OnlineTask.plan_lesson_id → PlanLesson` tarixi); plan dərsi yoxdursa – son tarix,
  o da yoxdursa (müddətsiz) – açılış tarixi + 7 gün.
- Statuslar plan gününə görə: **Plan gününə qədər yazmayıb** (hələ də yazmayıb) · **Gecikmə ilə yazıb** (plan günündən sonra, neçə gün) ·
  **Vaxtında** · **Plan günü hələ gəlməyib** (borc sayılmır). Müddətsiz testlərdə də bu qayda işləyir – ədalətli müqayisə üçün əsas ölçü budur.
- Hesabatda filtr «Plan gününə qədər yazmayanlar» (defolt) və sütun «Gecikmə (gün)»; icra % iki cür: plan üzrə vaxtında / ümumi.

### 5.2 «Hər şagird üçün tələb etmə imkanı»
- Hər şagird sətrində **«📩 Tələb et»**: şagirdə tətbiqdaxili bildiriş (mövcud bildiriş mexanizmi) – işlənməli testlərin siyahısı,
  istəyə görə yeni son tarix; testi bağlanıbsa – həmin şagird üçün yenidən açmaq («Yenidən göndər» `copy_task`, `student_ids=[id]`).
- Toplu: seçilmiş şagirdlərə / bütün borclulara «Tələb göndər». Mətn şablonu şagirdin dilində (AZ/EN/RU), müəllim redaktə edə bilər.
- Tələb tarixçəsi saxlanır (kimə, nə vaxt, hansı testlər) – sətirdə «Tələb edilib: 2 dəfə, son 20.10».

### 5.3 «Yazmayanları müəllim araşdıra bilsin»
- Şagird sətrindən **«🔍 Araşdır»** pəncərəsi (hər test üzrə faktlar, avtomatik):
  test şagirdə görünürdü/təyin olunmuşdu; açıb başlayıb, amma təhvil verməyib (cəhd var/yox, nə vaxt); bildiriş/tələb göndərilib, oxunub;
  son giriş tarixi; həmin plan günündə dərsdə davamiyyət (yox idi → «dərsdə olmayıb»); oxşar testləri işləyib-işləməyib.
- Müəllim **səbəb qeyd edir**: Üzrlü (xəstəlik, ailə), Texniki problem, İnternet/cihaz yoxdur, Unudub, İmtina, Digər + qısa qeyd.
  «Üzrlü» – icra faizinin məxrəcindən çıxır; səbəblər hesabatda sütun və şərti işarə ilə görünür; sinif hesabatında səbəblər üzrə xülasə.
- Saxlama üçün yeni cədvəl (miqrasiya – yalnız yeni cədvəllər, start-da avtomatik): `missing_notes` (task/şagird/səbəb/qeyd/müəllim/tarix)
  və `missing_requests` (tələb tarixçəsi).
