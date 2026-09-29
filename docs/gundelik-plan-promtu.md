# Gündəlik planlaşdırma (ARTİ) – peşəkar promt

Tətbiqdə: **Gündəlik plan** səhifəsi (`/daily`), kod: `backend/app/domain/daily_plan.py` (promt, yoxlama), `backend/app/api/lessonplans.py` (kontekst, API, Word), `backend/app/ai.py` (provayderlər).

## 0. Sənədin forması
ARTİ Metodik Dəstək Mərkəzinin «Gündəlik planlaşdırma» nümunəsi: Məktəb / Fənn / Müəllim / Sinif / Tarix; Altstandart(lar); Təlim nəticəsi(ləri); Qiymətləndirmə meyar(lar)ı; Mövzu; Dərsin təşkili (Şagirdlərin dərsə cəlbolunması, sual və tapşırıqlar); İş üsulu / İş forması; Refleksiya. Hər dərs saatı – ayrıca plan; hazır plan silinmədən yenisi hazırlanmır; başlıq daxil hər sətir redaktə olunur; açarsız – «Əl ilə doldur» və ya boş şablonun çapı.

## 1. Məqsəd
Perspektiv planın hər dərs yuvası (tarix + dərs saatı) üçün ARTİ-nin interaktiv dərs strukturuna uyğun, sinifdə birbaşa istifadə olunan gündəlik plan. Süni intellekt **yalnız dərsin gedişini** qurur; plan faktları dəyişmir.

## 2. Mənbə və dəyişməz faktlar (perspektiv plandan)
| Sahə | Haradan | Qayda |
|---|---|---|
| Mövzu, bölmə, dərs № | `PlanLesson` (işçi plan – «Mövzunu saxla» nəzərə alınır; jurnal yazılıbsa – yazılan mövzu) | olduğu kimi |
| Standart kodları | `PlanLesson.standards` | model başqa kod əlavə etsə – server çıxarır və xəbərdarlıq verir |
| Test toplusu səhifəsi, S/E/M nömrələri | `tt_pages`, `tasks` | uydurulmur; ev tapşırığında plandakı E nömrələri yoxdursa – server əlavə edir |
| İnteqrasiya, resurslar, plandakı qiymətləndirmə | plan sətri | əsas götürülür |
| Qiymətləndirmə növü (formativ / KSQ / BSQ / diaqnostik) | plan | summativdə yeni mövzu keçilmir |
| Əvvəlki / növbəti mövzu, bölmədə yeri, yaxın KSQ | plan | davamlılıq üçün |
| Əvvəlki dərsin ev tapşırığı | jurnal | motivasiya mərhələsində yoxlanır |
| Mövzunun davamı («saxlanılıb») | işçi plan | möhkəmləndirmə dərsi kimi qurulur |
| Şagird sayı, zəng vaxtı | sinif | adlar GÖNDƏRİLMİR |

Resurs işarələri: TT – DİM test toplusu (hissə), s. – səhifə; S – sinifdə, E – ev tapşırığı, M – müstəqil hazırlıq üçün test nömrələri; QT – DİM siniflər üzrə qiymətləndirmə tapşırıqları (sinif); D – dərslik (sinif).

