// Çat – müəllim və şagird üçün ortaq. Yeni mesajlar hər 4 saniyədən bir yoxlanılır.
import { useEffect, useRef, useState } from 'react'
import { api, del, get, post } from '../api'
import { useAuth } from '../auth'
import { useT } from '../i18n'
import { Drawer, ErrorBox, Icon, Pill, toast, Top, useLoad } from '../ui'

type Room = { id: number; kind: 'class' | 'dm' | 'staff'; title: string; unread: number; last: { text: string; at: string } | null }
type Msg = { id: number; sender_id: number; sender: string; text: string | null; deleted: boolean; at: string; file: { name: string; type: string; size: number; url: string } | null }

export default function Chat() {
  const t = useT()
  const { me } = useAuth()
  const [rooms, err, , reload] = useLoad<Room[]>(() => get('/api/chat/rooms'), [])
  const [room, setRoom] = useState<Room | null>(null)
  const [contacts, setContacts] = useState<any[] | null>(null)
  const [reports, setReports] = useState<any[] | null>(null)
  useEffect(() => { const i = setInterval(reload, 15000); return () => clearInterval(i) }, [reload])
  return (
    <>
      <Top title={t('Çat')} sub="Tam məxfilik: yazışmanı yalnız iştirakçılar görür"
        actions={<>
          <button className="btn" onClick={async () => setContacts(await get('/api/chat/contacts'))}>+ Yeni yazışma</button>
          {me?.role !== 'student' && <button className="btn" onClick={async () => setReports(await get('/api/chat/reports'))}>Bildirişlər (!)</button>}
        </>} />
      <ErrorBox error={err} />
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1fr)', gap: 12 }}>
        {!room ? (
          <div className="jlist">
            {(rooms || []).map(r => (
              <button key={r.id} className="jrow" style={{ all: 'unset', display: 'grid', gridTemplateColumns: '36px minmax(0,1fr) auto', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--line)', cursor: 'pointer' }} onClick={() => setRoom(r)}>
                <Icon name={r.kind === 'staff' ? 'staff' : r.kind === 'class' ? 'classes' : 'feedback'} />
                <span><b>{r.title}</b><span className="sub small muted" style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.last?.text || '—'}</span></span>
                {r.unread > 0 ? <Pill tone="acc">{r.unread}</Pill> : <span />}
              </button>))}
            {rooms?.length === 0 && <div className="empty">Söhbət yoxdur.</div>}
          </div>
        ) : <RoomView room={room} onBack={() => { setRoom(null); reload() }} />}
      </div>
      {contacts && (
        <Drawer title="Kimə yazmaq olar" onClose={() => setContacts(null)}>
          <div className="stack">{contacts.map(c => (
            <button key={c.id} className="btn" style={{ justifyContent: 'flex-start' }} onClick={async () => { const r = await post('/api/chat/dm', { user_id: c.id }); setContacts(null); setRoom({ ...r, unread: 0, last: null }); reload() }}>
              {c.full_name} <span className="small muted">{c.role === 'student' ? 'şagird' : 'müəllim'}</span></button>))}
            {contacts.length === 0 && <p className="muted">Yazışma üçün uyğun şəxs yoxdur.</p>}</div>
        </Drawer>)}
      {reports && (
        <Drawer title="Şagirdlərin bildirdiyi mesajlar" onClose={() => setReports(null)}>
          <p className="small muted">Yalnız «!» ilə bildirilən mesajlar görünür, yazışmanın qalanı görünmür.</p>
          <div className="stack">{reports.map(r => (
            <section key={r.id} className="panel">
              <p className="small muted">{r.class_name} · bildirən: {r.reporter} · {new Date(r.at).toLocaleString('az-AZ')}</p>
              <p><b>{r.message.sender}:</b> {r.message.text}</p>
              {r.reason && <p className="small">Səbəb: {r.reason}</p>}
              {r.resolved ? <Pill tone="ok">baxılıb</Pill> : <button className="btn sm" onClick={async () => { await post(`/api/chat/reports/${r.id}/resolve`); setReports(await get('/api/chat/reports')) }}>Baxıldı</button>}
            </section>))}
            {reports.length === 0 && <p className="muted">Bildiriş yoxdur.</p>}</div>
        </Drawer>)}
    </>
  )
}

