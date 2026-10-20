// AVTOMATİK: backend/scripts/guide_videos.py --export-ts (əl ilə dəyişmə). Mətnlər t() ilə tərcümə olunur.
export type GuideChapter = { t: Record<string, number>; title: string }      // t: dil -> başlanğıc (san.)
export type GuideItem = { role: 'student' | 'teacher'; id: string; title: string; steps: string[]; chapters?: GuideChapter[]; duration?: Record<string, number> }
export const GUIDE: GuideItem[] = [
  {
    "role": "student",
    "id": "00-tanitim",
    "title": "Qısa tanıtım",
    "steps": [
      "Bu, ana səhifədir: bu günün dərsləri və xatırlatmalar burada.",
      "Menyuda «Dərs» bölməsi də var.",
      "«Tapşırıqlar»da müəllimin verdiyi testləri tapırsan.",
      "«Başla» ilə testi başlat.",
      "Variantı seç – cavab avtomatik saxlanır.",
      "«Nəticələrim»də bütün nəticələrin görünür.",
      "«Nəticə paketi»: cavabların, düzgün cavablar və izahlar.",
      "Çətin olanda «Bələdçi»yə qayıt – bütün videolar orada."
    ],
    "chapters": [
      {
        "t": {
          "az": 3.6,
          "en": 3.6,
          "ru": 3.6
        },
        "title": "Ana səhifə və menyu"
      },
      {
        "t": {
          "az": 12.7,
          "en": 12.7,
          "ru": 12.7
        },
        "title": "Tapşırıq və test"
      },
      {
        "t": {
          "az": 33.0,
          "en": 33.0,
          "ru": 34.5
        },
        "title": "Nəticələrim"
      },
      {
        "t": {
          "az": 42.3,
          "en": 42.3,
          "ru": 44.5
        },
        "title": "Bələdçi və kömək"
      }
    ],
    "duration": {
      "az": 51.1,
      "ru": 53.3,
      "en": 51.1
    }
  },
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
    ],
    "duration": {
      "az": 33.3,
      "ru": 36.4,
      "en": 33.3
    }
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
    ],
    "duration": {
      "az": 28.9,
      "ru": 29.9,
      "en": 28.9
    }
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
    ],
    "duration": {
      "az": 42.4,
      "ru": 43.8,
      "en": 42.4
    }
  },
  {
    "role": "student",
    "id": "04-sinaq",
    "title": "Sınaq və planlaşdırılmış imtahanlar",
    "steps": [
      "«Plan» bölməsində yaxınlaşan summativ və sınaqları gör.",
      "Sınaq vaxtı gələndə o, «Tapşırıqlar»da açılır.",
      "«Sınaqlar» bölməsində sınaq imtahanları ayrıca göstərilir."
    ],
    "duration": {
      "az": 19.5,
      "ru": 20.8,
      "en": 19.5
    }
  },
  {
    "role": "student",
    "id": "05-netice",
    "title": "Nəticələr və səhvlər üzərində iş",
    "steps": [
      "«Nəticələrim»də bütün nəticələr tarix üzrə sıralanır.",
      "«Nəticə paketi»ni aç: öz cavabın, düzgün cavab və hər sualın mövzusu burada görünür.",
      "Səhv suallara baxıb izahı oxu və təkrar et. Razı deyilsənsə – apelyasiya yaza bilərsən."
    ],
    "duration": {
      "az": 24.8,
      "ru": 26.5,
      "en": 24.8
    }
  },
  {
    "role": "student",
    "id": "06-islemeli-testler",
    "title": "İşləməli olduğun testlər",
    "steps": [
      "«Tapşırıqlar»da hələ işləmədiyin testlər siyahıda görünür.",
      "Hər testin müddəti və bağlanma vaxtı yanında yazılıb. İşlədiklərinin balı görünür."
    ],
    "duration": {
      "az": 17.2,
      "ru": 17.6,
      "en": 17.2
    }
  },
  {
    "role": "student",
    "id": "07-material-meshgele",
    "title": "Materiallar və əlavə məşğələlər",
    "steps": [
      "«Materiallar» – müəllimin yüklədiyi dərs materialları.",
      "«Əlavə məşğələlər» – qrupun cədvəli və proqramı."
    ],
    "duration": {
      "az": 14.8,
      "ru": 15.0,
      "en": 14.8
    }
  },
  {
    "role": "student",
    "id": "08-telefon",
    "title": "Telefonda istifadə",
    "steps": [
      "Tətbiq telefonda da eyni işləyir.",
      "Aşağıdakı düymələrlə bölmələr arasında keç.",
      "Əlavə bölmələr «Daha çox» düyməsindədir."
    ],
    "duration": {
      "az": 16.9,
      "ru": 16.9,
      "en": 16.9
    }
  },
  {
    "role": "teacher",
    "id": "00-tanitim",
    "title": "Qısa tanıtım",
    "steps": [
      "Əsas səhifədə «Bu həftə diqqət» və günün işləri görünür.",
      "Sol menyu qruplara bölünüb: Dərs, Planlaşdırma, Qiymətləndirmə, Siniflər, Ünsiyyət.",
      "«Perspektiv plan»da sinfi seçirsiniz.",
      "Dərslər mövzular üzrə sıralanır, hər mövzunun testi yanındadır.",
      "«Testləri təyin et» – testlər plana görə avtomatik təyin olunur.",
      "Əvvəl «Önbaxış» – heç nə yazmır, sonra «Təsdiq et».",
      "«Kim nəyi işləyib» – hər şagird üzrə bal, ✗ – yazmayıb.",
      "«KSQ / BSQ» bölməsi: imtahanlar, kağız variantlar və nəticələr.",
      "Vərəqəni çap edin, skan edin – bal avtomatik hesablanır.",
      "«Jurnal səhifəsi» – davamiyyət və qiymətlər tarix üzrə.",
      "«Analitika və hesabat» – sinif və şagird üzrə statistika."
    ],
    "chapters": [
      {
        "t": {
          "az": 3.6,
          "en": 3.6,
          "ru": 3.6
        },
        "title": "Menyu"
      },
      {
        "t": {
          "az": 15.4,
          "en": 15.4,
          "ru": 16.6
        },
        "title": "Plan və mövzu testləri"
      },
      {
        "t": {
          "az": 34.8,
          "en": 34.8,
          "ru": 36.3
        },
        "title": "Sinif matrisi"
      },
      {
        "t": {
          "az": 43.2,
          "en": 43.2,
          "ru": 44.2
        },
        "title": "Kağız test və skan"
      },
      {
        "t": {
          "az": 65.6,
          "en": 65.6,
          "ru": 66.6
        },
        "title": "Jurnal və hesabat"
      }
    ],
    "duration": {
      "az": 78.6,
      "ru": 80.1,
      "en": 78.6
    }
  },
  {
    "role": "teacher",
    "id": "01-menyu",
    "title": "Menyu və əsas səhifə",
    "steps": [
      "Əsas səhifədə «Bu həftə diqqət» və günün işləri görünür.",
      "Sol menyu qruplara bölünüb: Dərs, Planlaşdırma, Qiymətləndirmə, Siniflər, Ünsiyyət.",
      "«Bələdçi» bölməsində bütün videolar var."
    ],
    "duration": {
      "az": 21.5,
      "ru": 22.9,
      "en": 21.5
    }
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
    ],
    "duration": {
      "az": 28.1,
      "ru": 28.8,
      "en": 28.1
    }
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
    ],
    "duration": {
      "az": 35.2,
      "ru": 33.7,
      "en": 35.2
    }
  },
  {
    "role": "teacher",
    "id": "04-kagiz-test",
    "title": "Kağız test (KSQ): vərəqə, skan, nəticə",
    "steps": [
      "«Jurnal»da sinfi seç.",
      "«KSQ / BSQ» bölməsi: imtahanlar, kağız variantlar və nəticələr.",
      "Cavab vərəqəsini çap et, şagirdlər doldursun, skan et – bal avtomatik hesablanır. «Nəticələri göndər» şagirdə nəticə paketini açır."
    ],
    "duration": {
      "az": 26.0,
      "ru": 28.4,
      "en": 26.0
    }
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
    ],
    "duration": {
      "az": 33.7,
      "ru": 35.2,
      "en": 33.7
    }
  },
  {
    "role": "teacher",
    "id": "06-jurnal-hesabat",
    "title": "Jurnal və hesabatlar",
    "steps": [
      "«Jurnal»da sinfi seç.",
      "«Jurnal səhifəsi» – davamiyyət və qiymətlər tarix üzrə sütunlarda.",
      "«Analitika və hesabat» – sinif və şagird üzrə statistika."
    ],
    "duration": {
      "az": 19.8,
      "ru": 19.8,
      "en": 19.8
    }
  }
]
// Poster (960 px JPG): az/en -> NN-ad.jpg, ru -> NN-ad.ru.jpg
export const guidePoster = (role: string, id: string, lang = 'az') => `/guide/${role}/${id}${lang === 'ru' ? '.ru' : ''}.jpg`
// Video yolu: ru -> NN-ad.ru.mp4 (RU interfeys + səs); az və en -> NN-ad.az.mp4 (en: EN alt yazı)
export const guideVideoSrc = (role: string, id: string, lang: string) => `/guide/${role}/${id}.${lang === 'ru' ? 'ru' : 'az'}.mp4`
// Alt yazılar videonun öz vaxtı ilə: RU video – yalnız ru.vtt; AZ video – az.vtt və en.vtt
export const guideSubLangs = (lang: string): string[] => (lang === 'ru' ? ['ru'] : ['az', 'en'])
