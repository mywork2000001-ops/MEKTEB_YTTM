// API müştərisi: kuki ilə sessiya, JSON, xətaların Azərbaycan dilində göstərilməsi, Tənzimləmələr açarı.

export class ApiError extends Error {
  status: number
  data: unknown
  constructor(status: number, message: string, data?: unknown) {
    super(message)
    this.status = status
    this.data = data
  }
}

const SETTINGS_KEY = 'mk-settings-token'

export function settingsToken(): string | null {
  try { return sessionStorage.getItem(SETTINGS_KEY) } catch { return null }
}
export function setSettingsToken(t: string | null) {
  try { t ? sessionStorage.setItem(SETTINGS_KEY, t) : sessionStorage.removeItem(SETTINGS_KEY) } catch { /* noop */ }
}

function message(status: number, data: any): string {
  const d = data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && !Array.isArray(d) && d.message) return d.message
  if (Array.isArray(d)) {
    // Pydantic: ilk xətanı insan dilində
    const e = d[0]
    const msg = String(e?.msg || '').replace(/^Value error, /, '')
    const field = Array.isArray(e?.loc) ? e.loc.slice(1).join('.') : ''
    return field ? `${field}: ${msg}` : msg || 'Məlumat düzgün deyil'
  }
  if (status === 401) return 'Daxil olun'
  if (status === 403) return 'Bu bölmə sizin üçün deyil'
  if (status === 404) return 'Tapılmadı'
  if (status >= 500) return 'Serverdə xəta baş verdi. Bir az sonra yenidən yoxlayın'
  return 'Xəta baş verdi'
}

type Opts = { method?: string; body?: unknown; form?: FormData; params?: Record<string, unknown> }

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const url = new URL(path, location.origin)
  for (const [k, v] of Object.entries(opts.params || {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  }
  const headers: Record<string, string> = {}
  const tok = settingsToken()
  if (tok) headers['X-Settings-Token'] = tok
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  let res: Response
  try {
    res = await fetch(url.pathname + url.search, { method: opts.method || (body ? 'POST' : 'GET'), headers, body, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'İnternet bağlantısı yoxdur')
  }
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('application/json') ? await res.json().catch(() => null) : null
  if (!res.ok) {
    if (res.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/me') window.dispatchEvent(new Event('mk-unauth'))
    throw new ApiError(res.status, message(res.status, data), data)
  }
  return data as T
}

export const get = <T = any>(p: string, params?: Record<string, unknown>) => api<T>(p, { params })
export const post = <T = any>(p: string, body?: unknown) => api<T>(p, { method: 'POST', body: body ?? {} })
export const put = <T = any>(p: string, body?: unknown) => api<T>(p, { method: 'PUT', body })
export const patch = <T = any>(p: string, body?: unknown) => api<T>(p, { method: 'PATCH', body })
export const del = <T = any>(p: string, body?: unknown, params?: Record<string, unknown>) =>
  api<T>(p, { method: 'DELETE', body, params })
