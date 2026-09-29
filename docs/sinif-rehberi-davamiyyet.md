# Sinif rəhbərinin davamiyyət jurnalı – nəticə (29.09.2026)

Promt: `docs/sinif-rehberi-davamiyyet-promtu.md`.

## Nə edildi
| Tələb | Həll |
|---|---|
| Sinfin dərs cədvəli (1–8-ci saat) | «Sinif rəhbəri → Dərs cədvəli»: sistemdə müəllimi olan dərslər avtomatik gəlir və kilidlidir, qalan fənləri (və müəllimi) rəhbər yazır; bölünən qrupun saatında paralel fənn yazıla bilər; zəng vaxtları görünür (`ClassLesson`) |
| Gündəlik davamiyyət | «Davamiyyət → Gündəlik qeyd»: tarix; sətir – şagird, sütun – həmin günün dərsləri; xanaya basmaqla V → Q → Ü → G → boş; «Boş xanalar – hamı var»; şagird üzrə «bütün gün» Q/Ü/V; üzrlü səbəb (xəstəlik (arayış), ailə, tədbir, digər) (`HomeroomAttendance`) |
| Jurnal əsas mənbədir | Fənn müəlliminin jurnalı olan xana 🔒 – rəhbər dəyişə bilmir (server də qəbul etmir, «locked» sayılır) |
| Qadağalar | Gələcək gün, həftəsonu, bayram/tətil, cədvəldə olmayan saat, başqa sinfin şagirdi – qeyd yazılmır |
| Aylıq cədvəl | Şagird × gün: buraxılmış saat (qırmızı – üzrsüz, «ü» – üzrlü, «g» – gecikmə, ✓); cəmlər; «Diqqət tələb edənlər»: 25%+ buraxma, ardıcıl 3+ gün gəlməmə, 3+ üzrsüz – valideynin telefonu (zəng düyməsi) ilə |
| Çap | Aylıq davamiyyət – A4 albom, ağ-qara, «Diqqət tələb edənlər» cədvəli, «Sinif rəhbəri: ____» |
| İcmal | Sinif rəhbəri icmalında və «Dövr üzrə» cədvəldə davamiyyət indi jurnal + rəhbər qeydlərinin birləşməsidir |
| Telefon | Cədvəllərdə şagird adı sabit (sürüşəndə görünür) |

## Metodik qərarlar
- Qeyd olunmamış saat buraxılmış sayılmır (faiz yalnız qeyd olunan dərslərdən); aylıq cədvəldə «Qeyd olunmayıb» sayı ayrıca göstərilir.
- «Ardıcıl gün»: şagirdin həmin gün qeyd olunan bütün dərslərdə olmaması; qeyd olunmayan gün ardıcıllığı pozmur.
- Bölünən qrupun jurnalı yalnız qrup üzvlərinə tətbiq olunur – digər yarımqrupu rəhbər qeyd edir.
- Hər yadda saxlama audit jurnalına yazılır (kim, nə vaxt, neçə qeyd).

## Testlər
`tests/test_api_homeroom_att.py` – cədvəl (sistem kilidi), gündəlik qeyd, jurnal prioriteti, silmə, gələcək/həftəsonu/yanlış saat,
aylıq hesabat, 25% və ardıcıl 3 gün xəbərdarlığı, giriş hüququ. Cəmi 113 test keçir.
