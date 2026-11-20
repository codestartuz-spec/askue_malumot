import { useEffect, useRef } from 'react'

// Energetika mavzusidagi animatsion fon: elektr uzatish minoralari, simlar bo'ylab yugurayotgan
// toklar, zanjir tugunlari va uchqunlar. Yengil: ~30 kadr/s, tab yopiq bo'lsa to'xtaydi.
export default function EnergyBackground({ intensity = 1 }) {
  const ref = useRef(null)
  useEffect(() => {
    const cv = ref.current
    const ctx = cv.getContext('2d')
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0, h = 0, dpr = 1, raf, last = 0, towers = [], lines = [], nodes = [], sparks = []

    const sprite = (r, color) => {
      const c = document.createElement('canvas'); c.width = c.height = r * 2
      const g = c.getContext('2d'), gr = g.createRadialGradient(r, r, 0, r, r, r)
      gr.addColorStop(0, color); gr.addColorStop(0.35, color.replace(/[\d.]+\)$/, '0.35)')); gr.addColorStop(1, 'rgba(0,0,0,0)')
      g.fillStyle = gr; g.fillRect(0, 0, r * 2, r * 2); return c
    }
    const glowBlue = sprite(16, 'rgba(120,190,255,0.95)')
    const glowYellow = sprite(14, 'rgba(255,210,60,0.95)')

    const build = () => {
      const small = w < 700
      const n = small ? 3 : Math.max(4, Math.round(w / 260))
      const base = h * 0.94
      towers = []; lines = []
      for (let i = 0; i < n; i++) {
        const x = (i + 0.5) * (w / n) + (Math.random() - 0.5) * 30
        const th = h * (small ? 0.26 : 0.3) * (0.85 + Math.random() * 0.3)
        towers.push({ x, base, th, tw: th * 0.34 })
      }
      for (let i = 0; i < towers.length - 1; i++) {
        const a = towers[i], b = towers[i + 1]
        for (const k of [0.62, 0.8, 0.98]) {
          const ya = a.base - a.th * k, yb = b.base - b.th * k
          const xa = a.x + (k === 0.98 ? 0 : a.tw * (1.15 - k * 0.55)), xb = b.x - (k === 0.98 ? 0 : b.tw * (1.15 - k * 0.55))
          lines.push({ xa, ya, xb, yb, sag: (b.x - a.x) * 0.07, pulses: Array.from({ length: 2 }, () => ({ t: Math.random(), v: 0.04 + Math.random() * 0.06 })) })
        }
      }
      const nn = small ? 26 : Math.min(70, Math.round((w * h) / 30000))
      nodes = Array.from({ length: nn }, () => ({ x: Math.random() * w, y: Math.random() * h * 0.75, ph: Math.random() * 6.28, sp: 0.6 + Math.random() }))
      sparks = Array.from({ length: small ? 14 : 28 }, () => ({ x: Math.random() * w, y: Math.random() * h, v: 8 + Math.random() * 22, s: 0.6 + Math.random() * 1.4, ph: Math.random() * 6 }))
    }
    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5)
      w = window.innerWidth; h = window.innerHeight
      cv.width = w * dpr; cv.height = h * dpr; cv.style.width = w + 'px'; cv.style.height = h + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); build(); draw(0, 0)
    }

    const draw = (t, dt) => {
      ctx.clearRect(0, 0, w, h)
      const I = intensity
      // zanjir tugunlari
      ctx.lineWidth = 1
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy
          if (d2 < 150 * 150) { ctx.strokeStyle = `rgba(90,150,255,${(1 - Math.sqrt(d2) / 150) * 0.16 * I})`; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke() }
        }
      }
      for (const n of nodes) {
        const k = 0.5 + 0.5 * Math.sin(t * 0.001 * n.sp + n.ph)
        ctx.fillStyle = `rgba(130,190,255,${(0.12 + k * 0.35) * I})`
        ctx.beginPath(); ctx.arc(n.x, n.y, 1.6 + k * 1.2, 0, 6.283); ctx.fill()
      }
      // minoralar
      ctx.strokeStyle = `rgba(110,160,235,${0.3 * I})`; ctx.lineWidth = 1.2
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
        for (const k of [0.62, 0.8]) { const y = base - th * k, a = wd * (1.15 - k * 0.55); ctx.moveTo(x - a, y); ctx.lineTo(x + a, y) }
        ctx.stroke()
      }
      // simlar va ular bo'ylab yugurayotgan tok
      for (const l of lines) {
        ctx.strokeStyle = `rgba(150,195,255,${0.28 * I})`; ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(l.xa, l.ya)
        ctx.quadraticCurveTo((l.xa + l.xb) / 2, (l.ya + l.yb) / 2 + l.sag * 2, l.xb, l.yb); ctx.stroke()
        for (const p of l.pulses) {
          p.t += p.v * dt; if (p.t > 1) p.t = 0
          const u = p.t, x = (1 - u) * (1 - u) * l.xa + 2 * (1 - u) * u * ((l.xa + l.xb) / 2) + u * u * l.xb
          const y = (1 - u) * (1 - u) * l.ya + 2 * (1 - u) * u * ((l.ya + l.yb) / 2 + l.sag * 2) + u * u * l.yb
          ctx.globalAlpha = 0.9 * I; ctx.drawImage(glowBlue, x - 16, y - 16, 32, 32); ctx.globalAlpha = 1
        }
      }
      // uchqunlar
      for (const s of sparks) {
        s.y -= s.v * dt; if (s.y < -10) { s.y = h + 10; s.x = Math.random() * w }
        const k = 0.5 + 0.5 * Math.sin(t * 0.004 + s.ph)
        ctx.globalAlpha = (0.15 + 0.5 * k) * I; ctx.drawImage(glowYellow, s.x - 7 * s.s, s.y - 7 * s.s, 14 * s.s, 14 * s.s); ctx.globalAlpha = 1
      }
    }

    const loop = (t) => {
      raf = requestAnimationFrame(loop)
      if (t - last < 50) return
      const dt = Math.min(0.1, (t - last) / 1000); last = t
      draw(t, dt)
    }
    resize()
    window.addEventListener('resize', resize)
    const vis = () => { cancelAnimationFrame(raf); if (!document.hidden && !reduce) raf = requestAnimationFrame(loop) }
    document.addEventListener('visibilitychange', vis)
    const pause = (e) => { if (e.target?.tagName === 'SELECT') { cancelAnimationFrame(raf); raf = 0 } }
    const resume = (e) => { if (e.target?.tagName === 'SELECT' && !raf && !document.hidden && !reduce) raf = requestAnimationFrame(loop) }
    document.addEventListener('focusin', pause); document.addEventListener('focusout', resume)
    vis()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); document.removeEventListener('visibilitychange', vis) }
  }, [intensity])
  return <canvas ref={ref} className="energy-bg" aria-hidden="true" />
}
