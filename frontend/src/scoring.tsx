// 100 ballıq sistem (docs/yuz-balliq-sistem-promtu.md) – serverdəki app/domain/scoring.py ilə EYNİ qayda (önbaxış üçün;
// son söz serverindir: «Avto» çətinlik statistikadan gələ bilər).
import { Pill } from './ui'

export type Level = 'asan' | 'orta' | 'çətin'
const TYPE_W: Record<string, number> = { mcq: 1, open: 1.5 }
const DIFF_W: Record<Level, number> = { asan: 1, orta: 1.5, 'çətin': 2 }
type QLike = { kind: 'mcq' | 'open'; difficulty?: Level | null; raw?: any }

export const levelOf = (q: QLike): [Level, 'müəllim' | 'avto'] =>
  q.difficulty ? [q.difficulty, 'müəllim'] : [(q.raw?.difficulty_auto as Level) || (q.kind === 'open' ? 'orta' : 'asan'), 'avto']

/** Ballar (cəmi 100, 0,5-ə yuvarlaq, qalıq ən böyük ballara). */
export function previewPoints(qs: QLike[]): number[] {
  if (!qs.length) return []
  const ws = qs.map(q => (TYPE_W[q.kind] || 1) * DIFF_W[levelOf(q)[0]])
  const total = ws.reduce((a, b) => a + b, 0)
  const pts = ws.map(w => Math.max(0.5, Math.round((100 * w / total) * 2) / 2))
  let diff = Math.round((100 - pts.reduce((a, b) => a + b, 0)) * 2) / 2
  const order = pts.map((p, i) => [p, i]).sort((a, b) => b[0] - a[0]).map(x => x[1])
  for (let k = 0; Math.abs(diff) >= 0.5 && k < 10 * pts.length; k++) {
    const i = order[k % order.length], step = diff > 0 ? 0.5 : -0.5
    if (pts[i] + step >= 0.5) { pts[i] += step; diff -= step }
  }
  return pts
}

export const fmtPts = (p: number | null | undefined) => (p == null ? '—' : String(p).replace('.', ','))

/** Sualın sətrində: çətinlik seçimi (Avto / Asan / Orta / Çətin) və bal. */
export function QPoints({ q, pts, onLevel }: { q: QLike; pts: number; onLevel?: (l: Level | null) => void }) {
  const [lvl, src] = levelOf(q)
  return (
    <span className="row" style={{ gap: 4, flexWrap: 'nowrap' }} onClick={e => e.stopPropagation()}>
      {onLevel && <select className="grade-sel" aria-label="Çətinlik" title="Çətinlik – balı müəyyən edir (avto: statistika və ya sual növü)"
        value={q.difficulty || ''} onChange={e => onLevel((e.target.value || null) as Level | null)}>
        <option value="">avto ({lvl})</option><option value="asan">asan</option><option value="orta">orta</option><option value="çətin">çətin</option>
      </select>}
      <Pill tone={src === 'müəllim' ? 'acc' : undefined}>{fmtPts(pts)} bal</Pill>
    </span>
  )
}

/** Siyahının başında: cəmi 100 bal və bölgü. */
export function PointsSummary({ qs }: { qs: QLike[] }) {
  if (!qs.length) return null
  const pts = previewPoints(qs)
  const sum = (k: string) => fmtPts(qs.reduce((a, q, i) => a + (q.kind === k ? pts[i] : 0), 0))
  return <p className="small muted" style={{ margin: '0 0 6px' }}>Cəmi <b>100 bal</b> · qapalı {sum('mcq')} · açıq {sum('open')} bal.
    Bal sualın növü (açıq ×1,5) və çətinliyinə (orta ×1,5, çətin ×2) görə; «avto» – şagird nəticələrinin statistikası, yoxdursa növ.</p>
}
