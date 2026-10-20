export type Sem = '1' | '2' | 'all'
export const semLabel = (s: Sem) => (s === 'all' ? 'bütün il' : `${s}-ci yarımil`)
