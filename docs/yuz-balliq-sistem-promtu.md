# 100 ballıq qiymətləndirmə – çətinlik və sual növünə görə bal (promt)

**İstək (12.10.2026):** testin balı cəmi 100 olsun; qapalı və açıq suallar çətinlik səviyyəsinə görə bal alsın; icra zamanı
(test həll olunarkən) nəzərə alınsın. **Harada:** hər ikisi – Müəllim köməkçisi testləri və viktorina saytı.
**Çətinlik:** avtomatik + müəllim dəyişə bilər (istifadəçi seçimi).

## Qayda
- Sualın çəkisi = **növ × çətinlik**: qapalı (variantlı) ×1, açıq ×1,5; asan ×1, orta ×1,5, çətin ×2.
- Bal = 100 × çəki ÷ cəmi çəki, **0,5-ə yuvarlaq**, cəmi dəqiq 100 (fərq ən böyük bala əlavə olunur).
- Çətinlik mənbəyi (prioritet): **müəllim** (test yaradanda seçir) → **statistika** (≥10 cavab: >70% düz – asan, 40–70% – orta,
  <40% – çətin; gecə yenilənir) → **növ** (qapalı – asan, açıq – orta).
- Ballar test yaradılanda **dondurulur** (sualın surətində) – sonradan statistika dəyişsə də verilmiş test dəyişmir (ədalət).
  Köhnə testlər (bal yoxdur) – bərabər bal (əvvəlki faizlə eyni).
- Nəticə = toplanan bal (0–100) = faiz; qiymət (2–5) buna görə. Sınaqda cərimə: hər səhv öz balının 1/N-i qədər çıxır.
- İcra zamanı: şagird hər sualın balını görür («Sual 3 / 20 · 6,5 bal»), nəticə «72,5 / 100 bal».

## Müəllim köməkçisi
- [ ] `app/domain/scoring.py`: çəki, bal paylanması; `OnlineTask` yaradılanda avtomatik (event), sual dəyişəndə yenidən.
- [ ] `TaskAttempt.points` (0–100) – bütün faiz hesabları (jurnal, reytinq, sertifikat, səviyyə, analitika, məşğələ) ondan.
- [ ] `BankQuestion.diff_auto / stat_n / stat_ok` – gecəlik statistika işi.
- [ ] UI: test yaradanda hər sualda çətinlik (Avto / Asan / Orta / Çətin) və bal önbaxışı, cəmi 100; şagird həll ekranında bal.

## Viktorina saytı (ayrıca repo – hub-educat-on / EduHub)
- [ ] Eyni qayda `viktorina.html` (müştəri) və `lib/viktorina/grade.ts` (server) – iki yerdə + paritet skripti; sertifikat faizi bala görə.
- [ ] Çətinlik: viktorina bazasında statistika yoxdursa – növə görə; müəllim linki yaradanda dəyişə bilər.
- [ ] Repo qaydaları: `check-tests.cjs`, `check-viktorina-import.cjs`, `viktorina-grade-parity.ts`.
