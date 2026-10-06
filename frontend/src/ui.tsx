// Ümumi UI komponentləri – maketin CSS sinifləri ilə.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ICONS } from './icons-data'
import { ApiError } from './api'
import { useT } from './i18n'
import { docCtx } from './doccontext'

export function Icon({ name, className = 'ico' }: { name: string; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: ICONS[name] || '' }} />
}

export function Pill({ tone, children }: { tone?: 'ok' | 'warn' | 'bad' | 'info' | 'acc'; children: ReactNode }) {
  return <span className={'pill' + (tone ? ' ' + tone : '')}>{children}</span>
}

export const levelTone = (l?: string | null) => (l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : l === 'Orta' ? 'warn' : undefined)
export const riskTone = (s?: string) => (s === 'Qırmızı' ? 'bad' : s === 'Sarı' ? 'warn' : 'ok')
export const gradeTone = (g?: number | null) => (g == null ? undefined : g >= 5 ? 'ok' : g === 4 ? 'info' : g === 3 ? 'warn' : 'bad')

/** Azərbaycan sıra sayı: 1-ci, 2-ci, 3-cü, 4-cü, 5-ci, 6-cı, 7-ci, 8-ci, 9-cu, 10-cu, 20-ci, 40-cı, 100-cü. */
export const ord = (v: number | string) => {
  const n = Number(v)
  const last: Record<number, string> = { 1: 'ci', 2: 'ci', 3: 'cü', 4: 'cü', 5: 'ci', 6: 'cı', 7: 'ci', 8: 'ci', 9: 'cu' }
  const tens: Record<number, string> = { 0: 'cı', 10: 'cu', 20: 'ci', 30: 'cu', 40: 'cı', 50: 'ci', 60: 'cı', 70: 'ci', 80: 'ci', 90: 'cı' }
  return `${n}-${n % 10 ? last[n % 10] : n % 100 === 0 && n ? 'cü' : tens[n % 100]}`
}
/** Dərsin «nə vaxt» yazısı: məktəbdə «3-cü saat», fərdi hazırlıqda (məktəb zəngi yoxdur) – real vaxt «17:00–18:30». */
export const lessonWhen = (period: number | string, time?: string | null) =>
  docCtx.private && time ? time : `${ord(period)} saat`