function RoomView({ room, onBack }: { room: Room; onBack: () => void }) {
  const t = useT()
  const { me } = useAuth()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [err, setErr] = useState<unknown>()
  const [rec, setRec] = useState<MediaRecorder | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const last = useRef(0)
  const load = async () => {
    try {
      const n = await get<Msg[]>(`/api/chat/rooms/${room.id}/messages`, { after_id: last.current })
      if (n.length) { last.current = n[n.length - 1].id; setMsgs(m => [...m, ...n]); post(`/api/chat/rooms/${room.id}/read`).catch(() => {}) }
    } catch (e) { setErr(e) }
  }
  useEffect(() => { last.current = 0; setMsgs([]); load(); const i = setInterval(load, 4000); return () => clearInterval(i) }, [room.id])
  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight) }, [msgs.length])
  const send = async (file?: File) => {
    if (!text.trim() && !file) return
    const fd = new FormData()
    if (text.trim()) fd.append('text', text)
    if (file) fd.append('file', file)
    try { await api(`/api/chat/rooms/${room.id}/messages`, { method: 'POST', form: fd }); setText(''); load() } catch (e) { setErr(e) }
  }
  const record = async () => {
    if (rec) { rec.stop(); setRec(null); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const r = new MediaRecorder(stream)
      const chunks: Blob[] = []
      r.ondataavailable = e => chunks.push(e.data)
      r.onstop = () => { stream.getTracks().forEach(x => x.stop()); const b = new Blob(chunks, { type: 'audio/webm' }); send(new File([b], 'səs.webm', { type: 'audio/webm' })) }
      r.start(); setRec(r)
    } catch { toast('Mikrofona icazə verilmədi') }
  }
  return (
    <section className="panel">
      <div className="row" style={{ marginBottom: 10 }}><button className="btn sm" onClick={onBack}>‹</button><b className="grow">{room.title}</b></div>
      <ErrorBox error={err} />
      <div className="msgs" ref={box}>
        {msgs.map(m => {
          const mine = m.sender_id === me?.id
          return (
            <div key={m.id} className={'bubble' + (mine ? ' me' : '')}>
              {!mine && <span className="who">{m.sender}</span>}
              {m.deleted ? <i className="muted">mesaj silinib</i> : <>
                {m.text && <span style={{ whiteSpace: 'pre-wrap' }}>{m.text}</span>}
                {m.file && (m.file.type.startsWith('image/') ? <a href={m.file.url} target="_blank" rel="noreferrer"><img src={m.file.url} alt={m.file.name} loading="lazy" /></a>
                  : m.file.type.startsWith('audio/') ? <audio controls src={m.file.url} preload="none" />
                  : m.file.type.startsWith('video/') ? <video controls src={m.file.url} preload="metadata" />
                  : <a href={m.file.url} target="_blank" rel="noreferrer">📄 {m.file.name} ({Math.round(m.file.size / 1024)} KB)</a>)}
              </>}
              <span className="who" style={{ textAlign: 'right' }}>{new Date(m.at).toLocaleTimeString('az-AZ', { hour: '2-digit', minute: '2-digit' })}
                {mine && !m.deleted && <button className="btn ghost sm" style={{ minHeight: 20, padding: '0 4px' }} onClick={async () => { await del(`/api/chat/messages/${m.id}`); setMsgs(x => x.map(y => y.id === m.id ? { ...y, deleted: true } : y)) }}>sil</button>}
                {!mine && !m.deleted && me?.role === 'student' && <button className="btn ghost sm" style={{ minHeight: 20, padding: '0 4px', color: 'var(--bad)' }} title="Müəllimə bildir" onClick={async () => { try { await post(`/api/chat/messages/${m.id}/report`, {}); toast('Müəllimə bildirildi') } catch (e: any) { toast(e.message) } }}>!</button>}
              </span>
            </div>)
        })}
        {msgs.length === 0 && <p className="muted small">Hələ mesaj yoxdur.</p>}
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <label className="btn sm" title="Şəkil, PDF, video (2 GB-a qədər)"><Icon name="clip" /><input type="file" hidden accept="image/*,application/pdf,audio/*,video/mp4,video/webm,video/quicktime" onChange={e => { const f = e.target.files?.[0]; if (f) send(f); e.target.value = '' }} /></label>
        <button className="btn sm" onClick={record} aria-pressed={!!rec} style={rec ? { color: 'var(--bad)' } : undefined} title="Səs"><Icon name="mic" />{rec ? 'dayandır' : ''}</button>
        <input className="sel grow" value={text} placeholder={t('Mesaj yazın…')} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
        <button className="btn primary sm" onClick={() => send()}>{t('Göndər')}</button>
      </div>
    </section>
  )
}
