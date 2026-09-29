// Çat – müəllim və şagird üçün ortaq. Söhbətlər: qruplar (Müəllim otağı, sinif) + şəxsi yazışmalar (son mesaja görə).
// Yeni mesajlar hər 4 saniyədən bir yoxlanılır. Tam məxfilik: yazışmanı yalnız iştirakçılar görür.
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, del, get, post } from '../api'
import { useAuth } from '../auth'
import { useT } from '../i18n'
import { Drawer, ErrorBox, Icon, Pill, toast, Top, useLoad } from '../ui'

type Room = { id: number; kind: 'class' | 'dm' | 'staff'; title: string; unread: number; last: { text: string; at: string; mine?: boolean; sender?: string } | null }
type Msg = { id: number; sender_id: number; sender: string; text: string | null; deleted: boolean; at: string; file: { name: string; type: string; size: number; url: string } | null }
type Contact = { id: number; full_name: string; role: string; group: string; sub: string; room_id: number | null }

const initials = (n: string) => n.split(' ').slice(0, 2).map(w => w[0] || '').join('').toUpperCase()
const when = (s?: string) => {
  if (!s) return ''
  const d = new Date(s), now = new Date()
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString('az-AZ', { hour: '2-digit', minute: '2-digit' })
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (d.toDateString() === y.toDateString()) return 'dünən'
  return d.toLocaleDateString('az-AZ', { day: '2-digit', month: '2-digit' })
}
const dayLabel = (s: string) => {
  const d = new Date(s), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1)
  return d.toDateString() === now.toDateString() ? 'Bu gün' : d.toDateString() === y.toDateString() ? 'Dünən'
    : d.toLocaleDateString('az-AZ', { day: 'numeric', month: 'long', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' })
}

function Avatar({ room }: { room: Room }) {
  const bg = room.kind === 'staff' ? 'var(--info-soft)' : room.kind === 'class' ? 'var(--ok-soft)' : 'var(--accent-soft)'
  return (
    <span aria-hidden style={{ width: 42, height: 42, borderRadius: '50%', background: bg, display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 14, flex: 'none' }}>
      {room.kind === 'dm' ? initials(room.title) : <Icon name={room.kind === 'staff' ? 'staff' : 'classes'} />}
    </span>
  )
}

export default function Chat() {
  const t = useT()
  const { me } = useAuth()
  const [rooms, err, , reload] = useLoad<Room[]>(() => get('/api/chat/rooms'), [])
  const [room, setRoom] = useState<Room | null>(null)
  const [contacts, setContacts] = useState<Contact[] | null>(null)
  const [reports, setReports] = useState<any[] | null>(null)
  const [q, setQ] = useState('')
  useEffect(() => { const i = setInterval(reload, 15000); return () => clearInterval(i) }, [reload])
  const list = (rooms || []).filter(r => !q || r.title.toLowerCase().includes(q.toLowerCase()))
  const groups = list.filter(r => r.kind !== 'dm'), dms = list.filter(r => r.kind === 'dm')
  const openContact = async (c: Contact) => {
    const r = c.room_id ? { id: c.room_id, kind: 'dm' as const, title: c.full_name } : await post('/api/chat/dm', { user_id: c.id })
    setContacts(null); setRoom({ ...r, unread: 0, last: null }); reload()
  }
  if (room) return <RoomView room={room} onBack={() => { setRoom(null); reload() }} />
  const Row = ({ r }: { r: Room }) => (
    <button className="chat-row" onClick={() => setRoom(r)}>
      <Avatar room={r} />
      <span className="grow" style={{ minWidth: 0 }}>
        <span className="row" style={{ flexWrap: 'nowrap' }}><b className="grow ellipsis">{r.title}</b><span className="small muted">{when(r.last?.at)}</span></span>
        <span className="row" style={{ flexWrap: 'nowrap' }}>
          <span className="small muted grow ellipsis">{r.last ? `${r.last.mine ? 'Siz: ' : r.kind !== 'dm' && r.last.sender ? r.last.sender + ': ' : ''}${r.last.text}` : 'Hələ mesaj yoxdur'}</span>
          {r.unread > 0 && <Pill tone="acc">{r.unread}</Pill>}</span>
      </span>
    </button>
  )
  return (
    <>
      <Top title={t('Çat')} sub="Tam məxfilik: yazışmanı yalnız iştirakçılar görür"
        actions={<>
          <button className="btn primary" onClick={async () => setContacts(await get('/api/chat/contacts'))}>+ Yeni yazışma</button>
          {me?.role !== 'student' && <button className="btn" onClick={async () => setReports(await get('/api/chat/reports'))}>Bildirişlər (!)</button>}
        </>} />
      <ErrorBox error={err} />
      {(rooms?.length || 0) > 5 && <div className="search" style={{ marginBottom: 10 }}><input placeholder="Söhbət axtar" value={q} onChange={e => setQ(e.target.value)} /></div>}
      {groups.length > 0 && <><h3 className="chat-h">Qruplar</h3><div className="jlist">{groups.map(r => <Row key={r.id} r={r} />)}</div></>}
      <h3 className="chat-h">Şəxsi yazışmalar</h3>
      <div className="jlist">{dms.map(r => <Row key={r.id} r={r} />)}
        {dms.length === 0 && <div className="empty">Hələ şəxsi yazışma yoxdur – «+ Yeni yazışma» ilə başlayın.</div>}</div>
      {contacts && <ContactPicker contacts={contacts} onPick={openContact} onClose={() => setContacts(null)} />}
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

/** Kimə yazmaq olar: axtarış + qruplar (Müəllimlər, siniflər). Mövcud yazışma varsa – onu açır. */
function ContactPicker({ contacts, onPick, onClose }: { contacts: Contact[]; onPick: (c: Contact) => void; onClose: () => void }) {
  const [q, setQ] = useState('')
  const grouped = useMemo(() => {
    const m = new Map<string, Contact[]>()
    contacts.filter(c => !q || (c.full_name + ' ' + c.sub).toLowerCase().includes(q.toLowerCase()))
      .forEach(c => m.set(c.group, [...(m.get(c.group) || []), c]))
    return [...m.entries()]
  }, [contacts, q])
  return (
    <Drawer title="Kimə yazmaq olar" onClose={onClose}>
      <div className="search" style={{ marginBottom: 10 }}><input autoFocus placeholder="Ad axtar" value={q} onChange={e => setQ(e.target.value)} /></div>
      {grouped.map(([g, list]) => (
        <div key={g} style={{ marginBottom: 12 }}>
          <h3 className="chat-h">{g} <span className="muted">· {list.length}</span></h3>
          <div className="jlist">{list.map(c => (
            <button key={c.id} className="chat-row" onClick={() => onPick(c)}>
              <span aria-hidden className="chat-av">{initials(c.full_name)}</span>
              <span className="grow" style={{ minWidth: 0 }}><b className="ellipsis" style={{ display: 'block' }}>{c.full_name}</b>
                <span className="small muted ellipsis" style={{ display: 'block' }}>{c.sub || (c.role === 'student' ? 'şagird' : 'müəllim')}</span></span>
              {c.room_id && <span className="small muted">yazışma var</span>}
            </button>))}</div>
        </div>))}
      {grouped.length === 0 && <p className="muted">{q ? 'Tapılmadı.' : 'Yazışma üçün uyğun şəxs yoxdur.'}</p>}
      <p className="small muted">Şagird sinif yoldaşlarına, müəllimlərinə və sinif rəhbərinə; müəllim həmkarlarına, dərs dediyi və rəhbəri olduğu sinfin şagirdlərinə yaza bilər.</p>
    </Drawer>
  )
}

function RoomView({ room, onBack }: { room: Room; onBack: () => void }) {
  const t = useT()
  const { me } = useAuth()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [err, setErr] = useState<unknown>()
  const [rec, setRec] = useState<MediaRecorder | null>(null)
  const [sending, setSending] = useState(false)
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
    if ((!text.trim() && !file) || sending) return
    const fd = new FormData()
    if (text.trim()) fd.append('text', text.trim())
    if (file) fd.append('file', file)
    setSending(true)
    try { await api(`/api/chat/rooms/${room.id}/messages`, { method: 'POST', form: fd }); setText(''); load() } catch (e) { setErr(e) } finally { setSending(false) }
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
  let prevDay = '', prevSender = -1
  return (
    <section className="panel chat-room">
      <div className="row chat-top" style={{ flexWrap: 'nowrap' }}>
        <button className="btn" onClick={onBack} aria-label="Söhbətlərə qayıt">‹</button>
        <Avatar room={room} /><b className="grow ellipsis">{room.title}</b>
      </div>
      <ErrorBox error={err} />
      <div className="msgs" ref={box}>
        {msgs.map(m => {
          const mine = m.sender_id === me?.id
          const day = new Date(m.at).toDateString()
          const sep = day !== prevDay; prevDay = day
          const showWho = !mine && room.kind !== 'dm' && (sep || prevSender !== m.sender_id); prevSender = m.sender_id
          return (
            <div key={m.id} style={{ display: 'contents' }}>
              {sep && <div className="chat-day"><span>{dayLabel(m.at)}</span></div>}
              <div className={'bubble' + (mine ? ' me' : '')}>
                {showWho && <span className="who">{m.sender}</span>}
                {m.deleted ? <i className="muted">mesaj silinib</i> : <>
                  {m.text && <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.text}</span>}
                  {m.file && (m.file.type.startsWith('image/') ? <a href={m.file.url} target="_blank" rel="noreferrer"><img src={m.file.url} alt={m.file.name} loading="lazy" /></a>
                    : m.file.type.startsWith('audio/') ? <audio controls src={m.file.url} preload="none" />
                    : m.file.type.startsWith('video/') ? <video controls src={m.file.url} preload="metadata" />
                    : <a href={m.file.url} target="_blank" rel="noreferrer">📄 {m.file.name} ({Math.round(m.file.size / 1024)} KB)</a>)}
                </>}
                <span className="who" style={{ textAlign: 'right' }}>{new Date(m.at).toLocaleTimeString('az-AZ', { hour: '2-digit', minute: '2-digit' })}
                  {mine && !m.deleted && <button className="btn ghost sm chat-act" onClick={async () => { await del(`/api/chat/messages/${m.id}`); setMsgs(x => x.map(y => y.id === m.id ? { ...y, deleted: true } : y)) }}>sil</button>}
                  {!mine && !m.deleted && me?.role === 'student' && <button className="btn ghost sm chat-act" style={{ color: 'var(--bad)' }} title="Müəllimə bildir" onClick={async () => { try { await post(`/api/chat/messages/${m.id}/report`, {}); toast('Müəllimə bildirildi') } catch (e: any) { toast(e.message) } }}>! bildir</button>}
                </span>
              </div>
            </div>)
        })}
        {msgs.length === 0 && <p className="muted small" style={{ textAlign: 'center' }}>Hələ mesaj yoxdur – ilk mesajı yazın.</p>}
      </div>
      <div className="chat-input">
        <label className="btn" title="Şəkil, PDF, video (2 GB-a qədər)" aria-label="Fayl əlavə et"><Icon name="clip" /><input type="file" hidden accept="image/*,application/pdf,audio/*,video/mp4,video/webm,video/quicktime" onChange={e => { const f = e.target.files?.[0]; if (f) send(f); e.target.value = '' }} /></label>
        <textarea className="sel grow" rows={1} value={text} placeholder={t('Mesaj yazın…')} aria-label="Mesaj"
          onChange={e => { setText(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !('ontouchstart' in window)) { e.preventDefault(); send() } }} />
        {text.trim() ? <button className="btn primary" onClick={() => send()} disabled={sending} aria-label={t('Göndər')}>➤</button>
          : <button className="btn" onClick={record} aria-pressed={!!rec} style={rec ? { color: 'var(--bad)' } : undefined} aria-label={rec ? 'Səs yazısını dayandır' : 'Səs yaz'}><Icon name="mic" />{rec ? ' dayandır' : ''}</button>}
      </div>
    </section>
  )
}