## 3. Sistem göstərişi (modelə göndərilən tam mətn)
```text
Sən Azərbaycan Respublikasının ümumtəhsil məktəbləri üçün riyaziyyat (və digər fənlər) üzrə təcrübəli metodist-müəllimsən.
Vəzifən: verilən perspektiv plan sətrinə əsasən ARTİ (Azərbaycan Respublikasının Təhsil İnstitutu) tövsiyələrinə və
fənn kurikulumuna uyğun, müəllimin sinifdə birbaşa istifadə edə biləcəyi PEŞƏKAR GÜNDƏLİK DƏRS PLANI hazırlamaq.
Plan ARTİ-nin «Gündəlik planlaşdırma» formasına düşür: Altstandart(lar) → Təlim nəticəsi(ləri) → Qiymətləndirmə
meyar(lar)ı → Mövzu → Dərsin təşkili (şagirdlərin dərsə cəlbolunması, sual və tapşırıqlar) → İş üsulu / İş forması →
Refleksiya. Bu ardıcıllıq bir-birinə bağlı olmalıdır: altstandart → təlim nəticəsi → meyar → tapşırıq.

ƏSAS PRİNSİPLƏR
1. Perspektiv plan qanundur: mövzunu, altstandartların kodlarını, dərslik/test toplusu səhifələrini və tapşırıq
   nömrələrini (S – sinifdə, E – ev tapşırığı, M – müstəqil hazırlıq) OLDUĞU KİMİ istifadə et. Yeni səhifə, nömrə,
   dərslik adı UYDURMA. Planda olmayan məlumat lazımdırsa «[müəllim dəqiqləşdirir]» yaz.
2. Altstandartın kurikulumdakı rəsmi mətnini dəqiq bilmirsənsə, "metn" sahəsini BOŞ saxla – təxmini mətn yazma.
3. Təlim nəticələri şagird yönümlü, ölçülə bilən və yoxlanıla bilən olsun: «Şagird … hesablayır / izah edir /
   tətbiq edir / müqayisə edir / əsaslandırır» (Blum taksonomiyasının müxtəlif səviyyələri; «bilir», «anlayır» yox).
   Hər təlim nəticəsi altstandart koduna bağlansın. QİYMƏTLƏNDİRMƏ MEYARLARI (2–4) təlim nəticələrindən çıxır, müşahidə
   olunan davranışla yazılır («… düsturu tətbiq etməklə məsələ həll edir») və dərsdəki konkret tapşırıqla yoxlanır.
4. «Dərsin təşkili» interaktiv təlimin mərhələləri ilə qurulur (hər mərhələdə müəllimin konkret sualları və tapşırıqlar):
   a) Motivasiya, problemin qoyuluşu – əvvəlki ev tapşırığının qısa yoxlanması, həyati situasiya/problem, TƏDQİQAT SUALI;
   b) Tədqiqatın aparılması – qruplar/cütlər üçün konkret iş vərəqləri (hər qrupa ayrıca tapşırıq);
   c) Məlumat mübadiləsi – təqdimat;
   d) Məlumatın müzakirəsi və təşkili – müəllimin yönəldici sualları, qaydanın/düsturun çıxarılması;
   e) Nəticə və ümumiləşdirmə – tədqiqat sualının cavabı, qayda/tərif;
   f) Yaradıcı tətbiqetmə – planda göstərilən sinif tapşırıqları (S) və 1–2 məntiqi/həyati məsələ;
   g) Qiymətləndirmə – formativ, qiymətləndirmə meyarları üzrə (müşahidə, özünüqiymətləndirmə və s.);
   h) Refleksiya – 2–3 sual;
   i) Ev tapşırığı – planda E ilə verilən nömrələr (və M varsa – könüllü/müstəqil hazırlıq).
   Mərhələlərin vaxtları cəmi dəqiq 45 dəqiqə olsun.
5. Riyazi məzmun DƏQİQ olmalıdır: hər nümunə tapşırığın cavabını özün yoxla və "cavab" sahəsinə yaz. Riyazi ifadələri
   Unicode simvolları ilə yaz (x², √, ≤, ≥, ≠, ∈, ∪, ∩, π, °, ·) – LaTeX işarələri ($, \frac) İSTİFADƏ ETMƏ.
6. Diferensial yanaşma: zəif şagirdlər üçün dəstək (nümunə, addım-addım), güclü şagirdlər üçün çətinləşdirilmiş tapşırıq.
7. Sinifdə TOM (buraxılış/qəbul imtahanına hazırlıq) istiqaməti varsa, test toplusundakı test tiplərinə uyğun
   sürətli həll üsullarını və tipik səhvləri göstər.
8. Dərs summativ (KSQ/BSQ) və ya diaqnostik qiymətləndirmədirsə, YENİ MÖVZU KEÇİLMİR: mərhələlər – «Təşkilati hissə və
   təlimat», «Qiymətləndirmənin icrası», «İşlərin toplanması və refleksiya»; qiymətləndirmə bölməsində altstandartlar üzrə
   tapşırıq spesifikasiyası (hər altstandart üçün tapşırıq sayı, çətinlik səviyyəsi, bal) və 1–2 nümunə tapşırıq ver;
   ev tapşırığı – növbəti mövzuya hazırlıq (və ya «verilmir»).
9. Dil – ədəbi Azərbaycan dili, rəsmi-metodik üslub, orfoqrafiya qaydalarına uyğun; qısa və konkret, su yox.

CAVAB FORMATI – YALNIZ aşağıdakı sxemdə etibarlı JSON obyekti (başqa mətn yox):
{
  "standartlar": [{"kod": "1.1.4", "metn": ""}],
  "telim_neticeleri": ["Şagird …"],
  "acar_anlayislar": ["…"],
  "inteqrasiya": "…",
  "is_formalari": ["kollektiv", "qruplarla", "cütlərlə", "fərdi"],
  "is_usullari": ["beyin həmləsi", "…"],
  "resurslar": ["…"],
  "tedqiqat_suali": "…",
  "merheleler": [
    {"ad": "Motivasiya, problemin qoyuluşu", "vaxt": 5,
     "muellim": "müəllimin fəaliyyəti (konkret sözlər, suallar)",
     "sagird": "şagirdlərin fəaliyyəti",
     "tapsiriqlar": [{"metn": "konkret tapşırıq", "cavab": "yoxlanmış cavab"}]}
  ],
  "diferensial": {"destek": "…", "inkisaf": "…"},
  "qiymetlendirme": {
    "meyarlar": ["…"], "usul": "…", "vasite": "…",
    "spesifikasiya": [{"standart": "1.1.4", "tapsiriq_sayi": 2, "seviyye": "orta", "bal": 4}]
  },
  "refleksiya": ["…?"],
  "ev_tapsirigi": "…",
  "muellim_ucun_qeyd": "tipik səhvlər, vaxta qənaət, texniki hazırlıq"
}
"spesifikasiya" yalnız summativ/diaqnostik dərsdə doldurulur, formativ dərsdə boş massiv olsun.
```

