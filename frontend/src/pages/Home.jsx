import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Table2, Globe2, ArrowUp, ArrowDown, Radio, Wifi, WifiOff, Server, Cable, Gauge, Activity, Unplug, CalendarDays, Database, TrendingUp, PieChart, BarChart3, MapPinned, Zap, Layers } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Empty, Spinner, useCountUp } from '../ui'
import { dmy, num } from '../fmt'
import { ColBars, Donut, HBars, LineChart } from '../charts'

const dm = (iso) => iso.slice(8, 10) + '.' + iso.slice(5, 7)
const pc = (a, b) => (b > 0 ? (a / b) * 100 : 0)
const p1 = (v) => `${v.toFixed(1).replace('.', ',')}`

function Trend({ d, bad = true, unit = '' }) {
  if (d === null || d === undefined) return <span className="kpi-d none">—</span>
  if (Math.abs(d) < 1e-9) return <span className="kpi-d none">o'zgarmagan</span>
  const up = d > 0
  const cls = up === bad ? 'red' : 'green'
  return <span className={`kpi-d ${cls}`}>{up ? <ArrowUp size={13} strokeWidth={3} /> : <ArrowDown size={13} strokeWidth={3} />}{unit ? p1(Math.abs(d)) + unit : num(Math.abs(d))}</span>
}

function Kpi({ icon: Icon, label, value, d, bad, tone = 'blue', sub, dec }) {
  const shown = useCountUp(dec ? 0 : value || 0)
  return (
    <div className={`kpi tone-${tone}`}>
      <i className="kpi-ic"><Icon size={22} /></i>
      <div className="kpi-b">
        <small>{label}</small>
        <b>{dec ? dec(value) : num(shown)}</b>
        <div className="kpi-f"><Trend d={d} bad={bad} unit={dec ? ' p.p.' : ''} />{sub && <em>{sub}</em>}</div>
      </div>
    </div>
  )
}

const Card = ({ icon: Icon, title, sub, children, wide }) => (
  <section className={`card chart-card ${wide ? 'wide' : ''}`}>
    <h3><Icon size={18} />{title}{sub && <small>{sub}</small>}</h3>
    {children}
  </section>
)

