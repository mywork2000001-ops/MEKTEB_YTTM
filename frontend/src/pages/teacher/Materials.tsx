import { useState } from 'react'
import { api, get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmtDate, gradeTone, PickFirst, Pill, Seg, toast, Top, useLoad } from '../../ui'
import { LessonSelect, useMyLessons, usePick } from './common'

type Mat = { id: number; kind: 'task' | 'video' | 'link' | 'note'; title: string; body: string | null; url: string | null; due_at: string | null
  file: { name: string; type: string; size: number; url: string } | null; submitted: number; graded: number; targets: number; created_at: string }
export const KIND: Record<string, string> = { task: 'Tapşırıq (PDF/fayl)', video: 'Video dərs', link: 'Link', note: 'Qeyd' }
const dtf = (s: string) => new Date(s).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function Materials() {
  const [lessons, err0] = useMyLessons()
  const [ta, setTa] = usePick('materials')
  const [list, err, , reload] = useLoad<Mat[] | null>(() => (ta ? get(`/api/materials/${ta}`) : Promise.resolve(null)), [ta])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  return (
    <>
      <Top title="Materiallar" sub="Sinfə / qrupa PDF tapşırıq, video dərs, link və ya qeyd göndərin"
        actions={ta ? <button className="btn primary" onClick={() => setCreating(true)}>+ Yeni material</button> : undefined} />
      <ErrorBox error={err0 || err} />
      <div className="toolbar"><LessonSelect lessons={lessons} value={ta} onChange={setTa} /></div>
      {!ta ? <PickFirst /> : (
        <div className="jlist">
          {list?.length === 0 && <div className="empty">Hələ material yoxdur.</div>}
          {list?.map(m => (
            <div className="jrow" key={m.id}>
              <span><b>{m.title}</b> <Pill>{KIND[m.kind]}</Pill><span className="sub small muted"><br />{dtf(m.created_at)}{m.due_at ? ` · son vaxt ${dtf(m.due_at)}` : ''}{m.file ? ` · ${m.file.name}` : ''}</span></span>
              <span className="row">{m.kind === 'task' && <Pill tone={m.submitted ? 'ok' : undefined}>{m.submitted}/{m.targets} təhvil · {m.graded} qiymət</Pill>}</span>
              <span className="row">
                {m.kind === 'task' && <button className="btn sm" onClick={() => setOpen(m.id)}>Cavablar</button>}
                <AsyncBtn className="btn sm ghost" ok="Arxivə göndərildi" onClick={async () => { await post(`/api/materials/${ta}/${m.id}/archive`); reload() }}>Arxiv</AsyncBtn>
              </span>
            </div>))}
        </div>)}
      {creating && ta && <CreateMaterial ta={ta} onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload() }} />}
      {open && ta && <Submissions ta={ta} id={open} onClose={() => { setOpen(null); reload() }} />}
    </>
  )
}

function CreateMaterial({ ta, onClose, onDone }: { ta: number; onClose: () => void; onDone: () => void }) {
  const [kind, setKind] = useState<'task' | 'video' | 'link' | 'note'>('task')
  const [f, setF] = useState({ title: '', body: '', url: '', due: '' })
  const [file, setFile] = useState<File | null>(null)
  const [err, setErr] = useState<unknown>()
  const submit = async () => {
    try {
      const fd = new FormData()
      fd.append('kind', kind); fd.append('title', f.title)
      if (f.body) fd.append('body', f.body)
      if (f.url) fd.append('url', f.url)
      if (f.due) fd.append('due_at', new Date(f.due).toISOString())
      if (file) fd.append('file', file)
      await api(`/api/materials/${ta}`, { method: 'POST', form: fd })
      toast('Göndərildi'); onDone()
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title="Yeni material" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Ləğv et</button><button className="btn primary" disabled={f.title.length < 2} onClick={submit}>Göndər</button></>}>
      <div className="stack">
        <Seg value={kind} onChange={setKind} options={[['task', 'PDF tapşırıq'], ['video', 'Video dərs'], ['link', 'Link'], ['note', 'Qeyd']]} />
        <Field label="Başlıq"><input value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></Field>
        {(kind === 'video' || kind === 'link') && <Field label="Ünvan" hint="məs. https://youtu.be/…"><input inputMode="url" value={f.url} onChange={e => setF({ ...f, url: e.target.value })} /></Field>}
        {(kind === 'task' || kind === 'note') && <Field label="Fayl" hint="PDF, Word, PowerPoint, şəkil, səs və ya video"><input type="file" accept=".pdf,.doc,.docx,.pptx,image/*,audio/*,video/mp4,video/webm" onChange={e => setFile(e.target.files?.[0] || null)} /></Field>}
        <Field label="Mətn / izah"><textarea value={f.body} onChange={e => setF({ ...f, body: e.target.value })} /></Field>
        {kind === 'task' && <Field label="Son vaxt" hint="keçəndən sonra gələn cavab «gecikmiş» qeyd olunur"><input type="datetime-local" value={f.due} onChange={e => setF({ ...f, due: e.target.value })} /></Field>}
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

function Submissions({ ta, id, onClose }: { ta: number; id: number; onClose: () => void }) {
  const [d, err, , reload] = useLoad<any>(() => get(`/api/materials/${ta}/${id}/submissions`), [ta, id])
  return (
    <Drawer title={d?.material.title || 'Cavablar'} onClose={onClose}>
      <ErrorBox error={err} />
      <div className="jlist">{d?.rows.map((r: any) => (
        <div key={r.student_id} className="jrow" style={{ gridTemplateColumns: '1fr', gap: 6 }}>
          <div className="row"><b className="grow">{r.full_name}</b>
            {!r.submission ? <Pill>təhvil verməyib</Pill> : <>{r.submission.late && <Pill tone="warn">gecikib</Pill>}<span className="small muted">{fmtDate(r.submission.submitted_at)}</span></>}</div>
          {r.submission && <>
            {r.submission.text && <p className="small" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{r.submission.text}</p>}
            {r.submission.file && <a className="small" href={r.submission.file.url} target="_blank" rel="noreferrer">📎 {r.submission.file.name}</a>}
            <div className="row">
              <select className="grade-sel" defaultValue={r.submission.grade ?? ''} onChange={async e => { await put(`/api/materials/${ta}/submissions/${r.submission.id}`, { grade: e.target.value ? Number(e.target.value) : null, comment: r.submission.comment }); toast('Qiymət yazıldı'); reload() }}>
                <option value="">qiymət —</option>{[5, 4, 3, 2].map(g => <option key={g}>{g}</option>)}</select>
              {r.submission.grade && <Pill tone={gradeTone(r.submission.grade)}>{r.submission.grade}</Pill>}
              <input className="sel grow" placeholder="Şərh" defaultValue={r.submission.comment || ''} onBlur={async e => { if (e.target.value !== (r.submission.comment || '')) { await put(`/api/materials/${ta}/submissions/${r.submission.id}`, { grade: r.submission.grade, comment: e.target.value || null }); toast('Şərh yazıldı') } }} />
            </div>
          </>}
        </div>))}</div>
    </Drawer>
  )
}