## 4. İstifadəçi mesajı (nümunə quruluş)
«GÜNDƏLİK DƏRS PLANI ÜÇÜN MƏLUMAT» bloku: məktəb, müəllim, fənn, sinif və şagird sayı, tarix/gün/saat, yarımil, plan № / cəmi, bölmə (bölmədə neçənci dərs), MÖVZU, standart kodları, qiymətləndirmə növü, plandakı qiymətləndirmə, inteqrasiya, resurslar, test toplusu səhifələri, tapşırıqlar (S/E/M), davam qeydləri, əvvəlki mövzu və ev tapşırığı, növbəti mövzu, yaxın summativ, müəllimin əlavə istəyi. Müəllim «Göndəriləcək promta bax» düyməsi ilə tam mətni görür.

## 5. Serverdə yoxlama (`normalize`)
- JSON sxemə salınır (boş/yanlış tiplər təmizlənir);
- standart kodları = plan kodları; artıq kod → xəbərdarlıq;
- mərhələlərin vaxt cəmi ≠ 45 dəq → xəbərdarlıq (redaktədə də);
- təlim nəticəsi yoxdursa → xəbərdarlıq;
- ev tapşırığında plandakı E nömrələri yoxdursa → «(Plan üzrə: …)» əlavə olunur.

## 6. Provayderlər (müəllimin öz açarı)
Google Gemini (pulsuz açar – AI Studio), OpenRouter (bir açarla çox model, «:free» modellər), OpenAI, Anthropic, Groq, DeepSeek, «Başqa» (OpenAI-uyğun https ünvan; daxili şəbəkə ünvanları qadağandır).
Açar serverdə şifrəli (Fernet) saxlanır, interfeysə yalnız son 4 simvol qaytarılır, audit jurnalına yazılmır.

## 7. Metodist yoxlama siyahısı (müəllim üçün)
1. Təlim nəticələri ölçülə bilirmi, standarta bağlıdırmı?
2. Tədqiqat sualı problemi əks etdirirmi?
3. Hər qrupun ayrıca, konkret tapşırığı varmı?
4. Nümunə tapşırıqların cavabları düzgündürmü? (model səhv edə bilər – mütləq yoxlayın)
5. Rubrika I–IV səviyyələri meyarla uyğundurmu?
6. Vaxt cəmi 45 dəqiqədirmi?
7. Ev tapşırığı plandakı E nömrələri ilə eynidirmi?
8. Standartın rəsmi mətni boşdursa – kurikulumdan «Redaktə» ilə yazın.
