// «Bələdçi»: yuxarıda tanıtım videosu (iri kart), aşağıda hər ssenari = kart (poster, müddət, alt yazı tətbiqin dilində) + addım-addım mətn.
// Video faylı yoxdursa (və ya brauzer aça bilmirsə) bölmə yalnız addımlarla göstərilir – səhv deyil.
// Videolar: backend/scripts/guide_videos.py ilə yazılır -> frontend/public/guide/{student|teacher}/NN-ad.az.mp4 / NN-ad.ru.mp4 (+ .jpg poster, .vtt alt yazı)
import { useContext } from 'react'
import { useAuth } from '../auth'
import { GuideButton } from '../GuideModal'
import { fmtDur, GuidePlayer } from '../GuidePlayer'
import { GUIDE, type GuideItem } from '../guideData'
import { I18nCtx, useT } from '../i18n'
import { Top } from '../ui'

function Scenario({ g, hero }: { g: GuideItem; hero?: boolean }) {
  const t = useT()
  const lang = useContext(I18nCtx)
  const dur = fmtDur(g.duration?.[lang] ?? g.duration?.az)
  return (
    <section className={'panel gcard' + (hero ? ' gc-hero' : '')} style={{ marginBottom: 16 }} id={g.id}>
      <GuidePlayer role={g.role} id={g.id} maxHeight={hero ? '66vh' : '46vh'} />
      <div className="gc-body">
        {hero && <span className="gc-badge">{t('Tanıtım videosu')}</span>}
        <h2>{t(g.title)}{dur && <span className="gc-dur">{dur}</span>}</h2>
        <h3 style={{ font: '600 13px/1.3 var(--f-body)', margin: '0 0 6px' }}>{t('Addımlar')}</h3>
        <ol style={{ margin: 0, paddingLeft: 20 }}>{g.steps.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{t(s)}</li>)}</ol>
      </div>
    </section>)
}

export default function Guide() {
  const { me } = useAuth()
  const t = useT()
  const role = me?.role === 'student' ? 'student' : 'teacher'
  const list = GUIDE.filter(g => g.role === role)
  const intro = list.find(g => g.id === '00-tanitim')
  const rest = list.filter(g => g.id !== '00-tanitim')
  return (
    <>
      <Top title="Video bələdçi" sub="Tətbiqdən necə istifadə etmək – qısa videolar və addım-addım izah" />
      <GuideButton />
      <h2 className="small muted" style={{ margin: '0 0 10px', fontWeight: 600 }}>{role === 'student' ? t('Şagird üçün') : t('Müəllim üçün')}</h2>
      <div className="grid g2" style={{ alignItems: 'start' }}>
        {intro && <Scenario g={intro} hero />}
        {rest.map(g => <Scenario key={g.id} g={g} />)}
      </div>
    </>)
}
