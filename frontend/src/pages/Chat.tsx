// Çat – müəllim və şagird üçün ortaq. Söhbətlər: qruplar (Müəllim otağı, sinif) + şəxsi yazışmalar (son mesaja görə).
// Yeni mesajlar hər 4 saniyədən bir yoxlanılır. Tam məxfilik: yazışmanı yalnız iştirakçılar görür.
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, del, get, patch, post } from '../api'
import { useAuth } from '../auth'
import { useT } from '../i18n'
import { azDT, Drawer, ErrorBox, Icon, Pill, toast, Top, useLoad } from '../ui'

type Room = { id: number; kind: 'class' | 'dm' | 'staff'; title: string; unread: number; avatar?: string | null; last: { text: string; at: string; mine?: boolean; sender?: string } | null }
type Msg = { id: number; sender_id: number; sender: string; avatar?: string | null; text: string | null; deleted: boolean; edited?: boolean; at: string; file: { name: string; type: string; size: number; url: string } | null }
type Read = { user_id: number; last_read_id: number; name: string }

/** Şəkli 256 px kvadrata kiçildib JPEG edir (telefon kamerasının 5 MB-lıq şəkli ~20 KB olur). */
async function squareJpeg(f: File, size = 256): Promise<Blob> {
  const img = await createImageBitmap(f)
  const s = Math.min(img.width, img.height)
  const c = document.createElement('canvas')
  c.width = c.height = size
  c.getContext('2d')!.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, size, size)
  return new Promise((ok, no) => c.toBlob(b => (b ? ok(b) : no(new Error('Şəkil oxunmadı'))), 'image/jpeg', 0.85))
}

function Face({ name, url, size = 42, bg = 'var(--accent-soft)' }: { name: string; url?: string | null; size?: number; bg?: string }) {
  return url
    ? <img src={url} alt="" aria-hidden className="chat-face" style={{ width: size, height: size }} />
    : <span aria-hidden className="chat-face" style={{ width: size, height: size, background: bg, fontSize: size > 30 ? 14 : 10 }}>{initials(name)}</span>
}

/** Çatda öz şəklim: seç → 256 px-ə kiçildilir → yüklənir; sil. */
function MyPhoto({ onClose }: { onClose: () => void }) {
  const [p, err, , reload] = useLoad<{ full_name: string; avatar: string | null }>(() => get('/api/chat/profile'), [])
  const [busy, setBusy] = useState(false)
  const pick = async (f?: File) => {
    if (!f) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', new File([await squareJpeg(f)], 'avatar.jpg', { type: 'image/jpeg' }))
      await api('/api/chat/avatar', { method: 'POST', form: fd }); toast('Şəkil qoyuldu'); reload()
    } catch (e) { toast(e instanceof Error ? e.message : 'Şəkil yüklənmədi') } finally { setBusy(false) }
  }
  return (
    <Drawer title="Çatda şəklim" onClose={onClose}>
      <ErrorBox error={err} />
      {p && <div className="stack" style={{ alignItems: 'center', textAlign: 'center' }}>
        <Face name={p.full_name} url={p.avatar} size={120} />
        <b>{p.full_name}</b>
        <p className="small muted">Şəkil çatda adınızın yanında görünür. İstədiyiniz şəkli seçin – avtomatik kvadrat kəsilib kiçildilir.</p>
        <label className="btn primary" style={{ minHeight: 44 }}>{busy ? 'Yüklənir…' : p.avatar ? 'Şəkli dəyiş' : 'Şəkil seç'}
          <input type="file" hidden accept="image/*" disabled={busy} onChange={e => { pick(e.target.files?.[0]); e.target.value = '' }} /></label>
        {p.avatar && <button className="btn ghost" onClick={async () => { await del('/api/chat/avatar'); toast('Şəkil silindi'); reload() }}>Şəkli sil</button>}
      </div>}
    </Drawer>
  )
}

