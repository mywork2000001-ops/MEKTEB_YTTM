// KSQ/BSQ kağız variantları: hər şagirdə bir A4 vərəq (iki üz) + cavab kartı (docs/ksq-bsq-kagiz-promtu.md §3).
// Ön üz: başlıq + suallar 1–16; arxa üz: 17–30 + cavab kartı (4 küncdə marker, imzalı QR, test dairələri, açıq cavab xanaları).
// Sığmazsa şrift avtomatik kiçilir (açılan pəncərədə ölçülür). Rəsmi çap – başlıqlar AZ, suallar şagirdin dilində.
import QRCode from 'qrcode'
import { esc, fmtD, mathHtml } from './print'
import { toast } from './ui'

export type KsqQ = { slot: number; kind: 'mcq' | 'open'; points: number; text: string; options: string[] | null; image?: string | null }
export type KsqSheet = { student_id: number; full_name: string; code: string; lang: string; qr: string; questions: KsqQ[] }
export type KsqPrint = {
  exam: { id: number; kind: string; no: number; semester: number; date: string; class_name: string; subject: string; school: string; teacher: string }
  sheets: KsqSheet[]; key: { code: string; full_name: string; answers: { slot: number; value: string; points: number }[] }[]
}

const L = 'ABCDE'
const front = (n: number) => Math.ceil(n * 16 / 30)   // ön üzdə ~53% (30 sualda 1–16)
const CELLS = 8                     // açıq cavab xanaları (backend CARD_MAX)
const HELP: Record<string, string> = {
  az: 'Test (1–9): düzgün cavabın dairəsini tam qaralayın. Açıq (10–30): hər xanaya bir simvol, soldan: 0–9  -  ,  /  ;   Nümunə: 3/7 · 2,5 · -4 · 1;4',
  ru: 'Тест (1–9): полностью закрасьте кружок верного ответа. Открытые (10–30): по одному символу в клетку, слева: 0–9  -  ,  /  ;   Пример: 3/7 · 2,5 · -4 · 1;4',
  en: 'Test (1–9): fill the circle of the correct answer completely. Open (10–30): one character per box, from the left: 0–9  -  ,  /  ;   Example: 3/7 · 2,5 · -4 · 1;4',
}

const CSS = `
@page{size:A4;margin:8mm}
*{box-sizing:border-box}
body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#000;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.side{width:194mm;height:280mm;overflow:hidden;position:relative;display:flex;flex-direction:column;page-break-after:always;break-after:page}
.side:last-child{page-break-after:auto;break-after:auto}
@media screen{body{background:#e5e7eb;padding:8px}.side{background:#fff;margin:0 auto 10px;padding:0;box-shadow:0 0 0 1px #bbb}}
.hd{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.5px solid #000;padding-bottom:2mm;margin-bottom:2mm;font-size:9pt;gap:4mm}
.hd b.t{font-size:13pt}
.hd .nm{font-size:11pt;font-weight:700}
.qs{flex:1 1 0;min-height:0;column-count:2;column-gap:6mm;column-fill:balance;column-rule:.5px solid #bbb;font-size:10pt;line-height:1.28;overflow:hidden}
.q{break-inside:avoid;margin:0 0 2.2mm}
.q .n{font-weight:700}
.q .p{float:right;font-size:.8em;border:1px solid #000;border-radius:2mm;padding:0 1.2mm;margin-left:1.5mm}
.q ol{margin:.6mm 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.4mm 4mm}
.q img{max-width:100%;max-height:30mm;display:block;margin:1mm 0}
.card{position:relative;flex:0 0 auto;height:114mm;border-top:1.2px dashed #000;padding:8mm 10mm 5mm;margin-top:2mm}
.cut{position:absolute;top:-3mm;left:50%;transform:translateX(-50%);background:#fff;font-size:7pt;padding:0 2mm}
.mk{position:absolute;width:6mm;height:6mm;background:#000}
.ctop{display:flex;gap:4mm;align-items:flex-start;margin-bottom:2mm}
.ctop img{width:22mm;height:22mm}
.cinfo{font-size:9pt;line-height:1.35;flex:1}
.cinfo .nm{font-size:11.5pt;font-weight:700}
.help{font-size:7.5pt;margin-top:1mm;color:#222}
.mcq{display:grid;grid-template-columns:repeat(3,1fr);gap:1.6mm 6mm;margin-bottom:2.5mm}
.row{display:flex;align-items:center;gap:1.6mm;font-size:9pt}
.row .no{width:6mm;text-align:right;font-weight:700}
.bub{width:5mm;height:5mm;border:1.1px solid #000;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:6.5pt;color:#777}
.open{display:grid;grid-template-columns:repeat(3,1fr);gap:1.8mm 4mm}
.box{width:5.4mm;height:6mm;border:1.1px solid #000;display:inline-block;margin-left:-1.1px}
.box:first-of-type{margin-left:0}
.key table{border-collapse:collapse;width:100%;font-size:8.5pt;margin-bottom:5mm;break-inside:avoid}
.key td,.key th{border:1px solid #000;padding:.6mm 1mm;text-align:center}
.key th{background:#eee}
`

