import { useEffect, useState } from 'react'
import { api, ApiError, del, detailText, get, patch, post, put } from '../../api'
import { useAuth } from '../../auth'
import { esc, head, printDoc, table } from '../../print'
import { kindLabel } from './common'
import { ProgramBox, PURPOSES } from './Programs'
import { AsyncBtn, ConfirmName, Disclosure, Drawer, ErrorBox, Field, fmt, fmtDate, isoDate, Loading, PickFirst, Pill, Seg, toast, useLoad, hourN } from '../../ui'
import { useT, tt } from '../../i18n'

type Cls = { id: number; name: string; code: string; kind: string; purpose?: string | null; parent_id: number | null; group_type?: 'bölünmə' | 'tədris' | null; split_with: string | null; utis_class: string | null; grade?: number | null; grade_set?: number | null; sector?: 'az' | 'ru' | null; exam_language?: string | null
  exam_date: string | null; bells: Record<string, string> | null; students: number; can_open: boolean; archived: boolean
  homeroom: { id: number; name: string } | null
  teachers: { id: number; name: string; subject: string }[]; mine: { ta_id: number; subject: string; weekly_hours: number; slots: Record<string, number[]>; has_summative: boolean; program_id: number | null; starts_on?: string | null; ends_on?: string | null
    times?: { weekday: number; start: string; end: string }[] | null } | null }
type Stud = { id: number; full_name: string; birth_date: string | null; gender: string | null; class_id: number; class_name: string; portal_code: string
  score_language: number | null; score_math: number | null; score_foreign: number | null; archived: boolean
  left_reason?: string | null; left_on?: string | null }
const DAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.']

export default function SettingsRoster({ tab }: { tab: 'classes' | 'students' | 'archive' }) {
  if (tab === 'classes') return <ClassesTab />
  if (tab === 'students') return <StudentsTab />
  return <ArchiveTab />
}

// ---------------------------------------------------------------- siniflər
function ClassesTab() {
  const t = useT()
  const [classes, err, loading, reload] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [edit, setEdit] = useState<Cls | 'new' | null>(null)
  const [join, setJoin] = useState<Cls | null>(null)
  const [members, setMembers] = useState<Cls | null>(null)
  const [split, setSplit] = useState<Cls | null>(null)
  const [study, setStudy] = useState<Cls | null>(null)
  const [add, setAdd] = useState<Cls | null>(null)
  if (loading && !classes) return <Loading />
  return (
    <>
      <ErrorBox error={err} />
      <div className="row" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={() => setEdit('new')}>{t('+ Yeni sinif / qrup')}</button>
        <span className="small muted">{t('Sinif məktəbə aiddir: başqa müəllim yaradıbsa, yenisini yaratmayın – «Qoşul» düyməsini basın.')}</span>
      </div>
      <PlansUpload onDone={reload} />
      <div className="jlist">
        {(classes || []).map(c => (
          <div className="jrow" key={c.id}>
            <span><span className="badge" title={t('Sinif ID-si')}>{c.code}</span> <b>{c.name}</b> <span className="small muted">{kindLabel(c)}{c.parent_id ? ' · ' + ((classes || []).find(p => p.id === c.parent_id)?.name || '') : ''}{c.split_with ? ' · paralel: ' + c.split_with : ''} · {c.students} {t('şagird')}</span>{c.purpose && <> <Pill tone="acc">{PURPOSES[c.purpose] || c.purpose}</Pill></>}
              <span className="sub small muted"><br />{c.teachers.map(t => `${t.name} (${t.subject})`).join(', ') || t('müəllim yoxdur')}</span>
              {c.kind !== 'qrup' && <span className="sub small muted"><br />{t('Sinif rəhbəri:')} {c.homeroom?.name || '—'}</span>}</span>
            <span className="row">{c.mine ? <Pill tone="ok">{c.mine.subject} · {c.mine.times
              ? `${[...new Set(c.mine.times.map(x => DAYS7[x.weekday].replace('Çərşənbə axşamı', 'Ç.a.').replace('Çərşənbə', 'Ç.').replace('Cümə axşamı', 'C.a.').replace('Cümə', 'C.').replace('Bazar ertəsi', 'B.e.').replace('Şənbə', 'Ş.').replace(/^Bazar$/, 'B.')))].join(', ')} · ${c.mine.times.map(x => unitsOf(x.start, x.end) * 45 + (unitsOf(x.start, x.end) - 1) * 5).join('/')} ${t('dəq.')}`
              : `${c.mine.weekly_hours} ${t('saat')}`}</Pill> : <Pill>{t('qoşulmamısınız')}</Pill>}</span>
            <span className="row">
              <button className="btn sm" onClick={() => setJoin(c)}>{c.mine ? 'Cədvəl' : 'Qoşul'}</button>
              {c.can_open && <button className="btn sm" onClick={() => setEdit(c)}>{t('Redaktə')}</button>}
              {c.can_open && c.kind !== 'qrup' && <button className="btn sm" onClick={() => setAdd(c)}>{t('+ Şagird')}</button>}
              {c.can_open && c.kind === 'qrup' && c.parent_id && <button className="btn sm" onClick={() => setMembers(c)}>{t('Bölünmə / şagird')}</button>}
              {c.can_open && c.kind === 'qrup' && !c.parent_id && <button className="btn sm" onClick={() => setStudy(c)}>{t('Üzvlər')}</button>}
              {c.can_open && c.kind !== 'qrup' && <button className="btn sm" onClick={() => setSplit(c)}>{t('Bölünmə yarat')}</button>}
            </span>
          </div>))}
        {classes?.length === 0 && <div className="empty">{t('Hələ sinif yoxdur.')}</div>}
      </div>
      {edit && <ClassForm cls={edit === 'new' ? null : edit} all={classes || []} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {join && <JoinForm cls={join} onClose={() => setJoin(null)} onDone={() => { setJoin(null); reload() }} />}
      {members && <Members cls={members} onClose={() => { setMembers(null); reload() }} />}
      {study && <StudyMembers cls={study} all={classes || []} onClose={() => { setStudy(null); reload() }} />}
      {add && <Drawer title={`${add.name} (ID: ${add.code}) – yeni şagird`} onClose={() => setAdd(null)}>
        <NewStudent classId={add.id} className={add.name} onDone={() => reload()} /></Drawer>}
      {split && <SplitForm parent={split} onClose={() => setSplit(null)} onDone={() => { setSplit(null); reload() }} />}
    </>
  )
}

function PlansUpload({ onDone }: { onDone: () => void }) {
  const t = useT()
  const [files, setFiles] = useState<File[]>([])
  const [res, setRes] = useState<any[] | null>(null)
  return (
    <Disclosure icon="plan" style={{ marginBottom: 12 }} title={t('Rəsmi perspektiv planları yüklə (hamısı birlikdə)')}>
      <div className="stack" style={{ marginTop: 10 }}>
        <p className="small muted">{t('Word (.docx) fayllarını seçin – fayl adına görə sinfə özü bağlanır (məs. «X-e sinif – Riyaziyyat perspektiv plan…» → X e). Jurnal qeydləri qorunur.')}</p>
        <input type="file" accept=".docx" multiple onChange={e => setFiles(Array.from(e.target.files || []))} />
        <AsyncBtn className="btn primary" disabled={!files.length} onClick={async () => {
          const fd = new FormData(); files.forEach(f => fd.append('files', f))
          const r = await api('/api/plan/import-many', { method: 'POST', form: fd }); setRes(r); onDone()
          toast(t('{length} plan yükləndi', { length: r.filter((x: any) => x.ok).length }))
        }}>{t('Yüklə (')}{files.length})</AsyncBtn>
        {res && <div className="jlist">{res.map((x: any) => (
          <div key={x.file} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
            <span className="small">{x.file}</span>
            {x.ok ? <Pill tone="ok">{x.class_name}: {x.lessons} {t('dərs · KSQ')} {x.ksq} {t('· BSQ')} {x.bsq}</Pill> : <Pill>{x.message}</Pill>}
          </div>))}</div>}
      </div>
    </Disclosure>
  )
}