export const fmt = (v: number | null | undefined, d = 1) => (v == null ? '—' : v.toFixed(d).replace('.', ','))
export const fmtDate = (s?: string | null) => (s ? s.slice(0, 10).split('-').reverse().join('.') : '—')
export const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
export const WD = ['B.', 'B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.', 'Ş.']
export const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr']
export const longDate = (s: string) => { const d = new Date(s + 'T00:00'); return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` }

/** Filtrli ekranlarda yuxarıda seçim edilənə qədər aşağı hissə boş qalır. */
export function PickFirst({ text = 'Yuxarıda seçim edin' }: { text?: string }) {
  const t = useT()
  return <div className="empty"><Icon name="info" /><p>{t(text)}</p></div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function Loading() {
  return <div className="empty" aria-busy="true">Yüklənir…</div>
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  const m = error instanceof ApiError ? error.message : String(error)
  return <div className="banner" style={{ background: 'var(--bad-soft)', color: 'var(--bad)' }} role="alert"><Icon name="info" />{m}</div>
}

/** Sadə yükləmə hook-u: [data, error, loading, reload]. */
/** Telefon ekranı (≤ 700px) – cədvəl əvəzinə kart/gün görünüşü üçün. */
export function useNarrow(): boolean {
  const q = '(max-width: 700px)'
  const [n, setN] = useState(() => typeof matchMedia !== 'undefined' && matchMedia(q).matches)
  useEffect(() => {
    const m = matchMedia(q); const f = () => setN(m.matches)
    m.addEventListener('change', f); return () => m.removeEventListener('change', f)
  }, [])
  return n
}

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]): [T | undefined, unknown, boolean, () => void] {
  const [data, setData] = useState<T>()
  const [err, setErr] = useState<unknown>()
  const [loading, setLoading] = useState(true)
  const [n, setN] = useState(0)
  useEffect(() => {
    let live = true
    setLoading(true)
    setErr(undefined)
    fn().then(d => { if (live) setData(d) }, e => { if (live) setErr(e) }).finally(() => { if (live) setLoading(false) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n])
  return [data, err, loading, useCallback(() => setN(x => x + 1), [])]
}

// ---------------------------------------------------------------- bildiriş (toast)
let toastFn: ((m: string) => void) | null = null
export const toast = (m: string) => toastFn?.(m)
export function ToastHost() {
  const [msg, setMsg] = useState<string | null>(null)
  const t = useRef<number>(0)
  useEffect(() => {
    toastFn = m => { setMsg(m); clearTimeout(t.current); t.current = window.setTimeout(() => setMsg(null), 2600) }
    return () => { toastFn = null }
  }, [])
  return msg ? <div className="toast" role="status">{msg}</div> : null
}

// ---------------------------------------------------------------- yan pəncərə (telefonda aşağıdan)
export function Drawer({ title, onClose, children, footer }: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', k)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', k); document.body.style.overflow = '' }
  }, [onClose])
  return createPortal(
    <div className="scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <section className="drawer" role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined}>
        <span className="grab" />
        <header><h2>{title}</h2><button className="btn ghost sm" onClick={onClose} aria-label="Bağla">✕</button></header>
        <div className="body">{children}</div>
        {footer && <footer>{footer}</footer>}
      </section>
    </div>, document.body)
}

/** Silmə/arxiv: adı yazaraq təsdiq. */
export function ConfirmName({ name, action, onConfirm, onCancel }: { name: string; action: string; onConfirm: (typed: string) => Promise<void> | void; onCancel: () => void }) {
  const [v, setV] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>()
  const ok = v.trim().replace(/\s+/g, ' ').toLocaleLowerCase('az') === name.trim().replace(/\s+/g, ' ').toLocaleLowerCase('az')
  return (
    <div className="confirm">
      <span>{action} üçün adı yazın: <b>{name}</b></span>
      <input className="sel" style={{ flex: '1 1 200px' }} value={v} onChange={e => setV(e.target.value)} aria-label="Təsdiq üçün ad" autoFocus />
      <button className="btn danger sm" disabled={!ok || busy} onClick={async () => { setBusy(true); try { await onConfirm(v) } catch (e) { setErr(e) } finally { setBusy(false) } }}>{action}</button>
      <button className="btn ghost sm" onClick={onCancel}>Ləğv et</button>
      <ErrorBox error={err} />
    </div>
  )
}

export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label?: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, l]) => <button key={v} type="button" aria-pressed={v === value} onClick={() => onChange(v)}>{l}</button>)}
    </div>
  )
}

export function Field({ label, hint, error, full, children }: { label: string; hint?: string; error?: string; full?: boolean; children: ReactNode }) {
  return (
    <label className={'f' + (full ? ' full' : '')}>
      {label}{children}
      {hint && <span className="hint">{hint}</span>}
      {error && <span className="err">{error}</span>}
    </label>
  )
}

export function Top({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  const t = useT()
  return <div className="top"><div><h1>{typeof title === 'string' ? t(title) : title}</h1>{sub && <p>{sub}</p>}</div>{actions && <div className="actions">{actions}</div>}</div>
}

export function Stat({ value, label }: { value: ReactNode; label: string }) {
  return <div className="kpi"><b>{value}</b><span>{label}</span></div>
}

/** Async düymə: basılanda gözləyir, xətanı bildirişlə göstərir. */
export function AsyncBtn({ onClick, children, className = 'btn', disabled, ok }: { onClick: () => Promise<unknown>; children: ReactNode; className?: string; disabled?: boolean; ok?: string }) {
  const [busy, setBusy] = useState(false)
  return (
    <button className={className} disabled={disabled || busy} onClick={async () => {
      setBusy(true)
      try { await onClick(); if (ok) toast(ok) } catch (e) { toast(e instanceof ApiError ? e.message : 'Xəta baş verdi') } finally { setBusy(false) }
    }}>{busy ? '…' : children}</button>
  )
}

/** Tarix/saat – brauzerin «az» lokalından asılı olmadan (bəzi brauzerlər «10-06» verir): 06.10.2026 15:00.
 *  Ay adı (month: 'long') və həftə günü Intl-dən, rəqəmlər əl ilə. */
export function azDT(v: Date | string | number, o?: Intl.DateTimeFormatOptions, mode: 'all' | 'date' | 'time' = 'all'): string {
  const d = v instanceof Date ? v : new Date(v)
  if (isNaN(+d)) return '—'
  const opts: Intl.DateTimeFormatOptions = o ?? (mode === 'time' ? { hour: '2-digit', minute: '2-digit' }
    : mode === 'date' ? { day: '2-digit', month: '2-digit', year: 'numeric' } : { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  const pad = (n: number) => String(n).padStart(2, '0')
  let date = ''
  if (opts.month === 'long' || opts.month === 'short') {
    const name = (k: 'month' | 'weekday', f: string) => new Intl.DateTimeFormat('az', { [k]: f }).format(d)
    date = [opts.weekday ? name('weekday', opts.weekday as string) + ',' : '', opts.day ? String(d.getDate()) : '', name('month', opts.month),
      opts.year ? String(d.getFullYear()) : ''].filter(Boolean).join(' ')
  } else if (opts.day || opts.month || opts.year) {
    date = [opts.day ? pad(d.getDate()) : '', opts.month ? pad(d.getMonth() + 1) : '', opts.year ? String(d.getFullYear()) : ''].filter(Boolean).join('.')
  }
  const time = opts.hour ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : ''
  return [date, time].filter(Boolean).join(' ')
}

/** Açılma – bağlanma: eyni gündürsə «06.10 16:32 – 18:32», yoxsa «06.10 16:32 – 07.10 18:32» (bağlanma tarixi itməsin). */
export function azRange(a: string | Date, b: string | Date): string {
  const x = new Date(a), y = new Date(b)
  const dm: Intl.DateTimeFormatOptions = { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }
  return `${azDT(x, dm)} – ${x.toDateString() === y.toDateString() ? azDT(y, { hour: '2-digit', minute: '2-digit' }) : azDT(y, dm)}`
}

/** «IV BÖLMƏ – FAİZ. NİSBƏT» → «IV bölmə – Faiz. Nisbət» (böyük hərflə yazılmış bölmə adı oxunaqlı olsun). */
export const prettySection = (s: string) => s.replace(/\s+/g, ' ').trim().split(' – ').map((part, i) => {
  if (i === 0) return part.replace(/BÖLMƏ/i, 'bölmə')
  if (part !== part.toLocaleUpperCase('az')) return part
  const low = part.toLocaleLowerCase('az')
  return low.replace(/(^|[.!?]\s+)(\p{L})/gu, (_, a, c) => a + c.toLocaleUpperCase('az'))
}).join(' – ')
