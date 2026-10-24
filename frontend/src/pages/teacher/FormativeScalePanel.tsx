// Müəllim: sinfin formativ şkalası (mövzu testi) – «3/4/5» üçün alt hədd, %; defolt = KSQ şkalası 31/61/81 (metodik audit M6).
import { useEffect, useState } from 'react'
import { del, get, put } from '../../api'
import { useT } from '../../i18n'
import { ErrorBox, Field, toast, useLoad } from '../../ui'

type Scale = { t3: number; t4: number; t5: number; default: boolean }

export default function FormativeScalePanel({ ta }: { ta: number }) {
  const t = useT()
  const [d, err, , reload] = useLoad<Scale>(() => get(`/api/tasks/formative-scale/${ta}`), [ta])
  const [f, setF] = useState<Scale | null>(null)
  useEffect(() => { if (d) setF(d) }, [d])
  if (!d || !f) return <ErrorBox error={err} />
  const bad = [f.t3, f.t4, f.t5].some(x => !Number.isInteger(x) || x < 1 || x > 100) ? t('Hədlər 1 ilə 100 arasında olmalıdır')
    : !(f.t3 < f.t4 && f.t4 < f.t5) ? t('Hədlər ciddi artan olmalıdır: «3» < «4» < «5»') : ''
  const num = (k: 't3' | 't4' | 't5', g: number) => (
    <Field label={t('Qiymət «{g}» üçün ən azı, %', { g })}>
      <input type="number" min={1} max={100} value={f[k]} onChange={e => setF({ ...f, [k]: Number(e.target.value) })} /></Field>)
  const save = () => put(`/api/tasks/formative-scale/${ta}`, { t3: f.t3, t4: f.t4, t5: f.t5 }).then(() => { toast(t('Saxlandı')); reload() }, e => toast(e.message))
  const reset = () => del(`/api/tasks/formative-scale/${ta}`).then(() => { toast(t('Defolta qaytarıldı')); reload() }, e => toast(e.message))
  return (
    <section className="panel" style={{ marginTop: 12 }}>
      <h2>{t('Formativ şkala (mövzu testi)')}</h2>
      <p className="small muted" style={{ marginTop: 0 }}>{t('Mövzu testinin faizi bu hədlərlə qiymətə çevrilir (altı «2»). Yeni şkala yalnız yeni təhvillərə və yenidən qiymətləndirməyə tətbiq olunur; köhnə qiymətlər dəyişmir. KSQ, BSQ və sınaq həmişə 31 / 61 / 81 şkalası ilə.')}</p>
      <div className="fg" style={{ border: '1px solid var(--line)', borderRadius: 10, padding: 10 }}>
        {num('t3', 3)}{num('t4', 4)}{num('t5', 5)}
        {bad && <div className="small" style={{ color: 'var(--bad)' }}>{bad}</div>}
        <div className="row" style={{ gap: 6 }}>
          <button className="btn primary sm" disabled={!!bad} onClick={save}>{t('Saxla')}</button>
          <button className="btn sm ghost" disabled={d.default} onClick={reset}>{t('Defolta qaytar')}</button>
        </div>
      </div>
    </section>
  )
}
