# OpenRouter: KSQ/BSQ cavab kartlarının yoxlanması (13.10.2026)

**Qayda (istifadəçi):** API açarı **yalnız yoxlama** üçündür (kart şəklini oxumaq). Testlərin təyini açarsız işləyir: suallar seçilmiş
layihələrdən (bank mənbələri) mövzular üzrə avtomatik götürülür, lazım olsa başqa layihə qoşulur.

## Necə işləyir (kod: `backend/app/domain/ksq_reader.py`)
1. Açar axtarışı: `MK_ANTHROPIC_API_KEY` → müəllimin «Süni intellekt» ayarı → məktəb admininin ayarı. Provayder `openrouter` və ya `anthropic`.
2. OpenRouter: `POST https://openrouter.ai/api/v1/chat/completions`, şəkil `data:image/jpeg;base64,…` (yalnız adsız cavab zonası),
   məcburi funksiya `submit_card` → `{answers:[{slot, value, confidence}]}`; `temperature 0`.
3. Model: ayardakı model şəkil oxuyursa (Claude, Gemini, GPT-4o/5, VL) – o; **OpenRouter preseti** (`@preset/ad`) olduğu kimi;
   şəkil oxumayan model (məs. DeepSeek) seçilibsə – avtomatik `anthropic/claude-sonnet-4.5`.
4. Etibar < 0,85 olan xanalar eyni modellə ikinci dəfə ayrıca oxunur; yenə aşağıdırsa – sarı, müəllim düzəldir.
5. Bal serverdə hesablanır (Claude/OpenRouter yalnız oxuyur).

## İstifadəçinin bir dəfəlik addımları
1. openrouter.ai → Keys → «Create key» (limit qoyun, məs. 5 $/ay).
2. İstəyə görə: Presets → yeni preset (model: `anthropic/claude-sonnet-4.5` və ya `google/gemini-2.5-flash`, temperature 0).
3. Müəllim köməkçisi → Tənzimləmələr → «Süni intellekt»: Xidmət **OpenRouter**, Model – siyahıdan və ya `@preset/ad`, açarı yapışdırın,
   «Bağlantını yoxla». Admin daxil etsə – bütün müəllimlər üçün işləyir.

## Xərc (təxmini)
Bir kart ≈ 1 sorğu (şəkil ~1200×500 px) + şübhəli xanalar üçün ikinci sorğu. «Resurslar» panelində bu ay oxunan kartların sayı görünür.
