# Müəllim köməkçisi – tam audit və təkmilləşdirmə promtu

**Rol:** Sən bu tətbiqin baş mühəndisi, təhlükəsizlik auditoru və UX redaktorusan. Məqsəd – tətbiqi real məktəbdə
(müəllim, admin, 75+ şagird, telefon/planşet/noutbuk) gündəlik, etibarlı, məxfi və pulsuz hostinqdə işlədən məhsula çevirmək.
Hər tapıntını **düzəlt, testlə yoxla, brauzerdə bax, commit et**. Heç bir tapıntını “sonra” saxlama, əgər istifadəçinin
qərarı tələb olunmursa. Qərar tələb edənləri ayrıca siyahıda sual kimi yaz.

**Sabit qaydalar (istifadəçinin qərarları – pozma):** filtrli ekranlarda seçim edilənə qədər aşağı hissə boş; bütün redaktə
Tənzimləmələrdə; silmə = arxiv (adı yazaraq təsdiq); tam məxfilik (heç kim, admin də, başqasının yazışmasını görmür; müəllim
yalnız «!» bildirilən mesajı görür); KSQ/BSQ bal→%→qiymət 0–30→2, 31–60→3, 61–80→4, 81–100→5; yarımil = (KSQ ortası)×0,4 + BSQ×0,6,
adi yuvarlaqlaşdırma; BSQ-1 – yarımilin son dərs günü (26.01-ə qədər), BSQ-2 – 14.06-ya qədər; rəsmi plan dəyişmir;
Uşaq İD/pinkod/şəxsiyyət vəsiqəsi saxlanmır; X e = UTİS «10 e»; XI a – TOM, XI peşə – adi, öz zəngi (08:00); müəllim girişi ID ilə
(M-001), şagird – giriş kodu + 4 rəqəmli PIN; interfeys AZ/EN/RU, rəsmi sənəd AZ; çap A4 portret ağ-qara; Render gecə 23:00–05:00 oyadılmır.

## 1. Doğruluq və tarix/vaxt
- [ ] Server UTC-dədir: «bu gün», jurnalda «gələcək dərs» yoxlaması, portalda gün, həftəlik cədvəl – **Asia/Baku** üzrə hesablansın; tzdata quraşdırılsın.
- [ ] Onlayn tapşırıq vaxtları: brauzerdə daxil edilən yerli vaxt → UTC, göstərəndə yerli vaxt; server taymeri əsasdır.
- [ ] Yarımil sərhədləri, bayramlar, BSQ tarixləri bazadan (tədris ili) – sabit kod yox.
- [ ] Qiymət/faiz hesabı hər yerdə eyni funksiya ilə (server) – interfeysdəki ilkin göstəriş eyni qaydaya uyğun.

## 2. Təhlükəsizlik və məxfilik
- [ ] HTTP başlıqları: Content-Security-Policy, X-Frame-Options/frame-ancestors, X-Content-Type-Options, Referrer-Policy, HSTS.
- [ ] Zəif parol xəbərdarlığı (admin/müəllim < 8 simvol) və ilk girişdən sonra dəyişmə tövsiyəsi.
- [ ] Giriş limiti: hesab üzrə kilid var; IP üzrə sürət limiti (PIN təxmininin qarşısı).
- [ ] Fayl endirmə: yalnız icazəli istifadəçi; nosniff; icazəli növlər.
- [ ] Çıxışda brauzer keşindəki (oflayn) məlumatlar silinsin – ortaq cihazda məxfilik.
- [ ] Audit jurnalı: bütün redaktələr; mesaj məzmunu yox.

## 3. Məlumatların qorunması (pulsuz hostinq riski)
- [ ] Render pulsuz PostgreSQL 30 gün sonra silinir → admin üçün **ehtiyat nüsxə (JSON ixrac)** və geri yükləmə; Neon-a köçmə təlimatı.
- [ ] Çat/material faylları bazada (silinmir); həcm limiti və xəbərdarlıq; Google Drive rejimi hazır.

## 4. Funksional çatışmazlıqlar (istifadəçi istəkləri)
- [ ] **Şagirdlərin IX sinif buraxılış ballarının** toplu redaktəsi və əlavə edilməsi (cədvəl şəklində, sinif üzrə).
- [ ] **Oflayn iş rejimi:** interfeys oflayn açılır; son baxılan məlumatlar (jurnal günü, plan, cədvəl, portal) oflayn görünür;
      oflayn yazılan jurnal qeydləri növbəyə düşür və internet gələndə avtomatik göndərilir; «oflayn» nişanı.
- [ ] **Şagird özünü qeydiyyatdan keçirmə linki:** müəllim sinif üçün link yaradır (müddət, say limiti, bağlamaq);
      şagird ad + doğum tarixi yazır → təkrar yoxlanılır → giriş kodu və PIN avtomatik verilir; müəllim yeni qeydiyyatları görür.
- [ ] Materiallar (PDF tapşırıq, video dərs, link) – hazırdır; yeni material/tapşırıq üçün şagirddə «yeni» nişanı.

## 5. İnterfeys və mobil
- [ ] Redmi Note 15 (≈393 px) və planşetdə bütün ekranlar: üfüqi sürüşmə yox, toxunma hədəfləri ≥ 40 px, cədvəllər kartlara çevrilir.
- [ ] Boş vəziyyətlər izahlı (plan yüklənməyib → harada yükləmək olar).
- [ ] Qaranlıq rejim və 6 rəng çaları bütün yeni ekranlarda.

## 6. Performans və etibarlılıq
- [ ] Test bazası sinxronizasiyası 512 MB RAM-da (Render) – brauzer yalnız dəyişiklik olanda; nəticə status səhifəsində.
- [ ] Soyuq açılış: sağlamlıq yoxlaması, oyaq saxlama 05:00–23:00.

## 7. Yoxlama
- [ ] Bütün backend testləri; yeni funksiyalar üçün testlər; brauzerdə (noutbuk + telefon ölçüsü) əsas axınlar; istehsalda sağlamlıq.
- [ ] Hər mərhələ ayrıca commit; hesabat istifadəçiyə qısa, Azərbaycan dilində.

## Sual kimi saxlananlar (istifadəçi qərarı)
- XI a buraxılış imtahanının dəqiq tarixi (şagird sayğacı üçün).
- Google Drive üçün OAuth açarı (2 GB fayllar).
- Neon hesabı (Render bazası 30 gün sonra silinməzdən əvvəl).
