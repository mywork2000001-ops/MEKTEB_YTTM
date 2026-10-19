# Kart: açılan bölmələr – peşəkar, müasir dizayn (19.10.2026)

İstifadəçi: «Açılan bölmələr və düymələr gözəl deyil və səmərəsizdir – peşəkar, müasir dizayn yarat və icra et.»
Əvvəlki iş: docs/menyu-acilan-bolmeler-promtu.md (3ec52f8, 2dc3c80, 64720ef).

## Canlıda müşahidə (1568×745, 19.10.2026)
1. **Əsas səhifə:** bağlı kart – boş hündür qutu, sağda kiçik boz «▾»; bağlıyken heç bir məlumat yoxdur (açmadan bilinmir:
   neçə dərs, növbəti dərs, risk). «Mövzu icrası» bağlı – sadəcə başlıq. Kartların hündürlüyü fərqli – boş sahə qalır.
2. **Menyu:** qrup başlıqları 11px böyük hərf, zəif kontrast, sayğac və ox çox kiçik; bütün qruplar açıq olanda yan panel
   745px-də sürüşür; aşağıdakı sitat bloku ~90px yer tutur.
3. **Uyğunsuzluq:** 13 yerdə ayrı-ayrı `<details>` (Journal, Plan, Reports, ExamSeries, HomeroomAttendance, SettingsRoster,
   şagird Plan/Results/Today …) – hər biri öz görünüşü ilə.

## Dizayn sistemi
- **Bir komponent** `ui.tsx` → `<Disclosure id title icon summary actions defaultOpen>`; bütün açılan bölmələr ona keçir
  (`.more` popover menyusu istisna).
- **Başlıq sətri:** min 52px, bütün sətir klik sahəsi; solda ikon (18px) + başlıq 15px/600; sağda **xülasə çipləri**
  (bağlıyken də görünür) + 28px dairəvi ox düyməsi, açılanda 180° fırlanır (200ms ease-out). Hover – yüngül fon,
  `:focus-visible` – aydın halqa. `aria-expanded`, `aria-controls`, Enter/Space.
- **Animasiya:** məzmun hündürlüyü `grid-template-rows: 0fr → 1fr` (240ms), `prefers-reduced-motion`-da animasiya yox.
- **Yadda saxlama:** hər bölmənin açıq/bağlı vəziyyəti `localStorage` (`mk.disc.<id>`, try/catch; yoxdursa defolt).
- **Rənglər/ölçülər** – mövcud CSS tokenləri (`:root`), qaranlıq rejim varsa onunla; yeni rəng icad etmə.
- **Mobil (≤ 600px):** kartlar tam en, başlıq 48px, çiplər ikinci sətrə keçir (sətirdən daşmır).

## Əsas səhifə
- Bağlıyken faydalı xülasə:
  - «Bugünkü dərslər» – «8 dərs · İndi: 3-cü saat X b» və ya «Növbəti 10:35 · X b» / «Dərslər bitdi»;
  - «Siniflərim» – «6 sinif · 101 şagird · ⚠ 9 yüksək risk»;
  - «Mövzu icrası» – geri qalan sinif sayı və ən çox geri qalan («X e −3 dərs») və ya «Hamısı planda ✓»;
  - «Bu həftə diqqət» və digər kartlar – eyni prinsip.
- Üstdə kiçik «Hamısını aç / Hamısını bağla» düyməsi.
- Kartlar yuxarıdan düzülür, bağlı kartlar eyni hündürlükdə, boş «uzanan» qutu yoxdur.

## Menyu
- Qrup başlığı 12px/600, kontrast WCAG AA; sağda ox (16px); bağlı qrupda kiçik sayğac, açıqda gizli; aktiv səhifənin qrupu
  həmişə açılır. Vəziyyət yadda qalır. Ox və başlıq eyni klik sahəsi.
- 745px hündürlükdə sürüşmə olmasın: sitat bloku `max-height: 800px` ekranda gizlənir (və ya kiçilir).
- Planşet/telefon «Daha çox» – eyni komponent.

## Mətnlər
Yeni xülasə mətnləri AZ/EN/RU (`t('{n} dərs', { n })` və s.), lüğətdə təkrar açar yoxdur.

## Yoxlama
- `npm run build` (frontend) uğurlu; vizual dəyişiklik – funksionallıq (məzmun, düymələr) eyni qalır.
- Chrome yoxlamasını Claude edir (1568×745, 900×700, 390×844).
