import { useState } from 'react'
import { useAuth } from '../auth'
import { ApiError } from '../api'
import { LANGS, useT, type Lang } from '../i18n'
import { Field, Seg } from '../ui'

export default function Login({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const { login } = useAuth()
  const t = useT()
  const [who, setWho] = useState<'teacher' | 'student'>('teacher')
  const [l, setL] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try { await login(l.trim(), p) } catch (x) { setErr(x instanceof ApiError ? x.message : 'Xəta baş verdi') } finally { setBusy(false) }
  }

  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 16 }}>
      <form className="panel lockbox" style={{ width: 'min(400px,100%)', margin: 0 }} onSubmit={submit}>
        <span className="logo" style={{ margin: '0 auto 10px', width: 48, height: 48, fontSize: 22 }}>M</span>
        <h1 style={{ font: '600 24px/1.2 var(--f-disp)', margin: '0 0 4px' }}>Müəllim köməkçisi</h1>
        <p className="muted" style={{ margin: '0 0 16px', fontSize: 13 }}>Rafiq Nuriyev adına 6 nömrəli tam orta məktəb</p>
        <Seg value={who} onChange={v => { setWho(v); setErr('') }} options={[['teacher', 'Müəllim'], ['student', t('Şagird')]]} label="Kim daxil olur" />
        <div style={{ display: 'grid', gap: 12, marginTop: 14 }}>
          {who === 'teacher' ? (
            <>
              <Field label="ID" hint="məs. M-001"><input autoComplete="username" autoCapitalize="characters" value={l} onChange={e => setL(e.target.value.toUpperCase())} required /></Field>
              <Field label={t('Parol')}><input type="password" autoComplete="current-password" value={p} onChange={e => setP(e.target.value)} required /></Field>
            </>
          ) : (
            <>
              <Field label={t('Giriş kodu')} hint="Məsələn: XE-001"><input autoComplete="username" autoCapitalize="characters" value={l} onChange={e => setL(e.target.value.toUpperCase())} required /></Field>
              <Field label="PIN" hint="4 rəqəm"><input type="password" inputMode="numeric" pattern="\d{4}" maxLength={4} autoComplete="current-password" value={p} onChange={e => setP(e.target.value.replace(/\D/g, ''))} required /></Field>
            </>
          )}
          {err && <div className="err" role="alert">{err}</div>}
          <button className="btn primary" disabled={busy}>{busy ? '…' : t('Daxil ol')}</button>
        </div>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 14 }}>
          {LANGS.map(([k, n]) => <button type="button" key={k} className={'chip'} aria-pressed={k === lang} onClick={() => setLang(k)}>{n}</button>)}
        </div>
      </form>
    </div>
  )
}
