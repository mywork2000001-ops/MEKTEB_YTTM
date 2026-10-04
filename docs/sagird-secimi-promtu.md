# Tapşırıqların şagirdlər üzrə təyini – mövzu testləri və sınaqlar (04.10.2026)

**Rol.** Sən «Müəllim köməkçisi»nin baş mühəndisi və təlim metodistisən. Məqsəd: müəllim mövzu testini və sınağı
**bütün sinfə, səviyyə qrupuna və ya seçdiyi ayrı-ayrı şagirdlərə** verə bilsin (differensial yanaşma, xəstə/gəlməyən
şagirdə sonradan, zəif nəticəlilərə təkrar). Eyni seçim üsulu bütün tapşırıq növlərində eyni görünsün.

## 0. Mövcud vəziyyət (audit)
| Yer | Backend | İnterfeys |
|---|---|---|
| Adi tapşırıq (Onlayn tapşırıqlar) | `student_ids` ✔ | «Kimə» ✔ (`TargetPicker`), amma redaktədə hazırkı seçim göstərilmir – «Hamı» görünür |
| Mövzu testi (Perspektiv plan → 🧪 Test) | `student_ids` ✔, `levels` ✔ | yalnız «bütün sinif / Zəif / Orta / Güclü qrup» – tək-tək şagird yoxdur |
| Sınaq (Sınaq imtahanları) | `student_ids` ✔ | **heç bir seçim yoxdur** – həmişə bütün sinif |
| Yenidən göndər | `student_ids` ✔ | seçim yoxdur – həmişə bütün sinif |
| Redaktə (auditoriyanı dəyiş) | `PATCH student_ids` ✔ | başlamış şagirdi çıxarmağa icazə verir – nəticəsi siyahıdan itir |

## 1. Sabit qaydalar
- `student_ids = None` – bütün sinif/qrup (sonradan sinfə əlavə olunan şagird də görür); siyahı – yalnız onlar.
- Şagird yalnız ona təyin olunmuş testi portalda görür, link ilə də aça bilmir (mövcud qayda saxlanılır).
- Səviyyə qrupları – Jurnal → «Səviyyə qrupları» (`LevelOverride`); şagird səviyyə adını görmür.
- Jurnala avtomatik yazı və reytinq yalnız təhvil verənlər üzrədir – seçim bunu dəyişmir.
- Məkanlar qarışmır (`_can_target`, `ws_cond`); admin sınaqda başqa müəllimin sinfini də seçə bilər.

## 2. Ümumi «Kimə» seçicisi (`StudentPicker`, frontend/src/pages/teacher/common.tsx)
- Mənbə: `GET /api/exams-online/targets/{ta_id}/students` → `[{id, full_name, portal_code, level}]` (icazə – `_can_target`).
- Rejimlər: **Hamı** · **Səviyyə qrupları** (Zəif / Orta / Güclü – bir neçəsi birlikdə, sayları ilə) · **Seçilmiş**
  (axtarış, «Hamısını seç», «Təmizlə», səviyyə nişanı) · istəyə görə **hazır siyahılar** (məs. «Yazmayanlar», «50%-dən aşağı»).
- Altda yekun: «18 şagirddən 7-si». `value` ilə ilkin seçim (redaktə üçün). Səviyyəsi olmayan şagird qrup rejimində düşmür – xəbərdarlıq.

## 3. Mövzu testi
- Hər sinif sətrində «Kimə» – `StudentPicker`; nəticə `targets[].student_ids` (Hamı → `null`).
- Səviyyə variantlı testdə də seçim işləyir: seçilən şagirdlər öz səviyyəsinin variantını alır.

## 4. Sınaq imtahanı
- Hər seçilmiş sinifdə «Kimə» (default – Hamı). Admin başqa müəllimin sinfində də seçə bilir.
- Nəticə və reytinq yalnız təyin olunanlar üzrə (mövcud `student_ids` filtri).

## 5. Redaktə – auditoriyanı dəyişmək
- Redaktə pəncərəsi hazırkı seçimi göstərir (indi «Hamı» görünür – səhv).
- Backend: testə başlamış və ya təhvil vermiş şagirdi auditoriyadan çıxarmaq olmaz – 409
  «… artıq başlayıb – çıxarmaq olmaz (nəticəsi itər)». Əlavə etmək həmişə olar.

## 6. Yenidən göndər – kimə
- «Yenidən göndər» pəncərəsində (həmin sinfə) «Kimə»: Hamı / **Yazmayanlar** (başlamayan + təhvil verməyən) /
  **Nəticəsi 50%-dən aşağı** / Səviyyə / Seçilmiş. Siyahılar həmin testin nəticələrindən hesablanır.
- Nəticələr pəncərəsində (Canlı izlə) – «Yazmayanlara yenidən göndər» düyməsi (test bağlanandan sonra).

## Qəbul meyarları
- Testlər: sınaqda seçilmiş şagirdlər (başqası portalda görmür); şagird siyahısı endpoint-i icazəsi; başlamış şagirdi
  çıxarmaq 409; mövzu testində seçim + variant.
- `npx tsc -b` və `npm run build` təmiz; bütün backend testləri keçir.
