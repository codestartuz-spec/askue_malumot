import { useMemo, useRef, useState } from 'react'
import { num } from './fmt'

export const PALETTE = ['#1d6fff', '#e31e24', '#16a34a', '#f59e0b', '#8b5cf6', '#0891b2', '#db2777']

const niceMax = (v) => {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p
}
const shortNum = (v) => (Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1).replace('.0', '')}M` : Math.abs(v) >= 1e4 ? `${Math.round(v / 1000)}k` : num(v))

/** Chiziqli grafik: bir nechta qator, hover'da qiymatlar, 1-2 nuqtada ham chiroyli ko'rinadi. */
export function LineChart({ labels, series, height = 230, unit = '', zero = false, fmt }) {
  const f = fmt || ((v) => num(v))
  const W = 640, H = height, L = 52, R = 18, T = 16, B = 30
  const [hi, setHi] = useState(null)
  const ref = useRef(null)
  const n = labels.length
  const all = series.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined))
  const lo0 = Math.min(...all), hi0 = Math.max(...all)
  const span = hi0 - lo0
  const min = zero || lo0 === hi0 ? 0 : Math.max(0, lo0 - span * 0.25)
  const max = niceMax(hi0 + (zero ? 0 : span * 0.1)) || 1
  const top = Math.max(max, hi0)
  const x = (i) => (n === 1 ? (L + W - R) / 2 : L + ((W - L - R) * i) / (n - 1))
  const y = (v) => T + (H - T - B) * (1 - (v - min) / ((top - min) || 1))
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((top - min) * i) / 4)
  const move = (e) => {
    const r = ref.current.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * W
    let best = 0
    for (let i = 0; i < n; i++) if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i
    setHi(best)
  }
  const gid = useMemo(() => `g${Math.random().toString(36).slice(2, 8)}`, [])
  return (
    <div className="chart-wrap">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="lchart" onMouseMove={move} onMouseLeave={() => setHi(null)} role="img">
        <defs>{series.map((s, k) => (
          <linearGradient key={k} id={`${gid}${k}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={s.color} stopOpacity=".28" /><stop offset="100%" stopColor={s.color} stopOpacity="0" />
          </linearGradient>))}</defs>
        {ticks.map((t, i) => (
          <g key={i}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid" /><text x={L - 8} y={y(t) + 4} className="ax" textAnchor="end">{fmt ? f(t) : shortNum(t)}{unit}</text></g>))}
        {labels.map((l, i) => (n <= 8 || i % Math.ceil(n / 8) === 0 || i === n - 1) && (
          <text key={i} x={x(i)} y={H - 8} className="ax" textAnchor="middle">{l}</text>))}
        {hi !== null && <line x1={x(hi)} x2={x(hi)} y1={T} y2={H - B} className="cursor" />}
        {series.map((s, k) => {
          const pts = s.values.map((v, i) => (v === null || v === undefined ? null : [x(i), y(v)])).filter(Boolean)
          if (!pts.length) return null
          const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
          const area = `${d} L${pts[pts.length - 1][0]},${H - B} L${pts[0][0]},${H - B} Z`
          return (
            <g key={k}>
              {k === 0 && pts.length > 1 && <path d={area} fill={`url(#${gid}${k})`} className="area" />}
              {pts.length > 1 && <path d={d} fill="none" stroke={s.color} strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" className="ln" pathLength="1" />}
              {s.values.map((v, i) => v !== null && v !== undefined && (
                <circle key={i} cx={x(i)} cy={y(v)} r={hi === i ? 5.5 : n > 14 ? 0 : 3.6} fill="#fff" stroke={s.color} strokeWidth="2.4" className="dot" />))}
            </g>)
        })}
      </svg>
      {hi !== null && (
        <div className="ctip" style={{ left: `${(x(hi) / W) * 100}%`, transform: x(hi) > W * 0.62 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)' }}>
          <b>{labels[hi]}</b>
          {series.map((s, k) => <div key={k}><i style={{ background: s.color }} />{s.name}<strong>{f(s.values[hi])}{unit}</strong></div>)}
        </div>)}
      {series.length > 1 && <div className="clegend">{series.map((s, k) => <span key={k}><i style={{ background: s.color }} />{s.name}</span>)}</div>}
    </div>
  )
}

/** Gorizontal ustunlar (tumanlar reytingi). items: [{name, value, sub?}] */
export function HBars({ items, color = '#1d6fff', unit = '', max, onlyPositive = false, limit = 20 }) {
  const list = (onlyPositive ? items.filter((i) => i.value > 0) : items).slice(0, limit)
  const m = max || Math.max(1, ...list.map((i) => i.value))
  if (!list.length) return <div className="chart-empty">Ma'lumot yo'q</div>
  return (
    <div className="hbars">{list.map((it, i) => (
      <div key={it.name} className="hb">
        <span className="hb-n" title={it.name}>{it.name}</span>
        <span className="hb-t"><i style={{ width: `${Math.max(2, (it.value / m) * 100)}%`, background: it.color || color, animationDelay: `${i * 35}ms` }} /></span>
        <b className="hb-v">{num(it.value)}{unit}{it.sub && <small>{it.sub}</small>}</b>
      </div>))}</div>
  )
}

/** Vertikal ustunlar. items: [{name, value, color}] */
export function ColBars({ items, height = 200 }) {
  const m = Math.max(1, ...items.map((i) => i.value))
  return (
    <div className="cols" style={{ height }}>{items.map((it, i) => (
      <div key={it.name} className="col">
        <b>{num(it.value)}</b>
        <span className="col-bar"><i style={{ height: `${Math.max(3, (it.value / m) * 100)}%`, background: `linear-gradient(180deg,${it.color},${it.color}aa)`, animationDelay: `${i * 70}ms` }} /></span>
        <small>{it.name}</small>
      </div>))}</div>
  )
}

/** Donut. items: [{name, value, color}] */
export function Donut({ items, center, sub, size = 190 }) {
  const total = items.reduce((a, b) => a + b.value, 0)
  const r = 70, c = 2 * Math.PI * r
  let acc = 0
  return (
    <div className="donut">
      <svg viewBox="0 0 200 200" width={size} height={size} role="img">
        <circle cx="100" cy="100" r={r} fill="none" stroke="#e7eefb" strokeWidth="26" />
        {total > 0 && items.map((it, i) => {
          const len = (it.value / total) * c
          const el = <circle key={i} cx="100" cy="100" r={r} fill="none" stroke={it.color} strokeWidth="26" strokeDasharray={`${Math.max(len - 1.5, 0)} ${c}`}
            strokeDashoffset={-acc} transform="rotate(-90 100 100)" className="dseg" style={{ animationDelay: `${i * 90}ms` }} />
          acc += len
          return el
        })}
        <text x="100" y="98" textAnchor="middle" className="d-c">{center ?? num(total)}</text>
        <text x="100" y="120" textAnchor="middle" className="d-s">{sub || 'jami'}</text>
      </svg>
      <ul>{items.map((it) => (
        <li key={it.name}><i style={{ background: it.color }} /><span>{it.name}</span><b>{num(it.value)}</b><small>{total ? `${((it.value / total) * 100).toFixed(1).replace('.', ',')}%` : ''}</small></li>))}</ul>
    </div>
  )
}
