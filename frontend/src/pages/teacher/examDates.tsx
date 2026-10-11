// Sınaq təyin edəndə tarix filtri (docs/sinaq-tarix-sinif-tekrar-promtu.md §2): sınağın KEÇİRİLDİYİ tarix üzrə
// Hamısı · İl · Ay · Həftə · Gün + ‹ › dövr keçidi. Tarix etiketdən gəlir (held_on, dəqiqlik: day | month | year).
// İl – təqvim ili (2025, 2026), tədris ili deyil. Gün/həftə yalnız günü bilinən sınaqları, ay – günü və ya ayı bilinənləri göstərir.
import { useMemo, useState } from 'react'
import { Chips, MONTHS } from '../../ui'

export type Dated = { held_on?: string | null; held_prec?: 'day' | 'month' | 'year' | null }
type Mode = 'all' | 'year' | 'month' | 'week' | 'day'
const RANK = { year: 1, month: 2, day: 3 } as const
const NEED: Record<Exclude<Mode, 'all'>, number> = { year: 1, month: 2, week: 3, day: 3 }
const ld = (s: string) => { const [y, m, d] = s.slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d) }
const dd = (d: Date) => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`

function range(m: Mode, a: Date): [Date, Date] | null {
  const y = a.getFullYear(), mo = a.getMonth()
  if (m === 'year') return [new Date(y, 0, 1), new Date(y + 1, 0, 1)]
  if (m === 'month') return [new Date(y, mo, 1), new Date(y, mo + 1, 1)]
  if (m === 'week') { const s = new Date(y, mo, a.getDate() - ((a.getDay() + 6) % 7)); return [s, new Date(s.getFullYear(), s.getMonth(), s.getDate() + 7)] }
  if (m === 'day') return [new Date(y, mo, a.getDate()), new Date(y, mo, a.getDate() + 1)]
  return null
}

/** Sınağın tarixi – dəqiqliyə görə: «27.09.2026», «sentyabr 2026», «2026». */
export function heldLabel(x: Dated): string | null {
  if (!x.held_on) return null
  const d = ld(x.held_on)
  return x.held_prec === 'year' ? String(d.getFullYear()) : x.held_prec === 'month' ? `${MONTHS[d.getMonth()]} ${d.getFullYear()}` : dd(d)
}

/** Tarix filtri: { bar – filtr sırası, fits – fayl uyğundurmu, sort – tarixə görə (yenidən köhnəyə; tarixsizlər sonda) }. */
export function useExamDates<T extends Dated>(items: T[]) {
  const [mode, setMode] = useState<Mode>('all')
  const latest = useMemo(() => items.filter(x => x.held_on && x.held_prec === 'day').map(x => x.held_on!).sort().pop(), [items])
  const [anchor, setAnchor] = useState<Date | null>(null)
  const a = anchor || (latest ? ld(latest) : new Date())
  const r = range(mode, a)
  const fits = (x: T) => {
    if (!r) return true
    if (!x.held_on || !x.held_prec || RANK[x.held_prec] < NEED[mode as Exclude<Mode, 'all'>]) return false
    const d = ld(x.held_on)
    return d >= r[0] && d < r[1]
  }
  const sort = (list: T[]) => [...list].sort((p, q) => (q.held_on || '').localeCompare(p.held_on || ''))
  const shift = (dir: 1 | -1) => r && setAnchor(dir > 0 ? r[1] : new Date(r[0].getTime() - 86400000))
  const label = !r ? '' : mode === 'year' ? String(r[0].getFullYear()) : mode === 'month' ? `${MONTHS[r[0].getMonth()]} ${r[0].getFullYear()}`
    : mode === 'day' ? dd(r[0]) : `${dd(r[0]).slice(0, 5)} – ${dd(new Date(r[1].getTime() - 86400000))}`
  const n = items.filter(fits).length
  const bar = (
    <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
      <span className="small muted">Sınağın tarixi</span>
      <Chips label="Sınağın tarixi" value={mode} onChange={m => { setMode(m); setAnchor(null) }}
        options={[['all', 'Hamısı'], ['year', 'İl'], ['month', 'Ay'], ['week', 'Həftə'], ['day', 'Gün']]} />
      {r && <><button type="button" className="btn sm" aria-label="Əvvəlki dövr" onClick={() => shift(-1)}>‹</button>
        <b className="small">{label}</b>
        <button type="button" className="btn sm" aria-label="Növbəti dövr" onClick={() => shift(1)}>›</button>
        <span className="small muted">{n} sınaq</span></>}
    </div>
  )
  return { bar, fits, sort, mode }
}
