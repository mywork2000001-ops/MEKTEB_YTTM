# Kart: imtahanda «Təhvil ver» təsadüfən basılmasın (21.10.2026)

**Sifarişçi:** müəllim: «imtahanlarda «Təhvil ver» «Növbəti»-nin yanındadır, şagirdlər təsadüfən basır».
**İcra:** Rəhbər (kiçik dəyişiklik) · `frontend/src/pages/student/Tasks.tsx` (Runner) · AZ/EN/RU.

## Səbəb
Telefonda alt yapışqan panel (`.exam-nav`) üç bərabər düymə: «‹ Əvvəlki» · «Növbəti ›» · «Təhvil ver» – eyni rəng (primary), yan-yana;
barmaq «Növbəti» əvəzinə «Təhvil ver»-ə düşür və test dərhal, təsdiqsiz təhvil verilir.

## Həll
1. Alt panel yalnız naviqasiya: «‹ Əvvəlki» · «Növbəti ›»; son sualda «Növbəti» əvəzinə **«Yoxla və bitir ›»** (təhvil VERMİR – yoxlama
   pəncərəsini açır).
2. **«Testi bitir»** düyməsi yuxarı paneldə (taymerin yanında, kiçik, `danger` görünüşü) – barmaq zonasından uzaq.
3. Hər iki düymə **yoxlama pəncərəsi** açır (window.confirm yox – tam ekran rejimini pozur): cavablanmış X / Y, cavabsız sualların
   nömrələri (toxunanda o suala keçir), «Testə qayıt» (əsas düymə) və «Bəli, təhvil ver» (danger; pəncərə açılandan 1 san. sonra aktiv).
4. Vaxt bitəndə avtomatik təhvil – əvvəlki kimi, təsdiqsiz.