function question(q: KsqQ): string {
  const opts = q.kind === 'mcq' && q.options?.length
    ? `<ol>${q.options.map((o, i) => `<li><b>${L[i]})</b> ${mathHtml(o)}</li>`).join('')}</ol>` : ''
  const pts = String(q.points).replace('.', ',')
  return `<div class="q"><span class="p">${pts} b</span><span class="n">${q.slot}.</span> ${mathHtml(q.text)}${q.image ? `<img src="${esc(q.image)}" alt="">` : ''}${opts}</div>`
}

function card(s: KsqSheet, ex: KsqPrint['exam'], qr: string): string {
  const mcq = s.questions.filter(q => q.kind === 'mcq'), open = s.questions.filter(q => q.kind !== 'mcq')
  const mk = ['top:2mm;left:2mm', 'top:2mm;right:2mm', 'bottom:2mm;left:2mm', 'bottom:2mm;right:2mm'].map(p => `<i class="mk" style="${p}"></i>`).join('')
  return `<div class="card"><span class="cut">✂ CAVAB KARTI</span>${mk}
    <div class="ctop"><img src="${qr}" alt="">
      <div class="cinfo"><div class="nm">${esc(s.full_name)}</div>
        ${esc(ex.class_name)} · ${esc(ex.subject)} · <b>${ex.kind}-${ex.no}</b> · ${fmtD(ex.date)} · variant <b>${esc(s.code)}</b> · 100 bal
        <div class="help">${esc((HELP[s.lang] || HELP.az).replace('1–9', `1–${mcq.length}`).replace('10–30', `${mcq.length + 1}–${s.questions.length}`))}</div></div></div>
    <div class="mcq">${mcq.map(q => `<div class="row"><span class="no">${q.slot}</span>${[...L].map(c => `<span class="bub">${c}</span>`).join('')}</div>`).join('')}</div>
    <div class="open">${open.map(q => `<div class="row"><span class="no">${q.slot}</span><span>${'<span class="box"></span>'.repeat(CELLS)}</span></div>`).join('')}</div>
  </div>`
}

function sheet(s: KsqSheet, ex: KsqPrint['exam'], qr: string): string {
  const head = `<div class="hd"><div><b class="t">${ex.kind}-${ex.no}</b> · ${esc(ex.subject)} · ${esc(ex.class_name)} · ${fmtD(ex.date)}<br>${esc(ex.school)}</div>
    <div style="text-align:right"><span class="nm">${esc(s.full_name)}</span><br>variant <b>${esc(s.code)}</b> · ${s.questions.length} sual · 100 bal</div></div>`
  const F = front(s.questions.length)
  const fr = s.questions.filter(q => q.slot <= F), back = s.questions.filter(q => q.slot > F)
  return `<section class="side">${head}<div class="qs">${fr.map(question).join('')}</div></section>
    <section class="side"><div class="hd" style="font-size:8pt"><span>${esc(s.full_name)} · ${esc(s.code)}</span><span>${ex.kind}-${ex.no} · 2-ci üz</span></div>
      <div class="qs">${back.map(question).join('')}</div>${card(s, ex, qr)}</section>`
}

