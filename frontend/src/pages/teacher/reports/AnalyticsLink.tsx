// Əməliyyat səhifəsində qalan qısa keçid: «📊 Analitikada ətraflı →» (hesabat görünüşü «Analitika və hesabat»a köçürülüb).
import { useNavigate } from 'react-router-dom'
import { useT } from '../../../i18n'

export default function AnalyticsLink({ to, text }: { to: string; text?: string }) {
  const t = useT()
  const nav = useNavigate()
  return <button type="button" className="btn sm no-print" onClick={() => nav(to)}>📊 {t(text || 'Analitikada ətraflı')} →</button>
}
