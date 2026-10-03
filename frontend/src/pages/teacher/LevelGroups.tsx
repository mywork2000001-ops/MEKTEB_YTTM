// Səviyyə qrupları (Zəif / Orta / Güclü) – fənn üzrə, sinif daxilində. İlkin bölgü avtomatik (IX buraxılış balı, sınaq,
// fənn reytinqi, diaqnostik test) → önizləmə → təsdiq; müəllim köçürür (kilidli); sonrakı dəyişikliklər yalnız təklifdir.
// Səviyyə etiketi şagirdə göstərilmir – şagird yalnız ona göndərilən tapşırığı / məşğələni görür.
import { useState } from 'react'
import { get, post, put } from '../../api'
import { AsyncBtn, Drawer, ErrorBox, Field, fmt, fmtDate, Loading, Pill, Seg, toast, useLoad } from '../../ui'
import { head, printDoc, SIGN, table } from '../../print'
import { useAuth } from '../../auth'
import { type MyLesson, useMyLessons } from './common'

type Member = { student_id: number; full_name: string; source: 'auto' | 'manual' | null; locked: boolean; score: number | null; components: Record<string, number | null> | null; note: string | null }
type Groups = { groups: Record<string, Member[]>; suggestions: number }
const COLS = ['Zəif', 'Orta', 'Güclü'] as const
const tone = (l: string) => (l === 'Güclü' ? 'ok' : l === 'Zəif' ? 'bad' : l === 'Orta' ? 'warn' : undefined)
const LABELS: Record<string, string> = { buraxilis: 'IX buraxılış', sinaq: 'sınaq', reytinq: 'reytinq', diaqnostik: 'diaqnostik' }
const comps = (c: Record<string, number | null> | null) => (c ? Object.entries(c).filter(([, v]) => v != null).map(([k, v]) => `${LABELS[k] || k} ${fmt(v as number, 0)}`).join(' · ') : '')

export default function LevelGroups({ ta }: { ta: MyLesson }) {
  const { me } = useAuth()
  const [d, err, loading, reload] = useLoad<Groups>(() => get(`/api/levels/${ta.id}`), [ta.id])
  const [drawer, setDrawer] = useState<null | 'auto' | 'suggest' | 'history' | 'cross'>(null)
  const move = async (m: Member, level: string | null, locked = true) => {
    await put(`/api/levels/${ta.id}/${m.student_id}`, { level, locked })
    toast(level ? `${m.full_name.split(' ').slice(0, 2).join(' ')} → ${level}` : 'Səviyyə götürüldü'); reload()
  }
  const print = () => d && printDoc({ title: `${ta.class_name} – səviyyə qrupları`, signers: [SIGN.teacher(me?.full_name), SIGN.deputy()],
    body: head(`${ta.class_name} – ${ta.subject}: səviyyə qrupları`, `${fmtDate(new Date().toISOString())} vəziyyəti · Zəif / Orta / Güclü – sinif daxilində fənn üzrə`) +
      [...COLS, 'Təyin edilməyib'].filter(k => (d.groups[k] || []).length).map(k => `<h3>${k} – ${d.groups[k].length} şagird</h3>` +
        table(['№', 'Şagird', 'Bal', 'Komponentlər', 'Mənbə'], d.groups[k].map((m, i) => [i + 1, m.full_name, fmt(m.score), comps(m.components),
          m.source === 'manual' ? 'müəllim' + (m.locked ? ' (kilidli)' : '') : m.source ? 'bölgü' : '—']), [2])).join('') +
      '<p class="note">Bölgü balı: IX buraxılış balı, sınaq ortası, fənn reytinqi və diaqnostik test (olanlar); ≥ 70 – güclü, 40–69,9 – orta, < 40 – zəif. Şagird öz səviyyə etiketini görmür.</p>' })
  if (!d) return err ? <ErrorBox error={err} /> : <Loading />
  const none = d.groups['Təyin edilməyib'] || []
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={() => setDrawer('auto')}>Avtomatik bölgü</button>
        <button className="btn" onClick={() => setDrawer('suggest')}>Təkliflər{d.suggestions ? ` (${d.suggestions})` : ''}</button>
        <button className="btn" onClick={() => setDrawer('cross')}>Paralel siniflərdən qrup</button>
        <button className="btn ghost" onClick={() => setDrawer('history')}>Tarixçə</button>
        <button className="btn ghost" onClick={print}>Çap</button>
        {loading && <span className="small muted">yenilənir…</span>}
      </div>
      <p className="small muted" style={{ marginTop: 0 }}>Səviyyə fənn üzrədir və sinif daxilində virtual qrupdur (ayrıca jurnal yaranmır). Onlayn test və tapşırığı
        «Kimə» bölməsində qrupa göndərmək olar. Şagird öz səviyyə etiketini görmür. 🔒 – müəllimin qərarı, avtomatik bölgü və təkliflər toxunmur.</p>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))' }}>
        {COLS.map(k => (
          <section key={k} className="panel">
            <h2><Pill tone={tone(k)}>{k}</Pill> <small>{d.groups[k].length} şagird</small></h2>
            {d.groups[k].length === 0 && <p className="small muted">Boşdur.</p>}
            {d.groups[k].map(m => <MemberRow key={m.student_id} m={m} level={k} onMove={move} />)}
          </section>))}
      </div>
      {none.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}>
          <h2>Təyin edilməyib <small>{none.length} – məlumat yoxdur və ya bölgü aparılmayıb</small></h2>
          {none.map(m => <MemberRow key={m.student_id} m={m} level={null} onMove={move} />)}
        </section>)}
      {drawer === 'auto' && <AutoSplit ta={ta} onClose={() => setDrawer(null)} onDone={() => { setDrawer(null); reload() }} />}
      {drawer === 'suggest' && <Suggestions ta={ta} onClose={() => setDrawer(null)} onDone={() => { setDrawer(null); reload() }} />}
      {drawer === 'history' && <History ta={ta} onClose={() => setDrawer(null)} />}
      {drawer === 'cross' && <CrossClass ta={ta} onClose={() => setDrawer(null)} />}
    </>
  )
}

