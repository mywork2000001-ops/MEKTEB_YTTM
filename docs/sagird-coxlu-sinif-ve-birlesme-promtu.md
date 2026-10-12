# Bir şagird bir neçə sinifdə/qrupda + təkrar şagirdlərin birləşdirilməsi – promt

**İstək (12.10.2026):** bir şagird bir neçə sinfə (qrupa) əlavə oluna bilsin; təkrar şagird varsa – birləşdirilsin.

## Audit
- Şagirdin **bir əsas sinfi** var (`students.class_id`); əlavə üzvlük – **qruplar** (`group_members`): bölünmə qrupu (ana
  sinifdən) və tədris qrupu (məktəbin istənilən sinfindən). Yəni çoxlu üzvlük modeldə var, amma yalnız «Tənzimləmələr»də,
  bütün siyahını yenidən seçməklə; «Siniflər»də və şagird kartında yoxdur.
- **Təkrar şagird** yarana bilir: `uq_student_person` (məktəb + ad + doğum tarixi) doğum tarixi boş olanda və ya ad fərqli
  yazılanda («Əliyev Murad» / «Əliyev Murad Rəşid oğlu») işləmir (qeydiyyat linki, UTİS idxalı, əl ilə əlavə).
  Birləşdirmə aləti yoxdur. Şagirdə 13 cədvəl istinad edir (davamiyyət, qiymət, KSQ/BSQ, test cəhdləri, sertifikat, səviyyə,
  qrup, məşğələ davamiyyəti, material cavabı, valideyn əlaqəsi, fərdi plan, sinif rəhbəri davamiyyəti, səviyyə tarixi) +
  JSON siyahılar (tapşırıq, material, məşğələ qrupu, sınaq seriyası).

## 1. Bir şagird – bir neçə qrup
- [ ] Siniflər → qrup seçiləndə: **«+ Başqa sinifdən şagird»** (sinif açılan siyahıdan, qeyd qutuları) və hər üzvdə **«✕»**
      (yalnız qrupdan çıxır – şagird silinmir, əsas sinfi dəyişmir). Bölünmə qrupu – yalnız ana sinifdən.
- [ ] Şagird kartı → **«Qruplar»**: əsas sinif + üzv olduğu qruplar; qoşula biləcəyi qruplar qeyd qutusu ilə (tədris qrupları
      və öz sinfinin bölünmə qrupları) + məşğələ qrupları (mövcud).
- [ ] Server: `POST /api/classes/{id}/members/add`, `DELETE /api/classes/{id}/members/{sid}`, `GET /api/classes/student/{sid}/groups`;
      icazə – sinfin müəllimi və ya admin (mövcud `_editable`).

## 2. Təkrar şagirdlər – tapmaq və birləşdirmək (yalnız admin)
- [ ] `GET /api/students/duplicates`: eyni məktəb, aktiv şagirdlər; açar – soyad + ad (ata adı / «oğlu/qızı» nəzərə alınmır);
      doğum tarixləri **fərqlidirsə – təkrar sayılmır**; güc: «eyni ad və doğum tarixi» > «eyni ad» > «ad + soyad».
      Hər cütdə: sinif, ID, doğum tarixi, qiymət/cəhd sayı (hansının məlumatı çoxdur).
- [ ] `POST /api/students/merge` {keep_id, drop_id, confirm (saxlanan şagirdin adı)}: bütün istinadlar `drop → keep`:
      birbaşa cədvəllər (metadata ilə – yeni cədvəl əlavə olunsa da düşməz) və JSON siyahılar. Toqquşma (eyni dərsdə hər
      ikisinin qeydi) – saxlananınkı qalır; test cəhdində – təhvil verilmiş olan qalır. Boş sahələr (doğum tarixi, cins,
      ballar, telefon, valideynlər) silinəndən doldurulur. Silinən: arxivə («Birləşdirildi → XE-001»), portal hesabı bağlanır.
      Audit jurnalına yazılır. Geri qaytarılmır – təsdiq adı yazmaqla.
- [ ] UI: «Siniflər və qruplar» → admin üçün **«Təkrar şagirdlər»**: cütlər, «Hansını saxlayaq?» seçimi, «Birləşdir».

## 3. Yoxlama
- Testlər: qrupa əlavə/çıxarma (başqa sinifdən, bölünmədə yalnız ana sinifdən), təkrarların tapılması (fərqli doğum tarixi –
  yox), birləşdirmə (qiymət, cəhd toqquşması, JSON, qrup, arxiv, hesab bağlı), icazə (müəllim – 403).
- Brauzer: Siniflər → qrup → əlavə/çıxar; şagird kartı → Qruplar; Təkrar şagirdlər → birləşdir.