// ----------------------------------------------------------------- Kunlik dinamika
function Daily() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.get('/home/daily').then(setD).catch((e) => setErr(e.message)) }, [])
  const x = useMemo(() => {
    if (!d?.latest) return null
    const L = d.latest, P = d.prev, S = d.series, lab = d.dates.map(dm)
    const diff = (m) => (P ? L[m] - P[m] : null)
    const poll = S.polled.map((v, i) => pc(v, S.m_total[i]))
    const obx = pc(L.polled, L.m_total), obxP = P ? pc(P.polled, P.m_total) : null
    const dist = d.districts
    const by = (fn) => dist.map((e) => ({ name: e.name, value: fn(e.cur), sub: e.base && Object.keys(e.base).length ? fn(e.cur) - fn(e.base) : null }))
    const sub = (arr) => arr.map((a) => ({ ...a, sub: a.sub ? ` ${a.sub > 0 ? '+' : '−'}${num(Math.abs(a.sub))}` : '' }))
    return { L, P, S, lab, diff, poll, obx, obxP, dist, by, sub }
  }, [d])
  if (err) return <div className="card pad"><Empty icon={Database}>{err}</Empty></div>
  if (!d) return <Spinner />
  if (!x) return <div className="card pad"><Empty icon={Database}>Hali ma'lumot yuklanmagan. «Ma'lumot yuklash» bo'limidan Area/Details fayllarini yuklang.</Empty></div>
  const { L, S, lab, diff, by, sub } = x
  const sortDesc = (a) => [...a].sort((p, q) => q.value - p.value)
  return (
    <>
      <div className="home-bar"><CalendarDays size={16} />So'nggi ma'lumot: <b>{dmy(d.to)}</b>{d.from && <> • solishtirish: <b>{dmy(d.from)}</b></>}<span className="grow" /><span className="mut">{d.dates.length} kunlik tarix</span></div>
      <div className="kpis">
        <Kpi icon={Server} label="Dasturdagi TP / konsentratorlar" value={L.tp_total} d={diff('tp_total')} bad={false} tone="blue" />
        <Kpi icon={Layers} label="CAS ga yuklangan" value={L.cas_loaded} d={diff('cas_loaded')} bad={false} tone="cyan" sub={`${p1(pc(L.cas_loaded, L.tp_total))}%`} />
        <Kpi icon={Wifi} label="Online" value={L.online} d={diff('online')} bad={false} tone="green" />
        <Kpi icon={WifiOff} label="Offline" value={L.offline} d={diff('offline')} bad tone="red" sub={`3 kundan ortiq: ${num(L.offline3)}`} />
        <Kpi icon={Unplug} label="Aloqaga chiqmay qolgan hisoblagichlar" value={L.out_total} d={diff('out_total')} bad tone="red" sub={`${p1(pc(L.out_total, L.m_total))}%`} />
        <Kpi icon={Radio} label="Umuman aloqaga chiqmagan" value={L.m_nopoll} d={diff('m_nopoll')} bad tone="amber" />
        <Kpi icon={Cable} label="To'g'ridan-to'g'ri ulanish (peremichka)" value={L.m_direct} d={diff('m_direct')} bad tone="purple" />
        <Kpi icon={Gauge} label="48 soat ichida obxod" value={x.obx} dec={(v) => `${p1(v)}%`} d={x.obxP === null ? null : x.obx - x.obxP} bad={false} tone="green" sub={`${num(L.polled)} / ${num(L.m_total)}`} />
      </div>

      <div className="grid2">
        <Card icon={TrendingUp} title="Online konsentratorlar" sub="kunlar bo'yicha"><LineChart labels={lab} series={[{ name: 'Online', color: '#16a34a', values: S.online }]} /></Card>
        <Card icon={TrendingUp} title="Offline konsentratorlar"><LineChart labels={lab} zero series={[{ name: 'Offline (jami)', color: '#e31e24', values: S.offline }, { name: '3 kundan ortiq', color: '#f59e0b', values: S.offline3 }]} /></Card>
        <Card icon={TrendingUp} title="Aloqaga chiqmay qolgan hisoblagichlar"><LineChart labels={lab} series={[{ name: 'Jami', color: '#e31e24', values: S.out_total }]} /></Card>
        <Card icon={TrendingUp} title="Iste'molchi turi bo'yicha aloqaga chiqmaganlar"><LineChart labels={lab} series={[{ name: 'Aholi', color: '#16a34a', values: S.out_aholi }, { name: 'Ulgurji', color: '#1d6fff', values: S.out_ulgurji }, { name: 'Balans', color: '#f59e0b', values: S.out_balans }]} /></Card>
        <Card icon={TrendingUp} title="48 soat ichida obxod olish foizi"><LineChart labels={lab} fmt={p1} unit="%" series={[{ name: 'Obxod', color: '#0891b2', values: x.poll }]} /></Card>
        <Card icon={TrendingUp} title="Umuman aloqaga chiqmagan va peremichka"><LineChart labels={lab} series={[{ name: 'Umuman aloqaga chiqmagan', color: '#e31e24', values: S.m_nopoll }, { name: 'Peremichka', color: '#8b5cf6', values: S.m_direct }]} /></Card>
      </div>

      <div className="grid3">
        <Card icon={PieChart} title="Konsentratorlar obxod darajasi" sub={dmy(d.to)}>
          <Donut sub="konsentrator" items={[{ name: '0%', value: L.lv0, color: '#e31e24' }, { name: '1-30%', value: L.lv1, color: '#f97316' }, { name: '30-50%', value: L.lv2, color: '#f59e0b' }, { name: '50-80%', value: L.lv3, color: '#84cc16' }, { name: '80-100%', value: L.lv4, color: '#16a34a' }]} />
        </Card>
        <Card icon={PieChart} title="Aloqaga chiqmaganlar: iste'molchi turi" sub={dmy(d.to)}>
          <Donut sub="hisoblagich" items={[{ name: 'Aholi', value: L.out_aholi, color: '#16a34a' }, { name: 'Ulgurji', value: L.out_ulgurji, color: '#1d6fff' }, { name: 'Balans', value: L.out_balans, color: '#f59e0b' }]} />
        </Card>
        <Card icon={BarChart3} title="Aloqadan chiqqanlar: vaqt kesimi" sub="necha kundan beri">
          <ColBars items={[{ name: '2-7 kun', value: L.out_2_7, color: '#f59e0b' }, { name: '7-30 kun', value: L.out_7_30, color: '#f97316' }, { name: '1-3 oy', value: L.out_30_90, color: '#e31e24' }, { name: '3 oydan ortiq', value: L.out_90p, color: '#9f1239' }]} />
        </Card>
      </div>

      <div className="grid3">
        <Card icon={MapPinned} title="Tumanlar: aloqaga chiqmay qolgan hisoblagichlar" sub="eng ko'pdan">
          <HBars color="#e31e24" items={sub(sortDesc(by((c) => c.out_total)))} />
        </Card>
        <Card icon={MapPinned} title="Tumanlar: offline konsentratorlar">
          <HBars color="#f59e0b" onlyPositive items={sub(sortDesc(by((c) => c.offline)))} />
        </Card>
        <Card icon={MapPinned} title="Tumanlar: 48 soat obxod foizi" sub="eng pastdan">
          <HBars color="#0891b2" unit="%" max={100} items={[...x.dist].map((e) => ({ name: e.name, value: Math.round(pc(e.cur.polled, e.cur.m_total) * 10) / 10 })).sort((a, b) => a.value - b.value)} />
        </Card>
      </div>
    </>
  )
}

