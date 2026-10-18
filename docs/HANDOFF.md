# HANDOFF — Claude ↔ Qwen iş jurnalı

Hər tapşırığın əvvəlində və sonunda bir sətir əlavə edin (yenisi aşağıda):
`[YYYY-MM-DD HH:MM] CLAUDE|QWEN — başladı/bitirdi: <tapşırıq>; budaq: <branch>; fayllar: <siyahı>; yoxlanmalı: <...>`

Qaydalar: CLAUDE.md (QWEN.md – docs/arxiv/, 18.10.2026-dan istifadə olunmur). Eyni faylı eyni vaxtda iki agent dəyişmir.

---

[2026-10-14 21:20] CLAUDE — bitirdi: Qwen Code quraşdırıldı, QWEN.md + bu jurnal yaradıldı, Qwen worktree `..\mk-qwen`; budaq: main
[2026-10-14 23:00] CLAUDE — bitirdi: agent sistemi (docs/agent-sistemi-promtu.md, docs/tasks/_shablon.md, claude-ds pro|flash|gemini|check|qwen). Pro limiti həftə sonuna qədər qənaətlə – yeni işlər kartla icraçılara.
[2026-10-14 21:20] CLAUDE — açıq işlər (yaddaşdan): Programs.tsx hələ yalnız AZ (EN/RU lazımdır); köçürmə şübhəsi (retake) canlı sınanmayıb; XI peşə KSQ-1 (P013) qərar gözləyir.
[2026-10-15] CLAUDE — bitirdi: əlavə KSQ/BSQ, onlayn+yazılı nəticə yanaşı (seçim), cavab kartı, bank ünvanı + apelyasiya (docs/tasks/ksq-bsq-elave-ve-iki-netice.md); main dcf72d1, Render deploy success; açıq: şagird vərəqində altmövzu adı, bankda needs_review nişanı, bank sualına keçid
[2026-10-15] CLAUDE — bitirdi: açıq 3 məsələ (3db8975) + audit apelyasiya (docs/tasks/audit-apelyasiya-sual-altmovzu.md, aeb6151): şagird kartında altmövzu adı, texniki kod şagirdə getmir; deploy success. Qərar gözləyir: altmövzu adının RU/EN tərcüməsi (BankFile.label – miqrasiya lazım), onlayn ekranda slot №-si; bank bölməsi yalnız admin üçün
[2026-10-18] CLAUDE — bitirdi: açıq qərarlar (docs/tasks/acik-qerarlar-18-10.md): altmövzu adı RU/EN (app/bank_labels.json, 439 ad, miqrasiyasız), Programs.tsx AZ/EN/RU; slot № – dəyişiklik yox; Drive qovluğu məhdudlaşdırıldı. Gözləyir: backup sirləri (istifadəçi girişi), XI peşə KSQ-1 = 18 sual qərarı canlıda yoxlanmalı
[2026-10-19] CLAUDE — bitirdi: struktur təmizliyi (a8ba1a4: QWEN/OpenRouter sənədləri docs/arxiv/, 3 worktree + 7 birləşmiş budaq silindi, Dim 2025 PDF → ../Mənbələr) + müəllim interfeysi (1f001a7, kart docs/muellim-dizayn-promtu.md, kodcu): ~1670 lüğət açarı (RU/EN-də dil qarışığı yox), qruplu menyu, Jurnal/Analitika-da sinif chip-ləri + son sinif yadda, kartda «Siz», alçaq ekran sıxlığı. Açıq: RU/EN tərcümələr skriptlə – canlıda RU rejimində gözlə yoxlamaq (yarımçıq cümlə parçaları ola bilər, məs. «Qrupa əlavə et (»).