/** Sütunlara sığmayanda (əlavə sütun / aşağı daşma) şrift 10 pt-dən 7 pt-yə qədər kiçilir. */
function fit(doc: Document) {
  doc.querySelectorAll<HTMLElement>('.qs').forEach(el => {
    let pt = 10
    const over = () => el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2
    while (over() && pt > 7) { pt -= 0.25; el.style.fontSize = pt + 'pt' }
    if (over()) el.style.outline = '2px solid red'                   // yenə sığmır – müəllim görsün
  })
  return [...doc.querySelectorAll<HTMLElement>('.qs')].filter(el => el.style.outline).length
}

function open(title: string, body: string, after?: (d: Document) => void) {
  const w = window.open('', '_blank')
  if (!w) { toast('Brauzer yeni pəncərəni blokladı – pop-up icazəsi verin'); return }
  w.document.open()
  w.document.write(`<!doctype html><html lang="az"><head><meta charset="utf-8"><title>${esc(title)}</title><style>${CSS}
    #bar{position:sticky;top:0;background:#f3f4f6;border-bottom:1px solid #ccc;padding:8px;display:flex;gap:8px;font:14px Arial;z-index:9}
    @media print{#bar{display:none}}</style></head><body><div id="bar"><button id="p" style="padding:8px 14px">Çap et (iki üzlü)</button>
    <button id="c" style="padding:8px 14px">Bağla</button><span id="m" style="align-self:center;color:#555"></span></div>${body}</body></html>`)
  w.document.close()
  ;(w.document.getElementById('p') as HTMLButtonElement).onclick = () => w.print()
  ;(w.document.getElementById('c') as HTMLButtonElement).onclick = () => w.close()
  if (after) setTimeout(() => after(w.document), 300)
}

export async function printSheets(d: KsqPrint) {
  const qrs = await Promise.all(d.sheets.map(s => QRCode.toDataURL(s.qr, { margin: 0, width: 300, errorCorrectionLevel: 'M' })))
  const ex = d.exam
  open(`${ex.class_name} – ${ex.kind}-${ex.no} vərəqlər`, d.sheets.map((s, i) => sheet(s, ex, qrs[i])).join(''), doc => {
    const bad = fit(doc)
    const m = doc.getElementById('m')
    if (m) m.textContent = `${d.sheets.length} şagird · ${d.sheets.length * 2} səhifə (iki üzlü çap edin)` + (bad ? ` · ⚠ ${bad} səhifədə suallar sığmır (qırmızı)` : '')
  })
}

export function printKey(d: KsqPrint) {
  const ex = d.exam
  const body = `<div class="key" style="padding:4mm"><h2 style="margin:0 0 3mm">${ex.kind}-${ex.no} · ${esc(ex.class_name)} · ${fmtD(ex.date)} — müəllim açarı</h2>
    ${d.key.map(k => `<table><tr><th colspan="15" style="text-align:left">${esc(k.code)} · ${esc(k.full_name)}</th></tr>
      ${[0, 15].map(o => `<tr>${k.answers.slice(o, o + 15).map(a => `<th>${a.slot}</th>`).join('')}</tr><tr>${k.answers.slice(o, o + 15).map(a => `<td><b>${esc(a.value)}</b></td>`).join('')}</tr>`).join('')}
    </table>`).join('')}</div>`
  open(`${ex.class_name} – ${ex.kind}-${ex.no} açar`, body)
}
