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
