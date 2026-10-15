# Audit: apelyasiya – konkret sual və şagirdin gördüyü altmövzu
- Tarix: 2026-10-15   Müəllif: Rəhbər (Claude)
- İcraçı: kodcu (audit + aşkar xətaların düzəlişi), budaq `qwen/audit-apelyasiya`
- Əsas: main `3db8975` (kart: docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 3–4 + açıq 3 məsələ)

## Məqsəd (müəllimin dili ilə)
Şagird apelyasiya verəndə **konkret bir sual** (öz variantındakı slot) müəllimə getsin. Nəticə göndəriləndən sonra şagird
cavab kartında həmin sualın **hansı altmövzudan** olduğunu görsün. Müəllim apelyasiyada eyni sualı, eyni altmövzunu və bankdakı №-ni görsün –
heç bir axtarış lazım olmasın.

## Yoxlanacaq zəncir (hər bənd: PASS / FAIL + sübut `fayl:sətir` və ya test adı)
### A. Sualın kimliyi (identity)
1. Apelyasiya `(exam_id, student_id, slot, source)` ilə yazılır; `slot` şagirdin **öz variantındakı** sualdır (`ExamVariant.questions[slot]`), başqa şagirdin eyni nömrəli sualı deyil.
2. Onlayn KSQ-də suallar `shuffle` ilə qarışdırılırsa – şagirdin ekranındakı sıra ilə `slot` uyğunluğu düzgündürmü? (kartda göstərilən № → apelyasiyaya gedən slot → müəllimdə görünən sual eyni olmalıdır).
3. Kağız mənbədə `ExamScan.reading/marks` slot indeksləri variantın slotları ilə eynidir; `lost`/`unprinted`/ləğv olunmuş slota apelyasiya verilmir.
4. `bank_id` və `bank_ref` apelyasiyada **variantın dondurulmuş surətindən** götürülür (bankdan yox); bank sonradan dəyişsə də apelyasiyada köhnə ünvan qalır.
5. Şablon (`template`) sualları: `bank_id` yoxdursa ünvan necə göstərilir, «hamıya tətbiq et» bu suallarda nə edir (səhv şagirdlərə tətbiq olunmamalıdır).

### B. Şagirdin gördüyü
6. Nəşrdən **əvvəl**: heç bir portal endpoint-i (kartım, bildiriş, nəticələr, onlayn test, çap vərəqi) altmövzu adını, `ref`-i, düz cavabı, ✓/✗ qaytarmır.
7. Nəşrdən **sonra**: cavab kartında hər sualın yanında **altmövzu adı** görünür (AZ/RU/EN – `ml()` və ya lüğət); texniki kod (`B6965`, file_id) şagirdə göstərilmir – yalnız müəllimə.
8. Apelyasiya formasında şagird hansı suala apelyasiya verdiyini görür: № + qısa sual mətni + altmövzu; göndərəndən sonra status (gözləyir/qəbul/rədd) və müəllimin cavabı.
9. Şagird yalnız öz kartını/apelyasiyasını görür (başqa şagird, başqa sinif – 403); müddət bitəndə 400; təkrar 409 – mesajlar şagirdin dilində.

### C. Müəllimin gördüyü
10. Apelyasiya panelində: şagird, № (şagirdin gördüyü nömrə ilə eyni), sual mətni/şəkil, şagirdin cavabı, açar, **altmövzu · №n**, «Bankda aç» (admin), kağızdırsa skan kəsiyi.
11. Qəbul → yalnız həmin slot düzəlir, bal yenidən hesablanır, «əl ilə» bal qorunur; «hamıya tətbiq et» yalnız eyni `bank_id` + eyni cavab; rədd əvvəlki düzəlişi geri alır; hamısı audit-də.
12. Yenidən skan / «Yenilə» / onlayn təkrar göndəriş qəbul olunmuş apelyasiyanın düzəlişini silmir.

### D. Kənar hallar
13. Əlavə KSQ/BSQ (extra_seq > 0) – apelyasiya və kart orada da işləyir, əsas imtahanla qarışmır.
14. Eyni şagirdin həm onlayn, həm kağız nəticəsi var – apelyasiya düzgün mənbəyə gedir, kartda iki mənbə ayrıca göstərilir.
15. Köhnə variantlar (ref dondurulmadan əvvəl yaradılmış) – ünvan oxuyanda hesablanır, xəta vermir.
16. i18n: yeni mətnlərin hamısı `i18n.ts`-də AZ/EN/RU; RU/EN-də AZ sözü qalmayıb.

## İcra qaydası
- Əvvəl **yalnız oxu və test yaz**: hər bənd üçün mövcud testi göstər və ya yeni test yaz (`backend/tests/test_audit_appeal.py`).
- FAIL olan bəndlər: kiçik və aşkar xətanı düzəlt (ayrıca commit, «Audit düzəlişi: …»); dizayn qərarı tələb edənləri **düzəltmə** – hesabatda «Qərar lazımdır» kimi yaz.
- Canlı DB-yə (Neon) qoşulma, push etmə. Miqrasiya lazım olsa – etmə, hesabatda yaz.
- Yoxlama: aid pytest + `npm run build`.

## Hesabat formatı
Cədvəl: № | bənd | PASS/FAIL/DÜZƏLDİ | sübut. Sonra: commit-lər, test/build son sətirləri, «Qərar lazımdır» siyahısı.
