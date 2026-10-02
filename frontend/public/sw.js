// Service worker: interfeys qabığı keşdə (tez və oflayn açılır); API – şəbəkə birinci, oflaynda son saxlanan cavab.
// Məxfilik: giriş, fayllar, test bazası və admin sorğuları keşə yazılmır; çıxışda API keşi silinir.
const SHELL = 'mk-shell-v3'
const API = 'mk-api-v1'
const NO_CACHE = /^\/api\/(auth\/(login|logout|password|prefs)|files|chat\/files|bank|admin|join|health)/

self.addEventListener('install', e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(['/', '/manifest.webmanifest', '/icon-192.png']))); self.skipWaiting() })
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== API).map(k => caches.delete(k)))))
  self.clients.claim()
})
self.addEventListener('message', e => { if (e.data === 'clear-api') caches.delete(API) })

self.addEventListener('fetch', e => {
  const u = new URL(e.request.url)
  if (e.request.method !== 'GET' || u.origin !== location.origin) return
  if (u.pathname.startsWith('/api/')) {
    if (NO_CACHE.test(u.pathname)) return
    e.respondWith(fetch(e.request).then(r => {
      if (r.ok) { const c = r.clone(); caches.open(API).then(x => x.put(e.request, c)) }
      return r
    }).catch(() => caches.match(e.request).then(hit => hit ? withHeader(hit) :
      new Response(JSON.stringify({ detail: 'Oflayn – bu məlumat hələ bu cihazda yüklənməyib' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))))
    return
  }
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(SHELL).then(x => x.put('/', c)); return r }).catch(() => caches.match('/')))
    return
  }
  if (u.pathname.startsWith('/assets/') || /\.(png|svg|webmanifest|woff2?)$/.test(u.pathname)) {
    e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(SHELL).then(x => x.put(e.request, c)) } return r })))
  }
})

// oflayn cavab işarəsi – interfeys «köhnə məlumat» göstərə bilsin
function withHeader(resp) {
  const h = new Headers(resp.headers)
  h.set('X-From-Cache', '1')
  return resp.blob().then(b => new Response(b, { status: resp.status, headers: h }))
}

// bildirişə toxunanda tətbiq açılır (açıqdırsa – həmin pəncərə) və bildirişin keçidinə gedir
self.addEventListener('notificationclick', e => {
  e.notification.close()
  const link = (e.notification.data && e.notification.data.link) || '/'
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => {
    const w = ws.find(x => new URL(x.url).origin === location.origin)
    if (w) return w.focus().then(() => w.navigate(link))
    return self.clients.openWindow(link)
  }))
})
