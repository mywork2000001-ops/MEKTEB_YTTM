# Növbəti sessiya – promt (yazıldı 21.10.2026, gecə; kompüter söndürülür)

**Rol:** Claude Code – Rəhbər (CLAUDE.md, `~/.claude/CLAUDE.md`). Əvvəl: `docs/audit/icra-2026-10-21.md` «Açıq qalanlar», `git worktree list`,
HUB-da `docs/cloud/HANDOFF.md` son sətirləri və `docs/cloud/REESTR.md`. Hesab: əsas hesabın limiti 25.10 21:00 (Bakı) açılır; o vaxta qədər
2-ci hesab – onun limiti bulud sessiyaları ilə ortaqdır, qənaətlə işlə (aid pytest, `tail`, fayl hissə-hissə).

## P1 – birinci növbədə
1. **KSQ → onlayn sınaq** – ✅ hazırdır (5c64aa3, deploy). Yalnız canlıda gözlə yoxla: Jurnal → KSQ/BSQ → «🎯 Bu KSQ əsasında sınaq» → analoji suallar, NewExam doldurulur.
2. **Bulud PR-ları HUB #6–9** (standartlar XI, X 1.1/1.2/2.1): bulud TAPSIRIQLAR.md §1 ilə `index.html`-siz yeniləyəcək. Review: seçmə
   sual yoxlaması, `node "sinif testi/tools/build-catalog.cjs" --check`, `node scripts/hub-audit.cjs --live`, merge. Kataloq və IEN kartı özü yenilənir.
3. **Canlıda gözlə yoxlama (Chrome qoşulubsa):** apelyasiya pəncərəsi düzəlişləri (✏️/🔍/⛔), «Testi bitir» yoxlama pəncərəsi (telefon ölçüsü),
   dəftər yoxlaması (📓), inkişaf zənciri və tərəqqi qruplarında mövzular. Problem – ekran şəkli ilə kart.

## P2
4. Telegram hesabatı (21:00) gəlirmi – `gh run list --workflow tg-hesabat.yml` (HUB). Gəlmirsə – səbəb.
5. `sort_incoming.py` (test-sources) – GitHub-da ilk işə düşmə: `incoming/_hints.json` yenilənirmi, dublikatlar `_dup`-a gedirmi.
   İpucu keyfiyyəti zəifdirsə (sinif/növ səhv) – qaydaları düzəlt (mətnli PDF-lər; skanlar onsuz da bulud üçündür).
6. IEN auditi (`docs/IEN_AUDIT.md`): P002 Lesson-1/9 və V portalı situasiya şəkilləri – bulud `cloud/ien-images` PR-ı; review/merge.
7. Dəftər yoxlaması: PDF dəstəyi (PyMuPDF backend-də yoxdur – əlavə et və ya şəkil tələb et), real AI çağırışı canlıda.

## P3
8. Zəncir 26.01.2027-yə VIII əvvəlinə çatır – müəllimlə: tempi artırmaq (həftədə 4) və ya IX-u növbəti dövrə saxlamaq.
9. P0010 `_sources` qırıq geri-keçidləri; P014 məzmunu; `hub-audit --live`-ı həftəlik workflow-a.
10. Telegram PDF-ləri layihələrə paylama skriptinin genişləndirilməsi (mövzu topluları → P013/P007 kimi, sınaqlar → Sinaqlar).

## Qaydalar (dəyişməz)
AZ/EN/RU hər mətn; mövzu testi seçimi yalnız `app/plan_tests.py`; `npm run build` (tsc -b); canlı DB/silmə – istifadəçinin razılığı;
HUB dəyişikliyi → IEN sinxronizasiyası (yaddaş `ien-sync`); PDF→test – yalnız bulud; sessiya sonunda `docs/audit/icra-YYYY-MM-DD.md`.
