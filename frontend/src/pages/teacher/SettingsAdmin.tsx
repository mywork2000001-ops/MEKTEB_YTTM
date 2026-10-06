import { useState } from 'react'
import { get, patch, post } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, Field, Loading, Pill, toast, useLoad } from '../../ui'
import { azDT } from '../../ui'

export default function SettingsAdmin({ tab }: { tab: 'teachers' | 'bank' | 'audit' }) {
  if (tab === 'teachers') return <Teachers />
  if (tab === 'bank') return <Bank />
  return <Audit />
}

function Teachers() {
  const [rows, err, , reload] = useLoad<any[]>(() => get('/api/teachers'), [])
  const [school] = useLoad<any>(() => get('/api/school'), [])
  const [f, setF] = useState({ login: '', full_name: '', subjects: '' })
  const [shown, setShown] = useState<{ login: string; pw: string } | null>(null)
  const [arch, setArch] = useState<number | null>(null)
  return (
    <div className="grid g2">
      <section className="panel">
        <h2>Müəllimlər</h2>
        <ErrorBox error={err} />
        <div className="jlist">{(rows || []).map(t => (
          <div key={t.id} className="jrow cols" style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 6 }}>
            <div className="row"><b className="grow">{t.full_name}</b><span className="mono small">{t.login}</span>
              {t.role === 'admin' ? <Pill tone="acc">admin</Pill> : t.archived ? <Pill>arxivdə</Pill> : <Pill tone="ok">{(t.subjects || []).join(', ') || 'müəllim'}</Pill>}</div>
            {t.role === 'teacher' && (
              <div className="row">
                <AsyncBtn className="btn sm" onClick={async () => { const r = await post(`/api/teachers/${t.id}/reset-password`); setShown({ login: t.login, pw: r.initial_password }) }}>Yeni parol</AsyncBtn>
                {t.archived ? <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/teachers/${t.id}/restore`); reload() }}>Geri qaytar</AsyncBtn>
                  : <button className="btn sm danger" onClick={() => setArch(t.id)}>Arxivə</button>}
              </div>)}
            {arch === t.id && <ConfirmName name={t.full_name} action="Arxivə göndər" onCancel={() => setArch(null)} onConfirm={async typed => { await post(`/api/teachers/${t.id}/archive`, { confirm: typed }); setArch(null); reload() }} />}
          </div>))}</div>
      </section>
      <section className="panel">
        <h2>Yeni müəllim hesabı</h2>
        <div className="stack">
          <Field label="Soyadı, adı, ata adı"><input value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label="Fənlər" hint="vergüllə"><input value={f.subjects} onChange={e => setF({ ...f, subjects: e.target.value })} /></Field>
          <AsyncBtn className="btn primary" disabled={f.full_name.length < 3} onClick={async () => {
            const r = await post('/api/teachers', { full_name: f.full_name, school_id: school?.id ?? null,
              subjects: f.subjects.split(',').map(s => s.trim()).filter(Boolean) })
            setShown({ login: r.login, pw: r.initial_password }); setF({ login: '', full_name: '', subjects: '' }); reload()
          }}>Yarat</AsyncBtn>
          <p className="small muted">ID avtomatik verilir (M-002, M-003, …). Müəllim yalnız öz fənnini, siniflərini və jurnalını görür; başqalarının yazışmasını heç kim görmür.</p>
        </div>
      </section>
      {shown && (
        <Drawer title="İlk giriş məlumatı" onClose={() => setShown(null)}>
          <dl className="kv"><dt>ID</dt><dd className="mono">{shown.login}</dd><dt>Parol</dt><dd className="mono" style={{ fontSize: 20 }}>{shown.pw}</dd></dl>
          <p className="small muted" style={{ marginTop: 12 }}>Parol yalnız indi göstərilir. Müəllim ilk girişdən sonra onu dəyişməlidir.</p>
        </Drawer>)}
    </div>
  )
}

function Bank() {
  const [st, err, , reload] = useLoad<any>(() => get('/api/bank/status'), [])
  const [sources, err2, , reloadS] = useLoad<any[]>(() => get('/api/bank/sources'), [])
  const [polling, setPolling] = useState(false)
  const sync = async (force: boolean) => {
    await post('/api/bank/sync' + (force ? '?force=true' : ''))
    toast('Yeniləmə başladı…')
    setPolling(true)
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const s = await get('/api/bank/status')
      if (s.last?.status !== 'running') break
    }
    setPolling(false); reload(); reloadS()
  }
  const when = (s?: string) => (s ? azDT(new Date(s), undefined, 'all') : '—')
  return (
    <div className="grid g2">
      <section className="panel">
        <h2>Əlavə test bazası <small>viktorina.html</small></h2>
        <ErrorBox error={err || err2} />
        {!st ? <Loading /> : (
          <>
            <dl className="kv">
              <dt>Mənbə</dt><dd className="small" style={{ overflowWrap: 'anywhere' }}>{st.source_url}</dd>
              <dt>Aktiv sual</dt><dd><b>{st.questions}</b></dd>
              <dt>Avtomatik yoxlama</dt><dd>{st.auto_minutes ? (st.auto_hours ? `hər gün ${st.auto_hours.replace('-', ':00–')}:00 (Bakı) – gündüz şagirdlərə mane olmasın` : `hər ${st.auto_minutes} dəqiqə`) : 'söndürülüb'}</dd>
              <dt>Son yoxlama</dt><dd>{when(st.last?.finished || st.last?.at)} {st.last && <Pill tone={st.last.status === 'error' ? 'bad' : st.last.status === 'updated' ? 'ok' : undefined}>{st.last.status}</Pill>}</dd>
              <dt>Son yenilənmə</dt><dd>{st.last_update ? `${when(st.last_update.finished)} · +${st.last_update.added} ~${st.last_update.updated} −${st.last_update.deactivated}` : '—'}</dd>
            </dl>
            {st.last?.message && <pre className="small" style={{ whiteSpace: 'pre-wrap', color: 'var(--bad)' }}>{st.last.message}</pre>}
            <p className="small muted">Viktorinada suallar dəyişəndə sistem özü yenilənir; əl ilə yeniləməyə ehtiyac yoxdur.</p>
            <div className="row">
              <AsyncBtn className="btn primary" disabled={polling} onClick={() => sync(false)}>{polling ? 'Yenilənir…' : 'İndi yoxla'}</AsyncBtn>
              <AsyncBtn className="btn" disabled={polling} onClick={() => sync(true)}>Hamısını yenidən oxu</AsyncBtn>
            </div>
          </>)}
      </section>
      <section className="panel">
        <h2>Mənbələr</h2>
        <div className="jlist">{(sources || []).map(s => (
          <label key={s.key} className="jrow cols" style={{ ['--cols' as any]: 'auto minmax(0,1fr) auto', ['--mcols' as any]: 'auto minmax(0,1fr) auto', cursor: 'pointer' }}>
            <input type="checkbox" checked={s.enabled} onChange={async e => { await patch(`/api/bank/sources/${s.key}`, { enabled: e.target.checked }); reloadS() }} />
            <span>{s.label}{!s.active && <span className="small muted"> · viktorinadan çıxarılıb</span>}</span>
            <span className="num small">{s.questions}</span>
          </label>))}</div>
        <p className="small muted">Söndürülən mənbənin sualları tapşırıq yaradarkən görünmür.</p>
      </section>
      <BankFiles sources={sources || []} />
    </div>
  )
}

const KINDS: [string, string][] = [['movzu', 'mövzu testi'], ['sinaq', 'sınaq'], ['yekun', 'yekun test'], ['diaqnostik', 'diaqnostik']]

/** Faylın növü (mövzu testi / sınaq) və sinfi – avtomatik təsnifat səhvdirsə admin düzəldir (sinxronizasiya toxunmur). */
function BankFiles({ sources }: { sources: any[] }) {
  const [src, setSrc] = useState('')
  const [files, err, , reload] = useLoad<any[] | null>(() => (src ? get('/api/bank/lessons', { source: src }) : Promise.resolve(null)), [src])
  const save = async (id: number, body: any) => { await patch(`/api/bank/files/${id}`, body); reload() }
  return (
    <section className="panel" style={{ gridColumn: '1 / -1' }}>
      <h2>Faylların növü və sinfi <small>mövzu testi perspektiv planda, sınaq «Sınaq imtahanları»nda görünür</small></h2>
      <select className="sel" value={src} onChange={e => setSrc(e.target.value)}>
        <option value="">Mənbə seçin</option>{sources.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}</select>
      <ErrorBox error={err} />
      {files && <div className="jlist" style={{ marginTop: 8, maxHeight: 420, overflow: 'auto' }}>
        {files.map(f => (
          <div key={f.id} className="jrow cols" style={{ ['--cols' as any]: 'minmax(0,1fr) 140px 110px auto', ['--mcols' as any]: '1fr' }}>
            <span className="small">{f.label} <span className="muted">({f.questions})</span></span>
            <select className="sel" value={f.kind} onChange={e => save(f.id, { kind: e.target.value })}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <input className="sel" defaultValue={(f.grades || []).join(', ')} placeholder="sinif: 9, 10" aria-label="Siniflər"
              onBlur={e => { const g = e.target.value.split(/[ ,;]+/).map(Number).filter(n => n >= 1 && n <= 12); if (g.join() !== (f.grades || []).join()) save(f.id, { grades: g }) }} />
            {f.meta_locked ? <button className="btn sm ghost" title="Əl ilə düzəlişi götür" onClick={() => save(f.id, { auto: true })}>avtomatik</button> : <span className="small muted">avto</span>}
          </div>))}
      </div>}
    </section>
  )
}

function Audit() {
  const [rows, err] = useLoad<any[]>(() => get('/api/audit', { limit: 300 }), [])
  return (
    <>
      <ErrorBox error={err} />
      <section className="panel" style={{ marginBottom: 14 }}>
        <h2>Ehtiyat nüsxə</h2>
        <p className="small muted">Bütün məlumatları (fayllardan başqa) JSON faylı kimi endirir. Pulsuz hostinqdə baza silinə bilər – həftədə bir dəfə endirin. Yeni bazaya yükləmə: <code>tools/restore_backup.py</code>.</p>
        <a className="btn primary" href="/api/admin/backup">Ehtiyat nüsxəni endir</a>
      </section>
      <p className="small muted">Kim, nə vaxt, nəyi dəyişib. Mesajların məzmunu burada yoxdur.</p>
      <div className="tbl-wrap"><table><thead><tr><th>Vaxt</th><th>İstifadəçi</th><th>Əməliyyat</th><th>Obyekt</th></tr></thead>
        <tbody>{(rows || []).map(a => <tr key={a.id}><td className="small">{azDT(new Date(a.at), undefined, 'all')}</td><td>{a.user || '—'}</td><td>{a.action}</td><td className="small">{a.entity} {a.entity_id ? '#' + a.entity_id : ''}</td></tr>)}</tbody></table></div>
    </>
  )
}
