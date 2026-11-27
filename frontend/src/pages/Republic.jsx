import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Globe2, Send, Megaphone, AlertTriangle, CheckCircle2, MailCheck, FileText, FileDown, FileSpreadsheet, Image as ImageIcon, ArrowUpDown, ArrowDown, ArrowUp, Trophy } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ChatTable, Modal, Spinner, useToast } from '../ui'
import { dmy } from '../fmt'
import { Cell } from './DynPage'
import { PdfEmpty, PdfFilters, isBlocked, usePdfDyn } from './pdfDyn'

export function SendModal({ a, b, mode, onClose, base = '/republic', title = "Qashqadaryo dinamikasini Telegram'ga yuborish", origHint = "Respublika yuborgan fayl, o'zgartirishsiz", images = 0 }) {
  const { can } = useAuth()
  const toast = useToast()
  const [chats, setChats] = useState(null)
  const [fmts, setFmts] = useState(new Set(images ? ['png', 'pdf'] : ['pdf']))
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
            {images > 0 && <label className={`opt ${fmts.has('png') ? 'on' : ''}`}><input type="checkbox" checked={fmts.has('png')} onChange={() => tg(setFmts, 'png')} disabled={busy} /><i><ImageIcon size={20} /></i><span><b>Jadval rasmlari ({images} ta)</b><small>Har bir jadval alohida rasm; kanalga albom (karusel) bo'lib boradi</small></span></label>}
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

// Qashqadaryo (tumanlar) va Respublika (viloyatlar) dinamikasi — bir xil jadval sahifasi.
// rank: viloyatlar reytingi (ustun bo'yicha saralash va o'rin 1…14) va Qashqadaryo qatorini ajratish.
const NUM_KEY = (m) => (m.startsWith('c') ? +m.slice(1) : null)
const sortOptions = (page) => {
  const lab = page.labels || []
  const out = []
  const seen = new Set()
  page.cols.forEach((c) => {
    if (c.t === 'n' && !seen.has(c.m)) { seen.add(c.m); out.push({ k: `n:${c.m}`, label: lab[NUM_KEY(c.m)] || c.m, val: (r) => r.cur[c.m] || 0 }) }
    if (c.t === 't' && !seen.has(c.m)) {
      seen.add(c.m)
      const i = NUM_KEY(c.m.replace('t', 'c'))
      out.push({ k: `t:${c.m}`, label: `${lab[i - 1] || c.m} — %`, val: (r) => parseFloat(String(r.cur[c.m] || '0').replace(',', '.')) || 0 })
    }
    if (c.t === 'p') out.push({ k: `p:${c.num}`, label: `${lab[NUM_KEY(c.num)] || c.num} — %`, val: (r) => (r.cur[c.den] > 0 ? (r.cur[c.num] || 0) / r.cur[c.den] : 0) })
  })
  return out
}

export function PdfDynPage({ base, perm, tab, fileLabel, scope, title, rank = false, images = false, Icon = Globe2, origHint, note }) {
  const { boot } = useAuth()
  const region = scope || boot?.region_name || ''
  const st = usePdfDyn(base, fileLabel)
  const { data, mode } = st
  const [pn, setPn] = useState(null)
  const [sk, setSk] = useState('')
  const [dir, setDir] = useState(-1)
  const cur = data ? (data.pages.find((p) => p.n === pn) || data.pages[0]) : null
  const opts = useMemo(() => (rank && cur ? sortOptions(cur) : []), [rank, cur])
  const so = opts.find((o) => o.k === sk)
  const rows = useMemo(() => {
    const r = (cur?.rows || []).map((x, i) => ({ ...x, _i: i }))
    if (!so) return r.map((x) => ({ ...x, rk: 0 }))
    const sorted = [...r].sort((a, b) => dir * (so.val(a) - so.val(b)) || a._i - b._i)
    return sorted.map((x, i) => ({ ...x, rk: i + 1 }))
  }, [cur, so, dir])
  return (
    <div className="dyn rep">
      {data && cur && (
        <div className="tabs scroll" role="tablist">
          {data.pages.map((p) => (
            <button key={p.n} role="tab" aria-selected={p.n === cur.n} className={`tab ${p.n === cur.n ? 'on' : ''}`} onClick={() => { setPn(p.n); setSk('') }}><span>{p.short}</span></button>))}
        </div>)}
      <div className="card head-card">
        <div className="titles">
          <h2 className="ttl">{cur ? `${region} ${cur.title}` : title}</h2>
          <div className="dinamika">{'DINAMIKA'.split('').join(' ')}</div>
        </div>
        <PdfFilters st={st} region={region} perm={perm} firstLabel="Oy boshidan" origHint={origHint} images={images} />
      </div>
      {!data && !st.err ? <Spinner /> : isBlocked(st) ? <PdfEmpty st={st} perm={perm} tab={tab} icon={Icon} /> : (<>
        {rank && opts.length > 0 && (
          <div className="card rank-bar">
            <Trophy size={17} />
            <label><span>Viloyatlar reytingi:</span>
              <select value={sk} onChange={(e) => { setSk(e.target.value); setDir(-1) }}>
                <option value="">Ro'yxat tartibida (reytingsiz)</option>
                {opts.map((o) => <option key={o.k} value={o.k}>{o.label}</option>)}
              </select></label>
            {so && <div className="seg">
              <button className={dir === -1 ? 'on' : ''} onClick={() => setDir(-1)}><ArrowDown size={15} />Eng ko'pdan</button>
              <button className={dir === 1 ? 'on' : ''} onClick={() => setDir(1)}><ArrowUp size={15} />Eng kamdan</button></div>}
            {so && <button className="btn ghost sm" onClick={() => setSk('')}><ArrowUpDown size={14} />Tozalash</button>}
            <small className="mut">{so ? `«${so.label}» bo'yicha 1 dan ${rows.length} gacha o'rin` : "Ustunni tanlang — viloyatlar o'rin raqami bilan saralanadi. Qashqadaryo qatori ajratib ko'rsatiladi."}</small>
          </div>)}
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
                {rows.map((r) => (
                  <tr key={r.id} className={rank && /qashqadaryo/i.test(r.name) ? 'me' : ''}>
                    <td className="name">{r.rk > 0 && <b className={`rk r${r.rk <= 3 ? r.rk : ''}`}>{r.rk}</b>}{r.name}</td>
                    {cur.cols.map((c, i) => <Cell key={i} col={c} row={r} canDrill={false} onDrill={() => {}} />)}
                  </tr>))}
              </tbody>
            </table>
          </div>
          {cur.warn && <div className="note" style={{ color: '#b45309', fontWeight: 600 }}>{cur.warn}</div>}
          <div className="note">{data.a ? <>Kunlik dinamika (↑↓): oxirgi ikki yuklangan PDF — <b>{dmy(data.a)}</b> bilan <b>{dmy(data.b)}</b> o'rtasidagi o'zgarish.</> : <>Dinamika (↑↓): oy boshidan <b>{dmy(data.b)}</b> gacha ({note}). Oxirgi ikki kunni solishtirish uchun «Kunlik» ni tanlang.</>}</div>
        </div></>)}
      {st.send && data && <SendModal a={data.a} b={data.b} mode={mode} base={base} images={images ? data.pages.length : 0}
        title={`${title}ni Telegram'ga yuborish`} onClose={() => st.setSend(false)} />}
    </div>
  )
}

export default function Republic() {
  return <PdfDynPage base="/republic" perm="republic" tab="resp" fileLabel="Qashqadaryo_dinamikasi" title="Qashqadaryo dinamikasi"
    origHint="Respublika markazi yuborgan asl PDF fayl" note="Qashqadaryo HETK PDF'i bo'yicha" />
}
