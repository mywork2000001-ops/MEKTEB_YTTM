import { lazy, Suspense, useEffect, useState } from 'react'
import { ApiError, get, patch, post, put, setSettingsToken, settingsToken } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, ErrorBox, Field, Loading, toast, Top, useLoad } from '../../ui'
import { LookPanel, PasswordPanel } from '../shared'

const Roster = lazy(() => import('./SettingsRoster'))
const Admin = lazy(() => import('./SettingsAdmin'))

export default function Settings() {
  const { me } = useAuth()
  const admin = me?.role === 'admin'
  const [lock, , , reloadLock] = useLoad<{ has_password: boolean }>(() => get('/api/settings/lock'), [])
  const [unlocked, setUnlocked] = useState(() => !!settingsToken())
  const [tab, setTab] = useState('look')
  // 15 dəqiqədən sonra avtomatik kilid (server də açarı qəbul etmir)
  useEffect(() => {
    if (!unlocked) return
    const t = setTimeout(() => { setSettingsToken(null); setUnlocked(false); toast('Tənzimləmələr kilidləndi') }, 15 * 60 * 1000)
    return () => clearTimeout(t)
  }, [unlocked])
  useEffect(() => {
    const h = (e: PromiseRejectionEvent) => { if (e.reason instanceof ApiError && e.reason.status === 423) { setSettingsToken(null); setUnlocked(false) } }
    window.addEventListener('unhandledrejection', h)
    return () => window.removeEventListener('unhandledrejection', h)
  }, [])

  if (!lock) return <Loading />
  if (lock.has_password && !unlocked) return <Unlock onDone={() => setUnlocked(true)} />

  const tabs: [string, string][] = [['look', 'Görünüş'], ['account', 'Hesab'], ['school', 'Məktəb'], ['classes', 'Siniflər'],
    ['students', 'Şagirdlər'], ['archive', 'Arxiv'], ['lock', 'Kilid'],
    ...(admin ? [['teachers', 'Müəllimlər'], ['bank', 'Test bazası'], ['audit', 'Audit jurnalı']] as [string, string][] : [])]
  return (
    <>
      <Top title="Tənzimləmələr" sub={admin ? 'Admin: bütün ümumi tənzimləmələr' : 'Yalnız sizə aid tənzimləmələr'}
        actions={lock.has_password ? <button className="btn sm" onClick={() => { setSettingsToken(null); setUnlocked(false) }}>Kilidlə</button> : undefined} />
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}</div>
      <Suspense fallback={<Loading />}>
        {tab === 'look' && <LookPanel />}
        {tab === 'account' && <PasswordPanel student={false} />}
        {tab === 'school' && <SchoolPanel admin={admin} />}
        {(tab === 'classes' || tab === 'students' || tab === 'archive') && <Roster tab={tab} />}
        {tab === 'lock' && <LockPanel has={lock.has_password} onChange={reloadLock} />}
        {(tab === 'teachers' || tab === 'bank' || tab === 'audit') && <Admin tab={tab} />}
      </Suspense>
    </>
  )
}

function Unlock({ onDone }: { onDone: () => void }) {
  const [p, setP] = useState('')
  const [err, setErr] = useState<unknown>()
  return (
    <form className="panel lockbox" onSubmit={async e => { e.preventDefault(); try { const r = await post<{ token: string }>('/api/settings/unlock', { password: p }); setSettingsToken(r.token); onDone() } catch (x) { setErr(x) } }}>
      <h2>Tənzimləmələr kilidlidir</h2>
      <Field label="Parol"><input type="password" value={p} onChange={e => setP(e.target.value)} autoFocus /></Field>
      <ErrorBox error={err} />
      <button className="btn primary w100" style={{ marginTop: 10 }}>Aç (15 dəqiqə)</button>
    </form>
  )
}

