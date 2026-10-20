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
      "Müddətsiz testdə taymer yoxdur: «Vaxt məhdudiyyəti yoxdur». İstədiyin vaxt «Təhvil ver» edə bilərsən.",
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
      "Sınaq vaxtı gələndə o, «Tapşırıqlar»da açılır.",
      "«Sınaqlar» bölməsində sınaq imtahanları ayrıca göstərilir."
    ]
  },
  {
    "role": "student",
    "id": "05-netice",
    "title": "Nəticələr və səhvlər üzərində iş",
    "steps": [
      "«Nəticələrim»də bütün nəticələr tarix üzrə sıralanır.",
      "«Nəticə paketi»ni aç: öz cavabın, düzgün cavab və hər sualın mövzusu burada görünür.",
      "Səhv suallara baxıb izahı oxu və təkrar et. Razı deyilsənsə – apelyasiya yaza bilərsən."
    ]
  },
  {
    "role": "student",
    "id": "06-islemeli-testler",
    "title": "İşləməli olduğun testlər",
    "steps": [
      "«Tapşırıqlar»da hələ işləmədiyin testlər siyahıda görünür.",
      "Hər testin müddəti və bağlanma vaxtı yanında yazılıb. İşlədiklərinin balı görünür."
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
      "«Perspektiv plan»da sinfi seç.",
      "Dərslər mövzular üzrə sıralanır, hər mövzunun testi yanında göstərilir.",
      "«🧪 Testləri təyin et» – plana görə mövzu testlərini avtomatik təyin edir.",
      "Əvvəl «Önbaxış» – heç nə yazmır, hansı dərsə hansı test düşəcəyini göstərir. Sonra «Təsdiq et»."
    ]
  },
  {
    "role": "teacher",
    "id": "03-sinif-matrisi",
    "title": "Sinif matrisi: kim nəyi işləyib",
    "steps": [
      "«Testlər və sınaqlar» → «Nəticələr və reytinq» → «Sinif və qrup».",
      "Sinfi seç.",
      "«Kim nəyi işləyib» – hər şagird üzrə testlər və sınaqlar: bal, ✗ – yazmayıb, ⏳ – hələ açıqdır.",
      "«Yalnız işlənməyənlər» – hər şagirdin işləmədiyi testlər qısa siyahı ilə.",
      "«🖨 Sinif üzrə çap» – siyahı PDF kimi hazırlanır; «Hər şagirdə ayrıca» hər şagird üçün ayrı vərəq çıxarır."
    ]
  },
  {
    "role": "teacher",
    "id": "04-kagiz-test",
    "title": "Kağız test (KSQ): vərəqə, skan, nəticə",
    "steps": [
      "«Jurnal»da sinfi seç.",
      "«KSQ / BSQ» bölməsi: imtahanlar, kağız variantlar və nəticələr.",
      "Cavab vərəqəsini çap et, şagirdlər doldursun, skan et – bal avtomatik hesablanır. «Nəticələri göndər» şagirdə nəticə paketini açır."
    ]
  },
  {
    "role": "teacher",
    "id": "05-meshgele-qruplari",
    "title": "Məşğələ qrupları və proqram",
    "steps": [
      "«Siniflər və qruplar» → «Məşğələ qrupları»: inkişaf (Zəif) və tərəqqi (Güclü) qrupları.",
      "«📚 Proqramları təyin et» – bütün qruplar üçün önbaxış cədvəli: tip, sinif, proqram, neçə məşğələ doldurulur.",
      "«Tətbiq et» – yalnız gələcək, mövzusuz məşğələlər doldurulur.",
      "Qrupu aç: «Proqram» bölməsində proqram seçilir, «Önbaxış» və «Yenidən hesabla» var; məşğələlərdə mövzular görünür."
    ]
  },
  {
    "role": "teacher",
    "id": "06-jurnal-hesabat",
    "title": "Jurnal və hesabatlar",
    "steps": [
      "«Jurnal»da sinfi seç.",
      "«Jurnal səhifəsi» – davamiyyət və qiymətlər tarix üzrə sütunlarda.",
      "«Analitika və hesabat» – sinif və şagird üzrə statistika."
    ]
  }
]
// Video yolu: ru -> NN-ad.ru.mp4 (RU interfeys + səs); az və en -> NN-ad.az.mp4 (en: EN alt yazı)
export const guideVideoSrc = (role: string, id: string, lang: string) => `/guide/${role}/${id}.${lang === 'ru' ? 'ru' : 'az'}.mp4`
// Alt yazılar videonun öz vaxtı ilə: RU video – yalnız ru.vtt; AZ video – az.vtt və en.vtt
export const guideSubLangs = (lang: string): string[] => (lang === 'ru' ? ['ru'] : ['az', 'en'])
