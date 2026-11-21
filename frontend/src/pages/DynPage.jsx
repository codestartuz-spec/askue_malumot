import { useEffect, useMemo, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Search, MapPin, MapPinned, CalendarRange, List, RefreshCw, ArrowLeft, Users } from 'lucide-react'
import { api, download, qs } from '../api'
import { useAuth } from '../auth'
import { TABLES, METRIC_TITLES } from '../tables'
import { Empty, Modal, Pager, Spinner, useCountUp, useDebounced, useToast } from '../ui'
import { dmy, num, pct } from '../fmt'

// Asl PDF'dagi och sariq «soni» ustunlari (1-asosli tartib raqami)
const CREAM = { konsentrator: new Set([7, 9, 11, 13, 15]), aloqa: new Set([1, 10, 12, 14, 16]) }

const POL = {
  bad: { up: 'red', down: 'blue' },
  mid: { up: 'blue', down: 'red' },
  good: { up: 'green', down: 'red' },
}

export function Delta({ v, pol }) {
  if (v === null || v === undefined || v === 0) return null
  const up = v > 0
  return <span className={`delta ${POL[pol][up ? 'up' : 'down']}`}><b>{up ? '↑' : '↓'}</b>{up ? num(v) : `-${num(Math.abs(v))}`}</span>
}

function Pin({ r }) {
  const { can } = useAuth()
  if (!can('map.view') || r.lat == null) return <td />
  const url = `https://www.google.com/maps/dir/?api=1&destination=${r.lat},${r.lon}&travelmode=driving`
  return <td><a className="icon-btn pin-btn" href={url} target="_blank" rel="noopener noreferrer" title="Google Maps'da ochish (yo'nalish)"><MapPinned size={17} /></a></td>
}

function DrillModal({ kind, metric, espId, brigadeId, scope, onClose }) {
  const { can } = useAuth()
  const toast = useToast()
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const dq = useDebounced(q)
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const size = 50
  useEffect(() => { setPage(1) }, [dq])
  useEffect(() => {
    const ac = new AbortController()
    setBusy(true)
    api.get(`/drill/${kind}${qs({ metric, esp_id: espId, brigade_id: brigadeId, q: dq, page, size })}`, ac.signal)
      .then((d) => { setData(d); setBusy(false) })
      .catch((e) => { if (e.name !== 'AbortError') { toast(e.message, 'err'); setBusy(false) } })
    return () => ac.abort()
  }, [kind, metric, espId, brigadeId, dq, page])
  const nav = useNavigate()
  const toMap = () => nav(`/xarita${qs({ metric, esp: espId, brig: brigadeId })}`)
  const exp = async () => {
    try { await download(`/drill/${kind}${qs({ metric, esp_id: espId, brigade_id: brigadeId, q: dq, export: true, name: `${METRIC_TITLES[metric]} — ${scope}` })}`, 'royxat.xlsx') }
    catch (e) { toast(e.message, 'err') }
  }
  const off = (page - 1) * size
  return (
    <Modal wide icon={List} title={`${METRIC_TITLES[metric]} — ${scope}`} onClose={onClose}
      footer={<>
        <div className="foot-info">{data ? `Jami: ${num(data.total)} ta` : ''}</div>
        {can('export') && <button className="btn ghost" onClick={exp}><Download size={16} />Excel</button>}
        {data && <Pager page={page} size={size} total={data.total} onPage={setPage} />}
      </>}>
      <div className="searchbar"><Search size={17} />
        <input placeholder={kind === 'meters' ? 'Hisoblagich raqami, hisob raqam, abonent yoki manzil…' : 'TP, DCU, podstansiya yoki fider…'} value={q} onChange={(e) => setQ(e.target.value)} />
        {busy && <RefreshCw size={16} className="spin" />}
      </div>
      <div className="tbl-scroll">
        {!data ? <Spinner /> : data.items.length === 0 ? <Empty icon={Search}>Hech narsa topilmadi</Empty> : kind === 'tr' ? (
          <table className="list">
            <thead><tr><th>№</th><th>Tuman</th><th>TP</th><th>Podstansiya</th><th>Fider</th><th>DCU</th><th>Brigada</th><th>Holati</th><th>Obxod %</th><th></th></tr></thead>
            <tbody>{data.items.map((r, i) => (
              <tr key={r.id}><td className="mut">{off + i + 1}</td><td>{r.esp}</td><td className="b">{r.tp_no}</td><td>{r.substation}</td><td>{r.feeder}</td>
                <td className="mono">{r.dcu}</td><td>{r.brigade || <em className="warn">Biriktirilmagan</em>}</td>
                <td>{r.state === 1 ? <span className="tag green">Online</span> : r.state === 2 ? <span className="tag red">Offline</span> : ''}</td>
                <td>{r.obx_level ?? ''}</td><Pin r={r} /></tr>))}</tbody>
          </table>
        ) : (
          <table className="list">
            <thead><tr><th>№</th><th>Tuman</th><th>Brigada</th><th>TP</th><th>Hisob raqam</th><th>Hisoblagich</th><th>Abonent</th><th>Manzil</th><th>Turi</th><th>Oxirgi obxod</th><th>Kun</th><th></th></tr></thead>
            <tbody>{data.items.map((r, i) => (
              <tr key={r.meter_no}><td className="mut">{off + i + 1}</td><td>{r.esp}</td><td>{r.brigade || <em className="warn">Biriktirilmagan</em>}</td><td>{r.tp_no}</td>
                <td className="mono">{r.account}</td><td className="mono b">{r.meter_no}</td><td>{r.name}</td><td>{r.address}</td>
                <td><span className={`tag ${r.ctype === 2 ? 'green' : r.ctype === 1 ? 'blue' : 'amber'}`}>{r.ctype_name}</span></td>
                <td>{r.last_poll || ''}</td><td>{r.days ?? ''}</td><Pin r={r} /></tr>))}</tbody>
          </table>
        )}
      </div>
    </Modal>
  )
}

