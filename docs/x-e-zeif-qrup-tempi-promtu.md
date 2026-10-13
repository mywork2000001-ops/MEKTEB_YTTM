# X e – perspektiv plan zəif qrup tempində (13.10.2026)

## Tələb
«X e üçün bizim dərs planı təzədən hazırlansın – zəif uşaqlar ilə, proqram tempində, zəif qrup kimi. 13 oktyabra qədər
dərslər olub, nəzərə al. Öz əlavələrini et, icra elə.»

## Əsas (təhlil – docs/zeif-sinif-iki-illik-proqram-promtu.md §2)
- IX buraxılış orta 19,1; 16/18 zəif; KSQ-1 orta 15,6, 44 % boş cavab.
- Plan: 237 dərs, həftədə 7 saat. I yarımildə V–IX sinif bazası (I–XVIII bölmələr, ~127 dərs), II yarımildə X–XI
  (XIX+ bölmələr).

## Qərar – «zəif qrup tempi» (`app/slow_plan.py`, `POST /api/programs/slow/{ta}`)
1. **13.10.2026-ya qədərki dərslər toxunulmur**: həmin tarixlərin yuvalarındakı plan dərsləri (KSQ-1 daxil) və jurnal
   olduğu kimi qalır.
2. **14.10-dan «Bazanın bərpası» bloku**: keçilmiş mövzuların hər biri üçün «Təkrar və bərpa: …» (10 dəqiqəlik
   mini-test ilə), ən çox 10 dərs.
3. **1-ci il = baza**: I yarımil materialının (V–IX sinif, I–XVIII bölmələr) qalan dərsləri **bütün ilə** yayılır.
   - Hər mövzu dərsindən sonra **«Məşq və möhkəmləndirmə»** gəlir: asan/orta tapşırıqlar, mövzu testi.
   - Yuva artıq qalırsa, bölmə sonunda «Təkrar: bölmə» əlavə olunur; çatmırsa, son bölmələrin məşq dərsləri azaldılır.
4. **Qiymətləndirmə yeni tempə görə**:
   - KSQ yalnız keçilmiş bölmələrdən sonra qoyulur, ən azı ~16 dərsdən bir, bölmə sonunda. Nömrələmə KSQ-2-dən davam edir.
   - Hər yarımilin sonunda «Təkrar: yarımil» və BSQ olur.
5. **2-ci il (XI sinif)** – II yarımil materialı (XIX+ bölmələr, ilkin KSQ/BSQ-lərlə) ayrıca proqram kimi kitabxanada
   saxlanır: «X e – zəif qrup tempi: 2-ci il». Tətbiq olunmur, gələn il qoşulur.
6. **Zəif qrup kimi**: proqramın səviyyəsi `Zəif`. Əvvəlki plan avtomatik kitabxanaya saxlanır, geri qaytarmaq mümkündür.
7. **Mənim əlavələrim**:
   - məşq dərslərinin qiymətləndirmə sətri: «mövzu testi (zəif qrup – asan/orta)»;
   - bərpa blokunda KSQ-1-in ən zəif mövzuları (natural ədədlər, sadə/mürəkkəb ədədlər, çoxluq əməlləri, kəsr, faiz,
     həndəsə əsasları) əhatə olunur;
   - önbaxış (`apply=false`) – tətbiqdən əvvəl hesabat: neçə dərs qaldı, nə əlavə olundu, KSQ sayı, xəbərdarlıqlar.

## Yoxlama
- pytest:
  - keçmiş yuvalar toxunulmur;
  - yuva sayı = plan dərs sayı;
  - hər yarımil BSQ ilə bitir;
  - KSQ nömrələri ardıcıldır;
  - məşq dərsləri var;
  - 2-ci il proqramı yaradılır.
- Canlı: önbaxış → tətbiq → perspektiv planda 14.10-dan bərpa bloku.

---

## Əlavə tələb: «Planlaşdırmada təkrarlar olsun»
Zəif qrupda bilik tez unudulur. Təkrar sistemli və **fasiləli** (spaced repetition) olmalıdır, yalnız yarımil sonunda yox.

### Təkrar növləri (1-ci il, 14.10-dan)
| Növ | Nə vaxt | Məzmun | Qiymətləndirmə |
|---|---|---|---|
| **Bazanın bərpası** | 14.10-dan, blok | keçilmiş mövzular (KSQ-1-in zəif yerləri) | 10 dəqiqəlik mini-test |
| **Məşq və möhkəmləndirmə** | hər mövzu dərsindən sonra | həmin mövzu – asan/orta | mövzu testi |
| **Bölmə təkrarı** | hər bölmənin sonunda | bölmənin bütün mövzuları | ümumiləşdirici tapşırıqlar |
| **Spiral təkrar** | hər ~10 mövzu/məşq dərsindən bir | **əvvəlki** bölmələrdən qarışıq tapşırıqlar (unutmaya qarşı) | 10 sual – qarışıq test |
| **KSQ-yə hazırlıq** | hər KSQ-dən əvvəl | KSQ-nin bölmələri | sınaq testi (KSQ formatında) |
| **Yarımil təkrarı** | BSQ-dən əvvəl | yarımilin materialı | yekunlaşdırıcı test |

### Yerləşdirmə qaydası
- Yuva çatmırsa, azaldılma ardıcıllığı belədir:
  1. məşq dərsləri **bərabər paylanaraq** (hər k-cı) azalır, sonda toplanmış dərslər silinmir;
  2. sonra spiral təkrar seyrəlir;
  3. bölmə təkrarı və KSQ-yə hazırlıq **saxlanır**.
- Yuva artıq qalırsa, əlavə spiral təkrar qoyulur.
- Hesabatda hər təkrar növünün sayı göstərilir.
