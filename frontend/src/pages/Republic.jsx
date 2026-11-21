import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe2, GitCompareArrows, CalendarRange, Download, FileText, FileSpreadsheet, FileDown, Send, ArrowUp, ArrowDown, RefreshCw, UploadCloud, Megaphone, Users, AlertTriangle, CheckCircle2, MailCheck } from 'lucide-react'
import { api, download, qs } from '../api'
import { useAuth } from '../auth'
import { ChatTable, Empty, Modal, Spinner, useToast } from '../ui'
import { dmy, num } from '../fmt'
import { Cell } from './DynPage'

const Diff = ({ v, bad = true }) => {
  if (v === null || v === undefined || v === 0) return <span className="mut">—</span>
  const up = v > 0
  return <span className={`delta ${up ? 'red' : 'blue'}`}>{up ? <ArrowUp size={13} strokeWidth={3} /> : <ArrowDown size={13} strokeWidth={3} />}{num(Math.abs(v))}</span>
}
const pdfD = (v) => (v === null || v === undefined || v === 0) ? '' : <span className={`pdfd ${v > 0 ? 'up' : 'dn'}`}>{v > 0 ? '↑' : '↓'} {num(Math.abs(v))}</span>

function SendModal({ a, b, mode, onClose }) {
  const { can } = useAuth()
  const toast = useToast()
  const [chats, setChats] = useState(null)
  const [fmts, setFmts] = useState(new Set(['pdf']))
  const [sel, setSel] = useState(new Set())
  const [job, setJob] = useState(null)
  const [ack, setAck] = useState(true)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)
  useEffect(() => { api.get('/telegram/chats').then(setChats).catch((e) => { toast(e.message, 'err'); setChats([]) }); return () => clearInterval(timer.current) }, [])
  const tg = (setter, k) => setter((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const poll = (id) => {
    clearInterval(timer.current)
    timer.current = setInterval(async () => {
      try {
        const j = await api.get(`/reports/send/${id}`)
        setJob(j)
        if (j.status !== 'running') { clearInterval(timer.current); setBusy(false); if (j.status === 'done') toast('Yuborish yakunlandi') }
      } catch { /* */ }
    }, 1200)
  }
  const go = async () => {
    setBusy(true)
    try { const r = await api.post('/republic/send', { fmts: [...fmts], chat_ids: [...sel], a, b, mode, ack }); setJob({ status: 'running', progress: 0, log: '' }); poll(r.id) }
    catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  return (
    <Modal wide icon={Send} title="Respublika dinamikasini Telegram'ga yuborish" onClose={busy ? () => {} : onClose}
      footer={<><div className="foot-info">{fmts.size} ta fayl{sel.size ? ` → ${sel.size} ta kanal` : ''}</div>
        <button className="btn ghost" onClick={onClose} disabled={busy}>Yopish</button>
        <button className="btn primary" disabled={busy || !fmts.size || !sel.size} onClick={go}><Send size={16} />Yuborish</button></>}>
      <div className="send-grid">
        <div>
          <div className="mp-sec dark">1. Qaysi formatda</div>
          <div className="opts">
            <label className={`opt ${fmts.has('pdf') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('pdf')} onChange={() => tg(setFmts, 'pdf')} disabled={busy} /><i><FileText size={20} /></i><span><b>PDF</b><small>{dmy(b)} holatiga{a ? `, ${dmy(a)} bilan solishtirib` : ', oy boshidan dinamika'}</small></span></label>
            <label className={`opt ${fmts.has('orig') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('orig')} onChange={() => tg(setFmts, 'orig')} disabled={busy} /><i><FileDown size={20} /></i><span><b>Asl PDF</b><small>Respublika yuborgan fayl, o'zgartirishsiz</small></span></label>
            <label className={`opt ${fmts.has('xlsx') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('xlsx')} onChange={() => tg(setFmts, 'xlsx')} disabled={busy} /><i><FileSpreadsheet size={20} /></i><span><b>Excel</b><small>Jadval ko'rinishida</small></span></label>
          </div>
        </div>
        <div>
          <div className="mp-sec dark">2. Qaysi kanal yoki guruhga</div>
          {!chats ? <Spinner /> : chats.length === 0 ? (
            <div className="empty sm"><Megaphone size={30} /><div>Hali kanal yoki guruh qo'shilmagan.{can('settings.manage') ? <> <Link to="/sozlamalar" onClick={onClose}>Sozlamalar</Link> bo'limidan qo'shing.</> : " Sadmin'ga murojaat qiling."}</div></div>
          ) : (
            <ChatTable chats={chats} sel={sel} busy={busy} onToggle={(id) => tg(setSel, id)} onAll={(v) => setSel(v ? new Set(chats.map((c) => c.id)) : new Set())} />)}
        </div>
      </div>
      <label className={`ack-opt ${ack ? 'on' : ''}`}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
        <i><MailCheck size={18} /></i><span><b>«Tanishdim» tugmasi</b><small>Xabar tagida tugma chiqadi; kim va qachon bosgani «Xabar yuborish → Jurnal» bo'limida ko'rinadi</small></span></label>
      {job && (<div className="send-prog"><div className="progress"><div className="bar" style={{ width: `${job.progress}%` }} /><span>{Math.round(job.progress)}%</span></div>
        <div className="send-log">{job.log.split('\n').filter(Boolean).map((l, i) => (
          <div key={i} className={l.startsWith('✗') ? 'bad' : 'ok'}>{l.startsWith('✗') ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}<span>{l.slice(2)}</span></div>))}
          {job.status === 'running' && <div className="mut">Yuborilmoqda…</div>}</div></div>)}
    </Modal>
  )
}

export default function Republic() {
  const { can } = useAuth()
  const toast = useToast()
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [send, setSend] = useState(false)
  const [busy, setBusy] = useState('')
  const [pn, setPn] = useState(null)
  const [mode, setMode] = useState('oy')
  const load = () => {
    setErr('')
    api.get(`/republic/compare${qs({ a, b, mode })}`).then((d) => { setData(d); if (!b) setB(d.b); if (!a && d.a) setA(d.a) }).catch((e) => { setErr(e.message); setData(null) })
  }
  useEffect(() => { load() }, [a, b, mode])
  const pick = (m) => { if (m !== mode) { setA(''); setMode(m) } }
  const dl = async (fmt) => {
    setBusy(fmt)
    try { await download(`/republic/download${qs({ fmt, a, b, mode })}`, `Respublika_dinamikasi.${fmt === 'xlsx' ? 'xlsx' : 'pdf'}`) } catch (e) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const dates = data?.dates || []
  const cur = data ? (data.pages.find((p) => p.n === pn) || data.pages[0]) : null
  return (
    <div className="dyn rep">
      {data && cur && (
        <div className="tabs scroll" role="tablist">
          {data.pages.map((p) => (
            <button key={p.n} role="tab" aria-selected={p.n === cur.n} className={`tab ${p.n === cur.n ? 'on' : ''}`} onClick={() => setPn(p.n)}><span>{p.short}</span></button>))}
        </div>)}
      <div className="card head-card">
        <div className="titles">
          <h2 className="ttl">{cur ? `Qashqadaryo hududiy filiali ${cur.title}` : 'Respublika dinamikasi'}</h2>
          <div className="dinamika">{'DINAMIKA'.split('').join(' ')}</div>
        </div>
        <div className="filters">
          <label className="filter"><span><Globe2 size={15} />Hudud nomi:</span><b className="static-box">Qashqadaryo hududiy filiali</b></label>
          <div className="seg" role="tablist" aria-label="Dinamika turi">
            <button role="tab" aria-selected={mode === 'oy'} className={mode === 'oy' ? 'on' : ''} onClick={() => pick('oy')}><CalendarRange size={15} />Oy boshidan</button>
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
            <button className="btn ghost" hidden={!can('republic.original')} disabled={!!busy} title="Respublika markazi yuborgan asl PDF fayl" onClick={() => dl('orig')}><FileDown size={16} />Asl PDF</button></>)}
          {can('telegram.send') && data && <button className="btn primary" onClick={() => setSend(true)}><Send size={16} />Telegramga yuborish</button>}
        </div>
      </div>
      {err ? (
        <div className="card pad"><Empty icon={Globe2}>{err}{can('republic.upload') && <div style={{ marginTop: 10 }}><Link className="btn primary" to="/yuklash?t=resp"><UploadCloud size={16} />PDF yuklash</Link></div>}</Empty></div>
      ) : !data ? <Spinner /> : mode === 'kunlik' && !data.a ? (
        <div className="card pad"><Empty icon={GitCompareArrows}>Kunlik solishtirish uchun kamida ikkita sananing PDF'i kerak — hozir faqat bitta ({dmy(data.b)}) yuklangan.
          {can('republic.upload') && <div style={{ marginTop: 10 }}><Link className="btn primary" to="/yuklash?t=resp"><UploadCloud size={16} />Yangi PDF yuklash</Link></div>}</Empty></div>
      ) : (<>
        <div className="card tcard">
          <div className="tbl-scroll">
            <table className={`dyn-table t-${cur.key}`}>
              <thead>
                {cur.head.map((hr, i) => (
                  <tr key={i}>{hr.map((h, j) => (
                    <th key={j} rowSpan={h.rs} colSpan={h.cs} className={((i === 0 && j === 0 ? 'h-name ' : '') + (h.c || '')).split(' ').filter(Boolean).map((c) => (c === 'h-name' ? 'h-name' : 'h-' + c)).join(' ').replace('h-name', 'h-h-name')}><span>{h.l}</span></th>))}</tr>))}
              </thead>
              <tbody>
                <tr className="total">
                  <td className="name">Jami</td>
                  {cur.cols.map((c, i) => <Cell key={i} col={c} row={{ cur: cur.cur, base: cur.base }} total canDrill={false} onDrill={() => {}} />)}
                </tr>
                {(cur.rows || []).map((r) => (
                  <tr key={r.id}>
                    <td className="name">{r.name}</td>
                    {cur.cols.map((c, i) => <Cell key={i} col={c} row={r} canDrill={false} onDrill={() => {}} />)}
                  </tr>))}
              </tbody>
            </table>
          </div>
          <div className="note">{data.a ? <>Kunlik dinamika (↑↓): oxirgi ikki yuklangan PDF — <b>{dmy(data.a)}</b> bilan <b>{dmy(data.b)}</b> o'rtasidagi o'zgarish.</> : <>Dinamika (↑↓): oy boshidan <b>{dmy(data.b)}</b> gacha (respublika PDF'i bo'yicha). Oxirgi ikki kunni solishtirish uchun «Kunlik» ni tanlang.</>}</div>
        </div></>)}
      {send && data && <SendModal a={data.a} b={data.b} mode={mode} onClose={() => setSend(false)} />}
    </div>
  )
}
