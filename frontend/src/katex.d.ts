declare module 'katex/contrib/auto-render' {
  const render: (el: HTMLElement, opts?: Record<string, unknown>) => void
  export default render
}
