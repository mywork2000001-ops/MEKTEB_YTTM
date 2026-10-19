# Sinfə görə testlər – plan dərsinin testi öz sinfinin bankından · audit + promt (19.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və riyaziyyat metodistisən. Məqsəd: perspektiv planın hər dərsinə
qoşulan test (onlayn mövzu testi, sinif testi, sınaq) **həmin mövzunun öz sinfinə** uyğun olsun – qrupun sinfinə görə yox.
Xüsusilə fərdi hazırlıq kurslarında (V→IX, V→XI «Sinif testləri» ardıcıl) V sinif mövzusuna V sinif testi, VII-yə VII düşməlidir.
Bağlı promt: docs/ferdi-perspektiv-plan-promtu.md (90 dəq. görüş, avtomatik plan) – bu iş onun §4-ünün test hissəsidir.

## 0. Sabit qaydalar
- Məktəb siniflərində indiki nəticə dəyişmir (X sinfi – P0010, IX – P007), yalnız yanlış sinif uyğunluğu aradan qalxır.
- Müəllimin əl ilə seçdiyi test (`LessonBankLink`, `p0010_manual`) heç vaxt avtomatik dəyişmir.
- Bankda olmayan test uydurulmur; boşluq hesabatda «yoxdur» kimi göstərilir, mənbə PDF-dən `pdf-oxuyucu` + `cavab-yoxlayici` ilə doldurulur.
- Mətnlər AZ/EN/RU; aid pytest + `npm run build`; canlı DB-yə yazı – istifadəçinin razılığı ilə.

## 1. Audit nəticələri (kod, 19.10.2026)
| # | Tapıntı | Yer | Nəticə |
|---|---|---|---|
| A1 | Test mənbəyi **bütün plan üçün bir** seçilir – qrupun sinfinə görə: `GRADE_SOURCE = {9: p007, 10: p003, 11: p003}` | `bank/match.py:16`, `ta_source` | IX hazırlıq qrupunda «V sinif: Natural ədədlər» dərsi IX toplusundan (P007) söz oxşarlığı ilə test alır – **sinfi səhv** |
| A2 | Matcher mövzunun «V sinif:» önəkini atır (`_PREFIX`) və `BankFile.grades`-ə baxmır | `bank/match.py` `Matcher`, `p0010_files` | mövzunun sinif məlumatı itir; bankda sinif etiketi (`grades`) olsa da istifadə olunmur |
| A3 | V–VIII sinif qrupları üçün mənbə yoxdur (`source_for` → None) | `bank/match.py:19` | V–VIII qruplarda və hazırlıq kursunun V–VIII hissəsində avtomatik test linki yoxdur, halbuki bankda P001 (V), P011 (VI), P003 (V–XI etiketlə) var (`classify.SOURCE_GRADES`) |
| A4 | Kurs proqramında sinif uyğunsuzluğu xəbərdarlığı söndürülüb (`not is_course(program)`) | `programs.py` `lessons_for` | VII qrupa «Buraxılış – IX» (V–IX) tətbiq olunanda xəbərdarlıq yoxdur; VIII–IX mövzuları qrupun keçmədiyi material ola bilər |
| A5 | Fərdi qrupda «sinif» məqsədi ilə DİM «Sinif testləri – VII» tətbiq olunanda məktəb formatı açılır: KSQ/BSQ, yarımillər; `has_summative` defolt True | `classes.py:313`, `expand` | repetitor qrupunda summativ olmamalıdır (repetitor-proqramlar-promtu §3) – yoxlanmalı və düzəlməli |
| A6 | Kitabda variant sayı sinfə görə fərqlidir: V–VII, X–XI – A–D; VIII – A–C; IX – **yalnız A–B** | `program_data/sinif_testleri.json` | «variant A – dərsdə, B – ev, C/D – sınaq» kimi sabit qayda IX-də işləmir; variant sinfə görə paylanmalıdır |
| A7 | Qarışıq qrupda (`class_grade` → None) proqramın sinfi götürülür | `lessons_for` | VIII+IX qarışıq qrupda hər şagirdə öz sinfinin testi verilə bilmir |

## 2. Həll
### 2.1 Dərsin öz sinfi
- `PlanLesson` üçün hesablanan sahə `lesson_grade`: (1) mövzu/bölmə önəki «V sinif: …», «VII sinif – …» → 7; (2) proqram şablonunda
  bölmənin `grade` sahəsi (yeni: `_prep_template` hər bölməyə `grade` yazır); (3) yoxdursa – proqramın sinfi; (4) sonra qrupun sinfi.
  Miqrasiyasız: plan açılanda hesablanır; proqram yenidən tətbiq olunanda `tasks`/`data`-da saxlanılır.

### 2.2 Sinfə görə mənbə və uyğunluq
- `GRADE_SOURCE` → sinif üzrə **sıralı mənbə siyahısı** (konfiq, bir yerdə):
  V: [DİM Sinif testləri bankı (varsa), P001, P003] · VI: [Sinif testləri, P011, P003] · VII–VIII: [Sinif testləri, P003] ·
  IX: [P007, Sinif testləri, P003] · X–XI: [P003, P013/Sinif testləri].
- `Matcher(db, sources, grade)`: yalnız `grade in BankFile.grades` olan fayllar (etiketsiz fayl – yalnız mənbə həmin sinfə aiddirsə);
  dərs üçün əvvəl 1-ci mənbə, uyğunluq həddi altındadırsa növbəti mənbə. Önək atılır, amma sinif süzgəc kimi qalır.
