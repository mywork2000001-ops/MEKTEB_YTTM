// «Akademik nəticələr → Standartlar üzrə»: standart və mövzular üzrə mənimsəmə (köhnə Journal.tsx «Standartlar» tabı – hesablama serverdədir, dəyişməyib).
import { useState } from 'react'
import { get } from '../../../api'
import { ErrorBox, fmt, Loading, Pill, useLoad } from '../../../ui'
import { useT } from '../../../i18n'

/** Standartlar / mövzular üzrə mənimsəmə: formativ qiymətləndirmə = perspektiv plan testləri (onlayn mövzu testləri). */
export default function Standards({ ta }: { ta: number }) {
  const t = useT()
  const [sem, setSem] = useState<'1' | '2' | 'all'>('1')
  const [d, err, loading] = useLoad<any>(() => get(`/api/journal/${ta}/standards`, sem === 'all' ? {} : { semester: sem }), [ta, sem])
  const tone = (p: number | null) => (p == null ? undefined : p >= 70 ? 'ok' : p >= 50 ? 'warn' : 'bad')
  const block = (title: string, key: 'standard' | 'topic', rows: any[]) => (
    <section className="panel" style={{ marginBottom: 12 }}>
      <h2>{title}</h2>
      {!rows.length ? <div className="empty">{t('Hələ plan testi nəticəsi yoxdur. Mövzu testi təyin edin – nəticə burada standartlara görə toplanacaq.')}</div> : (
        <div className="tbl-wrap"><table>
          <thead><tr><th>{key === 'standard' ? t('Standart') : t('Mövzu')}</th><th className="r">{t('Test sayı')}</th><th className="r">{t('Sinif ortası %')}</th><th>{t('Şagirdlər (orta %, aşağıdan yuxarı)')}</th></tr></thead>
          <tbody>{rows.map(r => (
            <tr key={r[key]}><td><b>{r[key]}</b>{key === 'standard' && r.source && <div className="small muted">{t(r.source === 'question' ? 'Mənbə: sualın öz standartı' : r.source === 'mixed' ? 'Mənbə: qarışıq (sual + dərs)' : 'Mənbə: dərsin standartı')}</div>}</td><td className="r num">{r.tests}</td>
              <td className="r">{r.class_pct == null ? '—' : <Pill tone={tone(r.class_pct)}>{fmt(r.class_pct)}%</Pill>}</td>
              <td className="small">{r.students.map((s: any) => <span key={s.student_id} style={{ marginRight: 8, whiteSpace: 'nowrap', color: s.pct < 50 ? 'var(--bad)' : undefined }}>{s.full_name.split(' ').slice(0, 2).join(' ')} <b>{fmt(s.pct)}%</b></span>)}</td></tr>))}</tbody>
        </table></div>)}
    </section>)
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 8 }}>{([['1', 'I yarımil'], ['2', 'II yarımil'], ['all', 'Bütün il']] as const).map(([k, l]) => <button key={k} className="chip" aria-pressed={sem === k} onClick={() => setSem(k)}>{t(l)}</button>)}</div>
      <p className="small muted">{t('Formativ qiymətləndirmə perspektiv plan testlərinə əsaslanır: standart və mövzu dərsin plan sətrindən götürülür. Şifahi/yazılı qiymətlər burada yoxdur.')}</p>
      {loading && !d ? <Loading /> : d && <>
        <p className="small muted">{t('Standart suala yazılıbsa, onlayn cavablar sualın öz standartı ilə hesablanır; yoxdursa – dərsin standartı ilə.')}</p>
        {d.class_avg_hidden && <p className="small muted">{t('Sinif ortası 5-dən az şagirddə göstərilmir.')}</p>}
        {block(t('Standartlar üzrə mənimsəmə'), 'standard', d.standards)}
        {block(t('Mövzular üzrə mənimsəmə'), 'topic', d.topics)}
      </>}
    </>
  )
}

/** «Bölmələr üzrə icra» – perspektiv plandakı bölmələr üzrə keçilmiş / olmalı mövzular (köhnə Journal.tsx «Mövzu icrası» tabından). */
export function SectionProgress({ ta }: { ta: number }) {
  const t = useT()
  const [p, err] = useLoad<{ sections: { section: string; semester: number; total: number; done: number; expected: number; from_seq: number; to_seq: number }[] }>(() => get(`/api/plan/${ta}/progress`), [ta])
  if (!p) return <><ErrorBox error={err} /><Loading /></>
  return (
    <>
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2>{t('Bölmələr üzrə icra')}</h2>
        <div className="stack" style={{ gap: 8 }}>{p.sections.map(x => (
          <div key={x.from_seq}>
            <div className="row small" style={{ justifyContent: 'space-between' }}><span><b>{x.section}</b> <span className="muted">№{x.from_seq}–{x.to_seq}</span></span>
              <span>{x.done}/{x.total}{x.done < x.expected ? <> · <span style={{ color: 'var(--bad)' }}>{x.expected - x.done} {t('geridə')}</span></> : ''}</span></div>
            <div style={{ position: 'relative', height: 8, background: 'var(--sunk)', borderRadius: 4, overflow: 'hidden' }} title={t('keçilib {done}, olmalı {expected}, cəmi {total}', { done: x.done, expected: x.expected, total: x.total })}>
              <i style={{ position: 'absolute', inset: 0, width: `${(x.done / x.total) * 100}%`, background: 'var(--accent)', borderRadius: 4 }} />
              {x.expected > 0 && x.expected < x.total && <i style={{ position: 'absolute', top: 0, bottom: 0, left: `calc(${(x.expected / x.total) * 100}% - 1px)`, width: 2, background: 'var(--ink)' }} />}
            </div>
          </div>))}</div>
        <p className="small muted" style={{ margin: '8px 0 0' }}>{t('Zolaq – keçilən mövzular; qara xətt – rəsmi plana görə bu günə qədər keçilməli olan.')}</p>
      </section>
    </>
  )
}
