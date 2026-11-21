import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe2, GitCompareArrows, CalendarRange, FileText, FileSpreadsheet, FileDown, Send, RefreshCw, UploadCloud, FileBarChart2 } from 'lucide-react'
import { api, download, qs } from '../api'
import { useAuth } from '../auth'
import { Empty, Spinner, useToast } from '../ui'
import { dmy, num } from '../fmt'
import { SendModal } from './Republic'

const G = 9
const BAR = { 4: 'ag-b4', 7: 'ag-b7', 8: 'ag-b7' }                      // foizli chiziqcha: guruh → rang sinfi
const VAL_T = ['ag-grn', 'ag-grn', 'ag-grn', 'ag-grn', 'ag-red', 'ag-dkr', 'ag-dkr', 'ag-red', 'ag-red']
const VAL_D = ['', '', '', '', 'ag-red', 'ag-big', 'ag-big', 'ag-red', 'ag-red']

const Dl = ({ cur, base, g }) => {
  const dv = (cur[`c${g}`] || 0) - (base[`c${g}`] || 0)
  if (!dv) return null
  return <span className={`agd ${dv > 0 ? 'up' : 'dn'}`}><b>{dv > 0 ? '↑' : '↓'}</b>{dv > 0 ? num(dv) : `-${num(Math.abs(dv))}`}</span>
}

function AgTable({ d }) {
  const mx = useMemo(() => Object.fromEntries(Object.keys(BAR).map((g) => [g, Math.max(0, ...d.rows.map((r) => r.cur[`c${g}`] || 0))])), [d])
  return (
    <table className="ag-table">
      <thead>
        <tr>
          <th rowSpan={3} className="agh ag-nm">Hudud</th>
          <th colSpan={8} rowSpan={2} className="agh ag-big">CAS dasturidagi hodisalar</th>
          <th colSpan={6} className="agh ag-red ag-s">Aloqadan chiqib ketgan hisoblagichlar</th>
          <th colSpan={2} rowSpan={3} className="agh ag-red ag-m">Kirish va chiqish simlari tutashtirilgan <i className="ag-sky">(перемичка)</i></th>
          <th colSpan={2} rowSpan={3} className="agh ag-red ag-m">Aloqaga chiqmagan hisoblagichlar</th>
        </tr>
        <tr>
          <th colSpan={2} rowSpan={2} className="agh ag-s">Jami Soni</th>
          <th colSpan={4} className="agh ag-pk ag-it ag-s">shundan</th>
        </tr>
        <tr>
          <th colSpan={2} className="agh ag-xs">Kirish va chiqish <b className="ag-rd">quvvati</b> orasidagi nomutanosiblik</th>
          <th colSpan={2} className="agh ag-s">Hisoblagich qutisi ochilgan</th>
          <th colSpan={2} className="agh ag-s">Klemmasi ochilgan</th>
          <th colSpan={2} className="agh ag-s">Kuchlanishsiz tok oqib o'tayotgan</th>
          <th colSpan={2} className="agh ag-pk ag-it ag-s">1-3 oy</th>
          <th colSpan={2} className="agh ag-pk ag-it ag-s">3 oydan ortiq</th>
        </tr>
      </thead>
      <tbody>
        <tr className="ag-total">
          <td className="ag-name">Jami</td>
          {Array.from({ length: G }, (_, g) => [
            <td key={`v${g}`} className={`ag-v ${VAL_T[g]}`}>{d.cur[`c${g}`] ? num(d.cur[`c${g}`]) : '-'}</td>,
            <td key={`d${g}`} className="ag-dl"><Dl cur={d.cur} base={d.base} g={g} /></td>])}
        </tr>
        {d.rows.map((r) => (
          <tr key={r.id}>
            <td className="ag-name">{r.name}</td>
            {Array.from({ length: G }, (_, g) => {
              const v = r.cur[`c${g}`] || 0
              const p = BAR[g] && mx[g] > 0 ? Math.max((v / mx[g]) * 100, 1) : 0
              return [
                <td key={`v${g}`} className={`ag-v ${VAL_D[g]} ${BAR[g] && v ? BAR[g] : ''}`} style={p ? { '--p': p } : undefined}><span>{v ? num(v) : ''}</span></td>,
                <td key={`d${g}`} className="ag-dl"><Dl cur={r.cur} base={r.base} g={g} /></td>]
            })}
          </tr>))}
      </tbody>
    </table>
  )
}

