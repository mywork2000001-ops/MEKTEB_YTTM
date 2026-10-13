import { Suspense, useEffect, useState } from 'react'
import { ApiError, del, get, patch, post, put, setSettingsToken, settingsToken } from '../../api'
import { useAuth } from '../../auth'
import { AsyncBtn, ErrorBox, Field, Loading, toast, Top, useLoad, ord } from '../../ui'
import { LookPanel, PasswordPanel } from '../shared'
import { useT } from '../../i18n'

import SettingsRoster from './SettingsRoster'
import SettingsAdmin from './SettingsAdmin'
import Programs from './Programs'
const Roster = SettingsRoster
const Admin = SettingsAdmin

export default function Settings() {
  const { me } = useAuth()
  const t = useT()
  const admin = me?.role === 'admin'
  const [lock, , , reloadLock] = useLoad<{ has_password: boolean }>(() => get('/api/settings/lock'), [])
  const [unlocked, setUnlocked] = useState(() => !!settingsToken())
  const [tab, setTab] = useState(() => new URLSearchParams(location.search).get('tab') || 'look')
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

  const tabs: [string, string][] = [['look', 'Görünüş'], ['account', 'Hesab'], ['school', me?.workspace === 'private' ? 'Fərdi məkan' : 'Məktəb'], ['classes', 'Siniflər'], ['programs', 'Proqramlar'],
    ['students', 'Şagirdlər'], ['archive', 'Arxiv'], ['ai', 'Süni intellekt'], ['lock', 'Kilid'],
    ...(admin ? [['teachers', 'Müəllimlər'], ['bank', 'Test bazası'], ['audit', 'Audit jurnalı']] as [string, string][] : [])]
  return (
    <>
      <Top title="Tənzimləmələr" sub={admin ? 'Admin: bütün ümumi tənzimləmələr' : 'Yalnız sizə aid tənzimləmələr'}
        actions={lock.has_password ? <button className="btn sm" onClick={() => { setSettingsToken(null); setUnlocked(false) }}>Kilidlə</button> : undefined} />
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} aria-selected={tab === k} onClick={() => setTab(k)}>{t(l)}</button>)}</div>
      <Suspense fallback={<Loading />}>
        {tab === 'look' && <LookPanel />}
        {tab === 'account' && <PasswordPanel student={false} />}
        {tab === 'school' && (me?.workspace === 'private' ? <PrivatePanel /> : <SchoolPanel admin={admin} />)}
        {(tab === 'classes' || tab === 'students' || tab === 'archive') && <Roster tab={tab} />}
        {tab === 'programs' && <Programs />}
        {tab === 'ai' && <AiPanel />}
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
  useEffect(() => { if (school) setF({ name: school.name, utis: school.utis || '', short_name: school.short_name || '', region: school.region || '', bells: school.bells || {},
    deputy: school.doc_settings?.deputy || '', director: school.doc_settings?.director || '' }) }, [school])
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
          <h3 className="small muted" style={{ margin: '14px 0 6px' }}>Rəsmi sənədlərdə imza (çap / PDF)</h3>
          <div className="fg">
            <Field label="Direktor müavini (tədris işləri üzrə)" hint="ad, soyad – hesabatların altında"><input value={f.deputy} onChange={e => setF({ ...f, deputy: e.target.value })} /></Field>
            <Field label="Direktor" hint="məktəb üzrə hesabatda"><input value={f.director} onChange={e => setF({ ...f, director: e.target.value })} /></Field>
          </div>
          <h3 className="small muted" style={{ margin: '14px 0 6px' }}>Dərs vaxtları (bütün məktəb)</h3>
          <div className="fg">{Array.from({ length: 8 }, (_, i) => String(i + 1)).map(k => (
            <Field key={k} label={`${ord(k)} saat`}><input value={f.bells[k] || ''} placeholder="08:50–09:35" onChange={e => setF({ ...f, bells: { ...f.bells, [k]: e.target.value } })} /></Field>))}</div>
          <AsyncBtn className="btn primary" ok="Yadda saxlanıldı" onClick={async () => {
            const bells = Object.fromEntries(Object.entries(f.bells).filter(([, v]) => v))
            await patch(`/api/schools/${school.id}`, { name: f.name, utis: f.utis || null, short_name: f.short_name || null, region: f.region || null, bells,
              doc_settings: { deputy: f.deputy.trim() || null, director: f.director.trim() || null } }); reload(); await refresh()
          }}>Yadda saxla</AsyncBtn>
        </section>)}
    </div>
  )
}

