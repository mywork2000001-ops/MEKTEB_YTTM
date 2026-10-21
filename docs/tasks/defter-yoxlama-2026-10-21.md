# Kart: dəftər yoxlaması – alt mövzuların icrası (AI + əl ilə, 21.10.2026)

Tam mətn əsas checkout-dadır; icra edildi (budaq worktree-agent-aef241ef99418aa96). Metodika: `docs/defter-yoxlama-promtu.md`.

## Əlavə 21.10 – əl ilə rejim (məktəbdə müəllim dəftərə gözlə baxır)
- `Materiallar → 📓 Dəftər`: bütün sinif × alt mövzu cədvəli (telefonda üfüqi sürüşmə, sabit ad sütunu); xanaya toxunuş: boş → ✅ → 🟡 → ❌ → boş,
  🟡-də qısa şərh (səhv nömrələri). Dərhal yazılır (`PUT /api/materials/{mid}/mark`), «saxla» düyməsi yoxdur.
- Cavab göndərməyən şagirdə də işarə qoyulur: cavabsız (mətnsiz/faylsız) `MaterialSubmission` yaranır, «təhvil verib» sayılmır.
- Saxlama – AI ilə eyni `material_submissions.ai_check`; `source: 'manual'|'ai'` (sətir səviyyəsində). Əl işarəsi AI-ni üstələyir,
  AI təkrar yoxlama əl işarələrinə toxunmur.
- İtki: hər alt mövzunun icra faizi (✅ / sinif) + `GET /api/materials/{mid}/check.csv`. Şagird yalnız ÖZ statuslarını görür.
