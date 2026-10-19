# MASTER PROMT · Yazılı testlər, ümumi cavab vərəqəsi, «📷 Skan», hər şagirdə öz rəqəmləri (19.10.2026)

**İstifadəçi tələbi (19.10.2026, tam icazə – miqrasiya, deploy daxil):** «Hər mövzu testi və sınaq üçün, məktəb və fərdi
siniflərdə – bir ümumi çap forması; yuxarıda yazılan hər şey; ardıcıl icra et.»
**Səbəb:** (1) XI-P sinfində KSQ-də şagirdlər bir-birindən köçürdü (hamıya eyni suallar); (2) fərdi sinifdə yazılı imtahan
keçirmək olmadı – test/sınaq üçün kağız rejimi və cavab kartı yox idi, müəllim onlayn keçirdi; (3) skan üçün hər dəfə Jurnala girmək.

Detallı spesifikasiyalar (bu promtun hissələri):
- docs/reqem-variantlari-promtu.md – parametrli suallar, hər şagirdə öz ədədləri (sympy, açar yoxlaması);
- docs/yazili-sinaq-ve-skan-duymesi-promtu.md – yazılı rejim, ümumi vərəqə, «📷 Skan»;
- docs/ferdi-yazili-imtahan-promtu.md – arxiv (birləşdirildi).

## Rol
Sən «Müəllim köməkçisi»nin baş mühəndisi və qiymətləndirmə metodistisən. Mövcud KSQ kart/QR/skan/oxuyucu
mexanizmini (`ksq_card`, `ksq_scan`, `ksq_reader`, `exam_scans`, `ExamVariant`) **təkrar istifadə et** – paralel sistem qurma.

## Sabit qaydalar
- **Hər** test növü: mövzu testi, sınaq (DİM), sərbəst yazılı iş, KSQ, BSQ – **bir ümumi cavab vərəqəsi** şablonu.
- **Hər** məkan: məktəb sinfi, qrup, fərdi (repetitor) sinif – eyni funksiyalar; fərdi nəticələr məktəb hesabatına düşmür.
- Perspektiv plan olmadan da işləyir (mövzu/bank faylı əl ilə seçilir); KSQ/BSQ qaydaları (`has_summative`, yarımil) dəyişmir.
- Bütün yeni mətnlər AZ/EN/RU; rəsmi sənədlər yalnız AZ. Açıq cavab kart formatı: `0-9 - , / ;`, ≤ 8 simvol.
- Canlı DB-yə yazmazdan əvvəl Neon backup / branch; miqrasiya geri qaytarıla bilən (downgrade) olsun.

## Ardıcıllıq (hər addım: test → kod → `pytest` aid testlər → `npm run build` → commit)
| № | İş | İcraçı | Vəziyyət |
|---|---|---|---|
| 1 | `backend/scripts/reqem_variantlari.py` – müstəqil skript, şablon JSON, açar yoxlaması, A4 + açar + `variants.json` | kodcu | icrada |
| 2 | «📷 Skan» düyməsi hər səhifədə + `POST /api/scans/any` (QR → imtahan + şagird, 403, əl ilə seçim) | kodcu | icrada |
| 3 | Yazılı rejim: «Onlayn / Yazılı / İkisi də» – hər mövzu testi və sınaqda, məktəb + fərdi; `Exam.kind` TEST/SINAQ/YI + miqrasiya | kodcu | icrada |
| 4 | Ümumi A4 cavab vərəqəsi (başlıq, QR, A–E, 8 xana, «Müəllim balı» 0·¼·½·¾·1, oriyentirlər, adlı/boş) + ayrıca sual kitabçası; KSQ kartı da bu şablonla; `ksq_reader` – `score` slotu | kodcu | icrada |
| 5 | Rəqəmlər tətbiqdə: `BankQuestion.template` (miqrasiya), seçim «Hər şagirdə öz rəqəmləri» – KSQ, test, sınaqda; retake yeni ədədlər | kodcu | gözləyir 1 |
| 6 | Şablonlar: XI-P KSQ mövzuları + P013 XI (Çoxhədlilər A/B), sonra digər siniflər – `cavab-yoxlayici`, skript `--check` | cavab-yoxlayici | gözləyir 5 |
| 7 | Review (Claude), main-ə birləşmə, Neon backup, miqrasiya, push, Render statusu, Chrome-da yoxlama (1396×663, telefon) | Claude | sonda |

## Qəbul meyarları (ümumi)
- Məktəb və fərdi sinifdə: mövzu testi və sınaq yazılı təyin olunur → kitabça + hər şagirdin vərəqəsi (QR) + açar çap olunur →
  «📷 Skan» ilə istənilən səhifədən skan → nəticə testin nəticələrində (seçilibsə – jurnalda).
- «Hamıya eyni, rəqəmlər fərqli» rejimində 25 şagirdin heç ikisinin ədədləri və açarı eyni deyil; hər şablon mənbə cavabını verir.
- Vərəqədə test dairələri, 8 xana, müəllim balı oxunur; boş forma əl ilə şagird seçimi ilə qəbul olunur.
- Köhnə KSQ/BSQ kart, skan, apelyasiya testləri keçir; `npm run build` uğurlu; deploy success; RU/EN mətnlər qarışıqsız.
- HANDOFF-a sətir; worktree və budaqlar birləşmədən sonra silinir.
