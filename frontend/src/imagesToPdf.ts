// Şəkillər → bir PDF (kitabxanasız): hər şəkil kiçildilir (ən uzun tərəf ≤ 1600 px), JPEG-ə çevrilir və PDF səhifəsinə
// DCTDecode ilə olduğu kimi yerləşdirilir. Telefonun fotosu (HEIC də, brauzer aça bilirsə) səhifə eninə – 595 pt (A4) – uyğunlaşır.
const MAX = 1600

async function toJpeg(f: File): Promise<{ bytes: Uint8Array; w: number; h: number }> {
  const bmp = await createImageBitmap(f, { imageOrientation: 'from-image' } as ImageBitmapOptions).catch(() => null)
  const src: CanvasImageSource & { width: number; height: number } = bmp ?? await new Promise<HTMLImageElement>((ok, bad) => {
    const img = new Image()
    img.onload = () => ok(img)
    img.onerror = () => bad(new Error(`${f.name}: şəkil açılmadı`))
    img.src = URL.createObjectURL(f)
  })
  const k = Math.min(1, MAX / Math.max(src.width, src.height))
  const w = Math.max(1, Math.round(src.width * k)), h = Math.max(1, Math.round(src.height * k))
  const c = document.createElement('canvas')
  c.width = w; c.height = h
  const g = c.getContext('2d')!
  g.fillStyle = '#fff'; g.fillRect(0, 0, w, h)
  g.drawImage(src, 0, 0, w, h)
  const blob = await new Promise<Blob>((ok, bad) => c.toBlob(b => (b ? ok(b) : bad(new Error('JPEG alınmadı'))), 'image/jpeg', 0.8))
  return { bytes: new Uint8Array(await blob.arrayBuffer()), w, h }
}

export async function imagesToPdf(files: File[]): Promise<Blob> {
  const imgs = []
  for (const f of files) imgs.push(await toJpeg(f))
  const enc = new TextEncoder()
  const parts: Uint8Array[] = []
  const offsets: number[] = []
  let len = 0
  const push = (x: string | Uint8Array) => { const b = typeof x === 'string' ? enc.encode(x) : x; parts.push(b); len += b.length }
  const obj = (n: number, body: (string | Uint8Array)[]) => { offsets[n] = len; push(`${n} 0 obj\n`); body.forEach(push); push('\nendobj\n') }
  push('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n')
  const n = imgs.length
  const pageIds = imgs.map((_, i) => 3 + i * 3)
  obj(1, ['<< /Type /Catalog /Pages 2 0 R >>'])
  obj(2, [`<< /Type /Pages /Kids [${pageIds.map(p => `${p} 0 R`).join(' ')}] /Count ${n} >>`])
  imgs.forEach((im, i) => {
    const p = 3 + i * 3, W = 595, H = Math.round(595 * im.h / im.w)
    const draw = `q ${W} 0 0 ${H} 0 0 cm /Im0 Do Q`
    obj(p, [`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${W} ${H}] /Resources << /XObject << /Im0 ${p + 2} 0 R >> >> /Contents ${p + 1} 0 R >>`])
    obj(p + 1, [`<< /Length ${draw.length} >>\nstream\n${draw}\nendstream`])
    obj(p + 2, [`<< /Type /XObject /Subtype /Image /Width ${im.w} /Height ${im.h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${im.bytes.length} >>\nstream\n`,
      im.bytes, '\nendstream'])
  })
  const total = 3 + n * 3
  const xref = len
  push(`xref\n0 ${total}\n0000000000 65535 f \n`)
  for (let k = 1; k < total; k++) push(`${String(offsets[k]).padStart(10, '0')} 00000 n \n`)
  push(`trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`)
  return new Blob(parts as BlobPart[], { type: 'application/pdf' })
}
