# Kart: video tanıtım (promt: `docs/video-tanitim-promtu.md`)

**İcraçı:** `kodcu` (worktree). Canlı DB, deploy, push – YOX. Miqrasiya – YOX (lazım deyil).
CLAUDE.md: hər yeni interfeys mətni `t()` + `frontend/src/i18n.ts` (AZ/EN/RU, Grep ilə əlavə et, tam oxuma, təkrar açar olmasın).

## A. Skript üslubu – `backend/scripts/guide_videos.py`
1. `HIGHLIGHT_JS`-ə overlay API əlavə et (`window.__guide`):
   - `title(main, sub)` – tam ekran titr kartı (tünd göy qradiyent, ağ böyük şrift, tətbiq adı «Müəllim köməkçisi», 2.5 san., solğunlaşaraq gedir);
   - `chapter(n, total, text)` – aşağı-solda lövhə «2/4 · Tapşırıqlar» (sürüşərək gəlir, ~2.5 san.);
   - `spot(selector)` – elementin ətrafı yumşaq tündləşir (box-shadow 0 0 0 9999px rgba(0,0,0,.45)), element üstündə nazik parlaq çərçivə; `spot(null)` – götürür;
   - `outro(main, sub)` – son titr («Hazırsan!» + «Videolar: menyuda «Bələdçi»»).
   - Kursor hərəkəti hamar (CSS transition ~.35s ease-out, `move_to` addımlarla), klik halqası qalır.
2. Addım növləri: `{'act': 'title'}`, `{'act': 'chapter', 'n':…, 'total':…, 'cap': L(...)}`, `{'act': 'outro'}`; `click/fill/hover`-da avtomatik `spot`.
   Fəsil başlanğıc vaxtlarını yadda saxla və `OUT/<role>/<id>.chapters.json` yaz: `[{"t": san., "title": {az,en,ru}}]`.
3. Hər ssenarinin əvvəlinə qısa titr (1.2 san.), sonuna qısa outro (1.2 san.) – bütün videolarda vahid üslub.
   Boş gözləmələri qısalt: addım müddəti = max(səs uzunluğu + 0.35 san., 1.2 san.); səssiz addım ≤ 1.2 san.
4. İki yeni ssenari `00-tanitim` (şagird, müəllim), mövcud addım/selektorlardan yığılır:
   - şagird (≤ 75 san.): Giriş titri → 1 Ana səhifə və menyu → 2 Tapşırıq/test işləmək → 3 Nəticələrim → 4 Bələdçi/kömək → outro;
   - müəllim (≤ 100 san.): titr → 1 Menyu → 2 Plan və mövzu testləri → 3 Sinif matrisi/nəticələr → 4 Kağız test və «📷 Skan» → 5 Jurnal/hesabat → outro.
   Səs mətni qısa, canlı, «sən»/«siz» (şagird – sən, müəllim – siz). AZ/EN/RU mətnlər `L(...)`.
5. Poster: hər videodan titrdən sonrakı kadr → `OUT/<role>/<id>.jpg` (≤ 120 KB, 960 px en).
6. `--export-ts` `guideData.ts`-ə `chapters` və `duration` (san.) əlavə etsin; `guideVideoSrc` dəyişmir; `guidePoster(role,id)` əlavə et.
7. Bütün videoları yenidən yarat (AZ+RU). Ümumi həcm ≤ 45 MB, hər fayl ≤ `MAX_MB`. Nəticə cədvəlini hesabata yaz (fayl, müddət, MB).

## B. Backend
- `backend/app/config.py`: `GUIDE_VERSION = 2`.
- `api/auth.py:58` – `guide_due` həm şagird, həm müəllim (staff) üçün; `api/portal.py` `guide_seen` – şagird yalnız-deyil: müəllim üçün də endpoint (mövcud yol saxlanır və ya ümumi `/api/auth/guide-seen`; frontend buna uyğun).
- `api/students.py:64` «🎬 ✓» nişanı: `>= 1` qalır.
- Testlər: müəllim üçün `guide_due` true → `guide-seen` → false; şagird qaydası pozulmayıb.

## C. Frontend
1. `GuideModal.tsx` → **xoş gəldin pəncərəsi** (Drawer yox, ortada modal, telefonda tam ekran):
   qradiyent başlıq («Xoş gəldin!» / müəllimə «Xoş gəlmisiniz!» + qısa şüar), poster + böyük ▶ (oynayanda video), fəsil çipləri
   (basanda `video.currentTime = t`), aşağıda düymələr: «Sonra bax» (sessiya üzrə), «Bir daha göstərmə» (`guide-seen`), «Bütün videolar» (Bələdçi səhifəsi).
   Video sona çatanda «guide-seen» avtomatik. Esc/scrim – «Sonra bax». Açılış animasiyası yumşaq (fade+scale, `prefers-reduced-motion`-da yox).
   Rol: şagird → `student/00-tanitim`, müəllim → `teacher/00-tanitim`. Dil: `guideVideoSrc` + `guideSubLangs`.
2. `pages/Guide.tsx` – tanıtım yuxarıda iri kart; qalanlar grid kartları (poster, başlıq `t()`, müddət «1:05»), basanda pleyer + fəsillər.
3. Şagirdin «🎬 Necə istifadə etməli» düyməsi və müəllim menyusunda «Bələdçi» eyni pəncərəni aça bilsin.
4. Bütün yeni mətnlər `t()` + i18n.ts AZ/EN/RU.

## Yoxlama (icraçı)
`backend/.venv/Scripts/python.exe -m pytest <aid testlər> -q 2>&1 | tail -5`; `cd frontend && npm run build 2>&1 | tail -5`
(worktree-də node_modules yoxdursa – əsas qovluğa junction, sonra sil). Videolar üçün yerli demo – skriptin öz rejimi.
Hesabat: budaq, commit, fayllar, test sayı, build, video cədvəli, 2 poster yolu (Rəhbər baxacaq), edilməyənlər.
