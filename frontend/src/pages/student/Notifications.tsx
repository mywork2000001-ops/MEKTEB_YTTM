// Şagird bildirişləri: açıq / tezliklə açılacaq testlər, sınaq nəticəsi, bu gün / sabah əlavə məşğələ.
// Server bildirişləri saxlamır – hər dəfə hesablanır; «görüldü» işarəsi yalnız bu cihazda (localStorage).
// Tətbiq açıq olanda (və ya quraşdırılmış PWA açıq olanda) yeni bildiriş brauzer bildirişi kimi də göstərilir.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { get } from '../../api'
import { Pill } from '../../ui'

type Note = { key: string; kind: string; title: string; text: string; link: string; at: string }
const SEEN = 'mk-seen-notes'
const TONE: Record<string, any> = { test: 'ok', 'sınaq': 'acc', 'nəticə': 'info', 'məşğələ': 'warn' }

function seen(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(SEEN) || '[]')) } catch { return new Set() }
}
function remember(keys: string[]) {
  try { localStorage.setItem(SEEN, JSON.stringify([...new Set([...seen(), ...keys])].slice(-300))) } catch { /* yaddaş bağlıdır */ }
}
async function show(n: Note) {
  try {
    const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined
    const opts = { body: n.text, icon: '/icon-192.png', tag: n.key, data: { link: n.link } }
    if (reg) await reg.showNotification(n.title, opts)
    else new Notification(n.title, opts)
  } catch { /* bildiriş icazəsi yoxdur */ }
}

export default function Notifications() {
  const nav = useNavigate()
  const [list, setList] = useState<Note[] | null>(null)
  const [fresh, setFresh] = useState<Set<string>>(new Set())
  const [perm, setPerm] = useState<string>(() => (typeof Notification !== 'undefined' ? Notification.permission : 'unsupported'))
  useEffect(() => {
    let live = true
    const load = () => get<Note[]>('/api/portal/notifications').then(x => {
      if (!live) return
      const old = seen()
      const nw = x.filter(n => !old.has(n.key))
      setList(x); setFresh(new Set(nw.map(n => n.key)))
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') nw.forEach(show)
      remember(nw.map(n => n.key))
    }, () => live && setList([]))
    load()
    const id = setInterval(load, 5 * 60 * 1000)
    return () => { live = false; clearInterval(id) }
  }, [])
  const ask = async () => {
    try { setPerm(await Notification.requestPermission()) } catch { setPerm('denied') }
  }
  if (!list || list.length === 0) return perm === 'default' ? (
    <section className="panel" style={{ marginBottom: 16 }}><div className="row"><span className="grow small muted">Yeni test və məşğələ barədə telefonda bildiriş almaq istəyirsən?</span>
      <button className="btn sm" onClick={ask}>Bildirişləri aç</button></div></section>) : null
  return (
    <section className="panel" style={{ marginBottom: 16 }}>
      <h2>Bildirişlər <small>{list.length}</small></h2>
      {list.map(n => (
        <button key={n.key} type="button" className="row" onClick={() => nav(n.link)}
          style={{ width: '100%', textAlign: 'left', background: 'none', border: 0, borderTop: '1px solid var(--line)', padding: '8px 0', cursor: 'pointer', color: 'inherit' }}>
          <Pill tone={TONE[n.kind]}>{n.kind}</Pill>
          <span className="grow"><b>{n.title}</b><br /><span className="small muted">{n.text}</span></span>
          {fresh.has(n.key) && <Pill tone="bad">yeni</Pill>}
        </button>))}
      {perm === 'default' && <div className="row" style={{ marginTop: 8 }}><span className="grow small muted">Tətbiq açıq olanda bildirişi telefonun ekranında da göstərək?</span>
        <button className="btn sm" onClick={ask}>Bildirişləri aç</button></div>}
    </section>
  )
}
