import { useEffect, useRef } from 'react'

// ASKUE mavzusidagi animatsion fon (yorug' uslub: oq/ko'k/qizil).
// Konsentratorlar (qizil markaz) atrofida hisoblagichlar (ko'k nuqtalar) joylashgan; ularning
// ma'lumotlari paketlar bo'lib konsentratorga yetib boradi, radio to'lqinlari tarqaladi,
// ba'zi hisoblagichlar aloqadan chiqadi (qizil, uzilgan chiziq) va qayta ulanadi (halqa).
// Pastda elektr uzatish minoralari va ular bo'ylab yuguruvchi tok. Yengil: ~25 kadr/s.
const BLUE = '24,84,196', RED = '215,25,32', GREY = '120,135,160'

export default function EnergyBackground({ intensity = 1 }) {
  const ref = useRef(null)
  useEffect(() => {
    const cv = ref.current
    const ctx = cv.getContext('2d')
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0, h = 0, dpr = 1, raf = 0, last = 0, hubs = [], towers = [], lines = [], packets = [], rings = []
    const rnd = Math.random

    const build = () => {
      const small = w < 700
      const n = small ? 3 : Math.max(4, Math.round(w / 330))
      hubs = []; packets = []; rings = []
      for (let i = 0; i < n; i++) {
        const hub = { x: (i + 0.5) * (w / n) + (rnd() - 0.5) * 50, y: h * (i % 2 ? 0.55 : 0.27) + (rnd() - 0.5) * h * 0.08, ph: rnd() * 6.28, flash: 0, meters: [] }
        const m = small ? 6 : 9 + Math.floor(rnd() * 4)
        for (let j = 0; j < m; j++) {
          const a = (j / m) * 6.283 + rnd() * 0.5, r = (small ? 46 : 62) + rnd() * (small ? 40 : 88)
          hub.meters.push({ x: hub.x + Math.cos(a) * r, y: hub.y + Math.sin(a) * r, st: 'on', until: 0, next: rnd() * 4000, ph: rnd() * 6 })
        }
        hubs.push(hub)
      }
      // elektr uzatish minoralari (pastda, yengil)
      towers = []; lines = []
      const nt = small ? 3 : Math.max(4, Math.round(w / 300)), base = h * 0.985
      for (let i = 0; i < nt; i++) {
        const th = h * (small ? 0.2 : 0.24) * (0.85 + rnd() * 0.3)
        towers.push({ x: (i + 0.5) * (w / nt) + (rnd() - 0.5) * 24, base, th, tw: th * 0.34 })
      }
      for (let i = 0; i < towers.length - 1; i++) {
        const a = towers[i], b = towers[i + 1]
        for (const k of [0.66, 0.84, 0.98]) {
          const xa = a.x + (k === 0.98 ? 0 : a.tw * (1.15 - k * 0.55)), xb = b.x - (k === 0.98 ? 0 : b.tw * (1.15 - k * 0.55))
          lines.push({ xa, ya: a.base - a.th * k, xb, yb: b.base - b.th * k, sag: (b.x - a.x) * 0.06, t: rnd(), v: 0.05 + rnd() * 0.05 })
        }
      }
    }
    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      w = window.innerWidth; h = window.innerHeight
      cv.width = w * dpr; cv.height = h * dpr; cv.style.width = w + 'px'; cv.style.height = h + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); build(); draw(performance.now(), 0)
    }

    const update = (t, dt) => {
      for (const hub of hubs) {
        hub.flash = Math.max(0, hub.flash - dt * 2.2)
        for (const m of hub.meters) {
          if (m.st === 'on' && t > m.next) {
            packets.push({ m, hub, u: 0, v: 0.7 + rnd() * 0.5, px: m.x, py: m.y })
            m.next = t + 2200 + rnd() * 5500
            if (rnd() < 0.07) { m.st = 'off'; m.until = t + 3500 + rnd() * 3500 }
          } else if (m.st === 'off' && t > m.until) {
            m.st = 'on'; m.next = t + 900
            rings.push({ x: m.x, y: m.y, t0: t })
          }
        }
      }
      for (let i = packets.length - 1; i >= 0; i--) {
        const p = packets[i]; p.u += p.v * dt
        if (p.u >= 1) { p.hub.flash = 1; packets.splice(i, 1) }
      }
      for (const l of lines) { l.t += l.v * dt; if (l.t > 1) l.t = 0 }
      for (let i = rings.length - 1; i >= 0; i--) if (t - rings[i].t0 > 1100) rings.splice(i, 1)
    }

    function draw(t, dt) {
      ctx.clearRect(0, 0, w, h)
      const I = intensity
      // konsentratorlar orasidagi magistral (harakatlanuvchi shtrix)
      ctx.lineWidth = 1.2; ctx.setLineDash([6, 6]); ctx.lineDashOffset = -t * 0.012
      ctx.strokeStyle = `rgba(${RED},${0.2 * I})`
      for (let i = 0; i < hubs.length - 1; i++) { ctx.beginPath(); ctx.moveTo(hubs[i].x, hubs[i].y); ctx.lineTo(hubs[i + 1].x, hubs[i + 1].y); ctx.stroke() }
      ctx.setLineDash([])
      for (const hub of hubs) {
        // hisoblagich — konsentrator liniyalari
        for (const m of hub.meters) {
          if (m.st === 'on') {
            ctx.strokeStyle = `rgba(${BLUE},${0.16 * I})`; ctx.lineWidth = 1
          } else {
            const k = 0.5 + 0.5 * Math.sin(t * 0.01 + m.ph)
            ctx.strokeStyle = `rgba(${RED},${(0.15 + k * 0.25) * I})`; ctx.lineWidth = 1; ctx.setLineDash([3, 4])
          }
          ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(hub.x, hub.y); ctx.stroke(); ctx.setLineDash([])
        }
        // radio to'lqinlari
        for (let k = 0; k < 2; k++) {
          const u = ((t * 0.00045 + hub.ph + k * 0.5) % 1), r = 14 + u * 70
          ctx.strokeStyle = `rgba(${BLUE},${(1 - u) * 0.22 * I})`; ctx.lineWidth = 1.2
          ctx.beginPath(); ctx.arc(hub.x, hub.y, r, 0, 6.283); ctx.stroke()
        }
        // hisoblagichlar
        for (const m of hub.meters) {
          if (m.st === 'on') {
            ctx.fillStyle = `rgba(${BLUE},${0.7 * I})`; ctx.beginPath(); ctx.arc(m.x, m.y, 3.2, 0, 6.283); ctx.fill()
            ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.beginPath(); ctx.arc(m.x, m.y, 1.1, 0, 6.283); ctx.fill()
          } else {
            const k = 0.5 + 0.5 * Math.sin(t * 0.01 + m.ph)
            ctx.fillStyle = `rgba(${GREY},${0.55 * I})`; ctx.beginPath(); ctx.arc(m.x, m.y, 3.2, 0, 6.283); ctx.fill()
            ctx.strokeStyle = `rgba(${RED},${(0.35 + k * 0.5) * I})`; ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.arc(m.x, m.y, 6 + k * 2, 0, 6.283); ctx.stroke()
          }
        }
        // konsentrator markazi
        const f = hub.flash
        ctx.fillStyle = `rgba(${RED},${0.9 * I})`; ctx.beginPath(); ctx.arc(hub.x, hub.y, 8 + f * 2.5, 0, 6.283); ctx.fill()
        ctx.strokeStyle = `rgba(255,255,255,.95)`; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(hub.x, hub.y, 8 + f * 2.5, 0, 6.283); ctx.stroke()
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(hub.x, hub.y, 2.6, 0, 6.283); ctx.fill()
      }
      // ma'lumot paketlari (hisoblagich → konsentrator)
      for (const p of packets) {
        const x = p.m.x + (p.hub.x - p.m.x) * p.u, y = p.m.y + (p.hub.y - p.m.y) * p.u
        ctx.strokeStyle = `rgba(${BLUE},${0.5 * I})`; ctx.lineWidth = 2
        ctx.beginPath(); ctx.moveTo(p.px, p.py); ctx.lineTo(x, y); ctx.stroke()
        ctx.fillStyle = `rgba(${BLUE},${0.95 * I})`; ctx.beginPath(); ctx.arc(x, y, 2.6, 0, 6.283); ctx.fill()
        p.px = p.px + (x - p.px) * 0.35; p.py = p.py + (y - p.py) * 0.35
      }
      // qayta ulanish halqasi
      for (const r of rings) {
        const u = (t - r.t0) / 1100
        ctx.strokeStyle = `rgba(${BLUE},${(1 - u) * 0.8 * I})`; ctx.lineWidth = 2
        ctx.beginPath(); ctx.arc(r.x, r.y, 5 + u * 26, 0, 6.283); ctx.stroke()
      }
      // minoralar va simlar
      ctx.strokeStyle = `rgba(${BLUE},${0.16 * I})`; ctx.lineWidth = 1.2
      for (const tw of towers) {
        const { x, base, th, tw: wd } = tw
        ctx.beginPath()
        ctx.moveTo(x - wd * 0.5, base); ctx.lineTo(x - wd * 0.07, base - th); ctx.moveTo(x + wd * 0.5, base); ctx.lineTo(x + wd * 0.07, base - th)
        for (let k = 0.1; k < 1; k += 0.15) {
          const y = base - th * k, half = wd * (0.5 - 0.43 * k)
          ctx.moveTo(x - half, y); ctx.lineTo(x + half, y)
          ctx.moveTo(x - half, y); ctx.lineTo(x + half * 0.2, y - th * 0.075)
          ctx.moveTo(x + half, y); ctx.lineTo(x - half * 0.2, y - th * 0.075)
        }
        for (const k of [0.66, 0.84]) { const y = base - th * k, a = wd * (1.15 - k * 0.55); ctx.moveTo(x - a, y); ctx.lineTo(x + a, y) }
        ctx.stroke()
      }
      for (const l of lines) {
        const cx = (l.xa + l.xb) / 2, cy = (l.ya + l.yb) / 2 + l.sag * 2
        ctx.strokeStyle = `rgba(${BLUE},${0.2 * I})`; ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(l.xa, l.ya); ctx.quadraticCurveTo(cx, cy, l.xb, l.yb); ctx.stroke()
        const u = l.t, x = (1 - u) * (1 - u) * l.xa + 2 * (1 - u) * u * cx + u * u * l.xb
        const y = (1 - u) * (1 - u) * l.ya + 2 * (1 - u) * u * cy + u * u * l.yb
        ctx.fillStyle = `rgba(${RED},${0.8 * I})`; ctx.beginPath(); ctx.arc(x, y, 2.2, 0, 6.283); ctx.fill()
      }
    }

    const loop = (t) => {
      raf = requestAnimationFrame(loop)
      if (t - last < 40) return
      const dt = Math.min(0.1, (t - last) / 1000); last = t
      update(t, dt); draw(t, dt)
    }
    resize()
    window.addEventListener('resize', resize)
    const start = () => { if (!raf && !document.hidden && !reduce) raf = requestAnimationFrame(loop) }
    const stop = () => { cancelAnimationFrame(raf); raf = 0 }
    const vis = () => { stop(); start() }
    document.addEventListener('visibilitychange', vis)
    const pause = (e) => { if (e.target?.tagName === 'SELECT') stop() }
    const resume = (e) => { if (e.target?.tagName === 'SELECT') start() }
    document.addEventListener('focusin', pause); document.addEventListener('focusout', resume)
    start()
    return () => { stop(); window.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', vis); document.removeEventListener('focusin', pause); document.removeEventListener('focusout', resume) }
  }, [intensity])
  return <canvas ref={ref} className="energy-bg" aria-hidden="true" />
}
