# «Sinif rəhbəri» – telefon rejimi auditi (29.09.2026)

Promt: `docs/sinif-rehberi-telefon-promtu.md`. Yoxlama: Playwright, 360 və 412 px, isMobile + hasTouch, bütün 8 tab və 2 pəncərə.

| № | Tapıntı | Düzəliş |
|---|---|---|
| 1 | Gündəlik davamiyyət: geniş cədvəl, V/Q/Ü/G düymələri < 36 px, şagird siyahısı birinci ekrandan kənarda | Telefonda ayrıca görünüş: dərs saatı çipləri (fənn, 🔒, boş xana sayı) → şagirdlər üzrə 48×44 px V/Q/Ü/G, «Bütün gün…», üzrlü səbəb seçimi, valideynə 📞 zəng düyməsi |
| 2 | «Yadda saxla» yuxarıda – aşağıda işləyəndə görünmür | Dəyişiklik olanda aşağıda sabit zolaq (menyunun üstündə) |
| 3 | Başlıq çox yer tuturdu (admin qutusu, yarımil seçimi, izah) | Telefonda yalnız aid olduğu tablarda göstərilir |
| 4 | Açılışda jurnalla kilidli 1-ci saat seçilirdi | Avtomatik olaraq rəhbərin qeyd etməli olduğu ilk saat seçilir |
| 5 | Dərs cədvəli: 5 günlük cədvəl ekrana sığmırdı, sahələr kiçik idi | Gün seçimi + 8 saat, 44 px sahələr (əvvəlki düzəliş) |
| 6 | Dərslər / Qiymət cədvəli: geniş cədvəllər | Kart və siyahı görünüşü; qalan cədvəllərdə ad sütunu sabit |

Yoxlanıb, səhv deyil: pəncərələrdə (valideyn, yeni qeyd) «Yadda saxla» menyu zolağının **üstündədir** – avtomatik yoxlamanın
«gizlənir» tapıntısı ekran görüntüsü ilə təkzib olundu (qat sırası).

Nəticə: 360 və 412 px-də bütün ekranlarda enə daşma 0, 36 px-dən kiçik toxunma hədəfi 0, JS xətası 0.