function MemberRow({ m, level, onMove }: { m: Member; level: string | null; onMove: (m: Member, l: string | null, locked?: boolean) => void }) {
  const c = comps(m.components)
  return (
    <div style={{ borderTop: '1px solid var(--line)', padding: '8px 0', display: 'grid', gap: 3 }}>
      <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
        <span className="small grow" style={{ minWidth: 0, overflowWrap: 'anywhere' }}><b>{m.full_name}</b>{m.locked ? ' 🔒' : ''}</span>
        {m.score != null && <span className="small num" style={{ fontWeight: 600 }}>{fmt(m.score)}</span>}
        <select className="grade-sel" value={level || ''} aria-label="Köçür" onChange={e => onMove(m, e.target.value || null)}>
          <option value="">—</option>{COLS.map(k => <option key={k} value={k}>{k}</option>)}</select>
        {level && <button className="btn sm ghost" title={m.locked ? 'Kilidi aç (təkliflər işləsin)' : 'Kilidlə'} onClick={() => onMove(m, level, !m.locked)}>{m.locked ? '🔓' : '🔒'}</button>}
      </div>
      {(c || m.source === 'manual') && <span className="small muted">{c || 'müəllimin qərarı'}</span>}
    </div>
  )
}

function AutoSplit({ ta, onClose, onDone }: { ta: MyLesson; onClose: () => void; onDone: () => void }) {
  const [mode, setMode] = useState<'fixed' | 'tercile'>('fixed')
  const [w, setW] = useState({ buraxilis: 30, sinaq: 40, reytinq: 30, diaqnostik: 30 })
  const [p, err, loading] = useLoad<any>(() => post(`/api/levels/${ta.id}/preview?mode=${mode}`, w), [ta.id, mode, JSON.stringify(w)])
  const [skip, setSkip] = useState<Set<number>>(new Set())
  const rows = (p?.rows || []) as any[]
  const chosen = rows.filter(r => r.change && !skip.has(r.student_id)).map(r => r.student_id)
  return (
    <Drawer title="Avtomatik bölgü – önizləmə" onClose={onClose}
      footer={<><span className="small muted grow">{chosen.length} dəyişiklik</span><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" disabled={!chosen.length} ok="Bölgü tətbiq olundu" onClick={async () => { await post(`/api/levels/${ta.id}/apply`, { student_ids: chosen, mode, weights: w }); onDone() }}>Tətbiq et</AsyncBtn></>}>
      <div className="stack">
        <Seg value={mode} onChange={setMode} options={[['fixed', 'Sabit həddlər (≥70 / 40–70 / <40)'], ['tercile', 'Üçdəbir (bərabər qruplar)']]} />
        <div className="fg">
          {(Object.keys(w) as (keyof typeof w)[]).map(k => (
            <Field key={k} label={`${LABELS[k]} – çəki`} hint={p ? `${p.used[k]} şagirddə məlumat var` : undefined}>
              <input type="number" min={0} max={100} value={w[k]} onChange={e => setW({ ...w, [k]: Number(e.target.value) })} /></Field>))}
        </div>
        <p className="small muted" style={{ margin: 0 }}>Olmayan komponent nəzərə alınmır, çəkilər yenidən paylanır (ilin əvvəlində yalnız IX buraxılış balı olur).
          IX buraxılış balı yalnız X–XI siniflərdə istifadə olunur. Kilidli (🔒) şagirdlərə toxunulmur.</p>
        <ErrorBox error={err} />
        {loading && !p ? <Loading /> : p && <>
          <div className="row">{COLS.map(k => <Pill key={k} tone={tone(k)}>{k}: {p.counts[k]}</Pill>)}</div>
          <div className="tbl-wrap"><table>
            <thead><tr><th></th><th>Şagird</th><th>Komponentlər</th><th className="r">Bal</th><th>İndi → təklif</th></tr></thead>
            <tbody>{rows.map(r => (
              <tr key={r.student_id}>
                <td>{r.change && <input type="checkbox" checked={!skip.has(r.student_id)} aria-label="Tətbiq et"
                  onChange={e => setSkip(s => { const n = new Set(s); if (e.target.checked) n.delete(r.student_id); else n.add(r.student_id); return n })} />}</td>
                <td className="small"><b>{r.full_name}</b>{r.locked ? ' 🔒' : ''}</td>
                <td className="small muted">{comps(r.components) || '—'}</td>
                <td className="r num">{fmt(r.score)}</td>
                <td className="small">{r.current || '—'} → {r.proposed ? <Pill tone={tone(r.proposed)}>{r.proposed}</Pill> : 'məlumat yoxdur'}</td>
              </tr>))}</tbody>
          </table></div></>}
      </div>
    </Drawer>
  )
}

function Suggestions({ ta, onClose, onDone }: { ta: MyLesson; onClose: () => void; onDone: () => void }) {
  const [list, err] = useLoad<any[]>(() => get(`/api/levels/${ta.id}/suggestions`), [ta.id])
  const [off, setOff] = useState<Set<number>>(new Set())
  const ids = (list || []).filter(s => !off.has(s.student_id)).map(s => s.student_id)
  return (
    <Drawer title="Köçürmə təklifləri" onClose={onClose}
      footer={<><span className="grow" /><button className="btn" onClick={onClose}>Bağla</button>
        <AsyncBtn className="btn primary" disabled={!ids.length} ok="Təkliflər qəbul olundu" onClick={async () => { await post(`/api/levels/${ta.id}/suggestions/accept`, { student_ids: ids }); onDone() }}>Seçilənləri qəbul et</AsyncBtn></>}>
      <ErrorBox error={err} />
      <p className="small muted">Təklif yalnız bal hədddən ən azı 5 bal o tərəfə keçəndə yaranır (şagird hər nəticədən sonra qrupdan qrupa «atılmasın»).
        Rüb sonunda bir dəfə baxmaq kifayətdir.</p>
      {!list ? <Loading /> : list.length === 0 ? <div className="empty">Təklif yoxdur.</div> : list.map(s => (
        <label key={s.student_id} className="check" style={{ borderTop: '1px solid var(--line)', padding: '8px 0' }}>
          <input type="checkbox" checked={!off.has(s.student_id)} onChange={e => setOff(o => { const n = new Set(o); if (e.target.checked) n.delete(s.student_id); else n.add(s.student_id); return n })} />
          <span className="grow"><b>{s.full_name}</b><span className="sub small muted" style={{ display: 'block' }}>bal {fmt(s.old_score)} → {fmt(s.score)} · {comps(s.components)}</span></span>
          <Pill tone={tone(s.current)}>{s.current}</Pill>→<Pill tone={tone(s.proposed)}>{s.proposed}</Pill>
        </label>))}
    </Drawer>
  )
}

function History({ ta, onClose }: { ta: MyLesson; onClose: () => void }) {
  const [list, err] = useLoad<any[]>(() => get(`/api/levels/${ta.id}/history`), [ta.id])
  return (
    <Drawer title="Səviyyə dəyişikliklərinin tarixçəsi" onClose={onClose}>
      <ErrorBox error={err} />
      {!list ? <Loading /> : list.length === 0 ? <div className="empty">Hələ dəyişiklik yoxdur.</div> : (
        <div className="tbl-wrap"><table>
          <thead><tr><th>Tarix</th><th>Şagird</th><th>Dəyişiklik</th><th>Mənbə</th></tr></thead>
          <tbody>{list.map((h, i) => (
            <tr key={i}><td className="small">{fmtDate(h.at)}</td><td className="small">{h.full_name}</td>
              <td className="small">{h.old || '—'} → {h.new || '—'}{h.score != null ? ` (bal ${fmt(h.score)})` : ''}</td>
              <td className="small">{h.source === 'auto' ? 'bölgü' : 'müəllim'}</td></tr>))}</tbody>
        </table></div>)}
    </Drawer>
  )
}

function CrossClass({ ta, onClose }: { ta: MyLesson; onClose: () => void }) {
  const [lessons] = useMyLessons()
  const same = (lessons || []).filter(l => l.subject === ta.subject && l.kind !== 'qrup')
  const [sel, setSel] = useState<number[]>([ta.id])
  const [level, setLevel] = useState<'Zəif' | 'Orta' | 'Güclü'>('Güclü')
  const [name, setName] = useState(`${ta.class_name.split(' ')[0]} – ${ta.subject.toLowerCase()}, güclü qrup`)
  const [err, setErr] = useState<unknown>()
  return (
    <Drawer title="Paralel siniflərdən səviyyə qrupu" onClose={onClose}
      footer={<><span className="grow" /><button className="btn" onClick={onClose}>Ləğv et</button>
        <AsyncBtn className="btn primary" disabled={!sel.length || name.trim().length < 2} onClick={async () => {
          try {
            const r = await post<any>('/api/levels/cross-class', { ta_ids: sel, level, name: name.trim() })
            toast(`«${r.name}» yaradıldı – ${r.members} şagird`); onClose()
          } catch (e) { setErr(e) }
        }}>Qrup yarat</AsyncBtn></>}>
      <div className="stack">
        <p className="small muted" style={{ margin: 0 }}>Seçilən siniflərdə bu səviyyədəki şagirdlərdən sərbəst tədris qrupu yaranır (məs. buraxılışa hazırlıq,
          olimpiada, təkrar). Ona onlayn test və əlavə məşğələ təyin edə bilərsiniz; şagirdlər öz siniflərində qalır.</p>
        <Field label="Səviyyə"><Seg value={level} onChange={v => { setLevel(v); setName(n => n.replace(/(zəif|orta|güclü) qrup$/i, `${v.toLowerCase()} qrup`)) }}
          options={[['Zəif', 'Zəif'], ['Orta', 'Orta'], ['Güclü', 'Güclü']]} /></Field>
        <Field label="Qrupun adı"><input value={name} maxLength={60} onChange={e => setName(e.target.value)} /></Field>
        <fieldset><legend>Siniflər ({ta.subject})</legend>
          {same.map(l => (
            <label key={l.id} className="check"><input type="checkbox" checked={sel.includes(l.id)}
              onChange={e => setSel(s => e.target.checked ? [...s, l.id] : s.filter(x => x !== l.id))} /> {l.class_name}</label>))}
        </fieldset>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}
