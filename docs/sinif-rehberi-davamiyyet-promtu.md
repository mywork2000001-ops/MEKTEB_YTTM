# Promt: sinif rəhbərinin davamiyyət jurnalı (1–8-ci saat, sinfin dərs cədvəlinə görə)

## Rol
Sən ümumtəhsil məktəbində təcrübəli **metodist və sinif rəhbəri**, eyni zamanda bu tətbiqin (FastAPI + React)
proqramçısısan. Sinif rəhbərinin gündəlik işini bilirsən: səhər davamiyyəti, üzrlü səbəblərin (arayış, ərizə) qeydi,
valideynlə əlaqə, aylıq davamiyyət hesabatı, direktor müavininə təqdim olunan cədvəl.

## Məqsəd
Sinif rəhbəri **sinfin bütün dərsləri üzrə** (1–8-ci saat, həftəlik dərs cədvəlinə görə) şagirdlərin davamiyyətini
qeyd edə bilsin, sinif üzrə gündəlik və aylıq davamiyyəti görsün, çap etsin.

## Dəyişməz qaydalar (istifadəçinin qərarları)
- Sinif rəhbəri başqa müəllimlərin jurnal qeydlərini görmür, yalnız yekun göstəriciləri görür.
- Fənn müəlliminin jurnalındakı davamiyyət o dərs üçün **əsas mənbədir**. Rəhbər onu dəyişmir, ekranda yalnız görür.
  Rəhbər sistemdə müəllimi olmayan fənlərin dərslərini və hələ yazılmamış dərsləri qeyd edir.
- Qayıb və üzrlü şagird dərsdə yoxdur, 25% və daha çox buraxma xəbərdarlıq sayılır.
- Gələcək tarixə və bayram/tətil gününə davamiyyət yazılmır.
- Çap: A4, ağ-qara (Canon), yalnız «Sinif rəhbəri: ____» imzası.
- Valideyn məlumatı yalnız rəhbər və admin üçündür.

## Tələblər
1. **Sinfin dərs cədvəli** (B.e.–C., 1–8-ci saat): fənn adı və müəllim.
   - Sistemdə olan müəllimlərin dərsləri avtomatik doldurulur və kilidlidir.
   - Qalan fənləri rəhbər özü yazır.
   - Zəng vaxtları məktəbin (və ya sinfin öz) cədvəlindən götürülür.
2. **Gündəlik davamiyyət** (tarix seçilir):
   - Cədvəl: sətirlər şagirdlər, sütunlar həmin günün dərsləri.
   - Status: V (var), Q (qayıb), Ü (üzrlü), G (gecikib).
   - Tez əməliyyatlar: «Hamı var»; şagird üzrə «Bütün gün yox» və «Bütün gün üzrlü».
   - Üzrlü üçün səbəb: xəstəlik (arayış), ailə, tədbir, digər.
   - Jurnaldan gələn xanalar kilidlidir və «jurnal» nişanı ilə görünür.
3. **Aylıq cədvəl**: şagird × gün, xanada buraxılmış saat sayı.
   - Cəmlər: dərs sayı, üzrsüz, üzrlü, gecikmə, faiz.
   - Xəbərdarlıqlar: 25% və daha çox buraxma, **ardıcıl 3 və daha çox gün** gəlməmə, üzrsüz buraxmalar.
   - Valideynin telefonu yanında göstərilir.
4. **Çap**: aylıq davamiyyət cədvəli (A4 albom) və gündəlik siyahı.
5. **İcmal**: sinif rəhbəri icmalındakı davamiyyət faizi jurnal və rəhbər qeydlərinin birləşməsindən hesablanır.

## Metodik yoxlama siyahısı
- Cədvəldə olmayan saata qeyd yazılmır; bayram və həftəsonu günlərində dərs yoxdur.
- Bölünən qrupda (məs. X b riyaziyyat/biologiya) jurnal yalnız qrupun üzvlərinə aiddir, qalan şagirdləri rəhbər qeyd edir.
- Arxivlənmiş şagird siyahıda görünmür.
- Tətbiqdə hər qeyd audit jurnalına yazılır (kim, nə vaxt).

## İcra qaydası
- Model + Alembic miqrasiyası, API (serverdə yoxlama), React interfeysi (telefon və kompüter).
- Avtomatik testlər: cədvəl, gündəlik qeyd, jurnal prioriteti, gələcək tarix/bayram, qrup, aylıq hesabat, xəbərdarlıqlar.
- `pytest`, `tsc`, `vite build`; brauzerdə yoxlama; nəticə `docs/sinif-rehberi-davamiyyet.md`; commit + push.
