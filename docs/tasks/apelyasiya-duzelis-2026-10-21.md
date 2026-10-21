# Kart: apelyasiyanın içindən cavabı düzəltmək (21.10.2026)

**Sifarişçi:** müəllim: «apelyasiyanın içindən lazım gəldikdə cavabı düzəltmək mümkün olsun».
**Rəhbər:** Claude (Opus) · **İcraçı:** `kodcu` (worktree) · **Qaydalar:** CLAUDE.md – AZ/EN/RU (`tt()`/`t()`, `i18n.ts` yalnız Grep);
şagirdə görünən server mesajları EN/RU ilə (`_L`); `npm run build` + aid pytest.

## Vəziyyət
Apelyasiya pəncərəsi (`frontend/src/pages/teacher/Exams.tsx::Appeals`, API `backend/app/api/exam_appeals.py`) yalnız «qəbul / hamıya tətbiq /
rədd» verir; «hamıya tətbiq» bank sualını `needs_review` edir, açarı DƏYİŞMİR. Düzəliş üçün hazır alətlər BAŞQA yerlərdədir:
- açar: `PUT /api/exams/{ta}/{exam}/variants/{student}/{slot}` (`edit_question`, `all_same` – eyni bank sualı olan bütün variantlar,
  `_rescore` + jurnal, `ksq_base.note_edit`);
- şagirdin oxunmuş cavabı (skan səhv oxuyub): `PUT /api/exam-scans/{scan_id}/slot` (`fix_slot`);
- sualı ləğv: `POST /api/exams/{ta}/{exam}/slots/{slot}/annul`;
- bank: `POST /api/bank/questions/{qid}/reviewed`.

## Tələb – apelyasiya kartında 3 düzəliş (hər apelyasiya üçün, açıq və ya qərar verilmiş)
1. **«✏️ Açarı düzəlt»** – sual MCQ-dirsə variant düymələri (A–E), açıqdırsa cavab sahəsi; işarə «Bu sualı alan hamıda» (defolt AÇIQ,
   = `all_same`) və «Bankda da düzəlt» (defolt AÇIQ). Saxla → `edit_question` (mövcud) → bank işarəsi seçilibsə bank sualının açarı
   (`BankQuestion.correct` / `answer`) da yenilənir və `needs_review=False` (yeni kiçik backend köməkçi; audit). Nəticə: «N şagirdin balı
   yenidən hesablandı», jurnal yenilənir (mövcud `_rescore`).
2. **«🔍 Şagirdin cavabını düzəlt»** (skan səhv oxuyubsa; `scan_id` varsa görünür) – dəyər sahəsi (MCQ – hərf) → `fix_slot`; skan kəsiyi
   (crop) yanında göstərilir.
3. **«⛔ Sualı ləğv et»** – təsdiqlə (window.confirm qadağandır – inline təsdiq düyməsi) → `annul_slot`.
Hər düzəlişdən sonra apelyasiya avtomatik **qəbul** olunur (`decision='accept'`, `apply_all` – açar düzəlişində «hamıda» seçilibsə) və
şagirdə hazır cavab mətni təklif olunur (redaktə oluna bilər): açar – «Açar səhv idi, düzəldildi – balınız yenidən hesablandı»;
oxunuş – «Kartınız səhv oxunmuşdu, düzəldildi»; ləğv – «Sual ləğv edildi, bal yenidən hesablandı» (AZ/EN/RU, şagirdin dilində).
Pəncərədə bal fərqi göstərilir (köhnə → yeni), sonra siyahı yenilənir. Əl ilə qiymət qoyulmuş şagirdlər (`manual_students`) – xəbərdarlıq.

## Backend (minimal)
- `exam_appeals.py`: `POST /{ta}/{exam}/{appeal_id}/fix` body `{kind: 'key'|'reading'|'annul', correct?, answer?, value?, all_same=True,
  bank=True, reply?}` – mövcud funksiyaları çağırır (kod təkrarı yox: endpoint funksiyalarını birbaşa çağırmaq əvəzinə məntiqi kiçik
  köməkçilərə çıxar), sonra `decide` məntiqi (qəbul) – BİR tranzaksiya, BİR audit sətri. Başqa müəllim – 404.
- Bank yeniləməsi: yalnız `a.bank_id` varsa; açar formatı bank sualının tipinə uyğun (MCQ – indeks).

## Testlər – `tests/test_exam_appeal.py`-ə əlavə
açar düzəlişi (all_same → başqa variantdakı şagirdin balı da dəyişir; bank açarı yeniləndi, needs_review False), oxunuş düzəlişi (yalnız
o şagird), ləğv, avtomatik qəbul + cavab, başqa müəllim 404, dil (EN/RU mesaj). Aid + tam pytest, `npm run build`.
