# Müəllim menyusu — açılan bölmələr (akkordeon), kompüter + planşet + telefon (19.10.2026)

Rol: UI/UX dizayner + frontend mühəndisi. Fayllar: `frontend/src/Layout.tsx`, `frontend/src/styles/extra.css`, `frontend/src/i18n.ts`.
Mövcud vəziyyət (1f001a7): `TEACHER_NAV`-da `group` (Dərs / Qiymətləndirmə / Siniflər / Ünsiyyət), sidebar-da qrup başlığı
sadəcə yazıdır (`.nav-group`); telefonda (≤700px) alt panel 4 düymə + «Daha çox» pəncərəsi (Drawer), orada da qrup başlıqları.
Məqsəd: **qrup başlığı basılan düymə olsun, altındakı bəndlər açılıb-bağlansın** — menyu qısalır, lazım olan bölmə bir toxunuşla açılır.
Şagird menyusu (qrupsuz) DƏYİŞMİR. URL, API, DB dəyişmir.

## Qərarlar
1. **Ortaq komponent `NavGroups`** (Layout.tsx daxilində): `items`-i qruplara bölür, hər qrup = başlıq düyməsi + bəndlər siyahısı.
   Sidebar-da və telefonun «Daha çox» pəncərəsində eyni komponent (fərq yalnız klik davranışı: NavLink və ya `nav()` + pəncərəni bağla).
2. **Başlıq düyməsi**: `<button aria-expanded aria-controls>` — solda qrup adı, sağda bəndlərin sayı (kiçik, boz) və ox ▾
   (açıqda 180° fırlanır). Hündürlük: kompüterdə 34px, telefonda 44px (barmaq üçün). Klaviatura: Enter/Space açır-bağlayır.
3. **Hansı qrup açıqdır (yaddaş)**:
   - Aktiv səhifənin qrupu **həmişə açıq** (səhifə dəyişəndə avtomatik açılır, bağlamaq olar, amma növbəti keçiddə yenə açılır).
   - Qalanları istifadəçinin seçimi — `localStorage['mk-nav-open']` (try/catch; oxunmasa — default).
   - Default (ilk dəfə): yalnız «Dərs» + aktiv səhifənin qrupu açıq.
   - Eyni anda bir neçə qrup açıq ola bilər (tək-açıq rejimi YOX — müəllim tez-tez Jurnal ↔ Testlər keçir).
4. **Bağlı qrupda aktiv səhifə** (istifadəçi əl ilə bağlayıbsa): başlıqda kiçik aksent nöqtəsi — harada olduğunu itirməsin.
5. **Animasiya**: `display:grid; grid-template-rows:0fr → 1fr`, 180ms; `prefers-reduced-motion` — animasiyasız.
   Bağlı bəndlər `inert` (və ya `hidden` animasiyadan sonra) — Tab ilə gizli linkə düşməsin.
6. **Planşet rejimi (701–1100px, dar sidebar)**: akkordeon işləyir, başlıq mətni görünür (indiki `font-size:0` xətti qaldırılır),
   ox saxlanılır; nav öz daxilində scroll edir.
7. **Telefon (≤700px)**: alt panel dəyişmir (Əsas, Jurnal, Çat, Hesabat, Daha çox). «Daha çox» pəncərəsi açılanda:
   qruplar akkordeon, default — hamısı **açıq** (pəncərədə yer var, əlavə toxunuş lazım deyil), bağlananlar yadda qalır
   (ayrı açar `mk-nav-open-m`). Alt paneldəki 4 bənd pəncərədə təkrarlanmır (indiki kimi); boş qalan qrup göstərilmir.
   «Çıxış» ən aşağıda, qruplardan ayrı.
8. **Görünüş**: mövcud tokenlər (`--side-muted`, `--side-hover`, `--accent`), yeni rəng yox; dark mode və `.big` şrift pozulmur.
   `@media (max-height:760px)` sıxlığı saxlanılır.
9. **Mətnlər AZ/EN/RU**: aria üçün `'{g} bölməsini aç'` / `'{g} bölməsini bağla'` (lüğətə EN+RU), qrup adları artıq lüğətdədir.

## Yoxlama
- `cd frontend && npm run build` — xətasız (lüğətdə təkrar açar yoxdur).
- Əl ilə: 1396×663 (kompüter), 900×700 (planşet), 390×844 (telefon) — açılır/bağlanır, aktiv qrup açıq, səhifə yenilənəndə seçim qalır,
  Tab ilə bağlı bəndə düşmür, şagird menyusu əvvəlki kimi.