function LockPanel({ has, onChange }: { has: boolean; onChange: () => void }) {
  const [p, setP] = useState('')
  return (
    <section className="panel" style={{ maxWidth: 480 }}>
      <h2>Tənzimləmələr parolu</h2>
      <p className="small muted">{has ? 'Parol qoyulub. Hər açılışdan sonra 15 dəqiqə açıq qalır.' : 'Hazırda parol yoxdur – Tənzimləmələr sərbəst açılır.'}</p>
      <Field label={has ? 'Yeni parol (boş – parolu götür)' : 'Parol'}><input type="password" value={p} onChange={e => setP(e.target.value)} /></Field>
      <div className="row" style={{ marginTop: 10 }}>
        <AsyncBtn className="btn primary" ok={p ? 'Parol qoyuldu' : 'Parol götürüldü'} onClick={async () => {
          await put('/api/settings/password', { new: p || null })
          if (p) { const r = await post<{ token: string }>('/api/settings/unlock', { password: p }); setSettingsToken(r.token) }
          setP(''); onChange()
        }}>Yadda saxla</AsyncBtn>
      </div>
    </section>
  )
}

function SchoolPanel({ admin }: { admin: boolean }) {
  const { me, refresh } = useAuth()
  const [school, err, , reload] = useLoad<any>(() => get('/api/school'), [me?.school_id])
  const [q, setQ] = useState('')
  const [found, setFound] = useState<any[]>([])
  const [f, setF] = useState<any>(null)
  useEffect(() => { if (school) setF({ name: school.name, utis: school.utis || '', short_name: school.short_name || '', region: school.region || '', bells: school.bells || {} }) }, [school])
  useEffect(() => {
    if (q.trim().length < 2) { setFound([]); return }
    const t = setTimeout(() => get<any[]>('/api/schools', { q }).then(setFound, () => setFound([])), 300)
    return () => clearTimeout(t)
  }, [q])
  return (
    <div className="grid g2">
      <section className="panel">
        <h2>Mənim məktəbim</h2>
        <ErrorBox error={err} />
        {school ? <p><b>{school.name}</b>{admin && <><br /><span className="small muted">UTİS: {school.utis || 'yazılmayıb'}</span></>}</p> : <p className="muted">Məktəb seçilməyib.</p>}
        <Field label="Məktəbi adına görə tapın" hint="Eyni məktəbin müəllimləri ortaq sinif siyahısını və Müəllim otağını görür">
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="məs. Rafiq Nuriyev" /></Field>
        <div className="stack" style={{ marginTop: 8 }}>
          {found.map(s => <AsyncBtn key={s.id} className="btn" ok="Məktəb seçildi" onClick={async () => { await post('/api/me/school', { school_id: s.id }); setQ(''); await refresh(); reload() }}>{s.name}</AsyncBtn>)}
        </div>
      </section>
      {admin && f && school && (
        <section className="panel">
          <h2>Məktəb məlumatları (admin)</h2>
          <div className="fg">
            <Field label="Ad" full><input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field>
            <Field label="UTİS kodu" hint="yalnız rəqəm"><input inputMode="numeric" value={f.utis} onChange={e => setF({ ...f, utis: e.target.value.replace(/\D/g, '') })} /></Field>
            <Field label="Region"><input value={f.region} onChange={e => setF({ ...f, region: e.target.value })} /></Field>
          </div>
          <h3 className="small muted" style={{ margin: '14px 0 6px' }}>Dərs vaxtları (bütün məktəb)</h3>
          <div className="fg">{Array.from({ length: 8 }, (_, i) => String(i + 1)).map(k => (
            <Field key={k} label={`${k}-ci saat`}><input value={f.bells[k] || ''} placeholder="08:50–09:35" onChange={e => setF({ ...f, bells: { ...f.bells, [k]: e.target.value } })} /></Field>))}</div>
          <AsyncBtn className="btn primary" ok="Yadda saxlanıldı" onClick={async () => {
            const bells = Object.fromEntries(Object.entries(f.bells).filter(([, v]) => v))
            await patch(`/api/schools/${school.id}`, { name: f.name, utis: f.utis || null, short_name: f.short_name || null, region: f.region || null, bells }); reload()
          }}>Yadda saxla</AsyncBtn>
        </section>)}
    </div>
  )
}
