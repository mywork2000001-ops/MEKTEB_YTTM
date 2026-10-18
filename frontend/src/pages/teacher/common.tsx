import { useEffect, useRef, useState } from 'react'
import { get } from '../../api'
import { useLoad } from '../../ui'
import { tt, useT } from '../../i18n'

export type MyLesson = {
  id: number; class_id: number; class_name: string; kind: string; subject: string; weekly_hours: number
  slots: Record<string, number[]>; has_summative: boolean; split_with: string | null; plan_lessons: number; lag: number; unfit: number; semester?: 1 | 2; program?: string | null; extra_programs?: number
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

/** Son seçilən sinif/qrup (bütün bölmələr üçün ortaq) – brauzerdə qalır, növbəti açılışda avtomatik seçilir. */
const LAST_LESSON = 'mk-last-lesson'
const readLast = (): number | null => { try { const s = localStorage.getItem(LAST_LESSON); return s ? Number(s) : null } catch { return null } }
const QUICK_COLORS = ['var(--accent)', 'var(--ok)', 'var(--warn)', 'var(--info)', 'var(--bad)']

export function LessonSelect({ lessons, value, onChange, label = 'Sinif / qrup', chips = true }: { lessons?: MyLesson[]; value: number | null; onChange: (v: number | null) => void; label?: string; chips?: boolean }) {
  const t = useT()
  const restored = useRef(false)
  // ilk açılışda seçim yoxdursa – son seçilən sinif (hələ də müəllimin siyahısındadırsa)
  useEffect(() => {
    if (!lessons || restored.current) return
    restored.current = true
    if (value == null) { const last = readLast(); if (last && lessons.some(l => l.id === last)) onChange(last) }
  }, [lessons])
  useEffect(() => { if (value != null) { try { localStorage.setItem(LAST_LESSON, String(value)) } catch { /* noop */ } } }, [value])
  const name = (l: MyLesson) => l.class_name + (l.subject !== 'Riyaziyyat' ? ` · ${l.subject}` : '')
  const ph = t(label === 'Sinif / qrup' ? '— Sinif / qrup seçin —' : '— {x} seçin —', { x: t(label) })
  return (
    <>
      <select className="sel" aria-label={t(label)} value={value ?? ''} onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{ph}</option>
        {(lessons || []).map(l => <option key={l.id} value={l.id}>{name(l)}</option>)}
      </select>
      {chips && value == null && !!lessons?.length && (
        <div className="quickpick" role="group" aria-label={t('Sürətli seçim')}>
          {lessons.map((l, i) => (
            <button key={l.id} type="button" className="chip" style={{ ['--cc' as any]: QUICK_COLORS[i % QUICK_COLORS.length] }} onClick={() => onChange(l.id)}>{name(l)}</button>))}
        </div>)}
    </>
  )
}

export const ATT: [string, string, string][] = [['var', 'V', 'var'], ['yox', 'Q', 'yox'], ['üzrlü', 'Ü', 'uzrlu'], ['gecikdi', 'G', 'gecikdi']]
export const HW: string[] = ['etdi', 'qismən', 'etmədi', 'köçürüb']

type Stu = { id: number; full_name: string; portal_code: string; level: 'Zəif' | 'Orta' | 'Güclü' | null }
export type Preset = { key: string; label: string; ids: number[] }
const LVS = ['Zəif', 'Orta', 'Güclü'] as const

/** «Kimə» (docs/sagird-secimi-promtu.md): hamı / səviyyə qrupları (Jurnal → Səviyyə qrupları) / seçilmiş şagirdlər /
 * hazır siyahılar (məs. «Yazmayanlar»). onChange(null) – bütün sinif; massiv – yalnız onlar. value – ilkin seçim (redaktə). */
export function StudentPicker({ ta, value, onChange, presets = [], legend = 'Kimə', initialPreset }:
  { ta: number; value?: number[] | null; onChange: (ids: number[] | null) => void; presets?: Preset[]; legend?: string; initialPreset?: string }) {
  const t = useT()
  const [list] = useLoad<Stu[]>(() => get(`/api/exams-online/targets/${ta}/students`), [ta])
  const [mode, setMode] = useState<string>(initialPreset && value ? initialPreset : value ? 'pick' : 'all')
  const [lv, setLv] = useState<Set<string>>(new Set())
  const [picked, setPicked] = useState<Set<number>>(new Set(value || []))
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const all = list || []
  const emit = (m: string, p: Set<number>, l: Set<string>) => {
    if (m === 'all') onChange(null)
    else if (m === 'levels') onChange(all.filter(s => s.level && l.has(s.level)).map(s => s.id))
    else onChange([...p])
  }
  const choose = (m: string, ids?: number[]) => {
    setMode(m)
    if (ids) { const p = new Set(ids); setPicked(p); emit('pick', p, lv) } else emit(m, picked, lv)
  }
  const toggleLv = (l: string) => {
    const n = new Set(lv); n.has(l) ? n.delete(l) : n.add(l)
    setLv(n); setMode(n.size ? 'levels' : 'all'); emit(n.size ? 'levels' : 'all', picked, n)
  }
  // siyahıda tək-tək dəyişmək: cari seçimdən başlayır və «Seçilmiş» rejiminə keçir
  const current = mode === 'all' ? new Set(all.map(s => s.id)) : mode === 'levels' ? new Set(all.filter(s => s.level && lv.has(s.level)).map(s => s.id)) : picked
  const flip = (id: number) => { const n = new Set(current); n.has(id) ? n.delete(id) : n.add(id); setPicked(n); setMode('pick'); emit('pick', n, lv) }
  const setAll = (on: boolean) => { const n = new Set(on ? all.map(s => s.id) : []); setPicked(n); setMode('pick'); emit('pick', n, lv) }
  const lc = (x: string) => x.toLocaleLowerCase('az')
  const shown = all.filter(s => !q || lc(s.full_name).includes(lc(q)) || lc(s.portal_code).includes(lc(q)))
  const noLevel = all.filter(s => !s.level).length
  return (
    <fieldset style={{ marginBottom: 0 }}><legend>{t(legend)}</legend>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button type="button" className="chip" aria-pressed={mode === 'all'} onClick={() => { setLv(new Set()); choose('all') }}>{t('Hamı')}{list ? ` (${all.length})` : ''}</button>
        {LVS.map(l => { const n = all.filter(s => s.level === l).length
          return <button key={l} type="button" className="chip" aria-pressed={mode === 'levels' && lv.has(l)} disabled={!n} onClick={() => toggleLv(l)}>{t(l)} ({n})</button> })}
        {presets.map(p => <button key={p.key} type="button" className="chip" aria-pressed={mode === p.key} disabled={!p.ids.length}
          onClick={() => { setMode(p.key); const n = new Set(p.ids); setPicked(n); emit('pick', n, lv) }}>{t(p.label)} ({p.ids.length})</button>)}
        <button type="button" className="chip" aria-pressed={mode === 'pick'} onClick={() => { setOpen(true); choose('pick', [...current]) }}>{t('Seçilmiş…')}</button>
        <button type="button" className="btn sm ghost right" onClick={() => setOpen(!open)}>{open ? t('Siyahını gizlət') : t('Siyahı')}</button>
      </div>
      <p className="small muted" style={{ margin: '6px 0 0' }}>{list ? t('{n} şagirddən {k}-i', { n: all.length, k: current.size }) : '…'}
        {mode === 'levels' && noLevel > 0 ? ' · ' + t('səviyyəsi təyin olunmayan {n} şagird daxil deyil (Jurnal → Səviyyə qrupları)', { n: noLevel }) : ''}
        {mode !== 'all' && current.size === 0 ? ' · ' + t('ən azı bir şagird seçin') : ''}</p>
      {open && <div style={{ marginTop: 8 }}>
        <div className="row" style={{ gap: 6, marginBottom: 6 }}>
          <input className="sel grow" placeholder={t('Ad və ya ID ilə axtar')} value={q} onChange={e => setQ(e.target.value)} />
          <button type="button" className="btn sm" onClick={() => setAll(true)}>{t('Hamısını seç')}</button>
          <button type="button" className="btn sm" onClick={() => setAll(false)}>{t('Təmizlə')}</button>
        </div>
        <div className="jlist" style={{ maxHeight: 240, overflow: 'auto' }}>
          {shown.map(s => (
            <label key={s.id} className="check" style={{ padding: '0 12px' }}>
              <input type="checkbox" checked={current.has(s.id)} onChange={() => flip(s.id)} />
              <span className="grow">{s.full_name} <span className="small muted">{s.portal_code}</span></span>
              {s.level && <span className="small muted">{t(s.level)}</span>}</label>))}
          {list && !shown.length && <div className="empty">{t('Şagird tapılmadı.')}</div>}
        </div></div>}
    </fieldset>
  )
}
/** Köhnə ad – eyni seçici (Materiallar, Onlayn tapşırıqlar). */
export const TargetPicker = StudentPicker

/** Növ adı: TOM / adi sinif, bölünmə qrupu (sinif daxilində), tədris qrupu (müxtəlif siniflərdən). */
export const kindLabel = (c: { kind: string; parent_id: number | null }) =>
  tt(c.kind !== 'qrup' ? (c.kind === 'TOM' ? 'TOM sinfi' : 'adi sinif') : c.parent_id ? 'bölünmə qrupu' : 'tədris qrupu')
