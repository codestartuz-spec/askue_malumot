// Respublika va AG dinamikasi uchun umumiy qismlar: holat (hook), filtrlar paneli, bo'sh holat xabarlari.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe2, GitCompareArrows, CalendarRange, FileText, FileSpreadsheet, FileDown, Send, RefreshCw, UploadCloud } from 'lucide-react'
import { api, download, qs } from '../api'
import { useAuth } from '../auth'
import { Empty, useToast } from '../ui'
import { dmy } from '../fmt'

/** base: '/republic' | '/ag'. Qaytaradi: holat va amallar. */
export function usePdfDyn(base, fileLabel) {
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
    api.get(`${base}/compare${qs({ a, b, mode })}`).then((d) => { setData(d); if (!b) setB(d.b); if (!a && d.a) setA(d.a) }).catch((e) => { setErr(e.message); setData(null) })
  }
  useEffect(() => { load() }, [a, b, mode]) // eslint-disable-line
  const pick = (m) => { if (m !== mode) { setA(''); setMode(m) } }
  const dl = async (fmt) => {
    setBusy(fmt)
    try { await download(`${base}/download${qs({ fmt, a, b, mode })}`, `${fileLabel}.${fmt === 'xlsx' ? 'xlsx' : 'pdf'}`) } catch (e) { toast(e.message, 'err') } finally { setBusy('') }
  }
  return { a, setA, b, setB, data, err, send, setSend, busy, mode, load, pick, dl, dates: data?.dates || [] }
}

/** Hudud nomi, rejim, sana tanlash, yuklab olish va Telegram tugmalari. */
export function PdfFilters({ st, region, perm, firstLabel, origHint }) {
  const { can } = useAuth()
  const { data, mode, dates, busy } = st
  return (
    <div className="filters">
      <label className="filter"><span><Globe2 size={15} />Hudud nomi:</span><b className="static-box">{region}</b></label>
      <div className="seg" role="tablist" aria-label="Dinamika turi">
        <button role="tab" aria-selected={mode === 'oy'} className={mode === 'oy' ? 'on' : ''} onClick={() => st.pick('oy')}><CalendarRange size={15} />{firstLabel}</button>
        <button role="tab" aria-selected={mode === 'kunlik'} className={mode === 'kunlik' ? 'on' : ''} onClick={() => st.pick('kunlik')}><GitCompareArrows size={15} />Kunlik</button>
      </div>
      {dates.length > 0 && mode === 'oy' && (<label className="filter"><span><CalendarRange size={16} />Sana:</span>
        <select value={data?.b || ''} onChange={(e) => st.setB(e.target.value)}>{dates.map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
        <button className="icon-btn" title="Yangilash" onClick={st.load}><RefreshCw size={16} /></button></label>)}
      {dates.length > 1 && mode === 'kunlik' && (<label className="filter"><span><GitCompareArrows size={16} />Solishtirish:</span>
        <select value={data?.a || ''} onChange={(e) => st.setA(e.target.value)}>
          {dates.filter((d) => !data || d < data.b).map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
        <b>→</b>
        <select value={data?.b || ''} onChange={(e) => { st.setB(e.target.value); st.setA('') }}>{dates.map((d) => <option key={d} value={d}>{dmy(d)}</option>)}</select>
        <button className="icon-btn" title="Yangilash" onClick={st.load}><RefreshCw size={16} /></button></label>)}
      <div className="spacer" />
      {can('report.download') && data && (<>
        <button className="btn ghost" disabled={!!busy} onClick={() => st.dl('pdf')}><FileText size={16} />PDF</button>
        <button className="btn ghost" disabled={!!busy} onClick={() => st.dl('xlsx')}><FileSpreadsheet size={16} />Excel</button>
        <button className="btn ghost" hidden={!can(`${perm}.original`)} disabled={!!busy} title={origHint} onClick={() => st.dl('orig')}><FileDown size={16} />Asl PDF</button></>)}
      {can('telegram.send') && data && <button className="btn primary" onClick={() => st.setSend(true)}><Send size={16} />Telegramga yuborish</button>}
    </div>
  )
}

/** Jadval o'rniga xabar ko'rsatish kerakmi (xato yoki kunlik rejimda bitta PDF). */
export const isBlocked = (st) => !!st.err || (st.mode === 'kunlik' && !!st.data && !st.data.a)

/** Xato / bitta PDF bo'lgandagi bo'sh holat xabari. */
export function PdfEmpty({ st, perm, tab, icon }) {
  const { can } = useAuth()
  const { data, err, mode } = st
  const upload = (label) => can(`${perm}.upload`) && <div style={{ marginTop: 10 }}><Link className="btn primary" to={`/yuklash?t=${tab}`}><UploadCloud size={16} />{label}</Link></div>
  if (err) return <div className="card pad"><Empty icon={icon}>{err}{upload('PDF yuklash')}</Empty></div>
  if (data && mode === 'kunlik' && !data.a) {
    return <div className="card pad"><Empty icon={GitCompareArrows}>Kunlik solishtirish uchun kamida ikkita sananing PDF'i kerak — hozir faqat bitta ({dmy(data.b)}) yuklangan.{upload('Yangi PDF yuklash')}</Empty></div>
  }
  return null
}
