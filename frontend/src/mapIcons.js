// Xarita belgilari (inline SVG): hisoblagich (aholi / ulgurji / balans) va konsentrator
import L from 'leaflet'

// Holatlar: har bir holat o'z rangi va nomiga ega
export const METER_ST = [
  { k: 'm1', label: 'Aloqada (0-2 kun)', color: '#16a34a' },
  { k: 'm2', label: '2-7 kun aloqasiz', color: '#f5b400' },
  { k: 'm3', label: '7-30 kun aloqasiz', color: '#f97316' },
  { k: 'm4', label: '1-3 oy aloqasiz', color: '#e11d2e' },
  { k: 'm5', label: '3 oydan ortiq aloqasiz', color: '#9f1239' },
  { k: 'm0', label: 'Umuman aloqaga chiqmagan', color: '#7b8aa3' },
  { k: 'mdir', label: "To'g'ridan-to'g'ri ulanish (peremichka)", color: '#8b3fd9' },
]
export const TR_ST = [
  { k: 't1', label: 'Online', color: '#16a34a' },
  { k: 't2', label: 'Offline (3 kungacha)', color: '#e11d2e' },
  { k: 't3', label: '3 kundan ortiq offline', color: '#9f1239' },
  { k: 't0', label: "Holati noma'lum", color: '#7b8aa3' },
  { k: 'tun', label: "Iste'molchi biriktirilmagan", color: '#0e7490' },
]
export const TR_LV = [
  { k: 'l1', label: 'Obxod 0%', color: '#b91c1c' }, { k: 'l2', label: 'Obxod 1-30%', color: '#ea580c' },
  { k: 'l3', label: 'Obxod 30-50%', color: '#d97706' }, { k: 'l4', label: 'Obxod 50-80%', color: '#65a30d' },
  { k: 'l5', label: 'Obxod 80-100%', color: '#16a34a' },
]
const MCOL = Object.fromEntries(METER_ST.map((x) => [x.k, x]))
export const meterState = (b) => MCOL['m' + b] || MCOL.m0
export function trState(p) {
  if (p.off3) return TR_ST[2]
  return p.st === 1 ? TR_ST[0] : p.st === 2 ? TR_ST[1] : TR_ST[3]
}

const G = {
  aholi: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  ulgurji: '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>',
  balans: '<path d="M12 3v18"/><path d="M5 21h14"/><path d="M5 7h14"/><path d="m5 7-3 7a3 3 0 0 0 6 0z"/><path d="m19 7-3 7a3 3 0 0 0 6 0z"/>',
  bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
  tr: '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19.1"/>',
}
export const KIND_NAME = { aholi: 'Aholi hisoblagichi', ulgurji: 'Ulgurji hisoblagich', balans: 'Balans hisoblagich', tr: 'Konsentrator (TP)' }
export const glyph = (kind, size = 18, color = '#fff') =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${G[kind]}</svg>`

export function pinIcon(kind, color, { big = false, focus = false, bad = false, direct = false } = {}) {
  const w = big ? 40 : 32, h = big ? 52 : 42
  const ring = kind === 'tr' ? '#0b2a6b' : '#ffffff'
  const html = `
    <div class="pin ${focus ? 'pin-focus' : ''} ${bad ? 'pin-bad' : ''}" style="width:${w}px;height:${h}px">
      <svg viewBox="0 0 32 42" width="${w}" height="${h}">
        <ellipse cx="16" cy="40" rx="6" ry="2" fill="rgba(0,0,0,.28)"/>
        <path d="M16 40C16 40 3 26 3 15a13 13 0 0 1 26 0c0 11-13 25-13 25z" fill="${color}" stroke="${ring}" stroke-width="${kind === 'tr' ? 2.6 : 2}"/>
        ${kind === 'tr' ? '<circle cx="16" cy="15" r="9.8" fill="#0b2a6b"/>' : '<circle cx="16" cy="15" r="9.6" fill="#ffffff"/>'}
      </svg>
      <span class="pin-g" style="top:${big ? 9 : 6}px">${glyph(kind, big ? 20 : 17, kind === 'tr' ? '#fff' : color)}</span>
      ${direct ? `<span class="pin-dir" title="Peremichka">${glyph('bolt', 10)}</span>` : ''}
    </div>`
  return L.divIcon({ html, className: 'pin-wrap', iconSize: [w, h], iconAnchor: [w / 2, h - 2], tooltipAnchor: [0, -h + 8] })
}

const compact = (n) => (n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1).replace('.0', '')}k` : String(n))
export function clusterIcon(c, color) {
  const isTr = c.t === 't'
  const size = Math.round(Math.min(62, 34 + Math.log10(c.n + 1) * 8) * (isTr ? 0.86 : 1))
  if (isTr) {
    // konsentrator guruhi: yumaloq kvadrat (hisoblagich doiralaridan farqlansin), biroz o'ngga-yuqoriga siljitilgan
    const off = 16
    return L.divIcon({
      html: `<div class="cl cl-t" style="width:${size}px;height:${size}px"><i>${glyph('tr', 13)}</i><b>${compact(c.n)}</b></div>`,
      className: 'cluster-wrap', iconSize: [size, size], iconAnchor: [size / 2 - off, size / 2 + off],
    })
  }
  const bad = c.n ? Math.round((c.bad / c.n) * 100) : 0
  const ring = color ? `${color} 0 100%` : bad >= 100 ? '#e11d2e 0 100%' : bad <= 0 ? '#16a34a 0 100%' : `#e11d2e 0 ${bad}%, #16a34a ${bad}% 100%`
  return L.divIcon({
    html: `<div class="cl cl-m" style="width:${size}px;height:${size}px;background:conic-gradient(from 0deg,${ring})"><span class="cl-in"><b>${compact(c.n)}</b></span></div>`,
    className: 'cluster-wrap', iconSize: [size, size],
  })
}
