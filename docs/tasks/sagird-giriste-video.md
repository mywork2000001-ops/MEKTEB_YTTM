# Tapşırıq kartı: şagird girişdə istifadə videosunu görsün

**Tarix:** 20.10.2026 · **Sifarişçi:** müəllim («ученик должен при входе видеть видео про пользование») · **Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree)
**Asılılıq:** videolar `.mp4` + AZ səs (kart `video-sesli-ve-keyfiyyetli.md`, paralel icrada). Bu kart yalnız yolları istifadə edir:
`guideVideoSrc(role, id, lang)` (`frontend/src/guideData.ts`, digər kodcu yaradır; hələ yoxdursa eyni imza ilə müvəqqəti yerli funksiya: ru → `/guide/student/NN-ad.ru.mp4`, az/en → `.az.mp4`), alt yazılar `…/NN-ad.{az,en,ru}.vtt`. Fayllara və `guide_videos.py`-ə **toxunma**.

## 1. İndiki vəziyyət
`frontend/src/GuideCard.tsx` – şagirdin «Bu gün» səhifəsində (`pages/student/Today.tsx`) kiçik banner «Videoya bax / Bağla»; «görüldü» yalnız
`localStorage`-da → başqa telefonda/brauzerdə yenidən, təmizlənəndə yenidən, bəzən heç görünmür. Video özü açılmır – yalnız /guide-a keçid.

## 2. Rəhbərin qərarları
1. **İlk girişdə video pəncərəsi (modal)** – şagird portalına daxil olan kimi (istənilən səhifə, **test/sınaq icra ekranı istisna**) tam ekran pəncərə:
   başlıq «Tətbiqdən necə istifadə etməli», video, «Bütün videolar» (→ /guide), «Sonra bax», «Bağla».
2. **Hansı video:** ekran eni < 600px → `08-telefon`, əks halda `02-ana-sehife`. Alt yazı – şagirdin dili (AZ/EN/RU); EN/RU-da alt yazı default açıq.
3. **Avtomatik səsli oynatma brauzerdə bloklanır** – pəncərədə video `poster` (ilk kadr) + böyük ▶ düyməsi; basanda səsli oynayır. `preload="metadata"`.
4. **«Görüldü» serverdə**, hər şagird üçün bir dəfə, bütün cihazlarda: `users.guide_seen_version` (Integer, nullable) – **yeni miqrasiya, yalnız ADD COLUMN**,
   start-da avtomatik (layihədəki mövcud qayda ilə; tək head-i yoxla). Backend sabiti `GUIDE_VERSION = 1`; video yenilənəndə 2 edilir → şagirdlər yenisini bir dəfə görür.
   - `GET` şagird «me»/sessiya cavabına `guide_due: bool` (`guide_seen_version < GUIDE_VERSION` və ya NULL).
   - `POST /api/portal/guide-seen` → `guide_seen_version = GUIDE_VERSION`. Çağırılır: video sona çatanda **və ya** «Bağla»/«Bütün videolar» basılanda.
   - «Sonra bax» – serverə yazmır, yalnız bu sessiya üçün gizlədir (sessionStorage, try/catch); növbəti girişdə yenə çıxır. 3 dəfə «Sonra bax»-dan sonra
     (sayğac serverdə lazım deyil – localStorage kifayətdir) yalnız kiçik banner qalsın.
5. **Həmişə əlçatan:** şagirdin «Bu gün» səhifəsində kiçik düymə «🎬 Necə istifadə etməli» (eyni pəncərəni açır) – köhnə GuideCard banneri bununla əvəzlənir.
   Menyudakı «Bələdçi» qalır.
6. **Müəllim görür:** sinif üzvləri siyahısında (şagird sətrində) kiçik nişan «🎬 ✓» – video baxılıb (`guide_seen_version >= 1`); başlıq izahı t() ilə.
   Yalnız göstərici, filtr lazım deyil.
7. Müəllim/admin üçün avtomatik pəncərə **yoxdur** (yalnız şagird).

## 3. Mətnlər (hamısı `t()` + `frontend/src/i18n.ts`, AZ / EN / RU)
- «Tətbiqdən necə istifadə etməli» / How to use the app / Как пользоваться приложением
- «Bu qısa videoya bax – hər şey aydın olacaq.» / Watch this short video – everything will be clear. / Посмотри это короткое видео – всё станет понятно.
- «Bütün videolar» / All videos / Все видео · «Sonra bax» / Watch later / Посмотреть позже · «Bağla» – mövcuddursa təkrar açar yaratma
- «🎬 Necə istifadə etməli» / 🎬 How to use / 🎬 Как пользоваться · «Bələdçi videosuna baxıb» / Watched the guide video / Посмотрел(а) видео-инструкцию
- Lüğətdə təkrar açar build-i yıxır – əvvəl Grep et.

## 4. Testlər və yoxlama
- pytest (yeni fayl və ya aid faylda): yeni şagird → `guide_due=true`; `POST guide-seen` → `false`; `GUIDE_VERSION` artırılanda yenə `true`;
  müəllim üçün endpoint 403/heç nə; başqa şagirdin bayrağı dəyişmir. Miqrasiya tək head.
- `cd frontend && npm run build` keçir.
- Aid pytest + `tests/test_migrations*` (varsa) keçir.
- Commit et (worktree budağında), **push etmə** – Rəhbər review edib birləşdirir.

## 5. Hesabat
Dəyişən fayllar, miqrasiya id, test sayı, build, ekran şəkli yoxdur (Rəhbər özü baxacaq).
