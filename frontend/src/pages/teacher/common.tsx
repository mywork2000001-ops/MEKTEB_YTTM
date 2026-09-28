import { useEffect, useState } from 'react'
import { get } from '../../api'
import { useLoad } from '../../ui'

export type MyLesson = {
  id: number; class_id: number; class_name: string; kind: string; subject: string; weekly_hours: number
  slots: Record<string, number[]>; has_summative: boolean; split_with: string | null; plan_lessons: number; lag: number; unfit: number
}

export function useMyLessons() {
  return useLoad<MyLesson[]>(() => get('/api/my/lessons'), [])
}

/** Seçim yaddaşda qalır (bölmə dəyişəndə itməsin), amma ilk açılışda boşdur – «seçənə qədər boş». */
export function usePick(key: string): [number | null, (v: number | null) => void] {
  const [v, setV] = useState<number | null>(() => {
    try { const s = sessionStorage.getItem('mk-pick-' + key); return s ? Number(s) : null } catch { return null }
  })
  useEffect(() => { try { v == null ? sessionStorage.removeItem('mk-pick-' + key) : sessionStorage.setItem('mk-pick-' + key, String(v)) } catch { /* noop */ } }, [key, v])
  return [v, setV]
}

export function LessonSelect({ lessons, value, onChange, label = 'Sinif / qrup' }: { lessons?: MyLesson[]; value: number | null; onChange: (v: number | null) => void; label?: string }) {
  return (
    <select className="sel" aria-label={label} value={value ?? ''} onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">— {label} seçin —</option>
      {(lessons || []).map(l => <option key={l.id} value={l.id}>{l.class_name}{l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : ''}</option>)}
    </select>
  )
}

export const ATT: [string, string, string][] = [['var', 'V', 'var'], ['yox', 'Q', 'yox'], ['üzrlü', 'Ü', 'uzrlu'], ['gecikdi', 'G', 'gecikdi']]
export const HW: string[] = ['etdi', 'qismən', 'etmədi', 'köçürüb']

type LevelRow = { student_id: number; full_name: string }
/** Kimə göndərilir: hamı / güclülər / ortalar / zəiflər / seçilmiş şagirdlər (differensial yanaşma). null = hamı. */
export function TargetPicker({ ta, onChange }: { ta: number; onChange: (ids: number[] | null) => void }) {
  const [levels] = useLoad<Record<string, LevelRow[]>>(() => get(`/api/analytics/${ta}/levels`), [ta])
  const [mode, setMode] = useState<'all' | 'Güclü' | 'Orta' | 'Zəif' | 'pick'>('all')
  const [picked, setPicked] = useState<Set<number>>(new Set())
  const all = levels ? [...levels['Güclü'], ...levels['Orta'], ...levels['Zəif']].sort((a, b) => a.full_name.localeCompare(b.full_name, 'az')) : []
  const apply = (m: typeof mode, p = picked) => {
    setMode(m)
    if (m === 'all') onChange(null)
    else if (m === 'pick') onChange(p.size ? [...p] : [])
    else onChange((levels?.[m] || []).map(r => r.student_id))
  }
  return (
    <fieldset style={{ marginBottom: 0 }}><legend>Kimə</legend>
      <div className="row" style={{ gap: 6 }}>
        {([['all', 'Hamı'], ['Güclü', 'Güclülər'], ['Orta', 'Ortalar'], ['Zəif', 'Zəiflər'], ['pick', 'Seçilmiş']] as const).map(([k, l]) => (
          <button key={k} type="button" className="chip" aria-pressed={mode === k} onClick={() => apply(k)}>
            {l}{k !== 'all' && k !== 'pick' && levels ? ` (${levels[k].length})` : ''}</button>))}
      </div>
      {mode === 'pick' && (
        <div className="jlist" style={{ maxHeight: 220, overflow: 'auto', marginTop: 8 }}>
          {all.map(s => (
            <label key={s.student_id} className="check" style={{ padding: '0 12px' }}>
              <input type="checkbox" checked={picked.has(s.student_id)} onChange={() => {
                const n = new Set(picked); n.has(s.student_id) ? n.delete(s.student_id) : n.add(s.student_id); setPicked(n); apply('pick', n)
              }} />{s.full_name}</label>))}
        </div>)}
      {mode !== 'all' && <p className="small muted" style={{ margin: '6px 0 0' }}>Səviyyə nəticələrə görə avtomatik müəyyən olunur (nəticə yoxdursa – IX sinif balı).</p>}
    </fieldset>
  )
}
