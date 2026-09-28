// Müəllim və şagird üçün ortaq tənzimləmə panelləri: görünüş/dil, parol/PIN.
import { useState } from 'react'
import { post } from '../api'
import { useAuth } from '../auth'
import { LANGS, useT } from '../i18n'
import { ACCENTS, parseLook } from '../prefs'
import { AsyncBtn, Field, Seg } from '../ui'

export function LookPanel() {
  const { me, setLook, setLang } = useAuth()
  const t = useT()
  const look = parseLook(me?.theme || localStorage.getItem('mk-look'))
  return (
    <div className="grid g2">
      <section className="panel">
        <h2>{t('Rəng çaları')}</h2>
        <div className="swatches" role="radiogroup">
          {ACCENTS.map(([k, name, c]) => <button key={k} role="radio" aria-checked={look.accent === k} aria-label={name} title={name} style={{ ['--cc' as any]: c }} onClick={() => setLook({ ...look, accent: k })} />)}
        </div>
        <h2 style={{ marginTop: 16 }}>{t('Rejim')}</h2>
        <Seg value={look.mode} onChange={m => setLook({ ...look, mode: m })} options={[['auto', t('Avtomatik')], ['light', t('İşıqlı')], ['dark', t('Qaranlıq')]]} />
        <label className="check" style={{ marginTop: 10 }}><input type="checkbox" checked={look.big} onChange={e => setLook({ ...look, big: e.target.checked })} />{t('Böyük şrift')}</label>
      </section>
      <section className="panel">
        <h2>{t('Dil')}</h2>
        <div className="stack">{LANGS.map(([k, n]) => <button key={k} className="chip" aria-pressed={me?.language === k} onClick={() => setLang(k)}>{n}</button>)}</div>
        <p className="small muted" style={{ marginTop: 10 }}>Rəsmi sənədlər (plan, çap) həmişə Azərbaycan dilindədir.</p>
      </section>
    </div>
  )
}

export function PasswordPanel({ student }: { student: boolean }) {
  const t = useT()
  const [f, setF] = useState({ old: '', new: '', again: '' })
  const valid = student ? /^\d{4}$/.test(f.new) : f.new.length >= 8
  const clean = (v: string) => (student ? v.replace(/\D/g, '').slice(0, 4) : v)
  return (
    <section className="panel" style={{ maxWidth: 440 }}>
      <h2>{student ? t('PIN-i dəyiş') : 'Parolu dəyiş'}</h2>
      <div className="stack">
        <Field label={student ? 'Köhnə PIN' : 'Köhnə parol'}><input type="password" inputMode={student ? 'numeric' : undefined} value={f.old} onChange={e => setF({ ...f, old: clean(e.target.value) })} /></Field>
        <Field label={student ? 'Yeni PIN (4 rəqəm)' : 'Yeni parol (ən azı 8 simvol)'}><input type="password" inputMode={student ? 'numeric' : undefined} value={f.new} onChange={e => setF({ ...f, new: clean(e.target.value) })} /></Field>
        <Field label="Təkrar" error={f.again && f.again !== f.new ? 'Uyğun gəlmir' : undefined}><input type="password" inputMode={student ? 'numeric' : undefined} value={f.again} onChange={e => setF({ ...f, again: clean(e.target.value) })} /></Field>
        <AsyncBtn className="btn primary" disabled={!valid || f.new !== f.again || !f.old} ok="Dəyişdirildi"
          onClick={async () => { await post('/api/auth/password', { old: f.old, new: f.new }); setF({ old: '', new: '', again: '' }) }}>{t('Yadda saxla')}</AsyncBtn>
      </div>
    </section>
  )
}
