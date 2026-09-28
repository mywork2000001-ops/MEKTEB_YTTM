import { useState } from 'react'
import { get, patch, post } from '../../api'
import { AsyncBtn, ConfirmName, Drawer, ErrorBox, Field, Loading, Pill, toast, useLoad } from '../../ui'

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
          <div key={t.id} className="jrow" style={{ gridTemplateColumns: '1fr', gap: 6 }}>
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
  const when = (s?: string) => (s ? new Date(s).toLocaleString('az-AZ') : '—')
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
              <dt>Avtomatik yoxlama</dt><dd>{st.auto_minutes ? `hər ${st.auto_minutes} dəqiqə` : 'söndürülüb'}</dd>
              <dt>Son yoxlama</dt><dd>{when(st.last?.finished || st.last?.at)} {st.last && <Pill tone={st.last.status === 'error' ? 'bad' : st.last.status === 'updated' ? 'ok' : undefined}>{st.last.status}</Pill>}</dd>
              <dt>Son yenilənmə</dt><dd>{st.last_update ? `${when(st.last_update.finished)} · +${st.last_update.added} ~${st.last_update.updated} −${st.last_update.deactivated}` : '—'}</dd>
            </dl>
            {st.last?.message && <pre className="small" style={{ whiteSpace: 'pre-wrap', color: 'var(--bad)' }}>{st.last.message}</pre>}
            <p className="small muted">Viktorina-da suallar dəyişəndə sistem özü yenilənir; əl ilə yeniləməyə ehtiyac yoxdur.</p>
            <div className="row">
              <AsyncBtn className="btn primary" disabled={polling} onClick={() => sync(false)}>{polling ? 'Yenilənir…' : 'İndi yoxla'}</AsyncBtn>
              <AsyncBtn className="btn" disabled={polling} onClick={() => sync(true)}>Hamısını yenidən oxu</AsyncBtn>
            </div>
          </>)}
      </section>
      <section className="panel">
        <h2>Mənbələr</h2>
        <div className="jlist">{(sources || []).map(s => (
          <label key={s.key} className="jrow" style={{ gridTemplateColumns: 'auto minmax(0,1fr) auto', cursor: 'pointer' }}>
            <input type="checkbox" checked={s.enabled} onChange={async e => { await patch(`/api/bank/sources/${s.key}`, { enabled: e.target.checked }); reloadS() }} />
            <span>{s.label}{!s.active && <span className="small muted"> · viktorina-dan çıxarılıb</span>}</span>
            <span className="num small">{s.questions}</span>
          </label>))}</div>
        <p className="small muted">Söndürülən mənbənin sualları tapşırıq yaradarkən görünmür.</p>
      </section>
    </div>
  )
}

function Audit() {
  const [rows, err] = useLoad<any[]>(() => get('/api/audit', { limit: 300 }), [])
  return (
    <>
      <ErrorBox error={err} />
      <p className="small muted">Kim, nə vaxt, nəyi dəyişib. Mesajların məzmunu burada yoxdur.</p>
      <div className="tbl-wrap"><table><thead><tr><th>Vaxt</th><th>İstifadəçi</th><th>Əməliyyat</th><th>Obyekt</th></tr></thead>
        <tbody>{(rows || []).map(a => <tr key={a.id}><td className="small">{new Date(a.at).toLocaleString('az-AZ')}</td><td>{a.user || '—'}</td><td>{a.action}</td><td className="small">{a.entity} {a.entity_id ? '#' + a.entity_id : ''}</td></tr>)}</tbody></table></div>
    </>
  )
}