function ClassForm({ cls, all, onClose, onDone }: { cls: Cls | null; all: Cls[]; onClose: () => void; onDone: () => void }) {
  const t = useT()
  // növ: TOM / adi – bütöv sinif; split – sinif daxilində bölünmə qrupu; study – müxtəlif siniflərdən tədris qrupu
  const type0 = !cls ? 'TOM' : cls.kind !== 'qrup' ? cls.kind : cls.parent_id ? 'split' : 'study'
  const [f, setF] = useState({ name: cls?.name || '', code: cls?.code || '', type: type0, parent_id: cls?.parent_id || '', split_with: cls?.split_with || '',
    utis_class: cls?.utis_class || '', grade: cls?.grade_set ? String(cls.grade_set) : '', exam_date: cls?.exam_date || '', bells: (cls?.bells || {}) as Record<string, string>,
    purpose: cls?.purpose || '', sector: cls?.sector || '', exam_language: cls?.exam_language || '' })
  const [ownBells, setOwnBells] = useState(!!cls?.bells && Object.keys(cls.bells).length > 0)
  const { me } = useAuth()
  const [where, setWhere] = useState<'school' | 'private'>(me?.workspace === 'private' ? 'private' : 'school')
  const [err, setErr] = useState<unknown>()
  const [confirm, setConfirm] = useState(false)
  const [plan, setPlan] = useState<File | null>(null)
  const [lessons] = useLoad<any[]>(() => get('/api/my/lessons'), [])
  const ta = lessons?.find(l => l.class_id === cls?.id)
  const group = f.type === 'split' || f.type === 'study'
  const priv = cls ? me?.workspace === 'private' : where === 'private'      // fərdi hazırlıq: məqsəd, real vaxtlar (zəng yox)
  const save = async () => {
    try {
      const body: any = { name: f.name, split_with: f.type === 'split' ? f.split_with || null : null, utis_class: group ? null : f.utis_class || null, grade: f.grade ? Number(f.grade) : null,
        exam_date: f.exam_date || null, bells: ownBells && !priv ? Object.fromEntries(Object.entries(f.bells).filter(([, v]) => v.trim())) : {},
        ...(priv ? { purpose: f.purpose || null } : { sector: f.sector || null, exam_language: f.exam_language || null }) }
      if (cls) await patch(`/api/classes/${cls.id}`, { ...body, ...(group ? {} : { kind: f.type }), ...(f.code && f.code !== cls.code ? { code: f.code } : {}) })
      else await post('/api/classes', { ...body, kind: group ? 'qrup' : f.type, parent_id: f.type === 'split' && f.parent_id ? Number(f.parent_id) : null, private: where === 'private' })
      if (!cls && where === 'private' && me?.workspace !== 'private') { toast(t('Fərdi sinif yaradıldı – fərdi məkana keçilir')); setTimeout(() => location.reload(), 600); return }
      toast('Yadda saxlanıldı'); onDone()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && (e.data as any)?.detail?.class_id) setErr(new Error(detailText((e.data as any).detail)))
      else setErr(e)
    }
  }
  return (
    <Drawer title={cls ? t('{name} – redaktə', { name: cls.name }) : t('Yeni sinif / qrup')} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button><button className="btn primary" onClick={save} disabled={!f.name || (f.type === 'split' && !f.parent_id)}>{t('Yadda saxla')}</button></>}>
      <div className="stack">
        {!cls && <fieldset style={{ margin: 0 }}><legend>{t('Harada')}</legend>
          <label className="check"><input type="radio" name="where" checked={where === 'school'} onChange={() => setWhere('school')} /> {t('Məktəb')}{me?.workspace !== 'private' && me?.school_name ? ` – ${me.school_name}` : ''}</label>
          <label className="check"><input type="radio" name="where" checked={where === 'private'} onChange={() => setWhere('private')} /> {t('Fərdi (hazırlıq / repetitor) – məktəbə aid deyil')}</label>
          {where === 'private' && <p className="small muted" style={{ margin: '4px 0 0' }}>{t('Fərdi sinif məktəbin hesabatlarına, siyahılarına və adminə düşmür; yalnız siz görürsünüz. Yuxarıdakı «Məktəb · Fərdi» düyməsi ilə məkanlar arasında keçirsiniz.')}</p>}
        </fieldset>}
        <div className="fg">
          <Field label={t('Ad')} full hint={group ? t('məs. X b (riyaziyyat qrupu), Olimpiada qrupu') : t('məs. X e, XI peşə sinfi')}><input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></Field>
          {cls && <Field label={t('Sinif ID-si')} hint={t('hərf və rəqəm; şagird ID-ləri bununla başlayır (XB-001). Köhnə şagird ID-ləri dəyişmir')}>
            <input value={f.code} maxLength={8} onChange={e => setF({ ...f, code: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '') })} />
            {f.code && f.code !== cls.code && <span className="small" style={{ color: 'var(--warn)', display: 'block', marginTop: 4 }}>⚠ {t('Artıq yaradılmış şagirdlərin kodları dəyişmir – yalnız yeni şagirdlər yeni ID ilə başlayacaq.')}</span>}</Field>}
          <Field label={t('Növ')} hint={cls && group ? t('qrupun növü dəyişmir') : cls ? t('TOM ↔ adi dəyişir') : undefined}>
            <select value={f.type} disabled={!!cls && group} onChange={e => setF({ ...f, type: e.target.value })}>
              <option value="TOM">{t('TOM sinfi')}</option><option value="adi">{t('Adi sinif')}</option>
              {(!cls || group) && <option value="split">{t('Bölünmə qrupu (sinif daxilində)')}</option>}
              {(!cls || group) && <option value="study">{t('Tədris qrupu (müxtəlif siniflərdən)')}</option>}
            </select></Field>
          {f.type === 'split' && <Field label={t('Ana sinif')}>{cls
            ? <input readOnly value={all.find(c => c.id === cls.parent_id)?.name || ''} />
            : <select value={f.parent_id} onChange={e => setF({ ...f, parent_id: e.target.value })}><option value="">—</option>{all.filter(c => c.kind !== 'qrup').map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>}</Field>}
          {f.type === 'split' && <Field label={t('Paralel fənn (sinfin digər yarısı)')} full><input value={f.split_with} onChange={e => setF({ ...f, split_with: e.target.value })} placeholder={t('Biologiya – Şərqiyə müəllimə')} /></Field>}
          {priv && <Field label={t('Hazırlıq məqsədi')} hint="uyğun proqram (məs. IX buraxılış hazırlığı) qoşulanda öndə çıxır və əvvəlcədən seçilir">
            <select value={f.purpose} onChange={e => setF({ ...f, purpose: e.target.value })}><option value="">{t('— seçilməyib —')}</option>
              {Object.entries(PURPOSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>}
          {!group && !priv && <Field label={t('UTİS sinfi')}><input value={f.utis_class} onChange={e => setF({ ...f, utis_class: e.target.value })} placeholder="10 e" /></Field>}
          <Field label={t('Sinif rəqəmi')} hint="boş – addan (IX a → 9); eyni mövzulu sinifləri tapmaq üçün"><select value={f.grade} onChange={e => setF({ ...f, grade: e.target.value })}>
            <option value="">{t('avtomatik')}{cls?.grade ? ` (${cls.grade})` : ''}</option>{Array.from({ length: 11 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}</select></Field>
          {!priv && <Field label={t('Sektor')} hint={group ? t('boş – ana sinifdən / Azərbaycan') : undefined}><select value={f.sector} onChange={e => setF({ ...f, sector: e.target.value })}>
            <option value="">{t('Azərbaycan')}</option><option value="ru">{t('Rus')}</option></select></Field>}
          {!priv && <Field label={t('Yazılı imtahanın dili')} hint={t('KSQ/BSQ və kağız testlər bu dildə çap olunur. Şagirdlərin interfeys dili vərəqə təsir etmir.')}><select value={f.exam_language} onChange={e => setF({ ...f, exam_language: e.target.value })}>
            <option value="">{t('Sektora uyğun')}</option><option value="az">{t('Azərbaycan dili')}</option><option value="ru">{t('Rus dili')}</option><option value="az_ru">{t('İkidilli (AZ + RU)')}</option></select></Field>}
          <Field label={t('İmtahan tarixi')} hint="şagird portalında sayğac"><input type="date" value={f.exam_date} onChange={e => setF({ ...f, exam_date: e.target.value })} /></Field>
        </div>
        {f.type === 'study' && <p className="small muted" style={{ margin: 0 }}>{t('Tədris qrupu (olimpiada, hazırlıq, dərnək): yaratdıqdan sonra «Qoşul» ilə cədvəli, «Üzvlər» ilə müxtəlif siniflərdən şagirdləri seçin.')}</p>}
        {priv ? <p className="small muted" style={{ margin: 0 }}>{t('Fərdi hazırlıqda məktəb zəngi yoxdur: dərs günlərini və real vaxtlarını «Qoşul» pəncərəsində yazırsınız.')}</p> :
        <fieldset><legend>{t('Dərs vaxtları')}</legend>
          <label className="check"><input type="checkbox" checked={ownBells} onChange={e => setOwnBells(e.target.checked)} /> {t('Bu sinfin öz zəngi var (məs. XI peşə 08:00)')}</label>
          {ownBells && <div className="fg" style={{ marginTop: 8 }}>{Array.from({ length: 9 }, (_, i) => String(i)).map(k => (
            <Field key={k} label={hourN(k)}><input value={f.bells[k] || ''} placeholder="08:00–08:45" onChange={e => setF({ ...f, bells: { ...f.bells, [k]: e.target.value } })} /></Field>))}</div>}
          {!ownBells && <p className="small muted" style={{ margin: '4px 0 0' }}>{t('Məktəbin ümumi zəngi işlənir.')}</p>}
        </fieldset>}
        {cls && cls.kind !== 'qrup' && <HomeroomField cls={cls} onDone={onDone} />}
        {cls && ta && (
          <fieldset><legend>{t('Rəsmi perspektiv plan (.docx)')}</legend>
            <p className="small muted">{ta.plan_lessons ? t('Yüklənib: {plan_lessons} dərs. Yenidən yükləmək jurnal qeydlərini saxlayır.', { plan_lessons: ta.plan_lessons }) : t('Plan yüklənməyib.')}</p>
            <div className="row"><input type="file" accept=".docx" onChange={e => setPlan(e.target.files?.[0] || null)} />
              <AsyncBtn className="btn" disabled={!plan} onClick={async () => {
                const fd = new FormData(); fd.append('file', plan!)
                const r = await api(`/api/plan/${ta.id}/import`, { method: 'POST', form: fd })
                toast(t('Plan yükləndi: {lessons} dərs, KSQ {ksq}, BSQ {bsq}', { lessons: r.lessons, ksq: r.ksq, bsq: r.bsq }))
              }}>{t('Yüklə')}</AsyncBtn></div>
          </fieldset>)}
        <ErrorBox error={err} />
        {cls && (confirm
          ? <ConfirmName name={cls.name} action="Arxivə göndər" onCancel={() => setConfirm(false)} onConfirm={async typed => { await post(`/api/classes/${cls.id}/archive`, { confirm: typed }); toast(t('Arxivə göndərildi')); onDone() }} />
          : <button className="btn danger" onClick={() => setConfirm(true)}>{t('Arxivə göndər')}</button>)}
      </div>
    </Drawer>
  )
}

/** Sinif rəhbəri: admin istənilən müəllimi təyin edir; müəllim rəhbəri olmayan sinfi özü götürür və ya özünü çıxarır. */
function HomeroomField({ cls, onDone }: { cls: Cls; onDone: () => void }) {
  const t = useT()
  const { me } = useAuth()
  const admin = me?.role === 'admin'
  const [teachers] = useLoad<any[]>(() => (admin ? get('/api/teachers') : Promise.resolve([])), [admin])
  const [v, setV] = useState(String(cls.homeroom?.id ?? ''))
  const set = async (id: number | null) => { await put(`/api/classes/${cls.id}/homeroom`, { teacher_id: id }); toast(t('Sinif rəhbəri yadda saxlanıldı')); onDone() }
  return (
    <fieldset><legend>{t('Sinif rəhbəri')}</legend>
      {admin ? (
        <div className="row">
          <select className="sel" value={v} onChange={e => setV(e.target.value)} aria-label={t('Sinif rəhbəri')}>
            <option value="">{t('— təyin edilməyib —')}</option>
            {(teachers || []).filter(t => !t.archived && t.school_id === me?.school_id).map(t => <option key={t.id} value={t.id}>{t.full_name}</option>)}
          </select>
          <AsyncBtn className="btn" disabled={v === String(cls.homeroom?.id ?? '')} onClick={() => set(v ? Number(v) : null)}>{t('Təyin et')}</AsyncBtn>
        </div>
      ) : cls.homeroom?.id === me?.id ? (
        <div className="row"><span className="grow">{t('Siz bu sinfin rəhbərisiniz.')}</span><AsyncBtn className="btn" onClick={() => set(null)}>{t('Rəhbərlikdən çıx')}</AsyncBtn></div>
      ) : cls.homeroom ? (
        <p className="small muted" style={{ margin: 0 }}>{t('Rəhbər:')} {cls.homeroom.name}{t('. Dəyişmək üçün adminə müraciət edin.')}</p>
      ) : (
        <div className="row"><span className="grow small muted">{t('Bu sinfin rəhbəri yoxdur.')}</span><AsyncBtn className="btn" onClick={() => set(me!.id)}>{t('Mən sinif rəhbəriyəm')}</AsyncBtn></div>
      )}
      <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Sinif rəhbəri sinfin bütün fənləri üzrə dərs sayını, qiymətləri, müvəffəqiyyəti və davamiyyəti görür (başqa müəllimlərin jurnal qeydlərini yox).')}</p>
    </fieldset>
  )
}

function JoinForm({ cls, onClose, onDone }: { cls: Cls; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [subject, setSubject] = useState(cls.mine?.subject || 'Riyaziyyat')
  const [slots, setSlots] = useState<Record<string, number[]>>(cls.mine?.slots || {})
  const { me } = useAuth()
  const privWs = me?.workspace === 'private'
  // köhnə qaydada (dərs saatı şəbəkəsi ilə) qoşulmuş fərdi qrup – şəbəkə saxlanılır, istəsə real vaxtlara keçir
  const legacy = privWs && !!cls.mine && !cls.mine.times && Object.keys(cls.mine.slots || {}).length > 0
  const [toTimes, setToTimes] = useState(false)
  const priv = privWs && (!legacy || toTimes)
  const days = privWs ? [...DAYS, 'Ş.', 'B.'] : DAYS   // fərdi qrupda şənbə və bazar da dərs günüdür
  // fərdi hazırlıq məktəb deyil: dərs – həftə günü + real başlama/bitmə vaxtı (məktəb zəngi və «saat» yoxdur)
  const [times, setTimes] = useState<{ weekday: number; start: string; end: string }[]>(cls.mine?.times || [])
  const [summ, setSumm] = useState(cls.mine?.has_summative ?? (cls.kind !== 'qrup' && me?.workspace !== 'private'))   // fərdi sinifdə defolt – yox
  const [err, setErr] = useState<unknown>()
  const [leave, setLeave] = useState(false)
  const [prog, setProg] = useState('')
  const [course, setCourse] = useState({ from: cls.mine?.starts_on || '', to: cls.mine?.ends_on || '' })   // kurs müddəti (boş – tədris ili)
  const [grade, setGrade] = useState('')            // sinif rəqəmi müəyyən deyilsə (qarışıq qrup) – proqram uyğunluğu üçün
  const [lib] = useLoad<any[]>(() => (cls.mine ? Promise.resolve([]) : get('/api/programs', { class_id: String(cls.id), ...(grade ? { grade_hint: grade } : {}) })), [cls.id, grade])
  const [auto, setAuto] = useState(true)
  // seçilən proqram bu cədvəl və kurs müddəti ilə neçə dərsə açılır, nə sığmır – qoşulmazdan əvvəl
  const [est, setEst] = useState<{ lessons: number; slots: number; warnings: string[]; warnings_i18n?: { key: string; params: Record<string, any> }[]; lint?: { key: string; params: Record<string, any>; message: string }[]; hours_mismatch?: boolean; program_hours?: number | null; class_hours?: number; budget?: any } | null>(null)
  const estKey = JSON.stringify([prog, priv ? times : slots, course, summ])
  useEffect(() => {
    setEst(null)
    if (cls.mine || !prog || !(priv ? times.length : Object.keys(slots).length)) return
    const t = setTimeout(() => {
      post<any>(`/api/programs/${prog}/estimate`, { class_id: cls.id, slots: priv ? {} : slots, times: priv ? times : null,
        starts_on: course.from || null, ends_on: course.to || null, has_summative: summ }).then(setEst).catch(() => setEst(null))
    }, 400)
    return () => clearTimeout(t)
  }, [estKey])
  useEffect(() => {
    if (!auto || !lib || !cls.purpose) return
    const best = lib.find(p => p.purpose_fits && p.fits)
    setProg(best ? String(best.id) : '')
  }, [lib, auto, cls.purpose])
  const hours = priv ? times.reduce((a, x) => a + unitsOf(x.start, x.end), 0) : Object.values(slots).reduce((a, v) => a + v.length, 0)
  // mövcud qrupun büdcəsi: seçilmiş proqramın bu cədvəllə önbaxışı
  const [bud, setBud] = useState<any>(null)
  useEffect(() => {
    if (!cls.mine?.program_id || !priv) return
    get<any>(`/api/programs/${cls.mine.program_id}/preview/${cls.mine.ta_id}`).then(r => setBud(r.budget)).catch(() => setBud(null))
  }, [cls.id])
  const toggle = (d: number, p: number) => {
    const cur = new Set(slots[d] || [])
    cur.has(p) ? cur.delete(p) : cur.add(p)
    setSlots({ ...slots, [d]: [...cur].sort((a, b) => a - b) })
  }
  return (
    <Drawer title={`${cls.name} – ${cls.mine ? t('dərs cədvəli') : t('sinfə qoşul')}`} onClose={onClose}
      footer={<><span className="small muted grow">{priv ? t('Həftədə {n} görüş · {m} saat', { n: times.length, m: hours }) : t('Həftədə {hours} saat', { hours })}</span><button className="btn" onClick={onClose}>{t('Ləğv et')}</button>
        <button className="btn primary" disabled={!hours || !subject} onClick={async () => { try { await post(`/api/classes/${cls.id}/join`, { subject, weekly_hours: hours, slots: priv ? {} : slots, ...(priv ? { times } : {}), has_summative: summ, program_id: prog ? Number(prog) : null, grade: grade ? Number(grade) : null, starts_on: course.from || null, ends_on: course.to || null }); toast('Yadda saxlanıldı'); onDone() } catch (e) { setErr(e) } }}>{t('Yadda saxla')}</button></>}>
      <div className="stack">
        <Field label={t('Fənn')}><input value={subject} onChange={e => setSubject(e.target.value)} /></Field>
        <label className="check"><input type="checkbox" checked={summ} onChange={e => setSumm(e.target.checked)} /> {t('KSQ/BSQ keçirilir (bölünən qrupda adətən yox)')}</label>
        {!cls.mine && !cls.grade && <Field label={t('Sinif rəqəmi')} hint="bu qrupun sinfi addan tapılmadı – seçin ki, uyğun proqramlar öndə çıxsın">
          <select value={grade} onChange={e => setGrade(e.target.value)}><option value="">{t('— müəyyən deyil (qarışıq qrup) —')}</option>
            {Array.from({ length: 11 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}</select></Field>}
        {!cls.mine && <Field label={t('Əsas perspektiv plan proqramı')} hint="jurnal və tarixlər ona görə; sinfə uyğun olanlar öndə. Əlavə proqramları qoşulandan sonra əlavə edə bilərsiniz">
          <select value={prog} onChange={e => { setAuto(false); setProg(e.target.value) }}><option value="">{t('— sonra seçəcəm (və ya Word planı yükləyəcəm) —')}</option>
            {(lib || []).map(p => <option key={p.id} value={p.id}>{p.purpose_fits ? '★ ' : p.fits && p.grade ? '✓ ' : ''}{p.title}{p.level ? ` · ${p.level}` : ''}</option>)}</select></Field>}
        {bud && <BudgetPill b={bud} />}
        {est && <div className="small" style={{ margin: 0 }}>
          <BudgetPill b={est.budget} />
          <span className="muted">{t('Proqram:')} {est.lessons} {t('dərs · kursda')} {est.slots} {t('dərs yuvası')}</span>
          {(est.warnings_i18n || est.warnings.map(w => ({ key: w, params: {} }))).map(w => <p key={w.key + JSON.stringify(w.params)} style={{ color: 'var(--warn)', margin: '4px 0 0' }}>⚠ {t(w.key, w.params)}</p>)}
          {est.hours_mismatch && <p style={{ color: 'var(--warn)', margin: '4px 0 0' }}>⚠ {t('Proqram həftədə {p} saatlıqdır, cədvəldə isə {c} saat var', { p: est.program_hours, c: est.class_hours })}</p>}
          {(est.lint || []).map(w => <p key={w.message} style={{ color: 'var(--warn)', margin: '4px 0 0' }}>⚠ {t(w.key, w.params)}</p>)}
          {est.warnings.length > 0 && <p className="muted" style={{ margin: '4px 0 0' }}>{t('Qoşulandan sonra «Cədvəl» → «Bölmələri seç» ilə lazım olan bölmələri seçə bilərsiniz.')}</p>}
        </div>}
        {!cls.mine && cls.purpose && <p className="small muted" style={{ margin: 0 }}>{t('Qrupun məqsədi:')} <b>{PURPOSES[cls.purpose] || cls.purpose}</b> {t('– ★ uyğun proqramlar öndədir.')}</p>}
        {me?.workspace === 'private' || course.from || course.to ? <CourseDates v={course} onChange={setCourse} />
          : <Disclosure variant="flat" title={<span className="small muted">{t('Kurs müddəti (istəyə görə)')}</span>}><CourseDates v={course} onChange={setCourse} /></Disclosure>}
        {legacy && !toTimes && <p className="small" style={{ margin: 0 }}>{t('Bu qrupun cədvəli köhnə qaydada (dərs saatı ilə) yazılıb.')}{' '}
          <button className="btn sm" onClick={() => setToTimes(true)}>{t('Real dərs vaxtlarına keç')}</button></p>}
        {priv ? <LessonTimes v={times} onChange={setTimes} /> : <>
        <p className="small muted">{t('Dərs saatlarını işarələyin (0 – birinci dərsdən əvvəlki saat, məs. XI peşə 08:00):')}</p>
        <div className="tbl-wrap"><table style={{ minWidth: 0 }}><thead><tr><th>{t('Saat')}</th>{days.map(d => <th key={d}>{d}</th>)}</tr></thead>
          <tbody>{Array.from({ length: 9 }, (_, p) => (
            <tr key={p}><th className="small">{p}</th>{days.map((_, d) => (
              <td key={d} style={{ textAlign: 'center' }}><input type="checkbox" aria-label={`${days[d]} ${hourN(p)}`} checked={(slots[d] || []).includes(p)} onChange={() => toggle(d, p)} /></td>))}</tr>))}</tbody></table></div></>}
        {cls.mine && <fieldset style={{ margin: 0 }}><legend>{t('Perspektiv plan proqramları')}</legend><ProgramBox ta={cls.mine.ta_id} /></fieldset>}
        <ErrorBox error={err} />
        {cls.mine && (leave
          ? <ConfirmName name={cls.name} action="Dərsdən çıx" onCancel={() => setLeave(false)} onConfirm={async () => { await api(`/api/classes/${cls.id}/leave`, { method: 'POST', params: { subject: cls.mine!.subject } }); toast(t('Dərsdən çıxdınız')); onDone() }} />
          : <button className="btn danger" onClick={() => setLeave(true)}>{t('Bu sinifdəki dərsimdən çıx')}</button>)}
      </div>
    </Drawer>
  )
}

const DAYS7 = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']
const toMin = (t: string) => { const [h, m] = (t || '0:0').split(':').map(Number); return h * 60 + m }

// görüş = N akademik saat: saat 45 dəq., aralarında 5 dəq. fasilə (server: meeting_units/meeting_end ilə eyni qayda)
const fmtMin = (m: number) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
export const unitsOf = (s: string, e: string) => Math.max(1, Math.round((toMin(e) - toMin(s) + 5) / 50))
const endOf = (s: string, u: number) => fmtMin(toMin(s) + u * 45 + (u - 1) * 5)

/** Fərdi qrupun görüşləri: gün + başlama + saat sayı (45/90/135 dəq.) → bitmə avtomatik. */
function LessonTimes({ v, onChange }: { v: { weekday: number; start: string; end: string }[]; onChange: (v: { weekday: number; start: string; end: string }[]) => void }) {
  const t = useT()
  const upd = (i: number, p: Partial<{ weekday: number; start: string; units: number }>) => onChange(v.map((x, j) => {
    if (j !== i) return x
    const start = p.start ?? x.start
    return { weekday: p.weekday ?? x.weekday, start, end: endOf(start, p.units ?? unitsOf(x.start, x.end)) }
  }))
  const add = () => {
    const last = v[v.length - 1]
    const st = last?.start || '17:00'
    onChange([...v, { weekday: last ? (last.weekday + 2) % 7 : 1, start: st, end: endOf(st, last ? unitsOf(last.start, last.end) : 2) }])
  }
  const total = v.reduce((a, x) => a + unitsOf(x.start, x.end), 0)
  return (
    <fieldset style={{ margin: 0 }}><legend>{t('Dərs vaxtları')}</legend>
      <p className="small muted" style={{ marginTop: 0 }}>{t('Fərdi hazırlıqda məktəb zəngi yoxdur – hər görüşün gününü, başlama vaxtını və saat sayını seçin (məs. Ç.a. 17:00, 2 saat). Bitmə avtomatik hesablanır.')}</p>
      {v.length === 0 && <p className="small muted">{t('Hələ dərs vaxtı yoxdur.')}</p>}
      {v.map((x, i) => {
        const u = unitsOf(x.start, x.end)
        return (
          <div key={i} className="row" style={{ gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            <select value={x.weekday} onChange={e => upd(i, { weekday: Number(e.target.value) })} aria-label={tt('Gün')}>{DAYS7.map((d, k) => <option key={k} value={k}>{d}</option>)}</select>
            <input type="time" value={x.start} onChange={e => upd(i, { start: e.target.value })} aria-label={tt('Başlayır')} style={{ width: 110 }} />
            <select value={u} onChange={e => upd(i, { units: Number(e.target.value) })} aria-label={tt('Saat sayı')}>
              <option value={1}>{t('1 saat (45 dəq.)')}</option><option value={2}>{t('2 saat (45+5+45)')}</option><option value={3}>{t('3 saat')}</option><option value={4}>{t('4 saat')}</option></select>
            <span className="small muted">{t('bitir')} {endOf(x.start, u)}</span>
            <button className="btn sm ghost right" onClick={() => onChange(v.filter((_, j) => j !== i))} aria-label={tt('Sil')}>✕</button>
          </div>)
      })}
      <button className="btn sm" onClick={add}>{t('+ Dərs vaxtı')}</button>
      {v.length > 0 && <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Həftədə {n} görüş · {m} saat', { n: v.length, m: total })}</p>}
    </fieldset>
  )
}

/** Büdcə nişanı: yaşıl – sığır, sarı – ehtiyat < 5%, qırmızı – çatmır. */
export function BudgetPill({ b }: { b?: { meetings: number; hours: number; need: number | null; spare: number | null; status: string | null; from?: string | null; to?: string | null } | null }) {
  const t = useT()
  if (!b) return null
  const tone = b.status === 'short' ? 'bad' : b.status === 'tight' ? 'warn' : 'ok'
  return <div className="small" style={{ margin: 0 }}>
    <Pill tone={tone as any}>{t('{n} görüş · {h} saat', { n: b.meetings, h: b.hours })}</Pill>{' '}
    {b.need != null && b.spare != null && <span className="muted">{b.spare >= 0
      ? t('plan {need} saat tələb edir · ehtiyat {x} saat', { need: b.need, x: b.spare })
      : t('plan {need} saat tələb edir · çatmır: {x} saat. Həftəyə 1 görüş əlavə edin və ya bölmələri azaldın', { need: b.need, x: -b.spare })}</span>}
  </div>
}

/** Qrupun kurs müddəti: dərslər, jurnal və proqram yalnız bu aralıqda (boş – tədris ilinin əvvəli / sonu). */
function CourseDates({ v, onChange }: { v: { from: string; to: string }; onChange: (v: { from: string; to: string }) => void }) {
  const t = useT()
  return (
    <div className="fg">
      <Field label={t('Kurs başlayır')} hint="boş – tədris ilinin əvvəli"><input type="date" value={v.from} onChange={e => onChange({ ...v, from: e.target.value })} /></Field>
      <Field label={t('Kurs bitir')} hint="boş – tədris ilinin sonu"><input type="date" value={v.to} min={v.from || undefined} onChange={e => onChange({ ...v, to: e.target.value })} /></Field>
    </div>
  )
}

function Members({ cls, onClose }: { cls: Cls; onClose: () => void }) {
  const t = useT()
  const [studs, , , reloadStuds] = useLoad<Stud[]>(() => get('/api/students', { class_id: cls.parent_id! }), [cls.parent_id])
  const [ids, setIds] = useState<Set<number>>(new Set())
  const [other, setOther] = useState(cls.split_with || '')
  const [adding, setAdding] = useState(false)
  const [side, setSide] = useState<'mine' | 'other'>('mine')
  const [q, setQ] = useState('')
  const [codes, setCodes] = useState('')
  const [codeMsg, setCodeMsg] = useState('')
  useEffect(() => { get<number[]>(`/api/classes/${cls.id}/members`).then(x => setIds(new Set(x))) }, [cls.id])
  const lc = (x: string) => x.toLocaleLowerCase('az')
  const shown = (studs || []).filter(s => !q || lc(s.full_name).includes(lc(q)) || lc(s.portal_code).includes(lc(q)))
  const num = (s: Stud) => Number(s.portal_code.split('-').pop())
  const byCodes = () => {
    const want = codes.toUpperCase().split(/[\s,;]+/).filter(Boolean)
    const map = new Map((studs || []).map(s => [s.portal_code.toUpperCase(), s.id]))
    const n = new Set(ids), bad: string[] = []
    // «7» və ya «007» yazsa da olar – sinif ID-si əlavə olunur
    const prefix = (studs || [])[0]?.portal_code.split('-').slice(0, -1).join('-')
    want.forEach(w => { const k = /^\d+$/.test(w) && prefix ? `${prefix}-${w.padStart(3, '0')}` : w; const id = map.get(k); id ? n.add(id) : bad.push(w) })
    setIds(n); setCodes('')
    setCodeMsg(t('{x1} şagird qrupa əlavə olundu', { x1: want.length - bad.length }) + (bad.length ? (' · ' + t('tanınmadı: {x1}', { x1: bad.join(', ') })) : ''))
  }
  const inner = cls.name.includes('(') ? cls.name.slice(cls.name.indexOf('(') + 1).replace(')', '').replace(/ qrupu$/, '').trim() : t('Bu qrup')
  const mine = inner.charAt(0).toLocaleUpperCase('az') + inner.slice(1)
  const otherName = (other.split('–')[0] || t('Digər fənn')).trim()
  const set = (sid: number, inGroup: boolean) => { const n = new Set(ids); inGroup ? n.add(sid) : n.delete(sid); setIds(n) }
  return (
    <Drawer title={t('{name} – bölünmə', { name: cls.name })} onClose={onClose}
      footer={<><span className="small muted grow">{mine}: {ids.size} · {otherName}: {(studs?.length || 0) - ids.size}</span>
        <AsyncBtn className="btn primary" ok="Bölünmə yadda saxlanıldı" onClick={async () => {
          if (other !== (cls.split_with || '')) await patch(`/api/classes/${cls.id}`, { split_with: other || null })
          await put(`/api/classes/${cls.id}/members`, { student_ids: [...ids] }); onClose()
        }}>{t('Yadda saxla')}</AsyncBtn></>}>
      <Field label={t('Paralel fənn (sinfin digər yarısı)')} hint="məs. Biologiya – Şərqiyə müəllimə"><input value={other} onChange={e => setOther(e.target.value)} /></Field>
      <div className="row" style={{ margin: '12px 0' }}>
        <button className="btn sm" onClick={() => setIds(new Set((studs || []).map(s => s.id)))}>{t('Hamısı:')} {mine}</button>
        <button className="btn sm" onClick={() => setIds(new Set())}>{t('Hamısı:')} {otherName}</button>
        <button className="btn sm" onClick={() => setIds(new Set((studs || []).filter(s => num(s) % 2 === 1).map(s => s.id)))}>{t('Tək ID-lər:')} {mine}</button>
        <button className="btn sm" onClick={() => setIds(new Set((studs || []).filter(s => num(s) % 2 === 0).map(s => s.id)))}>{t('Cüt ID-lər:')} {mine}</button>
        <button className="btn sm primary" aria-pressed={adding} onClick={() => setAdding(!adding)}>{t('+ Yeni şagird')}</button>
      </div>
      {adding && (
        <fieldset style={{ marginBottom: 12 }}><legend>{t('Yeni şagird – ana sinfə yazılır')}</legend>
          <Seg value={side} onChange={setSide} label={t('Qrup')} options={[['mine', mine], ['other', t('{otherName} (paralel)', { otherName })]]} />
          <NewStudent classId={cls.parent_id!} groupId={side === 'mine' ? cls.id : undefined} onDone={s => {
            reloadStuds()
            if (s && side === 'mine') { const n = new Set(ids); n.add(s.id); setIds(n) }
            if (s) toast(`${s.full_name} – ${side === 'mine' ? mine : otherName}`)
          }} />
        </fieldset>)}
      <fieldset style={{ marginBottom: 12 }}><legend>{t('ID ilə seç')}</legend>
        <div className="row" style={{ flexWrap: 'nowrap' }}>
          <input className="sel grow" value={codes} onChange={e => setCodes(e.target.value)} placeholder={t('məs. XB-001, XB-005 və ya 1 5 9')} aria-label={t('Şagird ID-ləri')}
            onKeyDown={e => { if (e.key === 'Enter' && codes.trim()) byCodes() }} />
          <button className="btn sm primary" disabled={!codes.trim()} onClick={byCodes}>{mine} {t('qrupuna əlavə et')}</button></div>
        {codeMsg && <p className="small muted" style={{ margin: '6px 0 0' }}>{codeMsg}</p>}
      </fieldset>
      <div className="search" style={{ marginBottom: 8 }}><input placeholder={t('Ad və ya ID ilə axtar')} value={q} onChange={e => setQ(e.target.value)} /></div>
      {!studs ? <Loading /> : (
        <div className="jlist">{shown.map(s => (
          <div key={s.id} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto' }}>
            <span><span className="mono small muted">{s.portal_code}</span> {s.full_name}</span>
            <div className="seg" role="group" aria-label={s.full_name} style={{ minWidth: 220 }}>
              <button aria-pressed={ids.has(s.id)} onClick={() => set(s.id, true)}>{mine}</button>
              <button aria-pressed={!ids.has(s.id)} onClick={() => set(s.id, false)}>{otherName}</button>
            </div>
          </div>))}
          {studs.length === 0 && <div className="empty">{t('Ana sinifdə şagird yoxdur – «+ Yeni şagird» ilə əlavə edin.')}</div>}</div>)}
    </Drawer>
  )
}

/** Yeni şagird (sinfə yazılır): yaradıldıqdan sonra giriş kodu və ilkin PIN bir dəfə göstərilir. */
export function NewStudent({ classId, groupId, className, onDone }: { classId: number; groupId?: number; className?: string; onDone: (s: { id: number; full_name: string } | null) => void }) {
  const t = useT()
  const [f, setF] = useState({ full_name: '', birth_date: '', gender: '' })
  const [made, setMade] = useState<{ full_name: string; portal_code: string; initial_pin: string | null } | null>(null)
  const [err, setErr] = useState<unknown>()
  const [dupArch, setDupArch] = useState<{ id: number; message: string } | null>(null)
  type Sim = { id: number; full_name: string; class_name: string; class_id: number }
  const [similar, setSimilar] = useState<Sim[] | null>(null)
  const submit = async (force: boolean) => {
    setErr(undefined); setDupArch(null); setSimilar(null)
    try {
      const r = await post('/api/students', { full_name: f.full_name.trim(), class_id: classId, birth_date: f.birth_date || null, gender: f.gender || null, ...(groupId ? { group_id: groupId } : {}), ...(force ? { force: true } : {}) })
      setMade(r); setF({ full_name: '', birth_date: '', gender: '' }); onDone({ id: r.id, full_name: r.full_name })
    } catch (e) {
      const d = e instanceof ApiError ? (e.data as any)?.detail : null
      if (d?.archived && d?.student_id) setDupArch({ id: d.student_id, message: detailText(d) })
      else if (d?.possible_duplicate?.length) setSimilar(d.possible_duplicate)
      else setErr(e)
    }
  }
  const words = f.full_name.trim().split(/\s+/).filter(Boolean).length
  return (
    <div className="stack">
      <div className="fg">
        <Field label={t('Soyadı, adı, ata adı')} full><input value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} placeholder={t('Məmmədov Əli Vüqar oğlu')} /></Field>
        <Field label={t('Doğum tarixi')}><input type="date" value={f.birth_date} onChange={e => setF({ ...f, birth_date: e.target.value })} /></Field>
        <Field label={t('Cins')}><select value={f.gender} onChange={e => setF({ ...f, gender: e.target.value })}><option value="">—</option><option value="Qız">{t('Qız')}</option><option value="Oğlan">{t('Oğlan')}</option></select></Field>
      </div>
      <ErrorBox error={err} />
      {f.full_name.trim() && words < 2 && <p className="small muted" style={{ margin: 0 }}>{t('Soyadı və adı yazın (ata adı da tövsiyə olunur).')}</p>}
      {similar && <div className="confirm" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
        <b>{t('Oxşar şagird artıq var')}</b>
        {similar.map(s => <div key={s.id} className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <span className="grow">{s.full_name} · <span className="muted">{s.class_name}</span></span>
          {s.class_id !== classId && <AsyncBtn className="btn sm primary" ok="Şagird bu sinfə əlavə sinif kimi əlavə olundu" onClick={async () => {
            await post(`/api/classes/${classId}/members/add`, { student_ids: [s.id] }); setSimilar(null); setF({ full_name: '', birth_date: '', gender: '' }); onDone({ id: s.id, full_name: s.full_name })
          }}>{t('Onu bu sinfə əlavə sinif kimi əlavə et')}</AsyncBtn>}
        </div>)}
        <div className="row" style={{ gap: 8 }}><AsyncBtn className="btn sm" onClick={() => submit(true)}>{t('Bu başqa şagirddir')}</AsyncBtn>
          <button className="btn sm ghost" onClick={() => setSimilar(null)}>{t('Ləğv et')}</button></div></div>}
      {dupArch && <div className="confirm"><span className="grow">{dupArch.message}</span>
        <AsyncBtn className="btn sm primary" ok="Şagird geri qaytarıldı" onClick={async () => {
          await post(`/api/students/${dupArch.id}/restore`); setDupArch(null); setErr(undefined); onDone({ id: dupArch.id, full_name: f.full_name.trim() })
        }}>{t('Arxivdən geri qaytar')}</AsyncBtn></div>}
      <AsyncBtn className="btn primary" disabled={words < 2 || f.full_name.trim().length < 5} onClick={() => submit(false)}>{t('Şagirdi əlavə et')}</AsyncBtn>
      {made && <div className="banner" style={{ background: 'var(--ok-soft)', color: 'var(--ok)', flexWrap: 'wrap' }}>
        <span className="grow">✓ <b>{made.full_name}</b> {t('əlavə olundu · ID')} <b className="mono">{made.portal_code}</b>{made.initial_pin && <> {t('· PIN')} <b className="mono">{made.initial_pin}</b> {t('(yazın – yalnız indi görünür)')}</>}</span>
        {made.initial_pin && <button className="btn sm" onClick={async () => printDoc({ title: `${made.full_name} – giriş vərəqəsi`,
          body: await sheetBody({ class_name: className || '', students: [{ full_name: made.full_name, portal_code: made.portal_code, pin: made.initial_pin }] }) })}>{t('Giriş vərəqəsini çap et')}</button>}
        <span className="small" style={{ flexBasis: '100%' }}>{t('Növbəti şagirdi yaza bilərsiniz.')}</span></div>}
      <p className="small muted" style={{ margin: 0 }}>{t('Uşaq İD, pinkod və şəxsiyyət vəsiqəsi daxil edilmir. Eyni ad + doğum tarixi ikinci dəfə yaradılmır.')}</p>
    </div>
  )
}

type Member = { id: number; full_name: string; class_id: number; class_name: string }

/** Tədris qrupu: üzvlər məktəbin istənilən sinfindən seçilir (sinif seç → işarələ). */
function StudyMembers({ cls, all, onClose }: { cls: Cls; all: Cls[]; onClose: () => void }) {
  const t = useT()
  const [sel, setSel] = useState<Map<number, Member>>(new Map())
  const [src, setSrc] = useState<number | null>(null)
  const [q, setQ] = useState('')
  const [err, setErr] = useState<unknown>()
  useEffect(() => { get<Member[]>(`/api/classes/${cls.id}/members/detail`).then(x => setSel(new Map(x.map(m => [m.id, m]))), setErr) }, [cls.id])
  const [cand] = useLoad<Member[] | null>(() => (src ? get(`/api/classes/${cls.id}/candidates`, { class_id: src }) : Promise.resolve(null)), [src])
  const toggle = (m: Member) => { const n = new Map(sel); n.has(m.id) ? n.delete(m.id) : n.set(m.id, m); setSel(n) }
  const list = (cand || []).filter(s => !q || s.full_name.toLowerCase().includes(q.toLowerCase()))
  const byClass = [...sel.values()].sort((a, b) => a.class_name.localeCompare(b.class_name) || a.full_name.localeCompare(b.full_name))
  return (
    <Drawer title={t('{name} – üzvlər', { name: cls.name })} onClose={onClose}
      footer={<><span className="small muted grow">{t('Seçilib:')} {sel.size}</span>
        <AsyncBtn className="btn primary" ok="Üzvlər yadda saxlanıldı" onClick={async () => { await put(`/api/classes/${cls.id}/members`, { student_ids: [...sel.keys()] }); onClose() }}>{t('Yadda saxla')}</AsyncBtn></>}>
      <div className="stack">
        <ErrorBox error={err} />
        <p className="small muted" style={{ margin: 0 }}>{t('Sinfi seçin və şagirdləri işarələyin – bir neçə sinifdən yığmaq olar. Şagird öz sinfində qalır, qrupa yalnız üzv olur.')}</p>
        <div className="toolbar">
          <select className="sel" value={src ?? ''} onChange={e => setSrc(e.target.value ? Number(e.target.value) : null)} aria-label={t('Sinif')}>
            <option value="">{t('— sinif seçin —')}</option>{all.filter(c => c.kind !== 'qrup').map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          {cand && <div className="search"><input placeholder={t('Axtar')} value={q} onChange={e => setQ(e.target.value)} /></div>}
          {cand && cand.length > 0 && <button className="btn sm" onClick={() => { const n = new Map(sel); list.forEach(m => n.set(m.id, m)); setSel(n) }}>{t('Hamısını seç')}</button>}
        </div>
        {cand && <div className="jlist">{list.map(s => (
          <label key={s.id} className="check jrow" style={{ gridTemplateColumns: 'auto minmax(0,1fr)' }}>
            <input type="checkbox" checked={sel.has(s.id)} onChange={() => toggle(s)} /><span>{s.full_name}</span></label>))}
          {cand.length === 0 && <div className="empty">{t('Sinifdə şagird yoxdur.')}</div>}</div>}
        <h3 className="small muted" style={{ margin: '8px 0 0' }}>{t('Qrupun üzvləri (')}{sel.size})</h3>
        <div className="jlist">{byClass.map(m => (
          <div key={m.id} className="jrow" style={{ gridTemplateColumns: 'minmax(0,1fr) auto auto' }}>
            <span>{m.full_name}</span><Pill>{m.class_name}</Pill>
            <button className="btn sm ghost" aria-label={`${m.full_name} – çıxar`} onClick={() => toggle(m)}>{t('Çıxar')}</button></div>))}
          {sel.size === 0 && <div className="empty">{t('Hələ üzv yoxdur.')}</div>}</div>
      </div>
    </Drawer>
  )
}

function SplitForm({ parent, onClose, onDone }: { parent: Cls; onClose: () => void; onDone: () => void }) {
  const t = useT()
  const [subject, setSubject] = useState('riyaziyyat')
  const [other, setOther] = useState('Biologiya')
  const [err, setErr] = useState<unknown>()
  return (
    <Drawer title={t('{name} – bölünmə yarat', { name: parent.name })} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button><button className="btn primary" disabled={!subject || !other} onClick={async () => {
        try {
          await post('/api/classes', { name: `${parent.name} (${subject} qrupu)`, kind: 'qrup', parent_id: parent.id, split_with: other })
          toast(t('Qrup yaradıldı – indi «Qoşul» ilə cədvəli, «Bölünmə» ilə şagirdləri seçin')); onDone()
        } catch (e) { setErr(e) }
      }}>{t('Yarat')}</button></>}>
      <div className="stack">
        <p className="small muted">{t('Sinif bəzi saatlarda iki qrupa bölünür: bir qrup sizin fənninizə, digəri paralel fənnə gedir. Şagirdləri sonra özünüz seçəcəksiniz.')}</p>
        <Field label={t('Sizin qrupun fənni')}><input value={subject} onChange={e => setSubject(e.target.value)} /></Field>
        <Field label={t('Paralel fənn (və müəllimi)')}><input value={other} onChange={e => setOther(e.target.value)} placeholder={t('Biologiya – Şərqiyə müəllimə')} /></Field>
        <ErrorBox error={err} />
      </div>
    </Drawer>
  )
}

// ---------------------------------------------------------------- şagirdlər
function StudentsTab() {
  const t = useT()
  const { me } = useAuth()
  const [classes] = useLoad<Cls[]>(() => get('/api/classes'), [])
  const [cid, setCid] = useState<number | null>(null)
  const [rows, err, , reload] = useLoad<Stud[] | null>(() => (cid ? get('/api/students', { class_id: cid }) : Promise.resolve(null)), [cid])
  const [edit, setEdit] = useState<Stud | 'new' | null>(null)
  const [pin, setPin] = useState<{ code: string; pin: string; name: string } | null>(null)
  const [scores, setScores] = useState(false)
  const openable = (classes || []).filter(c => c.can_open && c.kind !== 'qrup')
  return (
    <>
      <div className="toolbar">
        <select className="sel" value={cid ?? ''} onChange={e => setCid(e.target.value ? Number(e.target.value) : null)}>
          <option value="">{t('— sinif seçin —')}</option>{openable.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        {cid && <button className="btn primary" onClick={() => setEdit('new')}>{t('+ Şagird')}</button>}
        {cid && <SlipsButton cid={cid} />}
        {cid && <button className="btn" aria-pressed={scores} onClick={() => setScores(!scores)}>{scores ? t('Siyahıya qayıt') : t('IX buraxılış ballarını redaktə et')}</button>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}><AllSlipsButton />
        <span className="small muted">{t('Şagirdin ID və PIN-ini dəyişmək: sinfi seçin → şagirdi açın → «Giriş məlumatları».')}</span></div>
      {me?.role === 'admin' && <RosterImport onDone={reload} />}
      <ErrorBox error={err} />
      {!cid ? <PickFirst /> : scores ? <ScoresEditor rows={rows || []} onDone={() => { reload(); setScores(false) }} /> : (
        <div className="jlist">
          {(rows || []).map(s => (
            <div className="jrow" key={s.id}>
              <span><b>{s.full_name}</b><span className="sub small muted"> {fmtDate(s.birth_date)} {t('· IX riyaziyyat')} {fmt(s.score_math)}</span></span>
              <span className="mono small">{s.portal_code}</span>
              <span className="row"><button className="btn sm" onClick={() => setEdit(s)}>{t('Redaktə')}</button>
                <AsyncBtn className="btn sm" onClick={async () => { const r = await post(`/api/students/${s.id}/reset-pin`); setPin({ code: r.portal_code, pin: r.pin, name: s.full_name }) }}>{t('Yeni PIN')}</AsyncBtn></span>
            </div>))}
          {rows?.length === 0 && <div className="empty">{t('Sinifdə şagird yoxdur.')}</div>}
        </div>)}
      {edit && cid && <StudentForm s={edit === 'new' ? null : edit} classId={cid} classes={openable} onClose={() => setEdit(null)}
        onDone={(p) => { setEdit(null); reload(); if (p) setPin(p) }} />}
      {pin && (
        <Drawer title={t('Giriş məlumatı')} onClose={() => setPin(null)}>
          <p><b>{pin.name}</b></p>
          <dl className="kv"><dt>{t('Giriş kodu')}</dt><dd className="mono">{pin.code}</dd><dt>{t('PIN')}</dt><dd className="mono" style={{ fontSize: 24 }}>{pin.pin}</dd></dl>
          <p className="small muted" style={{ marginTop: 12 }}>{t('PIN yalnız indi göstərilir – yazın və şagirdə verin. Şagird PIN-i sonra özü dəyişə bilər.')}</p>
        </Drawer>)}
    </>
  )
}

type Sheet = { class_name: string; students: { full_name: string; portal_code: string; pin: string | null; qr?: string | null }[] }

/** QR kod (SVG): telefon kamerası ilə oxunur → /q/<token> → avtomatik giriş (kod və PIN yazmadan). */
async function qrSvg(token: string): Promise<string> {
  const QR = await import('qrcode')
  return QR.toString(`${location.origin}/q/${token}`, { type: 'svg', margin: 0, errorCorrectionLevel: 'M' })
}

/** Bir sinfin giriş vərəqələri (kəsilən kartlar, QR ilə) + müəllim nüsxəsi (cədvəl). */
async function sheetBody(sheet: Sheet): Promise<string> {
  const site = location.origin
  const qrs = await Promise.all(sheet.students.map(x => (x.qr ? qrSvg(x.qr) : Promise.resolve(''))))
  const slips = sheet.students.map((x, i) => `<div class="slip" style="display:flex;gap:4mm;align-items:center">
    <div style="flex:1;min-width:0"><div class="n">${esc(x.full_name)} <span class="muted">· ${esc(sheet.class_name)}</span></div>
    <div class="k">ID: ${esc(x.portal_code)} &nbsp; PIN: ${esc(x.pin ?? '— (şagird bilir)')}</div>
    <div class="muted">${qrs[i] ? 'Telefonun kamerasını QR-a tutun – avtomatik daxil olursunuz. Və ya: ' : ''}${esc(site)} → «Şagird» → ID və PIN.</div></div>
    ${qrs[i] ? `<div style="width:24mm;height:24mm;flex:none">${qrs[i].replace('<svg ', '<svg style="width:24mm;height:24mm" ')}</div>` : ''}</div>`).join('')
  return head(`${sheet.class_name} sinfi – Müəllim köməkçisi: giriş vərəqələri`, 'Kəsib hər şagirdə öz vərəqəsini verin') + `<div class="slips">${slips}</div>` +
    `<div class="pb"></div>` + head(`${sheet.class_name} – giriş kodları (müəllim nüsxəsi)`) +
    table(['№', 'Şagird', 'ID (giriş kodu)', 'PIN'], sheet.students.map((x, i) => [i + 1, x.full_name, x.portal_code, x.pin ?? 'şagird bilir / dəyişib']))
}

/** Bütün siniflərim üçün bir sənəd: PIN-i heç kimə məlum olmayanlara PIN avtomatik yaradılır, hər sinif ayrı səhifədə. */
function AllSlipsButton() {
  const t = useT()
  const [info, setInfo] = useState<string | null>(null)
  return (
    <span className="row">
      <AsyncBtn className="btn primary" onClick={async () => {
        const r = await post<{ classes: Sheet[]; new_pins: number }>('/api/students/login-sheets')
        if (!r.classes.length) { setInfo(t('Siniflərinizdə şagird yoxdur.')); return }
        setInfo(t('{length} sinif, {x2} şagird', { length: r.classes.length, x2: r.classes.reduce((a, c) => a + c.students.length, 0) }) + (r.new_pins ? (' · ' + t('{new_pins} şagirdə yeni PIN verildi', { new_pins: r.new_pins })) : ''))
        printDoc({ title: 'Giriş vərəqələri – bütün siniflər', body: (await Promise.all(r.classes.map(sheetBody))).join('<div class="pb"></div>') })
      }}>{t('Giriş vərəqələri – bütün siniflər (ID + PIN)')}</AsyncBtn>
      {info && <span className="small muted">{info}</span>}
    </span>
  )
}

function SlipsButton({ cid }: { cid: number }) {
  const t = useT()
  const [missing, setMissing] = useState<number | null>(null)
  const print = async (sheet: Sheet) => printDoc({ title: `${sheet.class_name} – giriş vərəqələri`, body: await sheetBody(sheet) })
  const run = async () => {
    const sheet = await get(`/api/students/by-class/${cid}/login-sheet`)
    const n = sheet.students.filter((x: any) => !x.pin).length
    if (n) { setMissing(n); return }
    print(sheet)
  }
  const regen = async (all: boolean) => {
    await post(`/api/students/by-class/${cid}/reset-pins${all ? '' : '?only_missing=true'}`)
    setMissing(null)
    print(await get(`/api/students/by-class/${cid}/login-sheet`))
  }
  return missing ? (
    <span className="confirm" style={{ width: 'auto' }}>{missing} {t('şagirdin ilkin PIN-i yoxdur (şagird dəyişib və ya köhnə qeyddir).')}
      <AsyncBtn className="btn sm primary" onClick={() => regen(false)}>{t('Yalnız onlara yeni PIN')}</AsyncBtn>
      <AsyncBtn className="btn sm" onClick={async () => { setMissing(null); print(await get(`/api/students/by-class/${cid}/login-sheet`)) }}>{t('Olduğu kimi çap et')}</AsyncBtn>
      <button className="btn ghost sm" onClick={() => setMissing(null)}>{t('Ləğv et')}</button></span>
  ) : <AsyncBtn className="btn" onClick={run}>{t('Giriş vərəqələri (ID + PIN) – çap / PDF')}</AsyncBtn>
}

function ScoresEditor({ rows, onDone }: { rows: Stud[]; onDone: () => void }) {
  const t = useT()
  type V = { l: string; m: string; f: string }
  const init = (s: Stud): V => ({ l: s.score_language == null ? '' : String(s.score_language), m: s.score_math == null ? '' : String(s.score_math), f: s.score_foreign == null ? '' : String(s.score_foreign) })
  const [vals, setVals] = useState<Record<number, V>>(() => Object.fromEntries(rows.map(s => [s.id, init(s)])))
  const num = (v: string) => (v.trim() === '' ? null : Number(v.replace(',', '.')))
  const bad = (v: string) => v.trim() !== '' && (isNaN(num(v)!) || num(v)! < 0 || num(v)! > 100)
  const changed = rows.filter(s => JSON.stringify(vals[s.id]) !== JSON.stringify(init(s)))
  const invalid = Object.values(vals).some(v => bad(v.l) || bad(v.m) || bad(v.f))
  const set = (id: number, k: keyof V, v: string) => setVals({ ...vals, [id]: { ...vals[id], [k]: v } })
  return (
    <>
      <p className="small muted">{t('IX sinif buraxılış imtahanı balları (0–100). Boş – bal yoxdur. Riyaziyyat balı şagirdin ilkin səviyyəsini müəyyən edir.')}</p>
      <div className="tbl-wrap"><table style={{ minWidth: 560 }}>
        <thead><tr><th>{t('Şagird')}</th><th className="r">{t('Tədris dili')}</th><th className="r">{t('Riyaziyyat')}</th><th className="r">{t('Xarici dil')}</th><th className="r">{t('Yekun')}</th></tr></thead>
        <tbody>{rows.map(s => { const v = vals[s.id]; const tot = [v.l, v.m, v.f].every(x => x.trim() !== '' && !bad(x)) ? (num(v.l)! + num(v.m)! + num(v.f)!).toFixed(1).replace('.', ',') : '—'
          return (
            <tr key={s.id}><td>{s.full_name}</td>
              {(['l', 'm', 'f'] as const).map(k => <td key={k} className="r"><input className="sel" inputMode="decimal" style={{ width: 86, textAlign: 'right', borderColor: bad(v[k]) ? 'var(--bad)' : undefined }} value={v[k]} onChange={e => set(s.id, k, e.target.value)} aria-label={s.full_name + ' ' + k} /></td>)}
              <td className="r num">{tot}</td></tr>) })}</tbody></table></div>
      <div className="row" style={{ marginTop: 12 }}>
        <span className="small muted">{changed.length} {t('şagird dəyişib')}</span>
        <AsyncBtn className="btn primary right" disabled={!changed.length || invalid} ok="Ballar yadda saxlanıldı" onClick={async () => {
          for (const s of changed) { const v = vals[s.id]; await patch(`/api/students/${s.id}`, { score_language: num(v.l), score_math: num(v.m), score_foreign: num(v.f) }) }
          onDone()
        }}>{t('Yadda saxla')}</AsyncBtn>
      </div>
    </>
  )
}

/** Şagirdin giriş məlumatları: ID (giriş kodu) və PIN – müəllim özü yazır və ya təsadüfi yaradır. */
function LoginFields({ s, onChanged }: { s: Stud; onChanged: () => void }) {
  const t = useT()
  const [code, setCode] = useState(s.portal_code)
  const [pin, setPin] = useState('')
  const [shown, setShown] = useState<string | null>(null)
  const setPinReq = async (value: string | null) => {
    const r = await post(`/api/students/${s.id}/reset-pin`, value ? { pin: value } : {})
    setShown(r.pin); setPin('')
  }
  return (
    <fieldset><legend>{t('Giriş məlumatları')}</legend>
      <div className="fg">
        <Field label={t('Giriş kodu (ID)')} hint="hərf, rəqəm, «-»">
          <span className="row" style={{ flexWrap: 'nowrap' }}><input value={code} maxLength={16} onChange={e => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ''))} />
            <AsyncBtn className="btn sm" disabled={code === s.portal_code || code.length < 3} ok="Giriş kodu dəyişdi"
              onClick={async () => { await patch(`/api/students/${s.id}`, { portal_code: code }); onChanged() }}>{t('Saxla')}</AsyncBtn></span></Field>
        <Field label={t('Yeni PIN')} hint="4 rəqəm; boş – təsadüfi">
          <span className="row" style={{ flexWrap: 'nowrap' }}><input inputMode="numeric" value={pin} maxLength={4} placeholder="••••" onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))} />
            <AsyncBtn className="btn sm" disabled={pin.length > 0 && pin.length < 4} onClick={() => setPinReq(pin || null)}>{pin ? t('Təyin et') : t('Təsadüfi')}</AsyncBtn></span></Field>
      </div>
      {shown && <p className="small" style={{ margin: '6px 0 0' }}>{t('Yeni PIN:')} <b style={{ fontFamily: 'monospace', fontSize: 16 }}>{shown}</b> {t('– giriş vərəqəsində də çap olunacaq. Şagirdin köhnə PIN-i artıq işləmir.')}</p>}
      <p className="small muted" style={{ margin: '6px 0 0' }}>{t('Kod dəyişəndə şagird yeni kodla daxil olur (köhnə kod işləmir).')}</p>
    </fieldset>
  )
}

function StudentForm({ s, classId, classes, onClose, onDone }: { s: Stud | null; classId: number; classes: Cls[]; onClose: () => void; onDone: (pin?: { code: string; pin: string; name: string }) => void }) {
  const t = useT()
  const [f, setF] = useState({ full_name: s?.full_name || '', class_id: s?.class_id || classId, birth_date: s?.birth_date || '', gender: s?.gender || '',
    score_language: s?.score_language ?? '', score_math: s?.score_math ?? '', score_foreign: s?.score_foreign ?? '' })
  const [err, setErr] = useState<unknown>()
  const [confirm, setConfirm] = useState(false)
  const num = (v: any) => (v === '' || v == null ? null : Number(String(v).replace(',', '.')))
  const save = async () => {
    try {
      const body = { full_name: f.full_name, class_id: Number(f.class_id), birth_date: f.birth_date || null, gender: f.gender || null,
        score_language: num(f.score_language), score_math: num(f.score_math), score_foreign: num(f.score_foreign) }
      if (s) { await patch(`/api/students/${s.id}`, body); toast('Yadda saxlanıldı'); onDone() }
      else { const r = await post('/api/students', body); onDone({ code: r.portal_code, pin: r.initial_pin, name: r.full_name }) }
    } catch (e) { setErr(e) }
  }
  return (
    <Drawer title={s ? s.full_name : t('Yeni şagird')} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>{t('Ləğv et')}</button><button className="btn primary" disabled={f.full_name.trim().length < 5} onClick={save}>{t('Yadda saxla')}</button></>}>
      <div className="stack">
        <div className="fg">
          <Field label={t('Soyadı, adı, ata adı')} full><input value={f.full_name} onChange={e => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field label={t('Sinif')}><select value={f.class_id} onChange={e => setF({ ...f, class_id: Number(e.target.value) })}>{classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label={t('Doğum tarixi')}><input type="date" value={f.birth_date} onChange={e => setF({ ...f, birth_date: e.target.value })} /></Field>
          <Field label={t('Cins')}><select value={f.gender} onChange={e => setF({ ...f, gender: e.target.value })}><option value="">—</option><option value="Qız">{t('Qız')}</option><option value="Oğlan">{t('Oğlan')}</option></select></Field>
          <Field label={t('IX: Tədris dili')}><input inputMode="decimal" value={f.score_language} onChange={e => setF({ ...f, score_language: e.target.value })} /></Field>
          <Field label={t('IX: Riyaziyyat')}><input inputMode="decimal" value={f.score_math} onChange={e => setF({ ...f, score_math: e.target.value })} /></Field>
          <Field label={t('IX: Xarici dil')}><input inputMode="decimal" value={f.score_foreign} onChange={e => setF({ ...f, score_foreign: e.target.value })} /></Field>
        </div>
        <p className="small muted">{t('Uşaq İD, pinkod və şəxsiyyət vəsiqəsi daxil edilmir və saxlanmır.')}</p>
        {s && <LoginFields s={s} onChanged={() => onDone()} />}
        <ErrorBox error={err} />
        {s && (confirm
          ? <Leave s={s} onCancel={() => setConfirm(false)} onDone={onDone} />
          : <button className="btn danger" onClick={() => setConfirm(true)}>{t('Məktəbdən getdi – passiv et')}</button>)}
      </div>
    </Drawer>
  )
}

function RosterImport({ onDone }: { onDone: () => void }) {
  const t = useT()
  const [utis, setUtis] = useState<File | null>(null)
  const [dim, setDim] = useState<File | null>(null)
  const [res, setRes] = useState<any>(null)
  const csv = () => {
    const rows = [['Sinif', 'Ad', 'Giriş kodu', 'PIN'], ...res.added.map((r: any) => [r.class_name, r.full_name, r.portal_code, r.pin])]
    const blob = new Blob(['﻿' + rows.map(r => r.join(';')).join(String.fromCharCode(10))], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'giris_kodlari.csv'; a.click()
  }
  return (
    <Disclosure icon="classes" style={{ marginBottom: 14 }} title={t('UTİS siyahısından şagird idxalı (admin)')}>
      <div className="stack" style={{ marginTop: 10 }}>
        <p className="small muted">{t('Siniflər «UTİS sinfi» sahəsinə görə uyğunlaşdırılır (məs. X e = 10 e). Uşaq İD, şəxsiyyət vəsiqəsi, pinkod saxlanmır; mövcud şagirdlər təkrarlanmır.')}</p>
        <label className="f">{t('UTİS faylı (.xlsx və ya .pdf)')}<input type="file" accept=".xlsx,.pdf" onChange={e => setUtis(e.target.files?.[0] || null)} /></label>
        <label className="f">{t('DİM buraxılış balları (.xlsx, istəyə görə)')}<input type="file" accept=".xlsx" onChange={e => setDim(e.target.files?.[0] || null)} /></label>
        <AsyncBtn className="btn primary" disabled={!utis} onClick={async () => {
          const fd = new FormData(); fd.append('utis', utis!); if (dim) fd.append('dim', dim)
          const r = await api('/api/import/roster', { method: 'POST', form: fd }); setRes(r); onDone()
          toast(t('{length} şagird əlavə olundu', { length: r.added.length }))
        }}>{t('İdxal et')}</AsyncBtn>
        {res && (<>
          <p className="small">{t('Uyğunlaşdırılan siniflər:')} <b>{res.matched_classes.join(', ') || '—'}</b> {t('· əlavə:')} <b>{res.added.length}</b>{res.without_scores ? (' · ' + t('balı olmayan: {without_scores}', { without_scores: res.without_scores })) : ''}</p>
          {res.added.length > 0 && <><button className="btn" onClick={csv}>{t('Giriş kodları və PIN-lər (CSV)')}</button>
            <p className="small muted">{t('PIN-lər yalnız indi göstərilir – faylı yükləyin, çap edib paylayın.')}</p></>}
        </>)}
      </div>
    </Disclosure>
  )
}

const LEAVE_REASONS = ['Başqa məktəbə köçdü', 'Başqa şəhərə / rayona köçdü', 'Xaricə getdi', 'Təhsilini dayandırdı', 'Səhv əlavə olunub', 'Digər']

/** Məktəbdən gedən şagird: passiv olur (qiymətləri, jurnal tarixçəsi qalır, portala giriş bağlanır). Geri qaytarmaq və ya silmək – «Arxiv»də. */
function Leave({ s, onCancel, onDone }: { s: Stud; onCancel: () => void; onDone: () => void }) {
  const t = useT()
  const [reason, setReason] = useState(LEAVE_REASONS[0])
  const [note, setNote] = useState('')
  const [date, setDate] = useState(isoDate(new Date()))
  return (
    <div className="panel" style={{ margin: 0, borderColor: 'var(--bad-soft)' }}>
      <b>{t('Məktəbdən getdi – passiv et')}</b>
      <p className="small muted" style={{ margin: '4px 0 10px' }}>{t('Şagird siyahılardan, jurnaldan və portaldan çıxır; qiymətləri və tarixçəsi silinmir. «Arxiv» bölməsindən geri qaytarmaq və ya həmişəlik silmək olar.')}</p>
      <div className="fg">
        <Field label={t('Səbəb')}><select value={reason} onChange={e => setReason(e.target.value)}>{LEAVE_REASONS.map(r => <option key={r} value={r}>{t(r)}</option>)}</select></Field>
        <Field label={t('Getdiyi tarix')}><input type="date" value={date} onChange={e => setDate(e.target.value)} /></Field>
        <Field label={t('Qeyd (istəyə görə)')} full><input value={note} maxLength={200} placeholder={t('məs. Bərdə şəhər 2 nömrəli məktəb')} onChange={e => setNote(e.target.value)} /></Field>
      </div>
      <ConfirmName name={s.full_name} action="Passiv et" onCancel={onCancel}
        onConfirm={async typed => {
          await post(`/api/students/${s.id}/archive`, { confirm: typed, reason: note.trim() ? `${reason}: ${note.trim()}` : reason, left_on: date || null })
          toast(t('Şagird passiv edildi (Arxiv)')); onDone()
        }} />
    </div>
  )
}

// ---------------------------------------------------------------- arxiv
function ArchiveTab() {
  const t = useT()
  const [classes, e1, , r1] = useLoad<Cls[]>(() => get('/api/classes', { archived: true }), [])
  const [studs, e2, , r2] = useLoad<Stud[]>(() => get('/api/students', { archived: true }), [])
  const [confirm, setConfirm] = useState<string | null>(null)
  const reload = () => { r1(); r2(); setConfirm(null) }
  return (
    <div className="stack">
      <ErrorBox error={e1 || e2} />
      <h2 className="sec">{t('Siniflər')}</h2>
      <div className="jlist">{(classes || []).map(c => (
        <div className="jrow cols" key={c.id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8 }}>
          <div className="row"><b className="grow">{c.name}</b>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/classes/${c.id}/restore`); reload() }}>{t('Geri qaytar')}</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('c' + c.id)}>{t('Həmişəlik sil')}</button></div>
          {confirm === 'c' + c.id && <ConfirmName name={c.name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/classes/${c.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {classes?.length === 0 && <div className="empty">{t('Arxivdə sinif yoxdur.')}</div>}</div>
      <h2 className="sec">{t('Şagirdlər')}</h2>
      <div className="jlist">{(studs || []).map(s => (
        <div className="jrow cols" key={s.id} style={{ ['--cols' as any]: '1fr', ['--mcols' as any]: '1fr', gap: 8 }}>
          <div className="row"><span className="grow"><b>{s.full_name}</b><span className="small muted"> · {s.class_name}</span>
            {(s.left_reason || s.left_on) && <span className="small muted" style={{ display: 'block' }}>{t('Passiv')}{s.left_on ? ` ${fmtDate(s.left_on)}` : ''}{s.left_reason ? ` – ${s.left_reason}` : ''}</span>}</span>
            <AsyncBtn className="btn sm" ok="Geri qaytarıldı" onClick={async () => { await post(`/api/students/${s.id}/restore`); reload() }}>{t('Geri qaytar')}</AsyncBtn>
            <button className="btn sm danger" onClick={() => setConfirm('s' + s.id)}>{t('Həmişəlik sil')}</button></div>
          {confirm === 's' + s.id && <ConfirmName name={s.full_name} action="Həmişəlik sil" onCancel={() => setConfirm(null)} onConfirm={async typed => { await del(`/api/students/${s.id}`, { confirm: typed }); toast('Silindi'); reload() }} />}
        </div>))}
        {studs?.length === 0 && <div className="empty">{t('Arxivdə şagird yoxdur.')}</div>}</div>
    </div>
  )
}
