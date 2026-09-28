import { useState } from 'react'
import { api, get } from '../../api'
import { AsyncBtn, ErrorBox, gradeTone, Loading, Pill, toast, Top, useLoad } from '../../ui'

const KIND: Record<string, string> = { task: 'Tapşırıq', video: 'Video dərs', link: 'Link', note: 'Qeyd' }
const dtf = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

function ytEmbed(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([\w-]{6,})/)
  return m ? `https://www.youtube-nocookie.com/embed/${m[1]}` : null
}

export default function Materials() {
  const [list, err, loading, reload] = useLoad<any[]>(() => get('/api/portal/materials'), [])
  return (
    <>
      <Top title="Materiallar" sub="Müəllimin göndərdiyi tapşırıqlar, video dərslər və linklər" />
      <ErrorBox error={err} />
      {loading && !list ? <Loading /> : list?.length === 0 ? <div className="empty">Material yoxdur.</div> : list?.map(m => <Card key={m.id} m={m} onDone={reload} />)}
    </>
  )
}

function Card({ m, onDone }: { m: any; onDone: () => void }) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const yt = m.kind === 'video' && m.url ? ytEmbed(m.url) : null
  const locked = m.submission?.grade != null
  return (
    <section className="panel" style={{ marginBottom: 12 }}>
      <h2 style={{ flexWrap: 'wrap' }}>{m.title} <Pill>{KIND[m.kind]}</Pill><small>{m.subject} · {m.teacher}</small></h2>
      {m.due_at && <p className="small" style={{ margin: '0 0 6px' }}>Son vaxt: <b>{dtf(m.due_at)}</b></p>}
      {m.body && <p style={{ whiteSpace: 'pre-wrap', margin: '0 0 8px' }}>{m.body}</p>}
      {yt ? <div style={{ position: 'relative', paddingTop: '56.25%', borderRadius: 10, overflow: 'hidden' }}><iframe src={yt} title={m.title} allowFullScreen style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }} /></div>
        : m.url && <a className="btn sm" href={m.url} target="_blank" rel="noreferrer noopener">Aç ↗</a>}
      {m.file && <p style={{ margin: '8px 0' }}><a className="btn sm" href={m.file.url} target="_blank" rel="noreferrer">📄 {m.file.name}</a></p>}
      {m.needs_submission && (
        <div className="stack" style={{ marginTop: 10, borderTop: '1px solid var(--line)', paddingTop: 10 }}>
          {m.submission ? (
            <div className="row">
              <Pill tone="ok">təhvil verilib · {dtf(m.submission.submitted_at)}</Pill>
              {m.submission.late && <Pill tone="warn">gecikib</Pill>}
              {m.submission.grade != null && <Pill tone={gradeTone(m.submission.grade)}>qiymət: {m.submission.grade}</Pill>}
              {m.submission.comment && <span className="small">Müəllim: {m.submission.comment}</span>}
            </div>) : null}
          {!locked && (
            <>
              <textarea className="sel" style={{ minHeight: 70, padding: 10 }} placeholder="Cavabınız (istəyə görə)" value={text} onChange={e => setText(e.target.value)} />
              <input type="file" accept="image/*,application/pdf" capture="environment" onChange={e => setFile(e.target.files?.[0] || null)} />
              <AsyncBtn className="btn primary" disabled={!text.trim() && !file} onClick={async () => {
                const fd = new FormData(); if (text.trim()) fd.append('text', text); if (file) fd.append('file', file)
                const r = await api(`/api/portal/materials/${m.id}/submit`, { method: 'POST', form: fd })
                toast(r.late ? 'Təhvil verildi (gecikmiş)' : 'Təhvil verildi'); setText(''); setFile(null); onDone()
              }}>{m.submission ? 'Yenidən təhvil ver' : 'Təhvil ver'}</AsyncBtn>
              <p className="small muted" style={{ margin: 0 }}>Dəftərin şəklini çəkib göndərə bilərsiniz.</p>
            </>)}
        </div>)}
    </section>
  )
}
