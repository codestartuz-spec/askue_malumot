export const num = (n) => (n === null || n === undefined ? '' : String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '))
export const pct = (a, b) => (b > 0 ? `${((a / b) * 100).toFixed(1).replace('.', ',')}%` : '')
export const dmy = (iso) => (iso ? iso.split('-').reverse().join('.') : '')
export const dt = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
