# PROMT · Qalan işlər (19.10.2026, axşam)

İstifadəçi: «оставшиеся работы – создай промт и выполняй поэтапно, даю все права».
Mənbə: docs/HANDOFF.md, docs/yazili-testler-master-promtu.md (addım 6–7), docs/tasks/acilan-bolmeler-dizayn.md, yaddaş qeydləri.

## Mərhələlər (hər biri: build/test → commit → HANDOFF sətri)
| № | İş | Kim | Vəziyyət |
|---|---|---|---|
| 1 | Açılan bölmələr dizaynı (kart acilan-bolmeler-dizayn.md): worktree `agent-a4872905…`-də yarımçıq iş – yoxla, `OwnNumbersReport.tsx` də `<Disclosure>`-a keçsin, `npm run build`, commit, main-ə birləşmə | Claude + kodcu | |
| 2 | Təmizlik: birləşmiş worktree `agent-a2b80c7…` və budaqlar silinir | Claude | |
| 3 | Aid pytest (paper_exams, own_numbers, ksq, scans) + `npm run build` main-də | Claude | |
| 4 | Push (`! git push origin main` – istifadəçi) → Render deploy statusu, `/api/health/db` | istifadəçi + Claude | |
| 5 | Master addım 6: canlıda «öz rəqəmləri» hesabatı XI-P KSQ və P013 XI üzrə (yalnız oxu, DB-yə yazı yox) | Claude | |
| 6 | Chrome: 1568×745, 900×700, 390×844 (pəncərə maksimal olmamalıdır) + RU rejimində mətnlər | Claude | |
| 7 | İstifadəçidən asılı: həftəlik backup sirləri (Google OAuth + Neon read-only), ~25.10 Neon saatları, 27.10 `exam_*_backup_20261013` silinməsi (yalnız razılıqla) | istifadəçi | gözləyir |

## Qaydalar
CLAUDE.md: AZ/EN/RU hər yeni mətn; yoxlama `npm run build`; canlı DB-yə yazı/silmə yalnız razılıqla; sirlər git-ə yox.
