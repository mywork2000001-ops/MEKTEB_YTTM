// Giriş vərəqəsindəki QR kod: kamera ilə açılan link (/q/<token>) şagirdi kod və PIN yazmadan daxil edir.
import { useEffect, useState } from 'react'
import { post } from '../api'

export default function QrLogin({ token }: { token: string }) {
  const [err, setErr] = useState('')
  useEffect(() => {
    post('/api/auth/qr', { token })
      .then(() => location.replace('/'))                       // tam yenilənmə – sessiya kukisi ilə açılır
      .catch(e => setErr(e?.message || 'QR kod işləmədi'))
  }, [token])
  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 16 }}>
      <div className="panel lockbox" style={{ width: 'min(400px,100%)', textAlign: 'center' }}>
        <span className="logo" style={{ margin: '0 auto 10px', width: 48, height: 48, fontSize: 22 }}>M</span>
        {!err ? <p>Daxil olunur…</p> : <>
          <p className="err" role="alert">{err}</p>
          <a className="btn primary" href="/">Kod və PIN ilə daxil ol</a>
        </>}
      </div>
    </div>
  )
}
