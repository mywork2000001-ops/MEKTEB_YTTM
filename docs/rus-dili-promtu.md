# Rus dili: şagird və müəllim tətbiqində tam tərcümə — audit və icra promtu

**Səbəb (12.10.2026):** rusdilli şagird (Fatimə) tapşırıqları başa düşmür; viktorinada DİM 9 (P007) sualları dil düyməsi ilə
rus dilinə keçmirdi. **Mövcud tərcüməçi:** `frontend/src/i18n.ts` (AZ / EN / RU, açar — Azərbaycan mətni, `useT()`),
istifadəçinin dili `User.language` (Tənzimləmələr). **Qayda:** yeni tərcüməçi yazılmır — mövcud lüğət genişləndirilir.

## 0. Audit
| № | Tapıntı | Təsiri | Qərar |
|---|---|---|---|
| 1 | Viktorina: P007-nin 5 bölməsində (`{az:{q,opts},ru:{…}}` formatı) sual idxal dilinə «donurdu» — 398 sual | Şagirdin dil düyməsi sualı tərcümə etmirdi | ✅ `normalizeQRaw` bütün dilləri saxlayır, həll (`sol`) də (viktorina b4589ad1) |
| 2 | Müəllim köməkçisi: sual mətni həmişə AZ (`ml = x.az \|\| x.ru …`) — 6 faylda | Rusdilli şagird testi AZ görürdü | ✅ ümumi `ml()` istifadəçinin dilində (`i18n.ts`, `setCurrentLang`) |
| 3 | Bank sinxronizasiyası yalnız mənbə faylı dəyişəndə yenidən oxuyur | Viktorina düzəlişi bazaya çatmırdı | ✅ viktorina dəyişəndə bütün fayllar yenidən oxunur |
| 4 | Verilmiş testlərin sual surətləri köhnə (yalnız AZ) | Açıq testlər rusca görünmür | ✅ `fill_task_translations` — eyni sualın tərcümələri surətə əlavə olunur (açar toxunulmur) |
| 5 | Lüğət ~100 ifadə; şagird səhifələrində ~230, müəllim səhifələrində ~3000+ sətir `t()`-siz | İnterfeys AZ qalır | Şagird — tam (mərhələ 1–2); müəllim — menyu və əsas ekranlar (mərhələ 3), qalanı tədricən |
| 6 | Server mesajları (xəta, status) AZ | Şagird xəta mətnini başa düşmür | Status sözləri lüğətdə; portal xətaları — `Accept-Language`-ə görə (mərhələ 4) |
| 7 | Rəsmi sənədlər (jurnal, plan, çap) | Qanunla AZ | Dəyişmir |

## 1. Mərhələlər
1. ✅ Test həlli ekranı (`student/Tasks.tsx`) + sual mətni + bank/viktorina düzəlişi — bc64cb8.
2. Şagirdin qalan səhifələri: Bu gün, Nəticələrim, Plan, Dərs, Materiallar, Bildirişlər, Uğurlarım, Əlavə məşğələ, Sorğular, Analitika.
3. Müəllim: menyu, Bu gün, Jurnal, Testlər və sınaqlar, Siniflər (ən çox istifadə olunanlar).
4. Server: portal xəta mesajları rus/ingilis dilində (`Accept-Language`).
5. Yoxlama: hər səhifədə RU rejimində Azərbaycan hərfləri (ə, ğ, ı, ş, ç, ö, ü) qalmamalıdır — avtomatik brauzer testi
   (`scripts/check-ru.cjs`: şagird kimi giriş, dil = ru, bütün səhifələr, sual mətnləri xaric).