export default function Ag() {
  const { can } = useAuth()
  const toast = useToast()
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [send, setSend] = useState(false)
  const [busy, setBusy] = useState('')
  const [mode, setMode] = useState('oy')
  const load = () => {
    setErr('')
    api.get(`/ag/compare${qs({ a, b, mode })}`).then((d) => { setData(d); if (!b) setB(d.b); if (!a && d.a) setA(d.a) }).catch((e) => { setErr(e.message); setData(null) })
  }
  useEffect(() => { load() }, [a, b, mode])
  const pick = (m) => { if (m !== mode) { setA(''); setMode(m) } }
  const dl = async (fmt) => {
    setBusy(fmt)
    try { await download(`/ag/download${qs({ fmt, a, b, mode })}`, `AG_dinamikasi.${fmt === 'xlsx' ? 'xlsx' : 'pdf'}`) } catch (e) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const dates = data?.dates || []
  return (
    <div className="dyn rep ag">
      <div className="card head-card">
        <div className="titles">
          <h2 className="ttl">{data?.title || "24.02.2023 dagi № 01-04-42-22 sonli topshiriq ijrosi bo'yicha"}</h2>
          <div className="ag-mal">Ma'lumot</div>
        </div>
        <div className="filters">
          <label className="filter"><span><Globe2 size={15} />Hudud nomi:</span><b className="static-box">{data?.region || 'Qashqadaryo HETK'}</b></label>
          <div className="seg" role="tablist" aria-label="Farq turi">
            <button role="tab" aria-selected={mode === 'oy'} className={mode === 'oy' ? 'on' : ''} onClick={() => pick('oy')}><CalendarRange size={15} />Boshidan</button>
            <button role="tab" aria-selected={mode === 'kunlik'} className={mode === 'kunlik' ? 'on' : ''} onClick={() => pick('kunlik')}><GitCompareArrows size={15} />Kunlik</button>
          </div>
          {dates.length > 0 && mode === 'oy' && (<label className="filter"><span><CalendarRange size={16} />Sana:</span>
            <select value={data?.b || ''} onChange={(e) => setB(e.target.value)}>{dates.map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
            <button className="icon-btn" title="Yangilash" onClick={load}><RefreshCw size={16} /></button></label>)}
          {dates.length > 1 && mode === 'kunlik' && (<label className="filter"><span><GitCompareArrows size={16} />Solishtirish:</span>
            <select value={data?.a || ''} onChange={(e) => setA(e.target.value)}>
              {dates.filter((d) => !data || d < data.b).map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
            <b>→</b>
            <select value={data?.b || ''} onChange={(e) => { setB(e.target.value); setA('') }}>{dates.map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
            <button className="icon-btn" title="Yangilash" onClick={load}><RefreshCw size={16} /></button></label>)}
          <div className="spacer" />
          {can('report.download') && data && (<>
            <button className="btn ghost" disabled={!!busy} onClick={() => dl('pdf')}><FileText size={16} />PDF</button>
            <button className="btn ghost" disabled={!!busy} onClick={() => dl('xlsx')}><FileSpreadsheet size={16} />Excel</button>
            <button className="btn ghost" hidden={!can('ag.original')} disabled={!!busy} title="AG markazi yuborgan asl PDF fayl" onClick={() => dl('orig')}><FileDown size={16} />Asl PDF</button></>)}
          {can('telegram.send') && data && <button className="btn primary" onClick={() => setSend(true)}><Send size={16} />Telegramga yuborish</button>}
        </div>
      </div>
      {err ? (
        <div className="card pad"><Empty icon={FileBarChart2}>{err}{can('ag.upload') && <div style={{ marginTop: 10 }}><Link className="btn primary" to="/yuklash?t=ag"><UploadCloud size={16} />PDF yuklash</Link></div>}</Empty></div>
      ) : !data ? <Spinner /> : mode === 'kunlik' && !data.a ? (
        <div className="card pad"><Empty icon={GitCompareArrows}>Kunlik solishtirish uchun kamida ikkita sananing PDF'i kerak — hozir faqat bitta ({dmy(data.b)}) yuklangan.
          {can('ag.upload') && <div style={{ marginTop: 10 }}><Link className="btn primary" to="/yuklash?t=ag"><UploadCloud size={16} />Yangi PDF yuklash</Link></div>}</Empty></div>
      ) : (
        <div className="card tcard">
          <div className="ag-farq">Farq: <b>{dmy(data.from)} - {dmy(data.to)}</b></div>
          <div className="tbl-scroll"><AgTable d={data} /></div>
          <div className="note">{data.a ? <>Kunlik farq (↑↓): oxirgi ikki yuklangan PDF — <b>{dmy(data.a)}</b> bilan <b>{dmy(data.b)}</b> o'rtasidagi o'zgarish.</> : <>Farq (↑↓): boshlang'ich sana <b>{dmy(data.start)}</b> dan <b>{dmy(data.b)}</b> gacha (AG PDF'i bo'yicha). Oxirgi ikki PDF'ni solishtirish uchun «Kunlik» ni tanlang.</>}</div>
        </div>)}
      {send && data && <SendModal a={data.a} b={data.b} mode={mode} base="/ag" title="AG dinamikasini Telegram'ga yuborish" origHint="AG markazi yuborgan fayl, o'zgartirishsiz" onClose={() => setSend(false)} />}
    </div>
  )
}
