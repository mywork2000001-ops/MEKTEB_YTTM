// Rəsmi sənəd konteksti (girişdə /api/auth/me-dən): məktəbin adı və imza verənlər.
// Ayrıca modul – print.ts (KaTeX ilə ağır) əsas paketə düşməsin.
export const DEFAULT_SCHOOL = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi'
export const docCtx = { school: DEFAULT_SCHOOL, deputy: '', director: '' }
export function setDocContext(school?: string | null, doc?: { deputy?: string | null; director?: string | null } | null) {
  docCtx.school = school?.trim() || DEFAULT_SCHOOL
  docCtx.deputy = doc?.deputy?.trim() || ''
  docCtx.director = doc?.director?.trim() || ''
}