type AiProv = { id: string; label: string; models: string[]; key_url?: string; hint?: string; custom: boolean }
type AiState = { purpose: string; provider: string | null; model: string | null; base_url: string | null; has_key: boolean; key_mask: string | null; fallback_plan?: boolean; providers: AiProv[] }
type ScanKey = { no: number; provider: string; model: string; on: boolean; has_key: boolean; key_mask: string | null
  status: { state: 'ok' | 'cooldown'; code: string | null; until: string | null; today: number } | null }
type ScanKeys = { keys: ScanKey[]; providers: { id: string; label: string; models: string[]; key_url?: string; hint?: string }[] }
type AiPurpose = 'scan' | 'plan' | 'review'
const AI_PURPOSES: [AiPurpose, string, string][] = [
  ['scan', '🗂 Kart oxuyucusu', 'KSQ/BSQ cavab kartlarının skanı – 5 açar, limit bitəndə avtomatik növbəti açara keçir'],
  ['plan', '📝 Gündəlik plan', 'Gündəlik planları süni intellekt hazırlayır'],
  ['review', '💬 Rəy', 'Test nəticələri və şagird sorğusu üzrə pedaqoji rəy'],
]

/** Süni intellekt – bir bölmə, təyinat açılan siyahıdan (docs/kart-oxuyucu-acarlar-promtu.md): kart oxuyucusu, gündəlik plan, rəy.
 *  Hər təyinatın öz açarı var – birinin kvotası bitəndə digərləri işləyir. */