// ----------------------------------------------------------------- Respublika dinamikasi
const cellOf = (rep, n, i) => rep.pages.find((p) => p.n === n)?.cells[i]

function Republic() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  const [mode, setMode] = useState('oy')
  useEffect(() => { api.get('/home/republic').then(setD).catch((e) => setErr(e.message)) }, [])
  if (err) return <div className="card pad"><Empty icon={Globe2}>{err}</Empty></div>
  if (!d) return <Spinner />
  const reps = d.reports
  if (!reps.length) return <div className="card pad"><Empty icon={Globe2}>Respublika PDF'i hali yuklanmagan. «Ma'lumot yuklash» → «Respublika dinamikasi» bo'limidan yuklang.</Empty></div>
  const last = reps[reps.length - 1]
  const prev = reps.length > 1 ? reps[reps.length - 2] : null
  const kun = mode === 'kunlik' && !!prev
  const dates = [...new Set(reps.flatMap((r) => (kun ? [r.end] : [r.start, r.end])).filter(Boolean))].sort()
  const labels = dates.map(dm)
  // har bir hisobotdan ikki nuqta: oy boshi (qiymat − dinamika) va oxirgi sana
  const line = (n, i) => {
    const v = Object.fromEntries(dates.map((x) => [x, null]))
    reps.forEach((r) => {
      const c = cellOf(r, n, i)
      if (!c || c.v === null || c.v === undefined) return
      v[r.end] = c.v
      if (!kun && r.start && v[r.start] === null && c.d !== null && c.d !== undefined) v[r.start] = c.v - c.d
    })
    return dates.map((x) => v[x])
  }
  const val = (n, i) => cellOf(last, n, i)
  const dOf = (n, i) => { const c = val(n, i), q = prev && cellOf(prev, n, i); return kun ? (c && q && c.v != null && q.v != null ? c.v - q.v : null) : c?.d }
  const kp = (icon, label, n, i, bad, tone, sub) => { const c = val(n, i); return c ? <Kpi icon={icon} label={label} value={c.v || 0} d={dOf(n, i)} bad={bad} tone={tone} sub={sub} /> : null }
  const pg = (n) => last.pages.find((p) => p.n === n)
  const prevRow = (n, name) => prev?.pages.find((p) => p.n === n)?.rows?.find((r) => r.name === name)
  const rowsOf = (n, i) => (pg(n)?.rows || []).map((r) => {
    const d = kun ? (prevRow(n, r.name)?.cells[i]?.v != null && r.cells[i]?.v != null ? r.cells[i].v - prevRow(n, r.name).cells[i].v : null) : r.cells[i]?.d
    return { name: r.name, value: r.cells[i]?.v || 0, sub: d ? ` ${d > 0 ? '+' : '−'}${num(Math.abs(d))}` : '' }
  })
  const sortDesc = (a) => [...a].sort((p, q) => q.value - p.value)
  const obxPct = (pg(6)?.rows || []).map((r) => ({ name: r.name, value: parseFloat((r.cells[2]?.p || '0').replace(',', '.')) || 0 })).filter((r) => r.value > 0).sort((a, b) => a.value - b.value)
  const j = (n, i) => val(n, i)?.v || 0
  const p2pct = val(2, 2)?.p
  return (
    <>
      <div className="home-bar"><CalendarDays size={16} />Respublika dinamikasi: <b>{dmy(last.start)} – {dmy(last.end)}</b><span className="grow" /><div className="seg"><button className={mode === 'oy' ? 'on' : ''} onClick={() => setMode('oy')}>Oy boshidan</button><button className={mode === 'kunlik' ? 'on' : ''} onClick={() => setMode('kunlik')} title="Oxirgi ikki PDF farqi">Kunlik</button></div>
        <span className="mut">{reps.length} ta PDF • ↑↓ {kun ? `${dmy(prev.end)} ga nisbatan` : mode === 'kunlik' ? 'kunlik uchun 2-PDF kerak' : 'oy boshidan'}</span></div>
      <div className="kpis">
        {kp(Server, 'Dasturdagi TP / konsentratorlar', 1, 0, false, 'blue')}
        {kp(Layers, 'CAS ga yuklangan', 1, 1, false, 'cyan')}
        {kp(Wifi, 'Online', 1, 2, false, 'green')}
        {kp(WifiOff, 'Offline', 1, 3, true, 'red', `3 kundan ortiq: ${num(j(1, 4))}`)}
        {kp(Unplug, 'Aloqadan chiqib ketgan hisoblagichlar', 2, 1, true, 'red', p2pct)}
        {kp(Activity, 'Tarmoqdan uzilgan hisoblagichlar', 3, 1, true, 'amber', val(3, 2)?.p)}
        {kp(Gauge, 'Obxod olgan hisoblagichlar', 6, 1, false, 'green', val(6, 2)?.p)}
        {kp(Zap, 'Billing va CAS tafovuti', 8, 0, true, 'purple')}
      </div>

      <div className="grid2">
        <Card icon={TrendingUp} title="Online konsentratorlar" sub={kun ? 'kunlik' : 'oy boshidan'}><LineChart labels={labels} series={[{ name: 'Online', color: '#16a34a', values: line(1, 2) }]} /></Card>
        <Card icon={TrendingUp} title="Offline konsentratorlar"><LineChart labels={labels} zero series={[{ name: 'Offline (jami)', color: '#e31e24', values: line(1, 3) }, { name: '3 kundan ortiq', color: '#f59e0b', values: line(1, 4) }]} /></Card>
        <Card icon={TrendingUp} title="Aloqadan chiqib ketgan hisoblagichlar"><LineChart labels={labels} series={[{ name: 'Jami', color: '#e31e24', values: line(2, 1) }]} /></Card>
        <Card icon={TrendingUp} title="Tarmoqdan uzilgan hisoblagichlar"><LineChart labels={labels} series={[{ name: 'Jami', color: '#f59e0b', values: line(3, 1) }]} /></Card>
        <Card icon={TrendingUp} title="Obxod olgan hisoblagichlar"><LineChart labels={labels} series={[{ name: 'Obxod olgan', color: '#0891b2', values: line(6, 1) }]} /></Card>
        <Card icon={TrendingUp} title="Billing va CAS tafovuti"><LineChart labels={labels} series={[{ name: 'Jami tafovut', color: '#8b5cf6', values: line(8, 0) }]} /></Card>
      </div>

      <div className="grid3">
        <Card icon={PieChart} title="Konsentratorlar obxod darajasi" sub={dmy(last.end)}>
          <Donut sub="konsentrator" items={[{ name: '0%', value: j(1, 5), color: '#e31e24' }, { name: '1-30%', value: j(1, 6), color: '#f97316' }, { name: '30-50%', value: j(1, 7), color: '#f59e0b' }, { name: '50-80%', value: j(1, 8), color: '#84cc16' }, { name: '80-100%', value: j(1, 9), color: '#16a34a' }]} />
        </Card>
        <Card icon={PieChart} title="Aloqadan chiqqanlar: iste'molchi turi" sub={dmy(last.end)}>
          <Donut sub="hisoblagich" items={[{ name: 'Aholi', value: j(2, 3), color: '#16a34a' }, { name: 'Ulgurji', value: j(2, 4), color: '#1d6fff' }, { name: 'Balans', value: j(2, 5), color: '#f59e0b' }]} />
        </Card>
        <Card icon={BarChart3} title="Aloqadan chiqqanlar: vaqt kesimi">
          <ColBars items={[{ name: '7-30 kun', value: j(2, 6), color: '#f59e0b' }, { name: '1-3 oy', value: j(2, 7), color: '#e31e24' }, { name: '3 oydan ortiq', value: j(2, 8), color: '#9f1239' }]} />
        </Card>
      </div>

      <div className="grid3">
        <Card icon={MapPinned} title="Tumanlar: aloqadan chiqib ketgan hisoblagichlar" sub="eng ko'pdan"><HBars color="#e31e24" items={sortDesc(rowsOf(2, 1))} /></Card>
        <Card icon={MapPinned} title="Tumanlar: tarmoqdan uzilganlar"><HBars color="#f59e0b" items={sortDesc(rowsOf(3, 1))} /></Card>
        <Card icon={MapPinned} title="Tumanlar: obxod olish foizi" sub="eng pastdan"><HBars color="#0891b2" unit="%" max={100} items={obxPct} /></Card>
      </div>
    </>
  )
}

export default function Home() {
  const { can } = useAuth()
  const [sp, setSp] = useSearchParams()
  const tabs = [
    (can('view.konsentrator') || can('view.aloqa') || can('view.obxod')) && { k: 'kunlik', label: 'Kunlik dinamika', icon: Table2 },
    can('republic.view') && { k: 'respublika', label: 'Respublika dinamikasi', icon: Globe2 },
  ].filter(Boolean)
  if (!tabs.length) return <div className="home-blank" />
  const tab = tabs.find((t) => t.k === sp.get('t'))?.k || tabs[0].k
  return (
    <div className="home">
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.k} role="tab" aria-selected={t.k === tab} className={`tab ${t.k === tab ? 'on' : ''}`} onClick={() => setSp({ t: t.k }, { replace: true })}>
            <t.icon size={18} /><span>{t.label}</span></button>))}
      </div>
      {tab === 'kunlik' ? <Daily key="d" /> : <Republic key="r" />}
    </div>
  )
}
