// Dövr filtri (gün / həftə / ay / yarımil / il) + sıralama (mövzu / tarix) – onlayn test və sınaq siyahıları üçün.
// Yarımil: I – sentyabr–yanvar, II – fevral–avqust; tədris ili 1 sentyabrdan.
import { useState } from 'react'
import { Seg } from './ui'

export type Period = 'all' | 'day' | 'week' | 'month' | 'half' | 'year'
export type Sort = 'topic' | 'date'

const PERIODS: [Period, string][] = [['all', 'Hamısı'], ['day', 'Gün'], ['week', 'Həftə'], ['month', 'Ay'], ['half', 'Yarımil'], ['year', 'İl']]
const d0 = (y: number, m: number, d = 1) => new Date(y, m, d)
const dm = (d: Date) => d.toLocaleDateString('az-AZ', { day: '2-digit', month: '2-digit' })

/** [başlanğıc, son) – yerli vaxtla. */
export function periodRange(p: Period, a: Date): [Date, Date] | null {
  const y = a.getFullYear(), m = a.getMonth()
  switch (p) {
    case 'all': return null
    case 'day': return [d0(y, m, a.getDate()), d0(y, m, a.getDate() + 1)]
    case 'week': { const s = d0(y, m, a.getDate() - ((a.getDay() + 6) % 7)); return [s, d0(s.getFullYear(), s.getMonth(), s.getDate() + 7)] }
    case 'month': return [d0(y, m), d0(y, m + 1)]
    case 'half': return m >= 8 ? [d0(y, 8), d0(y + 1, 1)] : m === 0 ? [d0(y - 1, 8), d0(y, 1)] : [d0(y, 1), d0(y, 8)]
    case 'year': { const sy = m >= 8 ? y : y - 1; return [d0(sy, 8), d0(sy + 1, 8)] }
  }
}

function periodLabel(p: Period, r: [Date, Date] | null): string {
  if (!r) return 'bütün testlər'
  const [s, e] = r
  const last = new Date(e.getTime() - 86400000)
  switch (p) {
    case 'day': return s.toLocaleDateString('az-AZ', { day: '2-digit', month: 'long', year: 'numeric', weekday: 'short' })
    case 'week': return `${dm(s)} – ${dm(last)}.${last.getFullYear()}`
    case 'month': return s.toLocaleDateString('az-AZ', { month: 'long', year: 'numeric' })
    case 'half': { const sy = s.getMonth() === 8 ? s.getFullYear() : s.getFullYear() - 1; return `${s.getMonth() === 8 ? 'I' : 'II'} yarımil ${sy}/${String(sy + 1).slice(2)}` }
    default: return `${s.getFullYear()}/${String(s.getFullYear() + 1).slice(2)} tədris ili`
  }
}

const load = (k: string, d: string) => { try { return localStorage.getItem(k) || d } catch { return d } }
const save = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* yaddaş yoxdur */ } }

/** Filtr vəziyyəti: seçim cihazda yadda qalır (dövr və sıralama), tarix isə hər açılışda bu gündür. */
export function usePeriod(key: string, defSort: Sort = 'date') {
  const [period, setP] = useState<Period>(() => load(`mk-period-${key}`, 'all') as Period)
  const [sort, setS] = useState<Sort>(() => load(`mk-sort-${key}`, defSort) as Sort)
  const [anchor, setAnchor] = useState(() => new Date())
  const range = periodRange(period, anchor)
  return {
    period, sort, range, label: periodLabel(period, range),
    setPeriod: (p: Period) => { setP(p); setAnchor(new Date()); save(`mk-period-${key}`, p) },
    setSort: (s: Sort) => { setS(s); save(`mk-sort-${key}`, s) },
    shift: (dir: 1 | -1) => range && setAnchor(dir > 0 ? range[1] : new Date(range[0].getTime() - 1)),
    today: () => setAnchor(new Date()),
    /** Test dövrə düşürmü (açılma vaxtına görə). */
    has: (iso: string) => { if (!range) return true; const t = Date.parse(iso); return t >= range[0].getTime() && t < range[1].getTime() },
  }
}

export type PeriodState = ReturnType<typeof usePeriod>

/** Siyahı üstündə: sıralama, dövr, «‹ dövr ›» naviqasiyası və nəticə sayı. */
export function PeriodBar({ f, count, total, topicLabel = 'Mövzu üzrə' }: { f: PeriodState; count: number; total: number; topicLabel?: string }) {
  return (
    <div className="stack" style={{ gap: 8, margin: '4px 0 10px' }}>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <Seg label="Sıralama" value={f.sort} onChange={f.setSort} options={[['topic', topicLabel], ['date', 'Tarix üzrə']]} />
        <Seg label="Dövr" value={f.period} onChange={f.setPeriod} options={PERIODS} />
      </div>
      <div className="row" style={{ gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        {f.range && <button className="btn sm" aria-label="Əvvəlki dövr" onClick={() => f.shift(-1)}>‹</button>}
        <b className="small">{f.label}</b>
        {f.range && <button className="btn sm" aria-label="Növbəti dövr" onClick={() => f.shift(1)}>›</button>}
        {f.range && <button className="btn sm ghost" onClick={f.today}>Bu gün</button>}
        <span className="small muted grow" style={{ textAlign: 'right' }}>{count === total ? `${total} test` : `${count} / ${total} test`}</span>
      </div>
    </div>
  )
}
