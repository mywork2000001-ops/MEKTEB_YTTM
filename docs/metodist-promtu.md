# Müəllim köməkçisi – metodist baxışı ilə tam funksional audit və icra promtu

**Rol:** Sən riyaziyyat üzrə təcrübəli metodist, məktəb direktor müavini (tədris işləri) və məhsul mühəndisisən.
Tətbiqi müəllimin real iş gününə (dərsə hazırlıq → dərs → qiymətləndirmə → əks əlaqə → hesabat) və şagirdin öyrənmə
yoluna (plan → dərs → ev tapşırığı → test → səhv üzərində iş → irəliləyiş) uyğunlaşdır. Hər bəndi **icra et, testlə, brauzerdə yoxla**.
Sabit qaydalar `docs/audit-promtu.md`-dəki kimidir (məxfilik, qiymət düsturları, BSQ tarixləri, rəsmi plan dəyişmir və s.).

## A. Dərsə hazırlıq (müəllim)
1. Jurnalda dərs kartı: mövzu + **məzmun standartları** + resurslar + plandakı tapşırıq nömrələri (sinifdə / ev / müstəqil).
2. **Ev tapşırığı plandan bir kliklə** (plandakı «E» aralığı); müəllim dəyişə bilər.
3. Geriləmə görünür (işçi plan sürüşməsi), «Mövzunu saxla» bir kliklə; ilin sonuna sığmayan dərslər xəbərdarlığı.

## B. Dərs zamanı
4. Davamiyyət bir toxunuşla (hamı var → istisnalar), qiymət: şifahi/yazılı/test (düzgün sayı → faiz → qiymət avtomatik).
5. Ev tapşırığının yoxlanması: etdi/qismən/etmədi/köçürüb → tapşırıq icrası faizi.
6. Oflayn: internet kəsiləndə jurnal yazısı növbəyə düşür, bərpa olanda göndərilir.

## C. Qiymətləndirmə və əks əlaqə
7. KSQ/BSQ: tapşırıq üzrə ✓/✗ → tapşırıq və **standart təhlili**; zəif standartlar (<50%) ayrıca siyahı – təkrar üçün tövsiyə.
8. Yarımil qiyməti = (KSQ ortası)×0,4 + BSQ×0,6 – şagird və müəllim eyni rəqəmi görür.
9. Onlayn test: vaxtlı, avtomatik yoxlanır; sual üzrə həll faizi; səhvlər şagirdin «Səhvlərim» bölməsinə düşür (izahla).

## D. Differensial yanaşma
10. Güclü / orta / zəif – nəticələrə görə avtomatik; **tapşırıq və materialı səviyyə qrupuna** (məs. yalnız zəiflərə) göndərmək.
11. Fərdi iş planı və valideynlə əlaqə jurnalı – risk qrupundakı şagird üçün.
12. Risk: izahlı amillər (IX balı, formativ orta, KSQ, davamiyyət, ev tapşırığı); 25%+ buraxma xəbərdarlığı.

## E. Şagirdin öyrənmə yolu (portal)
13. Bu gün: motivasiya + şəxsi qeyd, imtahan sayğacı, günün dərsləri və ev tapşırığı, açıq tapşırıqlar.
14. Materiallar: PDF tapşırıq (cavab – dəftərin şəkli), video dərs (YouTube içəridə), link.
15. Nəticələrim: KSQ/BSQ, yarımil, onlayn testlər, səhvlərim, nailiyyətlər; Analitika: özü vs sinif ortası (adsız).

## F. Məlumat və idarəetmə
16. **IX sinif buraxılış balları** – sinif üzrə cədvəldə toplu redaktə/əlavə.
17. Şagirdin **özünü qeydiyyatdan keçirmə linki** (müəllim yaradır, müddət/say limiti; kod + PIN avtomatik).
18. Ehtiyat nüsxə (JSON ixrac) – pulsuz baza 30 gün riski; audit jurnalı.
19. Təhlükəsizlik başlıqları, zəif parol xəbərdarlığı, çıxışda oflayn keşin silinməsi.

## G. Hesabat (direktor, metodbirlik)
20. Sinif hesabatı A4 ağ-qara, Excel; şagird üzrə fərdi hesabat (çap).

## Qəbul meyarları
- Bütün testlər keçir; yeni funksiyalar testlidir; telefon (≈393 px) və noutbukda üfüqi sürüşmə yoxdur.
- İstehsalda (Render) sağlamlıq 200; test bazası xətasız sinxronlaşır; planlar və şagirdlər yüklənib.
