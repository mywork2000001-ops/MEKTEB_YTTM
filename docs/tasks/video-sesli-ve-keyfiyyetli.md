# Tapşırıq kartı: video bələdçi – Azərbaycan dilində səs və yüksək keyfiyyət

**Tarix:** 20.10.2026 · **Sifarişçi:** müəllim («где голоса на азербайджанском языке и еще качество видео нехорошее»)
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` · Fayl: `backend/scripts/guide_videos.py` (+ Bələdçi səhifəsinin video yolu)

## 1. Problem (Rəhbər yoxladı)
- Səs yoxdur: skript yalnız alt yazı (.vtt) yazır, ffmpeg-də `-an`.
- Keyfiyyət: Playwright `record_video` özü aşağı bitreyt VP8 yazır, sonra `compress()` onu yenidən `crf 34–51`, **15 fps**, ≤ 3 MB sıxır → bulanıq mətn.

## 2. Alətlər (quraşdırılıb, `.venv`-də yoxlanıb)
- `edge-tts` (pulsuz, açarsız): səslər `az-AZ-BanuNeural` (qadın, **default**), `az-AZ-BabekNeural` (kişi). İnternet lazımdır.
- `imageio-ffmpeg` → tam ffmpeg 7.1 (`libx264`, `aac`, `libopus`, `libvpx-vp9`): `imageio_ffmpeg.get_ffmpeg_exe()`. `find_ffmpeg()` əvvəl bunu götürsün.
- Hər ikisini `backend/requirements-dev.txt`-ə yaz (yoxdursa yarat). **`requirements.txt`-ə YOX** (Render-ə lazım deyil).
- Windows konsolu cp1251-dir: çap edərkən `PYTHONIOENCODING=utf-8` və ya `sys.stdout.reconfigure(encoding='utf-8')`.

## 3. Nə etmək
### 3.1 Səs (AZ)
- Hər `cap`-lı addım üçün AZ mətnindən mp3 (edge-tts, `--voice`, default Banu; `rate` ≈ `-5%`). Addımda istəyə bağlı `say` sahəsi – səs üçün xüsusi mətn
  (məs. «XE-001» → «iks e sıfır sıfır bir», «PIN» → «pin»); yoxdursa `cap.az`. «» dırnaqları səsə getməsin.
- Keş: `backend/data/guide_tts/<sha1(voice+rate+mətn)>.mp3` (data/ git-ignore-dur) – təkrar yazıda yenidən yüklənmir.
- Səs uzunluğunu ölç (ffmpeg ilə decode/parse). Addım müddəti = `max(st['wait'], səs_uzunluğu + 0.5 s)`; səs addımın başlanğıcında (`a`) başlayır.
  Addımlar arasında səslər üst-üstə düşməməlidir.
- Mux: hər klip `adelay`-lə öz vaxtına, `amix=normalize=0`, sonra `loudnorm` (və ya sadə volume), AAC 128k mono.
- Arqumentlər: `--voice banu|babek`, `--no-voice` (köhnə kimi səssiz). Kod dil parametri ilə yazılsın ki, sonra `--voice-lang ru` əlavə etmək asan olsun (indi lazım deyil).
- edge-tts xətası → aydın mesaj və həmin video səssiz yazılır (skript yıxılmır).

### 3.2 Keyfiyyət
- `record_video` əvəzinə **CDP screencast**: `cdp = ctx.new_cdp_session(page)`, `Page.startScreencast {format:'jpeg', quality:92}`, hər `Page.screencastFrame` – faylı və `metadata.timestamp`-ı saxla, `Page.screencastFrameAck`.
  Kadrlar yalnız dəyişəndə gəlir → ffmpeg `concat` demuxer (`duration` ilə) → sabit **30 fps**.
- Kəskinlik: kompüter ssenariləri viewport 1280×720, `device_scale_factor=1.5` → çıxış **1920×1080**; telefon (390×780) `device_scale_factor=2` → 780×1560.
  Layout dəyişmir (viewport eyni), yalnız piksel sıxlığı artır.
- Kodlaşdırma: **MP4 H.264** `libx264 -preset slow -crf 20 -tune stillimage -pix_fmt yuv420p -movflags +faststart`, səs AAC. `MAX_MB` → 15 (hər video); həddi keçərsə crf 23, 26.
- Siçan kursoru/vurğu `HIGHLIGHT_JS`-dəki kimi qalsın (screencast real kursoru göstərmir – mövcud saxta kursor görünməlidir; yoxla).
- Başdakı login/hazırlıq hissəsi videoya düşməsin (indiki `t_start` məntiqi).

### 3.3 Tətbiq
- Çıxış: `frontend/public/guide/{role}/NN-ad.mp4`; köhnə `.webm` fayllarını sil. Bələdçi səhifəsi (`frontend/src/guideData.ts` / Guide komponenti) `.mp4` göstərsin,
  `<video controls preload="metadata">`, alt yazılar əvvəlki kimi (AZ/EN/RU, default istifadəçinin dili). Səs yalnız AZ-dır – RU/EN istifadəçidə alt yazı avtomatik açıq olsun.
- Yeni interfeys mətni olarsa – `t()` + i18n.ts AZ/EN/RU.
- VTT vaxtları yeni addım müddətləri ilə yazılsın.

## 4. Qəbul meyarları
1. `python scripts/guide_videos.py --check` – 14 ssenari, xəta yoxdur.
2. Tam yazı: 14 `.mp4`, hər birində **video 1920×1080 (telefon 780×1560) + audio axını**; ffmpeg ilə yoxla və cədvəl çap et: ad | ölçü | müddət | MB | səs var.
3. Hər videodan 1 kadr PNG (orta nöqtə) skretçpada – Rəhbər mətnin kəskinliyini gözlə yoxlayacaq. Yol: hesabatda tam yol.
4. Səs mətnləri ilə VTT AZ eyni vaxtdadır; səslər üst-üstə düşmür.
5. `cd frontend && npm run build` keçir; aid pytest (varsa guide testləri) keçir.
6. **Commit/push etmə** – Rəhbər review edib birləşdirir. Real şagird məlumatı yoxdur (demo baza).

## 5. Hesabat (qısa)
Dəyişən fayllar, cədvəl (§4.2), PNG yolları, build nəticəsi, problemlər (məs. TTS-in səhv oxuduğu sözlər – `say` ilə düzəldilənlər).

## 6. Əlavə (20.10.2026, istifadəçi: «добавь также для русского языка», tam icazə) – RU versiya
- Hər ssenari **iki dəfə** yazılır: **AZ** (AZ interfeys + `az-AZ-BanuNeural`) və **RU** (RU interfeys + `ru-RU-SvetlanaNeural`; kişi – `ru-RU-DmitryNeural`).
- Fayllar: `NN-ad.az.mp4` və `NN-ad.ru.mp4` (köhnə `NN-ad.webm`/`NN-ad.mp4` silinir). Alt yazılar: `NN-ad.az.vtt` (AZ video vaxtı ilə), `NN-ad.ru.vtt` (RU video vaxtı ilə),
  `NN-ad.en.vtt` – **AZ video** vaxtı ilə (EN istifadəçi AZ videoya EN alt yazı ilə baxır). Vaxtlar fərqlidir (səs uzunluğu fərqli) – hər videonun VTT-si öz yazısından.
- RU interfeys: girişdən sonra istifadəçi dilini RU et (tətbiqdəki mövcud yol: `auth.setLang` → serverdəki dil endpointi; girişsiz ekranlar üçün `localStorage['mk-lang']='ru'`
  init script ilə). Selektorlar AZ mətnə bağlıdırsa (`button:has-text("Şagird")`) – RU yazı üçün addımda `sel_ru` sahəsi və ya mətnsiz selektor (class/href/data-*).
  `--check` hər iki dil üçün keçməlidir.
- Səs mətni: RU – `cap.ru` (və ya `say_ru`); AZ – `cap.az` / `say`.
- CLI: `--langs az,ru` (default hər ikisi), `--voice-az banu|babek`, `--voice-ru svetlana|dmitry`.
- Bələdçi səhifəsi: istifadəçi dili `ru` → `.ru.mp4` + RU alt yazı; `az` → `.az.mp4`; `en` → `.az.mp4` + EN alt yazı (default açıq).
  Video yolunu seçən kiçik funksiya `guideVideoSrc(role, id, lang)` – `frontend/src/guideData.ts`-də export et (giriş pəncərəsi kartı onu istifadə edəcək).
- Qəbul: 28 mp4 (14×2), hər birində audio; cədvəldə dil sütunu; hər dildən ən azı 3 orta kadr PNG (RU kadrda interfeys rusca olmalıdır).
