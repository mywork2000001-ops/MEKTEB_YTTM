# Audit: şagird hissəsi (19.10.2026)

Əhatə: şagird portalı – backend `app/api/portal.py`, `auth.py` (giriş, QR, PIN), `invites.py` (qeydiyyat linki),
`materials.py`, `surveys.py`, `certificates.py` (şagird marşrutları); frontend `pages/student/*`, `Login.tsx`, `Join.tsx`, `QrLogin.tsx`.
Yanaşma: kodun oxunması (giriş hüquqları, məlumat sızması, vaxt/təhvil məntiqi, i18n), avtomatik i18n skanı (`t()/tt()` açarları lüğətdə – hamısı var).

## Yaxşı vəziyyətdə olanlar
- Hər şagird marşrutu `student_only` + `me_student`; tapşırıq/imtahan/apelyasiya/kart şəkli/fayl – yalnız özününkü (başqasınınkı 403/404).
- Testdə düz cavab və izah şagirdə göndərilmir (`_public_q`); cavablara baxış yalnız `show_answers` qaydası ilə.
- Taymer server vaxtı ilə; vaxt bitəndə serverdə avtomatik təhvil, 10 san. şəbəkə güzəşti; iki «Başla» yarışı (IntegrityError) düzgün.
- Sınaqda yer/sinif ortası yalnız test bağlanandan sonra; başqa şagirdin adı heç yerdə yoxdur.
- Sessiya kukisi httponly + samesite=lax; PIN dəyişəndə köhnə sessiya və QR etibarsız olur; hesab üzrə 5 səhv → 15 dəq. kilid.
- Sertifikat kodu 8 təsadüfi simvol – yoxlama səhifəsindən ad toplamaq praktik deyil.
- Uvicorn `--proxy-headers` ilə – IP limitləri real IP üzrə işləyir.

## Tapıntılar

| № | Ciddilik | Sahə | Problem | Həll |
|---|---|---|---|---|
| A1 | **Yüksək** | Məlumat sızması | `GET /portal/results`: skan/onlayn KSQ-BSQ üçün müəllim «Nəticəni şagirdlərə göstər» etməmiş bal, faiz, qiymət, hər tapşırığın ✓/✗-i və yarımil qiyməti görünür. Halbuki kart (`_card`) və bildiriş nəşrə qədər bunu gizlədir, onlayn KSQ təhvilində «nəticəni müəllim açacaq» yazılır. ✓/✗ + kartdakı «sistemin oxuduğu cavab» birlikdə düz cavabları açır (sonradan yazan şagirdə ötürülə bilər). | Şagirdin bu imtahan üçün skanı/onlayn kartı varsa və nəticə nəşr olunmayıbsa – bal/faiz/qiymət/✓✗/zəif standartlar gizli, «müəllim açanda görünəcək»; həmin yarımilin qiyməti də gizli. Əl ilə jurnala yazılan köhnə imtahanlar dəyişmir. |
| A2 | Orta | Təhlükəsizlik | Şagird PIN-i 4 rəqəmdir, kodlar ardıcıldır (XE-001…). Kilid yalnız hesab üzrədir – bir IP-dən «hər hesaba 4 cəhd» (password spraying) limitsizdir. | IP üzrə səhv giriş limiti: 10 dəq. ərzində 30 səhv → 10 dəq. 429 (yalnız səhvlər sayılır; sinif Wi-Fi-da düzgün girişlərə təsir etmir). |
| A3 | Orta | İstifadə | Qeydiyyat linki IP üzrə 10 dəq.-də 10 cəhd qəbul edir – bütün sinif məktəb Wi-Fi-ından (bir IP) qeydiyyatdan keçəndə 11-ci şagird 429 alır. | Limit 60 / 10 dəq. |
| A4 | Orta | Dil (RU/EN) | Şagirdə görünən server mesajları yalnız AZ: tapşırıq başlama/təhvil/vaxt bitdi, həll faylı, «Şagird qeydi tapılmadı», `/me`-dəki şəxsi motivasiya («Son tapşırıqda nəticən…»), giriş/QR/PIN xətaları. | `portal.py` – `_L(user, az, ru, en)`; giriş səhifəsində (istifadəçi hələ məlum deyil) – mesaj frontenddə `tt()` ilə, lüğətə EN/RU. |
| A5 | Orta | Dil (RU/EN) | Tərcüməsiz interfeys: `Join.tsx` (qeydiyyat səhifəsi tam), `QrLogin.tsx`, `Login.tsx` (ipucları, «Müəllim», «Kim daxil olur»), `Materials.tsx` («Material yoxdur.», «Son vaxt», «gecikib»), şagirdin öz çapları (`studentPrint.ts`, `Analytics.tsx` hesabatı). | `t()/tt()` + lüğət. Sertifikat (`certificate.tsx`) rəsmi forma kimi AZ qalır. |
| A6 | Aşağı | Möhkəmlik | `POST /portal/materials/{id}/submit` – mətn cavabının uzunluğu məhdud deyil. | ≤ 5000 simvol (400 + RU/EN mesaj). |
| A7 | Aşağı | Məxfilik | `/portal/analytics` sinif ortası kiçik qrupda (2–3 şagird) başqasının göstəricisini təxmin etməyə imkan verir. | Qərar üçün: sinifdə < 5 şagird olanda sinif ortasını göstərməmək. **Bu turda dəyişmir.** |
| A8 | Aşağı | Məxfilik | `/portal/materials` cavabında `student_ids` (materialın göndərildiyi şagirdlərin ID-ləri) şagirdə də gedir. | Şagird cavabından `student_ids` çıxarılır. |

## İcra
Kart: `docs/tasks/sagird-audit-duzelisler.md` (A1–A6, A8). A7 – istifadəçi təsdiqlədi (19.10): sinifdə < 5 şagird olanda sinif ortası gizlədilir.