- Matcher hər sinif+mənbə üçün bir dəfə qurulur (keş) – plan görünüşü yavaşımasın.
- `ta.bank_source` (müəllimin ayarı) qalır, amma «Avtomatik (dərsin sinfinə görə)» yeni defolt seçimdir; köhnə sabit seçim olan qruplar
  dəyişmir.

### 2.3 Variantların sinfə görə paylanması
- `sinif_testleri.json` → `variants` sinfə görə oxunur: dərs testi – A; ev tapşırığı / təkrar – B; aralıq sınaq – C (yoxdursa A-nın
  rəqəmləri dəyişdirilmiş variantı, `avto_reqem.py`); yekun – D (yoxdursa B + öz rəqəmləri). Planın «Resurs» sütununda real variant yazılır.

### 2.4 Sinif uyğunluğu yoxlaması
- Kurs proqramı qrupa tətbiq olunanda: proqramın ən yüksək sinfi > qrupun sinfi → xəbərdarlıq «Proqramda VIII–IX mövzuları var, qrup – VII»
  + təklif: «Yalnız V–VII bölmələrini seç». Qrupun sinfindən aşağı bölmələr «Təkrar (bazanın bərpası)» nişanı alır.
- Fərdi məkanda `has_summative` defolt **False**; «Sinif testləri – N» fərdi qrupa tətbiq olunanda KSQ/BSQ yerinə «Sınaq: bölmə» (formativ).

### 2.5 Qarışıq qrup (əlavə – seçilə bilər)
- Qrupun şagirdlərinin sinfi müxtəlifdirsə mövzu testi tapşırığı şagirdin öz sinfinə görə ayrı fayldan (eyni mövzu, öz sinfi); tapılmırsa
  ümumi fayl + qeyd.

## 3. Bank boşluqları hesabatı
`GET /api/bank/coverage?program_id=` (müəllim/admin) və skript `scripts/bank_coverage.py`: proqramın hər mövzusu üçün sinif + tapılan
fayl + uyğunluq balı; «yoxdur» siyahısı sinif üzrə. Nəticə ilə V–VIII «Sinif testləri» PDF-lərinin banka yazılması ayrıca kartla
planlaşdırılır (pdf-oxuyucu → cavab-yoxlayici → yigici; AZ/RU/EN).

## 4. UI
- Plan dərsində test nişanı: «V sinif · P001 · Natural ədədlər» (sinif rəngli çip); sinfi dərsin sinfindən fərqlidirsə qırmızı ⚠.
- Test seçimi pəncərəsində süzgəc: «Dərsin sinfi (V)» defolt, «Bütün siniflər» əl ilə.
- Proqram önbaxışında xülasə: «Testlər: 74/83 mövzu tapıldı · 9 yoxdur (VII – 5, VIII – 4)».

## 5. Testlər (`tests/test_bank_grade_match.py`)
1. IX hazırlıq kursu: «V sinif: …» dərsinə yalnız `grades ∋ 5` fayl düşür; P007 faylı düşmür.
2. VII fərdi qrup + «Sinif testləri – VII»: KSQ/BSQ yoxdur, testlər VII sinif fayllarından.
3. Məktəb X sinfi: nəticə köhnə ilə eyni (reqressiya).
4. Əl ilə seçilmiş link yenidən tətbiqdən sonra qalır.
5. IX mövzusunda variant C istənəndə – A + öz rəqəmləri (kitabda C yoxdur).
6. Uyğunsuzluq xəbərdarlığı: VII qrup + Buraxılış IX.

## 6. Əlavələr (metodist təklifi)
1. **Giriş diaqnostikası sinif üzrə**: hazırlıq kursunun ilk görüşü – V…IX hər sinifdən 3–4 sual; nəticə sinif üzrə xəritə
   («V – 90%, VI – 85%, VII – 40% …») və zəif sinfin bölmələrinə əlavə görüş təklifi.
2. **Şagird kartında sinif üzrə irəliləyiş**: hazırlıq şagirdi üçün «V–IX mənimsəmə» zolağı (mövzu testi ballarından).
3. **Sinfə görə çətinlik**: aralıq sınaqda suallar keçilən siniflərdən mütənasib (V–VI 30%, VII 30%, VIII–IX 40% – tənzimlənir).
4. **Köçürmə qorunması**: eyni qrupda eyni testi təkrar yazanda – öz rəqəmləri variantı avtomatik (reqem_variantlari/avto_reqem).
5. **Bank etiketinin yoxlanması**: `grades` boş və ya mənbə ilə ziddiyyətli fayllar admin üçün «Yoxlanmalı» siyahısında.

## 7. Qəbul meyarları
- Hazırlıq kursunda heç bir dərsə öz sinfindən başqa sinfin testi avtomatik qoşulmur (testlə yoxlanıb).
- V–VIII qruplarda bankda olan testlər avtomatik qoşulur; olmayanlar hesabatda görünür.
- Məktəb siniflərində reqressiya yoxdur; əl ilə seçilmiş linklər saxlanılır.
- Fərdi qrupda summativ (KSQ/BSQ) yoxdur; variantlar kitabdakı real saya uyğundur.
- Yeni mətnlər AZ/EN/RU; aid testlər + `npm run build` keçir.

**İcra ardıcıllığı (kodcu, ayrıca commit-lər):** 2.1 → 2.2 (+ testlər 1, 3, 4) → 2.4 → 2.3 → 3 → 4 → seçilən əlavələr.
Ferdi-perspektiv-plan promtu ilə birlikdə icra olunursa: əvvəl o promtun §2 (görüş vahidi), sonra bu promt, sonra onun §4 (plan şablonu).
