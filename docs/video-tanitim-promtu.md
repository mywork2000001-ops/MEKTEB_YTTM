# Video tanıtım – peşəkar, yığcam, tətbiq açılanda (20.10.2026)

**Sifarişçi:** müəllim (istifadəçi): «videoları daha peşəkar və cəm şəkildə verin, tətbiq açılanda görünsün, cəlbedici olsun».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Kart:** `docs/tasks/video-tanitim.md`
**Qaydalar:** CLAUDE.md – hər yeni mətn AZ/EN/RU (`t()`, `i18n.ts`); yoxlama `npm run build` + aid pytest; miqrasiya yoxdur.

## 1. Hazırkı vəziyyət
- `backend/scripts/guide_videos.py` – Playwright + CDP screencast → ffmpeg MP4 (1080p H.264), səs edge-tts (AZ/RU), alt yazı VTT.
- 14 video (şagird 8, müəllim 6), hər biri AZ və RU – cəmi 28 MP4, 37 MB. Ayrı-ayrı, uzun, «ekran yazısı» görünüşlü.
- Tətbiq açılanda yalnız **şagirdə** sağ tərəfdə kiçik pəncərə (Drawer) çıxır (`GuideModal.tsx`, `guide_due`, `GUIDE_VERSION = 1`).
- Müəllimə avtomatik heç nə göstərilmir; `pages/Guide.tsx` – sadə siyahı.

## 2. Məqsəd (qəbul meyarları)
| # | Tələb | Ölçü |
|---|---|---|
| M1 | **Yığcam tanıtım videosu** – hər rol üçün bir: şagird ≤ 75 san., müəllim ≤ 100 san.; 4–5 fəsil | `00-tanitim.{az,ru}.mp4` |
| M2 | **Peşəkar görünüş:** giriş titri (ad + şüar), fəsil başlığı lövhəsi («2/4 · Tapşırıqlar»), hədəf elementi işıqlandırma (ətraf tündləşir), hamar kursor, keçidlərdə yumşaq solğunlaşma, son titr («Hazırsan!») | gözlə yoxlama |
| M3 | Bütün videolar eyni üslubda (köhnə 14 video da yeni üslubla yenidən yazılır), boş gözləmələr qısaldılır | ümumi həcm ≤ 45 MB |
| M4 | **Tətbiq açılanda** – şagird və müəllimə ortada böyük, cəlbedici xoş gəldin pəncərəsi: başlıq, poster şəkli, böyük ▶, fəsil düymələri (basanda videoda o yerə keçir), «Sonra bax» / «Bir daha göstərmə» / «Bütün videolar» | GUIDE_VERSION = 2 – hamı bir dəfə görür |
| M5 | Bələdçi səhifəsi – video kartları: poster, müddət, tanıtım yuxarıda iri kart | gözlə |
| M6 | AZ/EN/RU: interfeys mətnləri, səs AZ və RU, alt yazı AZ/EN/RU | `npm run build` |

## 3. Rəhbər qərarları
- Fon musiqisi yoxdur (lisenziya riski); yalnız səs.
- Telefon üçün ayrıca tanıtım yoxdur – tanıtım 16:9, telefonda da oynayır; `08-telefon` kitabxanada qalır.
- Test icra ekranında (`data-solving`) və `/t/` yolunda pəncərə çıxmır (indiki qayda qalır).
- Gördü/bağladı – `guide_seen_version` (sütun var, miqrasiya lazım deyil); müəllimlər üçün də işləyir.
- Mövcud videoların ayrıca faylları saxlanır (kitabxana), tanıtım isə yeni fayl.

## 4. İcra ardıcıllığı
1. Kart → `kodcu` (worktree): skript üslubu + tanıtım ssenariləri + xoş gəldin pəncərəsi + Bələdçi kartları + backend (müəllim üçün `guide_due`).
2. Videoları yaratmaq (skript, yerli demo) → həcm və müddət yoxlaması.
3. Rəhbər review: aid pytest, `npm run build`, 2–3 videoya baxış (kadr şəkilləri), merge → push → Render success → canlıda `/guide/*/00-tanitim.*.mp4` 200.
4. Audit sətri (`docs/audit/icra-2026-10-20b.md`).