function AiPanel() {
  const t = useT()
  const [p, setP] = useState<AiPurpose>(() => {
    const u = new URLSearchParams(location.search).get('ai')
    let saved: string | null = null
    try { saved = localStorage.getItem('ai-purpose') } catch { /* gizli pəncərə */ }
    const v = u || saved
    return v === 'scan' || v === 'plan' || v === 'review' ? v : 'scan'
  })
  const pick = (v: AiPurpose) => { setP(v); try { localStorage.setItem('ai-purpose', v) } catch { /* gizli pəncərə */ } }
  const cur = AI_PURPOSES.find(x => x[0] === p)!
  return (
    <section className="panel" style={{ maxWidth: 720 }}>
      <h2>{t('Süni intellekt')}</h2>
      <Field label={t('Təyinat')} hint={t(cur[2])}>
        <select value={p} onChange={e => pick(e.target.value as AiPurpose)}>
          {AI_PURPOSES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></Field>
      <p className="small muted">{t('Hər təyinatın öz açarı var: birinin limiti və ya balansı bitəndə digərləri işləməyə davam edir. Açarlar serverdə şifrəli saxlanır, heç kimə göstərilmir. Pulsuz açar: Google AI Studio (aistudio.google.com) – hər Google hesabı ayrıca pulsuz kvota verir.')}</p>
      {p === 'scan' ? <ScanKeysForm key="scan" /> : <AiKeyForm key={p} purpose={p} />}
    </section>
  )
}

/** Bir təyinatın (plan / rəy) açarı. Açar şifrəli saxlanır, geri göstərilmir. */
function AiKeyForm({ purpose }: { purpose: 'plan' | 'review' }) {
  const t = useT()
  const q = `?purpose=${purpose}`
  const [s, err, , reload] = useLoad<AiState>(() => get('/api/ai/settings' + q), [purpose])
  const [f, setF] = useState<{ provider: string; model: string; api_key: string; base_url: string } | null>(null)
  const [test, setTest] = useState<string | null>(null)
  if (!s) return <><ErrorBox error={err} /><Loading /></>
  const v = f || { provider: s.provider || 'gemini', model: s.model || s.providers.find(x => x.id === (s.provider || 'gemini'))?.models[0] || '', api_key: '', base_url: s.base_url || '' }
  const prov = s.providers.find(x => x.id === v.provider) || s.providers[0]
  const set = (patch: Partial<typeof v>) => setF({ ...v, ...patch })
  const sameProv = s.has_key && s.provider === v.provider
  return (
    <>
      {purpose === 'plan' && <p className="small muted" style={{ marginTop: 0 }}>{t('Şagirdlərin adları göndərilmir – yalnız perspektiv plandakı dərs məlumatı.')}</p>}
      {purpose === 'review' && <p className="small muted" style={{ marginTop: 0 }}>{t('Şagird adları provayderə göndərilmir (kodla); sorğuda – yalnız ümumi rəqəmlər və anonim mətnlər.')}</p>}
      {s.has_key && <div className="banner" style={{ background: 'var(--ok-soft)', color: 'var(--ok)' }}>{t('Qoşulub')}: {s.providers.find(x => x.id === s.provider)?.label} · {s.model} · {t('açar')} {s.key_mask}</div>}
      {s.fallback_plan && <div className="banner">{t('Rəy üçün ayrıca açar yoxdur – hələlik gündəlik plan açarı işləyir.')}</div>}
      <div className="fg">
        <Field label={t('Xidmət (provayder)')}><select value={v.provider} onChange={e => { const np = s.providers.find(x => x.id === e.target.value)!; set({ provider: np.id, model: np.models[0] || '', api_key: '' }) }}>
          {s.providers.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></Field>
        <Field label="Model" hint={t('Siyahıdan seçin və ya adını yazın')}><input list={'ai-models-' + purpose} value={v.model} onChange={e => set({ model: e.target.value })} />
          <datalist id={'ai-models-' + purpose}>{prov.models.map(m => <option key={m} value={m} />)}</datalist></Field>
        {prov.custom && <Field label={t('Ünvan (base URL)')} hint={t('OpenAI-uyğun, https://…/v1')} full><input value={v.base_url} placeholder="https://api.mistral.ai/v1" onChange={e => set({ base_url: e.target.value })} /></Field>}
        <Field label={t('API açarı')} hint={sameProv ? t('Boş saxlasanız, köhnə açar qalır') : prov.hint} full>
          <input type="password" autoComplete="off" value={v.api_key} placeholder={sameProv ? s.key_mask || '' : t('Açarı buraya yapışdırın')} onChange={e => set({ api_key: e.target.value.trim() })} /></Field>
      </div>
      {prov.key_url && <p className="small">{t('Açarı haradan almalı')}: <a href={prov.key_url} target="_blank" rel="noreferrer">{prov.key_url.replace('https://', '')}</a>{prov.hint && !sameProv ? '' : prov.hint ? ' · ' + prov.hint : ''}</p>}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <AsyncBtn className="btn primary" ok={t('Yadda saxlandı')} onClick={async () => { await put('/api/ai/settings' + q, { ...v, api_key: v.api_key || null, base_url: v.base_url || null }); setF(null); setTest(null); reload() }}>{t('Yadda saxla')}</AsyncBtn>
        {(s.has_key || s.fallback_plan) && <AsyncBtn className="btn" onClick={async () => { setTest(t('Yoxlanılır…')); try { const r = await post<{ reply: string; model: string }>('/api/ai/test' + q); setTest(t('İşləyir ✓') + ' (' + r.model + ': «' + r.reply + '»)') } catch (e) { setTest((e as Error).message) } }}>{t('Yoxla')}</AsyncBtn>}
        {s.has_key && <AsyncBtn className="btn ghost" ok={t('Açar silindi')} onClick={async () => { await del('/api/ai/settings' + q); setF(null); setTest(null); reload() }}>{t('Açarı sil')}</AsyncBtn>}
      </div>
      {test && <p className="small" style={{ marginBottom: 0 }}>{test}</p>}
    </>
  )
}

const SCAN_CODE: Record<string, string> = { 'ai:rate': 'limit', 'ai:credit': 'balans bitib', 'ai:key': 'açar qəbul olunmur', 'ai:limit': 'aylıq limit', 'ai:model': 'model əlçatan deyil' }

/** Kart oxuyucusu: 5 açar, sıra ilə; limit / balans / açar xətasında oxuyucu özü növbəti açara keçir. */
function ScanKeysForm() {
  const t = useT()
  const [d, err, , reload] = useLoad<ScanKeys>(() => get('/api/ai/scan-keys'), [])
  type Row = { provider: string; model: string; api_key: string; on: boolean; keep_from: number | null; mask: string | null; status: ScanKey['status'] }
  const [rows, setRows] = useState<Row[] | null>(null)
  const [test, setTest] = useState<Record<number, string>>({})
  useEffect(() => { if (d) setRows(d.keys.map(k => ({ provider: k.provider, model: k.model, api_key: '', on: k.on || !k.has_key, keep_from: k.has_key ? k.no : null, mask: k.key_mask, status: k.status }))) }, [d])
  if (!d || !rows) return <><ErrorBox error={err} /><Loading /></>
  const set = (i: number, patch: Partial<Row>) => setRows(rs => rs!.map((r, k) => k === i ? { ...r, ...patch } : r))
  const move = (i: number, dir: -1 | 1) => setRows(rs => { const n = [...rs!]; const j = i + dir; if (j < 0 || j >= n.length) return n; [n[i], n[j]] = [n[j], n[i]]; return n })
  const save = async () => {
    await put('/api/ai/scan-keys', { keys: rows.map(r => ({ provider: r.api_key || r.keep_from ? r.provider : null, model: r.model, api_key: r.api_key || null, keep_from: r.api_key ? null : r.keep_from, on: r.on })) })
    setTest({}); reload()
  }
  const until = (s: string) => new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <>
      <p className="small muted" style={{ marginTop: 0 }}>{t('Oxuyucu açarları sıra ilə işlədir. Açarın limiti və ya balansı bitəndə kart həmin anda növbəti açarla oxunur. Bütün açarlar tükənəndə kartlar gözləyir və limit bərpa olunanda özü oxunur.')}</p>
      {rows.map((r, i) => {
        const pv = d.providers.find(x => x.id === r.provider) || d.providers[0]
        const st = r.status
        return (
          <div key={i} className="kpick" style={{ maxHeight: 'none', marginBottom: 8 }}>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <b>{t('Açar {n}', { n: i + 1 })}</b>
              {r.mask && !st && <span className="small muted">{r.mask}</span>}
              {st && (st.state === 'ok'
                ? <span className="small" style={{ color: 'var(--ok)' }}>✓ {t('hazırdır')} · {r.mask} · {t('bu gün: {n} kart', { n: st.today })}</span>
                : <span className="small" style={{ color: 'var(--warn)' }}>⏸ {t(SCAN_CODE[st.code || ''] || 'limit')} · {t('{t}-dək', { t: until(st.until!) })} · {r.mask}</span>)}
              <span className="grow" />
              <label className="check small"><input type="checkbox" checked={r.on} onChange={e => set(i, { on: e.target.checked })} />{t('Aktiv')}</label>
              <button type="button" className="btn sm ghost" disabled={i === 0} onClick={() => move(i, -1)} title={t('Yuxarı')}>↑</button>
              <button type="button" className="btn sm ghost" disabled={i === rows.length - 1} onClick={() => move(i, 1)} title={t('Aşağı')}>↓</button>
            </div>
            <div className="fg">
              <Field label={t('Xidmət (provayder)')}><select value={r.provider} onChange={e => { const np = d.providers.find(x => x.id === e.target.value)!; set(i, { provider: np.id, model: np.models[0], api_key: '', keep_from: null, mask: null, status: null }) }}>
                {d.providers.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></Field>
              <Field label="Model"><select value={r.model} onChange={e => set(i, { model: e.target.value })}>
                {[...new Set([r.model, ...pv.models])].map(m => <option key={m} value={m}>{m}</option>)}</select></Field>
              <Field label={t('API açarı')} hint={r.keep_from ? t('Boş saxlasanız, köhnə açar qalır') : pv.hint} full>
                <input type="password" autoComplete="off" value={r.api_key} placeholder={r.mask || t('Açarı buraya yapışdırın')} onChange={e => set(i, { api_key: e.target.value.trim() })} /></Field>
            </div>
            <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
              {r.keep_from && !r.api_key && d.keys[r.keep_from - 1]?.has_key && <AsyncBtn className="btn sm" onClick={async () => {
                setTest(x => ({ ...x, [i]: t('Yoxlanılır…') }))
                try { const res = await post<{ reply: string; model: string }>(`/api/ai/scan-keys/${r.keep_from}/test`); setTest(x => ({ ...x, [i]: t('İşləyir ✓') + ' (' + res.model + ')' })); reload() }
                catch (e) { setTest(x => ({ ...x, [i]: (e as Error).message })) } }}>{t('Yoxla')}</AsyncBtn>}
              {(r.keep_from || r.api_key) && <button type="button" className="btn sm ghost" onClick={() => set(i, { api_key: '', keep_from: null, mask: null, status: null })}>{t('Sil')}</button>}
              {pv.key_url && <a className="small" href={pv.key_url} target="_blank" rel="noreferrer">{t('Açarı haradan almalı')}: {pv.key_url.replace('https://', '')}</a>}
              {test[i] && <span className="small">{test[i]}</span>}
            </div>
          </div>)
      })}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <AsyncBtn className="btn primary" ok={t('Yadda saxlandı')} onClick={save}>{t('Yadda saxla')}</AsyncBtn>
        <AsyncBtn className="btn ghost" onClick={async () => { await post('/api/ai/scan-keys/reset'); toast(t('Limit işarələri sıfırlandı – gözləyən kartlar növbəti dövrədə oxunacaq')); reload() }}
          title={t('Balansı artırmısınızsa və ya yeni gün başlayıbsa')}>↺ {t('Limitləri sıfırla')}</AsyncBtn>
      </div>
      <p className="small muted" style={{ marginBottom: 0 }}>{t('Ayrıca kart açarı yoxdursa, kartları hələlik gündəlik plan açarı oxuyur. Yuxarıdakı «Sil» sətri təmizləyir – dəyişiklik «Yadda saxla» ilə tətbiq olunur.')}</p>
    </>
  )
}


/** Fərdi (repetitor) məkan: ad və dərs vaxtları; məktəbə aid deyil, yalnız sizə görünür. */
function PrivatePanel() {
  const { refresh } = useAuth()
  const [school, err, , reload] = useLoad<any>(() => get('/api/school'), [])
  const [f, setF] = useState<{ name: string; bells: Record<string, string> } | null>(null)
  useEffect(() => { if (school) setF({ name: school.name, bells: school.bells || {} }) }, [school])
  if (!f) return err ? <ErrorBox error={err} /> : <Loading />
  return (
    <>
    <section className="panel" style={{ maxWidth: 720 }}>
      <h2>Fərdi məkan <small>hazırlıq / repetitor</small></h2>
      <p className="small muted">Bu məkandakı siniflər, şagirdlər, jurnal və nəticələr məktəbin hesabatlarına, siyahılarına və adminə düşmür.
        Tədris ili və bayramlar məktəbin təqvimindən köçürülüb. Məkanlar arasında keçid – yuxarıdakı «Məktəb · Fərdi» düyməsi.</p>
      <div className="fg">
        <Field label="Ad (çap sənədlərinin başlığında)" full><input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} maxLength={300} /></Field>
      </div>
      <h3 className="small muted" style={{ margin: '14px 0 6px' }}>Dərs vaxtları</h3>
      <div className="fg">{Array.from({ length: 9 }, (_, i) => String(i)).map(k => (
        <Field key={k} label={`${ord(k)} saat`}><input value={f.bells[k] || ''} placeholder="15:00–15:45" onChange={e => setF({ ...f, bells: { ...f.bells, [k]: e.target.value } })} /></Field>))}</div>
      <AsyncBtn className="btn primary" ok="Yadda saxlanıldı" disabled={f.name.trim().length < 3} onClick={async () => {
        await patch('/api/workspaces/private', { name: f.name.trim(), bells: f.bells }); reload(); await refresh()
      }}>Yadda saxla</AsyncBtn>
    </section>
    <PrivateCalendar />
    </>
  )
}

/** Fərdi məkanın təqvimi: tədris ili (məs. yay hazırlığı), bayramlar və tətillər; məktəbin təqviminə qaytarmaq. */
function PrivateCalendar() {
  const [cal, err, , reload] = useLoad<any>(() => get('/api/workspaces/private/calendar'), [])
  const [y, setY] = useState<any>(null)
  const [h, setH] = useState({ date: '', to: '', name: '' })
  const [reset, setReset] = useState(false)
  useEffect(() => { if (cal) setY({ ...cal.year }) }, [cal])
  if (!cal || !y) return err ? <ErrorBox error={err} /> : <Loading />
  const fmtD = (d: string) => d.split('-').reverse().join('.')
  // eyni adlı, arasında 3 gündən az fasilə olan günlər – bir tətil (həftəsonu daxil deyil)
  const groups: { from: string; to: string; name: string; ids: number[] }[] = []
  for (const x of cal.holidays) {
    const g = groups[groups.length - 1]
    if (g && g.name === x.name && (new Date(x.date).getTime() - new Date(g.to).getTime()) / 864e5 <= 3) { g.to = x.date; g.ids.push(x.id) }
    else groups.push({ from: x.date, to: x.date, name: x.name, ids: [x.id] })
  }
  return (
    <section className="panel" style={{ maxWidth: 720, marginTop: 16 }}>
      <h2>Təqvim <small>tədris ili, bayramlar və tətillər</small></h2>
      <p className="small muted" style={{ marginTop: 0 }}>Perspektiv plan, jurnal günləri və yarımil hesabları bu tarixlərlə işləyir. Bayram və tətil günlərində dərs olmur –
        plan növbəti dərs gününə sürüşür. Məktəbin təqviminə təsir etmir.</p>
      <div className="fg">
        <Field label="Ad" hint="məs. 2026–2027 və ya Yay 2027"><input value={y.name} onChange={e => setY({ ...y, name: e.target.value })} maxLength={20} /></Field>
        <Field label="Başlanğıc"><input type="date" value={y.start} onChange={e => setY({ ...y, start: e.target.value })} /></Field>
        <Field label="I yarımilin sonu"><input type="date" value={y.sem1_end} onChange={e => setY({ ...y, sem1_end: e.target.value })} /></Field>
        <Field label="II yarımilin başlanğıcı"><input type="date" value={y.sem2_start} onChange={e => setY({ ...y, sem2_start: e.target.value })} /></Field>
        <Field label="İlin sonu"><input type="date" value={y.end} onChange={e => setY({ ...y, end: e.target.value })} /></Field>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <AsyncBtn className="btn primary" ok="Tədris ili yadda saxlanıldı" onClick={async () => {
          await put('/api/workspaces/private/year', { name: y.name, start: y.start, sem1_end: y.sem1_end, sem2_start: y.sem2_start, end: y.end }); reload()
        }}>Tədris ilini saxla</AsyncBtn>
        {!reset ? <button className="btn ghost" onClick={() => setReset(true)}>Məktəbin təqvimini yenidən köçür</button> : (
          <span className="row" style={{ gap: 6 }}><span className="small">Tarixlər və bayramlar məktəbinki ilə əvəzlənsin?</span>
            <AsyncBtn className="btn sm danger" ok="Məktəbin təqvimi köçürüldü" onClick={async () => { await post('/api/workspaces/private/calendar/reset'); setReset(false); reload() }}>Bəli</AsyncBtn>
            <button className="btn sm" onClick={() => setReset(false)}>Xeyr</button></span>)}
      </div>
      <h3 className="small muted" style={{ margin: '18px 0 6px' }}>Bayramlar və tətillər <span className="muted">({cal.holidays.length} gün)</span></h3>
      <div className="fg">
        <Field label="Tarix (və ya tətilin başlanğıcı)"><input type="date" value={h.date} onChange={e => setH({ ...h, date: e.target.value })} /></Field>
        <Field label="Son tarix" hint="tətil üçün; tək gün – boş"><input type="date" value={h.to} onChange={e => setH({ ...h, to: e.target.value })} /></Field>
        <Field label="Ad" full><input value={h.name} onChange={e => setH({ ...h, name: e.target.value })} placeholder="məs. Novruz bayramı, qış tətili" maxLength={120} /></Field>
      </div>
      <AsyncBtn className="btn" disabled={!h.date || h.name.trim().length < 2} ok="Əlavə olundu" onClick={async () => {
        await post('/api/workspaces/private/holidays', { date: h.date, to: h.to || null, name: h.name.trim() }); setH({ date: '', to: '', name: '' }); reload()
      }}>+ Əlavə et</AsyncBtn>
      <div className="mlist" style={{ marginTop: 10 }}>{cal.holidays.length === 0 ? <div className="mrow"><span className="muted small">Bayram yoxdur.</span></div> :
        groups.map(g => (
          <div key={g.ids[0]} className="mrow"><span><b>{g.from === g.to ? fmtD(g.from) : `${fmtD(g.from).slice(0, 5)}–${fmtD(g.to)}`}</b> <span className="small muted">{g.name}{g.ids.length > 1 ? ` · ${g.ids.length} gün` : ''}</span></span>
            <span className="mact"><AsyncBtn className="btn sm ghost" ok="Silindi" onClick={async () => { for (const id of g.ids) await del(`/api/workspaces/private/holidays/${id}`); reload() }}>Sil</AsyncBtn></span></div>))}</div>
    </section>
  )
}
