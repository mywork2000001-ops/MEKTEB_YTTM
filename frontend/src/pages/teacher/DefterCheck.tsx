import { useEffect, useRef, useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, toast } from '../../ui'
import { useT } from '../../i18n'

type Item = { status: string | null; note: string; wrong: string[]; source: string }
type Row = { student_id: number; full_name: string; submission_id: number | null; has_photo: boolean; items: Record<string, Item>
  grade: number | null; teacher_comment: string | null; comment: string | null; summary: string | null }
type Tbl = { material: { id: number; title: string }; subtopics: string[]; rows: Row[]; percent: Record<string, number> }

const ICON: Record<string, string> = { done: '✅', partial: '🟡', missing: '❌', illegible: '❔' }
// bir toxunuş: boş → ✅ → 🟡 → ❌ → boş (❔ AI nəticəsidir – toxunuşda ✅-dən davam edir)
const NEXT: Record<string, string | null> = { '': 'done', done: 'partial', partial: 'missing', missing: null, illegible: 'done' }

export default function DefterCheck({ ta, mid, onClose }: { ta: number; mid: number; onClose: () => void }) {
  const t = useT()
  const [d, setD] = useState<Tbl | null>(null)
  const [err, setErr] = useState<unknown>()
  const [extra, setExtra] = useState<string[]>([])
  const [neu, setNeu] = useState('')
  const [sugg, setSugg] = useState<string[]>([])
  const [busy, setBusy] = useState<{ done: number; total: number; running: boolean } | null>(null)
  const extraRef = useRef<string[]>([])
  extraRef.current = extra

  const load = async () => {
    try { setD(await get(`/api/materials/${mid}/defter?extra=${encodeURIComponent(extraRef.current.join('|'))}`)) } catch (e) { setErr(e) }
  }
  useEffect(() => { load() }, [mid])
  useEffect(() => { get(`/api/materials/${mid}/subtopics`).then((r: any) => setSugg(r.subtopics || [])).catch(() => {}) }, [mid])
  useEffect(() => {
    if (!busy?.running) return
    const h = setInterval(async () => {
      const s: any = await get(`/api/materials/${mid}/check-all`)
      setBusy({ done: s.done + s.failed, total: s.total, running: s.running })
      if (!s.running) { clearInterval(h); toast(t('Dəftər yoxlaması bitdi')); load() }
    }, 3000)
    return () => clearInterval(h)
  }, [busy?.running])

  const cols = d?.subtopics || []
  const save = async (r: Row, sub: string, status: string | null, note?: string) => {
    // dərhal ekranda dəyiş, arxada yaz (düymə yoxdur)
    setD(p => p && ({ ...p, rows: p.rows.map(x => x.student_id !== r.student_id ? x : { ...x, items: { ...x.items, [sub]: { ...(x.items[sub] || { wrong: [] }), status, note: note ?? (status === 'partial' ? x.items[sub]?.note || '' : ''), source: 'manual' } as Item } }) }))
    try { await put(`/api/materials/${mid}/mark`, { student_id: r.student_id, subtopic: sub, status, note: status === 'partial' ? note ?? r.items[sub]?.note ?? null : null }) } catch (e) { setErr(e); load() }
  }
  const tap = (r: Row, sub: string) => save(r, sub, NEXT[r.items[sub]?.status || ''])
  const pct = (sub: string) => d && d.rows.length ? Math.round(100 * d.rows.filter(r => r.items[sub]?.status === 'done').length / d.rows.length) : 0
  const addCol = (s: string) => { s = s.trim(); if (s && !cols.includes(s)) { const n = [...extra, s]; setExtra(n); extraRef.current = n; load() } setNeu('') }
  const aiBody = { subtopics: cols }

  return (
    <Drawer title={t('Dəftər yoxlaması') + (d ? ' · ' + d.material.title : '')} onClose={onClose}
      footer={<><a className="btn" href={`/api/materials/${mid}/check.csv`}>{t('CSV yüklə')}</a><button className="btn" onClick={onClose}>{t('Bağla')}</button></>}>
      <ErrorBox error={err} />
      <p className="small muted" style={{ margin: '0 0 8px' }}>{t('Xanaya toxunun: ✅ → 🟡 → ❌ → boş. Dərhal yazılır; qiymət qoyulmur.')}</p>
      <div className="row" style={{ flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
        <input className="sel grow" placeholder={t('Yeni alt mövzu')} value={neu} onChange={e => setNeu(e.target.value)} onKeyDown={e => e.key === 'Enter' && addCol(neu)} />
        <button className="btn sm" disabled={!neu.trim()} onClick={() => addCol(neu)}>{t('Əlavə et')}</button>
      </div>
      {sugg.filter(s => !cols.includes(s)).length > 0 && <div className="row" style={{ flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        <span className="small muted">{t('Təklif')}:</span>
        {sugg.filter(s => !cols.includes(s)).slice(0, 8).map(s => <button key={s} className="btn sm ghost" onClick={() => addCol(s)}>+ {s}</button>)}
      </div>}
      {cols.length > 0 && <div className="row" style={{ gap: 6, marginBottom: 8 }}>
        <AsyncBtn className="btn sm" disabled={!!busy?.running} onClick={async () => {
          const r: any = await post(`/api/materials/${mid}/check-all`, aiBody)
          if (r.started) setBusy({ done: 0, total: r.started, running: true }); else toast(t('Yoxlanacaq şəkil yoxdur'))
        }}>🤖 {t('Hamısını yoxla')}</AsyncBtn>
        {busy?.running && <span className="small muted">{busy.done}/{busy.total}</span>}
      </div>}
      {d && cols.length === 0 && <div className="empty">{t('Əvvəlcə alt mövzu əlavə edin.')}</div>}
      {d && cols.length > 0 && <div style={{ overflowX: 'auto' }}>
        <table className="tbl" style={{ minWidth: 'max-content', borderCollapse: 'collapse' }}>
          <thead><tr>
            <th style={{ position: 'sticky', left: 0, background: 'var(--bg, #fff)', textAlign: 'left' }}>{t('Şagird')}</th>
            {cols.map(c => <th key={c} style={{ minWidth: 70, fontSize: 12 }}>{c}<br /><span className="muted">{pct(c)}%</span></th>)}
          </tr></thead>
          <tbody>{d.rows.map(r => (
            <tr key={r.student_id}>
              <td style={{ position: 'sticky', left: 0, background: 'var(--bg, #fff)', whiteSpace: 'nowrap' }}>
                {r.full_name}
                {r.has_photo && <AsyncBtn className="btn sm ghost" onClick={async () => { await post(`/api/materials/${mid}/submissions/${r.submission_id}/check`, aiBody); load() }}>🤖</AsyncBtn>}
              </td>
              {cols.map(c => { const it = r.items[c]; return (
                <td key={c} style={{ textAlign: 'center', padding: 2 }}>
                  <button className="btn ghost" style={{ minWidth: 48, minHeight: 44, fontSize: 20 }} title={it?.source === 'ai' ? '🤖' : ''} onClick={() => tap(r, c)}>
                    {it?.status ? ICON[it.status] : '·'}{it?.source === 'ai' && it.status ? <sup style={{ fontSize: 9 }}>AI</sup> : null}</button>
                  {it?.status === 'partial' && <input className="sel" style={{ width: 70, fontSize: 12 }} placeholder={t('səhv №')} defaultValue={it.note} onBlur={e => { if (e.target.value !== it.note) save(r, c, 'partial', e.target.value) }} />}
                </td>) })}
            </tr>))}</tbody>
        </table>
        {d.rows.filter(r => r.comment).map(r => (
          <div key={r.student_id} className="small" style={{ marginTop: 6 }}>
            <b>{r.full_name}</b>: {r.summary} <span className="muted">«{r.comment}»</span>{' '}
            {r.submission_id && r.grade == null && <button className="btn sm ghost" onClick={async () => { await put(`/api/materials/${ta}/submissions/${r.submission_id}`, { grade: null, comment: r.comment }); toast(t('Şərh köçürüldü')); load() }}>{t('Şərhi köçür')}</button>}
          </div>))}
      </div>}
    </Drawer>
  )
}