export function Cell({ col, row, onDrill, canDrill, total, cream }) {
  const cur = row.cur, base = row.base
  if (col.t === 'n') {
    const v = cur[col.m]
    const shown = total ? <CountNum v={v} /> : num(v)
    return (
      <td className={`c-${col.cls.split(' ').join(' c-')} ${cream ? 'cream' : ''}`}>
        {v > 0 && canDrill ? <button className="numlink" onClick={() => onDrill(col)}>{shown}</button> : (v > 0 ? shown : '')}
      </td>
    )
  }
  if (col.t === 't') return <td className="c-pct">{cur[col.m] || ''}</td>
  if (col.t === 'p') {
    const a = cur[col.num], b = cur[col.den]
    const k = b > 0 ? a / b : null
    const shade = col.num.endsWith('polled') && k !== null && k < 0.97 ? { background: `rgba(227,30,36,${Math.min(0.28, (0.97 - k) * 1.6)})` } : undefined
    return <td className="c-pct" style={shade}>{pct(a, b)}</td>
  }
  const v = base ? cur[col.m] - base[col.m] : null
  return <td className="c-d"><Delta v={v} pol={col.pol} /></td>
}
const CountNum = ({ v }) => num(useCountUp(v))

export default function DynPage({ table, esp, setEsp, from, setFrom, to, setTo, tabs, actions }) {
  const cfg = TABLES[table]
  const { boot, can } = useAuth()
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [drill, setDrill] = useState(null)
  const [tick, setTick] = useState(0)
  const [loading, setLoading] = useState(true)
  const lastTable = useRef(table)

  useEffect(() => {
    const ac = new AbortController()
    setErr('')
    setLoading(true)
    if (lastTable.current !== table) { setData(null); lastTable.current = table }
    api.get(`/dynamics${qs({ table, esp_id: esp, date_from: from, date_to: to })}`, ac.signal)
      .then((x) => { setData(x); setLoading(false) }).catch((e) => { if (e.name !== 'AbortError') { setErr(e.message); setLoading(false) } })
    return () => ac.abort()
  }, [table, esp, from, to, tick])

  const espName = data?.esp?.label || boot?.region_name || ''
  const dates = data?.dates || []
  const byBrigade = !!esp
  const rows = data?.rows || []
  const canDrill = can('drill.view')

  const openDrill = (col, row) => {
    const isTotal = !row
    setDrill({
      kind: cfg.drill, metric: col.m,
      espId: byBrigade ? Number(esp) : (isTotal ? undefined : row.id),
      brigadeId: byBrigade && row ? row.id : undefined,
      scope: byBrigade ? `${espName}${row ? ', ' + row.name : ''}` : (isTotal ? (boot?.region_name || '') : row.name),
    })
  }
  const totalRow = useMemo(() => data?.total ? { cur: data.total.cur, base: data.total.base } : null, [data])

  return (
    <div className="dyn">
      {tabs}
      <div className="card head-card">
        <div className="titles">
          <h2 className="ttl">{espName} {cfg.title}</h2>
          <div className="dinamika">{'DINAMIKA'.split('').join(' ')}</div>
        </div>
        <div className="filters">
          <label className="filter">
            <span><MapPin size={15} />Hudud nomi:</span>
            <select value={esp} onChange={(e) => setEsp(e.target.value)}>
              <option value="">Barcha tumanlar</option>
              {boot.esps.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
          </label>
          {esp && <button className="btn ghost sm" onClick={() => setEsp('')}><ArrowLeft size={15} />Barcha tumanlar</button>}
          <div className="spacer" />
          <div className="dyn-range">
            <CalendarRange size={16} /><span>Dinamika:</span>
            {can('dynamics.compare') && dates.length > 1 ? (<>
              <select value={data?.base || ''} onChange={(e) => setFrom(e.target.value)}>
                {dates.filter((d) => !data?.to || d < data.to).map((d) => <option key={d} value={d}>{dmy(d)}</option>)}
              </select><b>–</b>
              <select value={data?.to || ''} onChange={(e) => setTo(e.target.value)}>
                {dates.map((d) => <option key={d} value={d}>{dmy(d)}</option>)}
              </select>
            </>) : <b>{data?.base ? `${dmy(data.base)} – ${dmy(data.to)}` : data?.to ? dmy(data.to) : ''}</b>}
            <button className="icon-btn" title="Yangilash" onClick={() => setTick((t) => t + 1)}><RefreshCw size={16} /></button>
          </div>
          {actions?.(data)}
        </div>
      </div>

      <div className={`card tcard ${loading && data ? 'busy' : ''}`}>
        {err ? <div className="pad denied">{err}</div> : !data ? <Spinner /> : rows.length === 0 ? (
          <Empty icon={CalendarRange}>Hali ma'lumot yuklanmagan. Sadmin «Ma'lumot yuklash» bo'limidan fayllarni yuklaydi.</Empty>
        ) : (
          <div className="tbl-scroll">
            <table className={`dyn-table t-${table}`}>
              <thead>
                {cfg.head.map((hr, i) => (
                  <tr key={i}>{hr.map((h, j) => (
                    <th key={j} rowSpan={h.rs} colSpan={h.cs} className={(h.c || '').split(' ').map((c) => 'h-' + c).join(' ')}><span>{h.l}</span></th>))}</tr>))}
              </thead>
              <tbody>
                <tr className="total">
                  <td className="name">Jami</td>
                  {cfg.cols.map((c, i) => <Cell key={i} col={c} row={totalRow} total canDrill={canDrill} onDrill={(col) => openDrill(col, null)} />)}
                </tr>
                {rows.map((r, ri) => (
                  <tr key={r.id} >
                    <td className={`name ${!byBrigade ? 'link' : ''} ${r.id === 0 && byBrigade ? 'warn' : ''}`}>
                      {!byBrigade ? <button onClick={() => setEsp(String(r.id))}>{r.name}</button> : <>{r.name}{r.members?.length > 0 && <small className="staff"><Users size={11} />{r.members.join(', ')}</small>}</>}
                    </td>
                    {cfg.cols.map((c, i) => <Cell key={i} col={c} row={r} cream={CREAM[table]?.has(i + 1)} canDrill={canDrill} onDrill={(col) => openDrill(col, r)} />)}
                  </tr>))}
              </tbody>
            </table>
          </div>
        )}
        {data?.base === null && rows.length > 0 && <div className="note">Dinamika (↑↓) ko'rinishi uchun kamida ikki xil sanadagi ma'lumot yuklangan bo'lishi kerak.</div>}
        {!byBrigade && rows.length > 0 && <div className="note">Tuman nomiga bosing — o'sha tuman brigadalar kesimida ochiladi. Raqam ustiga bosing — nomma-nom ro'yxat chiqadi (oxirgi yuklangan ma'lumot bo'yicha).</div>}
      </div>
      {drill && <DrillModal {...drill} onClose={() => setDrill(null)} />}
    </div>
  )
}
