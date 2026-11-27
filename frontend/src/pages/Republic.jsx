import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe2, Send, Megaphone, AlertTriangle, CheckCircle2, MailCheck, FileText, FileDown, FileSpreadsheet } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ChatTable, Modal, Spinner, useToast } from '../ui'
import { dmy } from '../fmt'
import { Cell } from './DynPage'
import { PdfEmpty, PdfFilters, isBlocked, usePdfDyn } from './pdfDyn'

export function SendModal({ a, b, mode, onClose, base = '/republic', title = "Qashqadaryo dinamikasini Telegram'ga yuborish", origHint = "Respublika yuborgan fayl, o'zgartirishsiz" }) {
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
    try { const r = await api.post(`${base}/send`, { fmts: [...fmts], chat_ids: [...sel], a, b, mode, ack }); setJob({ status: 'running', progress: 0, log: '' }); poll(r.id) }
    catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  return (
    <Modal wide icon={Send} title={title} onClose={busy ? () => {} : onClose}
      footer={<><div className="foot-info">{fmts.size} ta fayl{sel.size ? ` → ${sel.size} ta kanal` : ''}</div>
        <button className="btn ghost" onClick={onClose} disabled={busy}>Yopish</button>
        <button className="btn primary" disabled={busy || !fmts.size || !sel.size} onClick={go}><Send size={16} />Yuborish</button></>}>
      <div className="send-grid">
        <div>
          <div className="mp-sec dark">1. Qaysi formatda</div>
          <div className="opts">
            <label className={`opt ${fmts.has('pdf') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('pdf')} onChange={() => tg(setFmts, 'pdf')} disabled={busy} /><i><FileText size={20} /></i><span><b>PDF</b><small>{dmy(b)} holatiga{a ? `, ${dmy(a)} bilan solishtirib` : ', oy boshidan dinamika'}</small></span></label>
            <label className={`opt ${fmts.has('orig') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('orig')} onChange={() => tg(setFmts, 'orig')} disabled={busy} /><i><FileDown size={20} /></i><span><b>Asl PDF</b><small>{origHint}</small></span></label>
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
  const { boot } = useAuth()
  const region = boot?.region_name || ''
  const st = usePdfDyn('/republic', 'Respublika_dinamikasi')
  const { data, mode } = st
  const [pn, setPn] = useState(null)
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
          <h2 className="ttl">{cur ? `${region} ${cur.title}` : 'Qashqadaryo dinamikasi'}</h2>
          <div className="dinamika">{'DINAMIKA'.split('').join(' ')}</div>
        </div>
        <PdfFilters st={st} region={region} perm="republic" firstLabel="Oy boshidan" origHint="Respublika markazi yuborgan asl PDF fayl" />
      </div>
      {!data && !st.err ? <Spinner /> : isBlocked(st) ? <PdfEmpty st={st} perm="republic" tab="resp" icon={Globe2} /> : (<>
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
          {cur.warn && <div className="note" style={{ color: '#b45309', fontWeight: 600 }}>{cur.warn}</div>}
          <div className="note">{data.a ? <>Kunlik dinamika (↑↓): oxirgi ikki yuklangan PDF — <b>{dmy(data.a)}</b> bilan <b>{dmy(data.b)}</b> o'rtasidagi o'zgarish.</> : <>Dinamika (↑↓): oy boshidan <b>{dmy(data.b)}</b> gacha (respublika PDF'i bo'yicha). Oxirgi ikki kunni solishtirish uchun «Kunlik» ni tanlang.</>}</div>
        </div></>)}
      {st.send && data && <SendModal a={data.a} b={data.b} mode={mode} onClose={() => st.setSend(false)} />}
    </div>
  )
}
