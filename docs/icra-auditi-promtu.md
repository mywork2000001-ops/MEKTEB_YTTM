# Promt: işin icra auditi – hər iş paketinin sonunda (daimi qayda, 20.10.2026)

**Sifarişçi:** müəllim («bu, bütün gələcək işlər üçün qaydadır», 20.10.2026) · **İcraçı:** Rəhbər (Claude), sessiyanı bitirməzdən əvvəl.

## Məqsəd
İstifadəçi texniki adam deyil və işi özü yoxlaya bilmir. Ona görə hər sessiyanın (və ya böyük iş paketinin) sonunda **dürüst icra auditi**
yazılır: nə istənib, nə edilib, necə yoxlanıb, nə qalıb. «Hazırdır» yalnız sübutla deyilir.

## Rəhbərin qərarları
1. **Fayl:** `docs/audit/icra-YYYY-MM-DD.md` (bir gündə bir neçə sessiya – `-b`, `-c`). Qısa, cədvəlli, AZ dilində.
2. **Mənbə – istifadəçinin sözləri:** sessiyadakı hər istək ayrıca sətir (rus/azərbaycan dilində dediyi kimi qısa), heç biri itməsin –
   sessiya ortasında gələn əlavə istəklər də.
3. **Status yalnız bunlardan biri:** ✅ edildi və yoxlandı · 🟡 edildi, yoxlanmayıb (səbəbi) · ⏳ qismən · ❌ edilmədi (səbəbi) · 🔒 istifadəçinin
   addımı lazımdır (məs. `! git push`).
4. **Sübut sütunu (məcburi):** commit hash, test sayı (`N passed`), `npm run build` nəticəsi, deploy statusu, miqrasiya id-si,
   canlıda yoxlama (URL/ekran). Sübut yoxdursa – status 🟡-dan yuxarı ola bilməz.
5. **Dəyişməz yoxlamalar** (layihə CLAUDE.md): tam `pytest` (yalnız aid testlər kifayət deyil – sonda bir dəfə tam), `npm run build`,
   AZ/EN/RU (yeni mətnlər `t()`-dədir), miqrasiya yalnız əlavə (ADD COLUMN/TABLE), sirlər git-də yoxdur, worktree/budaqlar silinib.
6. **Canlı əməliyyatlar** (miqrasiya, toplu dəyişiklik, deploy): ayrıca bölmə – edilib/edilməyib, nə vaxt, geri qaytarma yolu.
7. **Açıq qalanlar** – növbəti sessiya üçün sıralı siyahı (P1/P2/P3) + kimin addımıdır (Rəhbər / istifadəçi).
8. **İstifadəçiyə yekun** – çatda 5–10 sətir sadə dildə (rus/AZ): nə hazırdır, nəyi özü etməlidir, nə qalıb.
9. **Davamlılıq:** HANDOFF.md-yə bir sətir + yaddaş (open-work) audit faylına keçidlə. Növbəti sessiya **əvvəlcə** son audit faylının
   «Açıq qalanlar» bölməsini oxuyur.

## Şablon
```
# İcra auditi – YYYY-MM-DD
| # | İstək (istifadəçi) | Status | Sübut | Qeyd |
## Yoxlamalar: pytest (tam) · build · i18n · miqrasiya · worktree
## Canlı əməliyyatlar
## Açıq qalanlar (P1/P2/P3, kim)
```
