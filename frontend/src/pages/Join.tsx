// Şagirdin özünü qeydiyyatdan keçirməsi (müəllimin göndərdiyi link) – girişsiz səhifə.
import { useEffect, useState } from 'react'
import { ApiError, get, post } from '../api'
import { Field, Seg } from '../ui'
import { LANGS, useT, type Lang } from '../i18n'

export default function Join({ token, lang, setLang }: { token: string; lang: Lang; setLang: (l: Lang) => void }) {
  const t = useT()
  const [info, setInfo] = useState<{ school: string; class_name: string } | null>(null)
  const [err, setErr] = useState('')
  const [f, setF] = useState({ full_name: '', gender: 'Qız' as 'Qız' | 'Oğlan' })
  const [done, setDone] = useState<{ portal_code: string; pin: string; full_name: string; class_name: string } | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { get(`/api/join/${token}`).then(setInfo, e => setErr(e instanceof ApiError ? e.message : 'Xəta')) }, [token])
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { setDone(await post(`/api/join/${token}`, f)) } catch (x) { setErr(x instanceof ApiError ? x.message : 'Xəta baş verdi') } finally { setBusy(false) }
  }
  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 16 }}>
      <div className="panel lockbox" style={{ width: 'min(420px,100%)', margin: 0, textAlign: 'left' }}>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 10 }}>
          {LANGS.map(([k, n]) => <button type="button" key={k} className="chip" aria-pressed={k === lang} onClick={() => setLang(k)}>{n}</button>)}
        </div>
        <span className="logo" style={{ margin: '0 auto 10px', width: 48, height: 48, fontSize: 22 }}>M</span>
        <h1 style={{ font: '600 22px/1.2 var(--f-disp)', margin: '0 0 4px', textAlign: 'center' }}>{t('Şagird qeydiyyatı')}</h1>
        {info && <p className="muted" style={{ textAlign: 'center', margin: '0 0 14px', fontSize: 13 }}>{info.school}<br /><b>{t('{c} sinfi', { c: info.class_name })}</b></p>}
        {done ? (
          <div className="stack">
            <p><b>{t('Qeydiyyat tamamlandı, {name}!', { name: done.full_name })}</b></p>
            <dl className="kv"><dt>{t('Giriş kodu')}</dt><dd className="mono" style={{ fontSize: 22 }}>{done.portal_code}</dd><dt>PIN</dt><dd className="mono" style={{ fontSize: 22 }}>{done.pin}</dd></dl>
            <p className="small" style={{ color: 'var(--bad)' }}>{t('Siz artıq daxil olmusunuz. Başqa cihazdan girmək üçün kodu və PIN-i yazın və ya şəklini çəkin – bir daha göstərilməyəcək.')}</p>
            <a className="btn primary" href="/">{t('Davam et')}</a>
          </div>
        ) : info ? (
          <form className="stack" onSubmit={submit}>
            <Field label={t('Soyadınız və adınız')} hint={t('məs. Əliyeva Aysel')}><input value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} required minLength={3} autoComplete="name" autoFocus /></Field>
            <Seg value={f.gender} onChange={g => setF({ ...f, gender: g })} options={[['Qız', t('Qız')], ['Oğlan', t('Oğlan')]]} label={t('Cins')} />
            {err && <div className="err" role="alert">{t(err)}</div>}
            <button className="btn primary" disabled={busy}>{busy ? '…' : t('Qeydiyyatdan keç')}</button>
            <p className="small muted" style={{ margin: 0 }}>{t('Uşaq İD, pinkod və ya şəxsiyyət vəsiqəsi soruşulmur.')}</p>
          </form>
        ) : <p className="err" role="alert">{err ? t(err) : t('Yüklənir…')}</p>}
      </div>
    </div>
  )
}
