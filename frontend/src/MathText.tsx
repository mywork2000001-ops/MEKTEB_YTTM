// Riyaziyyat mətni: $…$, $$…$$, \(…\), \[…\] – KaTeX ilə (viktorina ilə eyni qayda). Mətn HTML kimi deyil, mətn kimi qoyulur.
import { useEffect, useRef } from 'react'
import 'katex/dist/katex.min.css'
import renderMathInElement from 'katex/contrib/auto-render'

const DELIMS = [
  { left: '$$', right: '$$', display: true }, { left: '\[', right: '\]', display: true },
  { left: '\(', right: '\)', display: false }, { left: '$', right: '$', display: false },
]

export function MathText({ text, as: Tag = 'span', className, style }: { text: string; as?: 'span' | 'p' | 'div'; className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.textContent = text
    if (/[$\]/.test(text)) {
      try { renderMathInElement(el, { delimiters: DELIMS, throwOnError: false, strict: 'ignore' }) } catch { /* xam mətn qalır */ }
    }
  }, [text])
  return <Tag ref={ref as never} className={className} style={style} />
}
