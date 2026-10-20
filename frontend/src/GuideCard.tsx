// İlk girişdə şagirdə bir dəfə: «Tətbiqlə tanış ol» kartı (bağlana bilər; localStorage – əlçatmazdırsa kart sadəcə hər dəfə görünmür/gizlənir).
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useT } from './i18n'
import { Icon } from './ui'

const KEY = 'mk-welcome-guide'
const seen = () => { try { return localStorage.getItem(KEY) === '1' } catch { return true } }
const mark = () => { try { localStorage.setItem(KEY, '1') } catch { /* yaddaş əlçatmazdır */ } }

export default function GuideCard() {
  const t = useT()
  const nav = useNavigate()
  const [show, setShow] = useState(() => !seen())
  if (!show) return null
  const close = () => { mark(); setShow(false) }
  return (
    <div className="banner" style={{ alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
      <Icon name="info" />
      <b style={{ flex: '1 1 220px' }}>{t('Tətbiqlə tanış ol – 3 dəqiqəlik video')}</b>
      <button type="button" className="btn primary" onClick={() => { mark(); nav('/guide') }}>{t('Videoya bax')}</button>
      <button type="button" className="btn" onClick={close}>{t('Bağla')}</button>
    </div>)
}
