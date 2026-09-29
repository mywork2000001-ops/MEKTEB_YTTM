// Vahid çap / PDF modulu: A4, ağ-qara (Canon), rəsmi sənəd Azərbaycan dilində.
// printDoc() – yeni pəncərədə önbaxış + «Çap et» + «PDF yüklə» (PDF serverdə Chromium ilə hazırlanır).
import renderMathInElement from 'katex/contrib/auto-render'

export const esc = (s: unknown) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))
export const fmtN = (v: number | null | undefined, d = 1) => (v == null ? '—' : v.toFixed(d).replace('.', ','))
export const fmtD = (s?: string | null) => (s ? s.slice(0, 10).split('-').reverse().join('.') : '—')

export const SCHOOL = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi'

const CSS = `
@page{size:A4;margin:12mm}
*{box-sizing:border-box}
body{font:12px/1.4 "Times New Roman","Liberation Serif",serif;color:#000;background:#fff;margin:0}
h1{font-size:16px;text-align:center;margin:0 0 4px}
h2{font-size:14px;margin:14px 0 6px}
.sch{text-align:center;font-weight:700;margin:0 0 2px}
.sub{text-align:center;margin:0 0 12px}
table{border-collapse:collapse;width:100%;page-break-inside:auto}
tr{page-break-inside:avoid}
th,td{border:1px solid #000;padding:3px 5px;vertical-align:top}
th{background:#D9D9D9;font-weight:700}
.r{text-align:right}.c{text-align:center}.b{font-weight:700}.muted{color:#444}
.sign{margin-top:24px}
.slips{display:grid;grid-template-columns:1fr 1fr}
.slip{border:1px dashed #000;padding:7mm 5mm;page-break-inside:avoid}
.slip .n{font-weight:700;font-size:14px}.slip .k{font:700 17px "Courier New",monospace;margin:4px 0}
.q{margin:0 0 10px;page-break-inside:avoid}.q .opts{margin:4px 0 0 18px}
.q img{max-width:60%;max-height:60mm;display:block;margin:4px 0}
.pb{page-break-before:always}
@media screen{body{padding:12mm;max-width:210mm;margin:0 auto;box-shadow:0 0 0 1px #ddd}}
`

export type Doc = { title: string; body: string; landscape?: boolean }

export function docHtml(d: Doc): string {
  return `<!doctype html><html lang="az"><head><meta charset="utf-8"><title>${esc(d.title)}</title><style>${CSS}${d.landscape ? '@page{size:A4 landscape}' : ''}</style></head><body>${d.body}</body></html>`
}

/** Riyaziyyat mətnini ($…$, \(…\)) MathML-ə çevirir – çapda və serverdə (JS-siz) düzgün görünür. */
export function mathHtml(text: string): string {
  const el = document.createElement('span')
  el.textContent = text
  if (/[$]|\\[([]/.test(text)) {
    try {
      renderMathInElement(el, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false }, { left: '$', right: '$', display: false }], throwOnError: false, output: 'mathml' })
    } catch { /* xam mətn */ }
  }
  return el.innerHTML
}

export async function downloadPdf(d: Doc) {
  const r = await fetch('/api/print/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
    body: JSON.stringify({ html: docHtml(d), title: d.title, landscape: !!d.landscape }) })
  if (!r.ok) {
    let m = 'PDF hazırlanmadı'
    try { m = (await r.json()).detail || m } catch { /* noop */ }
    throw new Error(m)
  }
  const blob = await r.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = d.title.replace(/[\\/:*?"<>|]+/g, ' ').trim() + '.pdf'
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30_000)
}

/** Önbaxış pəncərəsi: sənəd + «Çap et» / «PDF yüklə» / «Bağla» (düymələr çapa düşmür). */
export function printDoc(d: Doc) {
  const w = window.open('', '_blank')
  if (!w) { alert('Pəncərə açılmadı – brauzerdə açılan pəncərələrə icazə verin'); return }
  fillPrint(w, d)
}

/** Məlumat serverdən sonra gəlirsə: pəncərəni KLİK anında açır (brauzer bloklamasın), sonra doldurur. */
export function printLater(): { show: (d: Doc) => void; fail: (msg: string) => void } | null {
  const w = window.open('', '_blank')
  if (!w) { alert('Pəncərə açılmadı – brauzerdə açılan pəncərələrə icazə verin'); return null }
  w.document.write('<p style="font:16px Arial,sans-serif;padding:24px">Sənəd hazırlanır…</p>')
  return { show: d => fillPrint(w, d), fail: msg => { w.document.body.innerHTML = `<p style="font:16px Arial,sans-serif;padding:24px">${esc(msg)}</p>` } }
}

function fillPrint(w: Window, d: Doc) {
  w.document.open()
  const bar = `<div id="mk-bar" style="position:sticky;top:0;background:#f3f4f6;border-bottom:1px solid #ccc;padding:8px;display:flex;gap:8px;font:14px Arial,sans-serif;z-index:9">
    <button id="mk-print" style="padding:8px 14px">Çap et</button><button id="mk-pdf" style="padding:8px 14px">PDF yüklə</button>
    <button id="mk-close" style="padding:8px 14px">Bağla</button><span id="mk-msg" style="align-self:center;color:#555"></span></div>
    <style>@media print{#mk-bar{display:none}}</style>`
  w.document.write(docHtml(d).replace('<body>', '<body>' + bar))
  w.document.close()
  const $ = (id: string) => w.document.getElementById(id) as HTMLButtonElement | null
  const msg = (t: string) => { const m = w.document.getElementById('mk-msg'); if (m) m.textContent = t }
  $('mk-print')!.onclick = () => w.print()                   // inline skript CSP ilə bloklanır – kənardan bağlanır
  $('mk-close')!.onclick = () => w.close()
  $('mk-pdf')!.onclick = async () => {
    msg('PDF hazırlanır…')
    try { await downloadPdf(d); msg('PDF yükləndi') } catch (e) { msg((e as Error).message) }
  }
}

/** Standart başlıq: məktəb, sənədin adı, alt sətir. */
export const head = (title: string, sub?: string) =>
  `<p class="sch">${esc(SCHOOL)}</p><h1>${esc(title)}</h1>${sub ? `<p class="sub">${esc(sub)}</p>` : ''}`

export const table = (heads: string[], rows: (string | number | null | undefined)[][], alignRight: number[] = []) =>
  `<table><thead><tr>${heads.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r =>
    `<tr>${r.map((v, i) => `<td class="${alignRight.includes(i) ? 'r' : ''}">${esc(v ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`
