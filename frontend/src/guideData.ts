// AVTOMATİK: backend/scripts/guide_videos.py --export-ts (əl ilə dəyişmə). Mətnlər t() ilə tərcümə olunur.
export type GuideItem = { role: 'student' | 'teacher'; id: string; title: string; steps: string[] }
export const GUIDE: GuideItem[] = [
  {
    "role": "student",
    "id": "01-giris",
    "title": "Tətbiqə giriş",
    "steps": [
      "Tətbiqi brauzerdə aç. Giriş səhifəsi açılır.",
      "«Şagird» seçimini bas.",
      "İstədiyin dili seç: Azərbaycanca, English və ya Русский.",
      "Müəllimin verdiyi giriş kodunu yaz (məsələn: XE-001).",
      "4 rəqəmli PIN-i yaz. PIN-i heç kimə vermə.",
      "«Daxil ol» düyməsinə bas – hazırsan!"
    ]
  },
  {
    "role": "student",
    "id": "02-ana-sehife",
    "title": "Ana səhifə və menyu",
    "steps": [
      "Ana səhifə: bu günün dərsləri, tapşırıqları və xatırlatmalar burada görünür.",
      "«Dərs» – bu günün dərsi və ev tapşırığı.",
      "«Tapşırıqlar» – sənə verilmiş testlər.",
      "«Nəticələrim» – işlədiyin testlərin nəticələri.",
      "«Bələdçi» – bu videolara istənilən vaxt qayıda bilərsən."
    ]
  },
  {
    "role": "student",
    "id": "03-movzu-testi",
    "title": "Mövzu testini işləmək",
    "steps": [
      "«Tapşırıqlar» bölməsində testi tap.",
      "«Başla» düyməsi ilə testə başla.",
      "Düzgün hesab etdiyin variantı seç. Cavab avtomatik saxlanır.",
      "Suallar arasında irəli-geri keçə bilərsən. Sonda «Təhvil ver» düyməsini bas."
    ]
  },
  {
    "role": "student",
    "id": "04-sinaq",
    "title": "Sınaq və planlaşdırılmış imtahanlar",
    "steps": [
      "«Plan» bölməsində yaxınlaşan summativ və sınaqları gör.",
      "Sınaq vaxtı gələndə o, «Tapşırıqlar»da açılır."
    ]
  },
  {
    "role": "student",
    "id": "05-netice",
    "title": "Nəticələr və səhvlər üzərində iş",
    "steps": [
      "«Nəticələrim»də bütün nəticələr tarix üzrə sıralanır.",
      "Nəticəni aç: səhv suallar, düzgün cavab və izah burada görünür.",
      "Səhvlərə baxıb təkrar et. Razı deyilsənsə – apelyasiya yaza bilərsən."
    ]
  },
  {
    "role": "student",
    "id": "06-islemeli-testler",
    "title": "İşləməli olduğun testlər",
    "steps": [
      "«Tapşırıqlar»da hələ işləmədiyin testlər siyahıda görünür.",
      "Hər testin müddəti və bağlanma vaxtı yanında yazılıb."
    ]
  },
  {
    "role": "student",
    "id": "07-material-meshgele",
    "title": "Materiallar və əlavə məşğələlər",
    "steps": [
      "«Materiallar» – müəllimin yüklədiyi dərs materialları.",
      "«Əlavə məşğələlər» – qrupun cədvəli və proqramı."
    ]
  },
  {
    "role": "student",
    "id": "08-telefon",
    "title": "Telefonda istifadə",
    "steps": [
      "Tətbiq telefonda da eyni işləyir.",
      "Aşağıdakı düymələrlə bölmələr arasında keç.",
      "Əlavə bölmələr «Daha çox» düyməsindədir."
    ]
  },
  {
    "role": "teacher",
    "id": "01-menyu",
    "title": "Menyu və əsas səhifə",
    "steps": [
      "Əsas səhifədə «Bu həftə diqqət» və günün işləri görünür.",
      "Sol menyu qruplara bölünüb: Dərs, Planlaşdırma, Qiymətləndirmə, Siniflər, Ünsiyyət.",
      "«Bələdçi» bölməsində bütün videolar var."
    ]
  },
  {
    "role": "teacher",
    "id": "02-plan-testleri",
    "title": "Perspektiv plan və plan testləri",
    "steps": [
      "«Perspektiv plan»da dərslər mövzular üzrə sıralanır.",
      "Plandakı mövzuya test «Testlər və sınaqlar» bölməsindən təyin olunur."
    ]
  },
  {
    "role": "teacher",
    "id": "03-sinif-matrisi",
    "title": "Sinif matrisi: kim nəyi işləyib",
    "steps": [
      "«Siniflər və qruplar»da sinfi seç.",
      "Sinfin şagirdləri və hər birinin işlədiyi / işləmədiyi testlər görünür.",
      "İşlənməyənlər siyahısını çap edə və ya Excel-ə çıxara bilərsən."
    ]
  },
  {
    "role": "teacher",
    "id": "04-kagiz-test",
    "title": "Kağız test (KSQ): vərəqə, skan, nəticə",
    "steps": [
      "«Testlər və sınaqlar»da kağız test və KSQ bölməsini aç.",
      "Cavab vərəqəsini çap et, şagirdlər doldursun, sonra skan et – nəticə avtomatik hesablanır."
    ]
  },
  {
    "role": "teacher",
    "id": "05-meshgele-qruplari",
    "title": "Məşğələ qrupları və proqram",
    "steps": [
      "«Siniflər və qruplar» → «Məşğələ qrupları».",
      "Qrup yarat, şagirdləri əlavə et və qrupa proqram təyin et."
    ]
  },
  {
    "role": "teacher",
    "id": "06-jurnal-hesabat",
    "title": "Jurnal və hesabatlar",
    "steps": [
      "«Jurnal»da davamiyyət və qiymətlər yazılır.",
      "«Analitika və hesabat» – sinif və şagird üzrə statistika."
    ]
  }
]