const SMILES = ['😀', '😁', '😂', '🤣', '😊', '🙂', '😉', '😍', '🥰', '😎', '🤩', '🤔', '😮', '😢', '😭', '😅', '😇', '🙃', '😴', '😬',
  '👍', '👎', '👏', '🙏', '🤝', '👋', '💪', '✌️', '👌', '☝️', '❤️', '💙', '💚', '⭐', '🌟', '🔥', '💯', '✅', '❌', '❓',
  '📚', '📖', '✏️', '📝', '📐', '📏', '🧮', '🎓', '🏆', '🎉', '⏰', '📅', '💡', '🧠', '➕', '➖', '✖️', '➗', '🟰', '∞']
const STICKERS = ['👍', '👏', '🌟', '🏆', '💯', '🎉', '🔥', '❤️', '🙏', '😂', '😮', '🤔', '😢', '✅', '📚', '✏️', '🎓', '💡', '⏰', '👋', '🤝', '💪', '😎', '🥳']
/** Yalnız 1–3 smayldan ibarət mesaj – böyük (stiker kimi) göstərilir. */
const bigEmoji = (s: string | null) => {
  if (!s || s.length > 24 || !/^[\p{Extended_Pictographic}\p{Emoji_Component}‍️\s]+$/u.test(s) || /[0-9#*]/.test(s)) return false
  const n = [...s.replace(/\s/g, '').replace(/[‍️\u{1F3FB}-\u{1F3FF}]/gu, '')].length
  return n >= 1 && n <= 3
}

function EmojiPanel({ onEmoji, onSticker, onClose }: { onEmoji: (e: string) => void; onSticker: (e: string) => void; onClose: () => void }) {
  const [tab, setTab] = useState<'smile' | 'sticker'>('smile')
  return (
    <div className="emoji-panel" role="dialog" aria-label="Smayl və stikerlər">
      <div className="row" style={{ gap: 6, marginBottom: 6 }}>
        <button className={'btn sm' + (tab === 'smile' ? ' primary' : '')} onClick={() => setTab('smile')}>Smayllar</button>
        <button className={'btn sm' + (tab === 'sticker' ? ' primary' : '')} onClick={() => setTab('sticker')}>Stikerlər</button>
        <button className="btn sm ghost right" onClick={onClose} aria-label="Bağla">✕</button>
      </div>
      {tab === 'smile'
        ? <div className="emoji-grid">{SMILES.map(e => <button key={e} type="button" onClick={() => onEmoji(e)} aria-label={e}>{e}</button>)}</div>
        : <><div className="emoji-grid big">{STICKERS.map(e => <button key={e} type="button" onClick={() => onSticker(e)} aria-label={'Stiker ' + e}>{e}</button>)}</div>
          <p className="small muted" style={{ margin: '6px 0 0' }}>Stikerə toxunun – dərhal göndərilir.</p></>}
    </div>
  )
}
type Contact = { id: number; full_name: string; role: string; group: string; sub: string; room_id: number | null; avatar?: string | null }

const initials = (n: string) => n.split(' ').slice(0, 2).map(w => w[0] || '').join('').toUpperCase()
const when = (s?: string) => {
  if (!s) return ''
  const d = new Date(s), now = new Date()
  if (d.toDateString() === now.toDateString()) return azDT(d, { hour: '2-digit', minute: '2-digit' })
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (d.toDateString() === y.toDateString()) return 'dünən'
  return azDT(d, { day: '2-digit', month: '2-digit' })
}
const dayLabel = (s: string) => {
  const d = new Date(s), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1)
  return d.toDateString() === now.toDateString() ? 'Bu gün' : d.toDateString() === y.toDateString() ? 'Dünən'
    : azDT(d, { day: 'numeric', month: 'long', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' })
}

function Avatar({ room }: { room: Room }) {
  if (room.kind === 'dm') return <Face name={room.title} url={room.avatar} />
  return (
    <span aria-hidden style={{ width: 42, height: 42, borderRadius: '50%', background: room.kind === 'staff' ? 'var(--info-soft)' : 'var(--ok-soft)', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 14, flex: 'none' }}>
      <Icon name={room.kind === 'staff' ? 'staff' : 'classes'} />
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
  const [photo, setPhoto] = useState(false)
  useEffect(() => { const i = setInterval(reload, 15000); return () => clearInterval(i) }, [reload])
  const list = (rooms || []).filter(r => !q || r.title.toLowerCase().includes(q.toLowerCase()))
  const groups = list.filter(r => r.kind !== 'dm'), dms = list.filter(r => r.kind === 'dm')
  const openContact = async (c: Contact) => {
    const r = c.room_id ? { id: c.room_id, kind: 'dm' as const, title: c.full_name, avatar: c.avatar } : await post('/api/chat/dm', { user_id: c.id })
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
          <button className="btn" onClick={() => setPhoto(true)}>Şəklim</button>
          {me?.role !== 'student' && <button className="btn" onClick={async () => setReports(await get('/api/chat/reports'))}>Bildirişlər (!)</button>}
        </>} />
      <ErrorBox error={err} />
      {(rooms?.length || 0) > 5 && <div className="search" style={{ marginBottom: 10 }}><input placeholder="Söhbət axtar" value={q} onChange={e => setQ(e.target.value)} /></div>}
      {groups.length > 0 && <><h3 className="chat-h">Qruplar</h3><div className="jlist">{groups.map(r => <Row key={r.id} r={r} />)}</div></>}
      <h3 className="chat-h">Şəxsi yazışmalar</h3>
      <div className="jlist">{dms.map(r => <Row key={r.id} r={r} />)}
        {dms.length === 0 && <div className="empty">Hələ şəxsi yazışma yoxdur – «+ Yeni yazışma» ilə başlayın.</div>}</div>
      {contacts && <ContactPicker contacts={contacts} onPick={openContact} onClose={() => setContacts(null)} />}
      {photo && <MyPhoto onClose={() => { setPhoto(false); reload() }} />}
      {reports && (
        <Drawer title="Şagirdlərin bildirdiyi mesajlar" onClose={() => setReports(null)}>
          <p className="small muted">Yalnız «!» ilə bildirilən mesajlar görünür, yazışmanın qalanı görünmür.</p>
          <div className="stack">{reports.map(r => (
            <section key={r.id} className="panel">
              <p className="small muted">{r.class_name} · bildirən: {r.reporter} · {azDT(new Date(r.at), undefined, 'all')}</p>
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
<Face name={c.full_name} url={c.avatar} />
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
  const [editing, setEditing] = useState<Msg | null>(null)
  const [emoji, setEmoji] = useState(false)
  const [reads, setReads] = useState<Read[]>([])
  const [readers, setReaders] = useState<number | null>(null)
  const [askClear, setAskClear] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const last = useRef(0)
  const since = useRef<string | null>(null)
  const load = async () => {
    try {
      const n = await get<Msg[]>(`/api/chat/rooms/${room.id}/messages`, { after_id: last.current })
      if (n.length) { last.current = n[n.length - 1].id; setMsgs(m => [...m, ...n]); post(`/api/chat/rooms/${room.id}/read`).catch(() => {}) }
      // başqasının düzəltdiyi/sildiyi mesajlar (səhifəni yeniləmədən)
      if (since.current) {
        const c = await get<{ now: string; items: Msg[] }>(`/api/chat/rooms/${room.id}/changes`, { since: since.current })
        since.current = c.now
        if (c.items.length) { const ch = new Map(c.items.map(x => [x.id, x])); setMsgs(m => m.map(x => ch.get(x.id) || x)) }
      } else {
        since.current = (await get<{ now: string }>(`/api/chat/rooms/${room.id}/changes`, { since: new Date().toISOString() })).now
      }
      setReads(await get<Read[]>(`/api/chat/rooms/${room.id}/reads`))
    } catch (e) { setErr(e) }
  }
  useEffect(() => { last.current = 0; since.current = null; setMsgs([]); setEditing(null); load(); const i = setInterval(load, 4000); return () => clearInterval(i) }, [room.id])
  useEffect(() => { box.current?.scrollTo(0, box.current.scrollHeight) }, [msgs.length])
  const grow = (el: HTMLTextAreaElement | null) => { if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px' } }
  const sendText = async (body: string) => {
    const fd = new FormData()
    fd.append('text', body)
    await api(`/api/chat/rooms/${room.id}/messages`, { method: 'POST', form: fd })
    load()
  }
  const send = async (file?: File) => {
    if ((!text.trim() && !file) || sending) return
    if (editing && !file) {
      setSending(true)
      try {
        const m = await patch<Msg>(`/api/chat/messages/${editing.id}`, { text: text.trim() })
        setMsgs(x => x.map(y => (y.id === m.id ? m : y))); setEditing(null); setText(''); setTimeout(() => grow(input.current))
      } catch (e) { setErr(e) } finally { setSending(false) }
      return
    }
    const fd = new FormData()
    if (text.trim()) fd.append('text', text.trim())
    if (file) fd.append('file', file)
    setSending(true)
    try { await api(`/api/chat/rooms/${room.id}/messages`, { method: 'POST', form: fd }); setText(''); setEmoji(false); setTimeout(() => grow(input.current)); load() } catch (e) { setErr(e) } finally { setSending(false) }
  }
  const insertEmoji = (e: string) => {
    const el = input.current
    const a = el?.selectionStart ?? text.length, b = el?.selectionEnd ?? text.length
    const v = text.slice(0, a) + e + text.slice(b)
    setText(v)
    setTimeout(() => { if (el) { el.focus(); el.setSelectionRange(a + e.length, a + e.length); grow(el) } })
  }
  const canEdit = (m: Msg) => !m.deleted && !!m.text && Date.now() - new Date(m.at).getTime() < 24 * 3600 * 1000
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
        <button className="btn ghost" onClick={() => setAskClear(true)} aria-label="Söhbəti sil" title="Söhbəti sil"><Icon name="trash" /></button>
      </div>
      {askClear && (
        <div className="confirm" style={{ borderRadius: 0 }}>
          <span className="grow">{room.kind === 'dm' ? 'Yazışma yalnız sizdə silinəcək – həmsöhbətdə qalır.' : 'Söhbət tarixçəsi yalnız sizdə təmizlənəcək – digər iştirakçılarda qalır.'}</span>
          <button className="btn sm" onClick={() => setAskClear(false)}>Ləğv et</button>
          <button className="btn sm danger" onClick={async () => {
            try { await del(`/api/chat/rooms/${room.id}`); toast(room.kind === 'dm' ? 'Yazışma silindi' : 'Tarixçə təmizləndi'); onBack() } catch (e) { setErr(e); setAskClear(false) }
          }}>Sil</button>
        </div>)}
      <ErrorBox error={err} />
      <div className="msgs" ref={box}>
        {msgs.map(m => {
          const mine = m.sender_id === me?.id
          const day = new Date(m.at).toDateString()
          const sep = day !== prevDay; prevDay = day
          const showWho = !mine && room.kind !== 'dm' && (sep || prevSender !== m.sender_id); prevSender = m.sender_id
          const big = !m.deleted && !m.file && bigEmoji(m.text)
          return (
            <div key={m.id} style={{ display: 'contents' }}>
              {sep && <div className="chat-day"><span>{dayLabel(m.at)}</span></div>}
              <div className={'bubble' + (mine ? ' me' : '') + (big ? ' sticker' : '') + (editing?.id === m.id ? ' editing' : '')}>
                {showWho && <span className="who row" style={{ gap: 6, flexWrap: 'nowrap' }}><Face name={m.sender} url={m.avatar} size={22} />{m.sender}</span>}
                {m.deleted ? <i className="muted">mesaj silinib</i> : <>
                  {m.text && (big ? <span className="emoji-big" role="img" aria-label="stiker">{m.text}</span>
                    : <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.text}</span>)}
                  {m.file && (m.file.type.startsWith('image/') ? <a href={m.file.url} target="_blank" rel="noreferrer"><img src={m.file.url} alt={m.file.name} loading="lazy" /></a>
                    : m.file.type.startsWith('audio/') ? <audio controls src={m.file.url} preload="none" />
                    : m.file.type.startsWith('video/') ? <video controls src={m.file.url} preload="metadata" />
                    : <a href={m.file.url} target="_blank" rel="noreferrer">📄 {m.file.name} ({Math.round(m.file.size / 1024)} KB)</a>)}
                </>}
                <span className="who" style={{ textAlign: 'right' }}>{m.edited && <i>düzəldilib · </i>}{azDT(new Date(m.at), { hour: '2-digit', minute: '2-digit' })}
                  {mine && !m.deleted && (() => {
                    const who = reads.filter(r => r.user_id !== me?.id && r.last_read_id >= m.id)
                    if (room.kind === 'dm') return <span className={'chat-tick' + (who.length ? ' read' : '')} title={who.length ? 'Oxundu' : 'Göndərildi'}>{who.length ? ' ✓✓ oxundu' : ' ✓'}</span>
                    return who.length
                      ? <button className="btn ghost sm chat-act chat-tick read" onClick={() => setReaders(readers === m.id ? null : m.id)} aria-expanded={readers === m.id}>✓✓ {who.length} oxudu</button>
                      : <span className="chat-tick" title="Hələ heç kim oxumayıb"> ✓</span>
                  })()}
                  {mine && canEdit(m) && !big && <button className="btn ghost sm chat-act" onClick={() => { setEditing(m); setText(m.text || ''); setEmoji(false); setTimeout(() => { input.current?.focus(); grow(input.current) }) }}>düzəlt</button>}
                  {mine && !m.deleted && <button className="btn ghost sm chat-act" onClick={async () => { await del(`/api/chat/messages/${m.id}`); setMsgs(x => x.map(y => y.id === m.id ? { ...y, deleted: true } : y)); if (editing?.id === m.id) { setEditing(null); setText('') } }}>sil</button>}
                  {!mine && !m.deleted && me?.role === 'student' && <button className="btn ghost sm chat-act" style={{ color: 'var(--bad)' }} title="Müəllimə bildir" onClick={async () => { try { await post(`/api/chat/messages/${m.id}/report`, {}); toast('Müəllimə bildirildi') } catch (e: any) { toast(e.message) } }}>! bildir</button>}
                </span>
                {readers === m.id && <span className="chat-readers">Oxuyanlar: {reads.filter(r => r.user_id !== me?.id && r.last_read_id >= m.id).map(r => r.name).join(', ')}</span>}
              </div>
            </div>)
        })}
        {msgs.length === 0 && <p className="muted small" style={{ textAlign: 'center' }}>Hələ mesaj yoxdur – ilk mesajı yazın.</p>}
      </div>
      {editing && <div className="chat-editing"><span className="grow ellipsis"><b>Düzəliş:</b> {editing.text}</span>
        <button className="btn sm ghost" onClick={() => { setEditing(null); setText(''); setTimeout(() => grow(input.current)) }} aria-label="Düzəlişi ləğv et">✕</button></div>}
      {emoji && <EmojiPanel onEmoji={insertEmoji} onClose={() => setEmoji(false)}
        onSticker={async s => { setEmoji(false); try { await sendText(s) } catch (e) { setErr(e) } }} />}
      <div className="chat-input">
        {!editing && <label className="btn" title="Şəkil, PDF, video (2 GB-a qədər)" aria-label="Fayl əlavə et"><Icon name="clip" /><input type="file" hidden accept="image/*,application/pdf,audio/*,video/mp4,video/webm,video/quicktime" onChange={e => { const f = e.target.files?.[0]; if (f) send(f); e.target.value = '' }} /></label>}
        <button className="btn" onClick={() => setEmoji(v => !v)} aria-pressed={emoji} aria-label="Smayl və stikerlər" title="Smayl və stikerlər">😊</button>
        <textarea ref={input} className="sel grow" rows={1} value={text} placeholder={t(editing ? 'Mesajı düzəldin…' : 'Mesaj yazın…')} aria-label="Mesaj"
          onChange={e => { setText(e.target.value); grow(e.target) }}
          onKeyDown={e => {
            if (e.key === 'Escape' && editing) { setEditing(null); setText('') }
            if (e.key === 'Enter' && !e.shiftKey && !('ontouchstart' in window)) { e.preventDefault(); send() }
          }} />
        {text.trim() || editing ? <button className="btn primary" onClick={() => send()} disabled={sending || !text.trim()} aria-label={t(editing ? 'Yadda saxla' : 'Göndər')}>{editing ? '✓' : '➤'}</button>
          : <button className="btn" onClick={record} aria-pressed={!!rec} style={rec ? { color: 'var(--bad)' } : undefined} aria-label={rec ? 'Səs yazısını dayandır' : 'Səs yaz'}><Icon name="mic" />{rec ? ' dayandır' : ''}</button>}
      </div>
    </section>
  )
}
