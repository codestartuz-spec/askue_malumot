import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Send, FileText, FileSpreadsheet, Building2, Globe2, Megaphone, Users, CheckCircle2, AlertTriangle, MailCheck } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ChatTable, Modal, Spinner, useToast } from '../ui'

export default function SendReport({ espId, dates, onClose }) {
  const { boot, can } = useAuth()
  const toast = useToast()
  const [chats, setChats] = useState(null)
  const [what, setWhat] = useState(() => new Set(espId ? ['d-pdf'] : ['r-pdf']))
  const [esps, setEsps] = useState(() => new Set(espId ? [Number(espId)] : []))
  const [sel, setSel] = useState(new Set())
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [ack, setAck] = useState(true)
  const timer = useRef(null)

  useEffect(() => { api.get('/telegram/chats').then(setChats).catch((e) => { toast(e.message, 'err'); setChats([]) }); return () => clearInterval(timer.current) }, [])
  const tg = (set, setter, k) => setter((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const dist = what.has('d-pdf') || what.has('d-xlsx')
  const allEsp = boot.esps.length > 0 && esps.size === boot.esps.length

  const items = []
  if (what.has('r-pdf')) items.push({ kind: 'region', fmt: 'pdf' })
  if (what.has('r-xlsx')) items.push({ kind: 'region', fmt: 'xlsx' })
  if (dist) boot.esps.filter((e) => esps.has(e.id)).forEach((e) => {
    if (what.has('d-pdf')) items.push({ kind: 'district', fmt: 'pdf', esp_id: e.id })
    if (what.has('d-xlsx')) items.push({ kind: 'district', fmt: 'xlsx', esp_id: e.id })
  })
  const ready = items.length > 0 && sel.size > 0 && !busy

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
    try {
      const r = await api.post('/reports/send', { items, chat_ids: [...sel], ack, date_from: dates.from, date_to: dates.to })
      setJob({ status: 'running', progress: 0, log: '' }); poll(r.id)
    } catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  const opt = (k, icon, title, sub) => (
    <label className={`opt ${what.has(k) ? 'on' : ''}`}><input type="checkbox" checked={what.has(k)} onChange={() => tg(what, setWhat, k)} disabled={busy} />
      <i>{icon}</i><span><b>{title}</b><small>{sub}</small></span></label>)

  return (
    <Modal wide icon={Send} title="Telegram kanal / guruhga yuborish" onClose={busy ? () => {} : onClose}
      footer={<>
        <div className="foot-info">{items.length ? `${items.length} ta fayl` : 'Fayl tanlanmagan'}{sel.size ? ` → ${sel.size} ta kanal` : ''}</div>
        <button className="btn ghost" onClick={onClose} disabled={busy}>Yopish</button>
        <button className="btn primary" disabled={!ready} onClick={go}><Send size={16} />Yuborish</button>
      </>}>
      <div className="send-grid">
        <div>
          <div className="mp-sec dark">1. Nimani yuborish</div>
          <div className="opts">
            {opt('r-pdf', <FileText size={20} />, 'Viloyat dinamikasi — PDF', 'Barcha tumanlar, 3 jadval')}
            {opt('r-xlsx', <FileSpreadsheet size={20} />, 'Viloyat dinamikasi — Excel', 'Barcha tumanlar, 3 varaq')}
            {opt('d-pdf', <FileText size={20} />, 'Tumanlar — PDF', 'Brigadalar kesimida, har bir tuman alohida')}
            {opt('d-xlsx', <FileSpreadsheet size={20} />, 'Tumanlar — Excel', 'Brigadalar kesimida, har bir tuman alohida')}
          </div>
          {dist && (
            <div className="esp-pick">
              <div className="mp-sec dark"><Building2 size={15} />Qaysi tumanlar (brigadalar kesimida)</div>
              <label className="check all"><input type="checkbox" checked={allEsp} onChange={(e) => setEsps(e.target.checked ? new Set(boot.esps.map((x) => x.id)) : new Set())} disabled={busy} /><span>Barcha tumanlar</span></label>
              <div className="esp-grid">{boot.esps.map((e) => (
                <label key={e.id} className="check"><input type="checkbox" checked={esps.has(e.id)} onChange={() => tg(esps, setEsps, e.id)} disabled={busy} /><span>{e.label}</span></label>))}</div>
            </div>)}
        </div>
        <div>
          <div className="mp-sec dark">2. Qaysi kanal yoki guruhga</div>
          {!chats ? <Spinner /> : chats.length === 0 ? (
            <div className="empty sm"><Megaphone size={30} /><div>Hali kanal yoki guruh qo'shilmagan.{can('settings.manage') ? <> <Link to="/sozlamalar" onClick={onClose}>Sozlamalar</Link> bo'limidan qo'shing.</> : " Sadmin'ga murojaat qiling."}</div></div>
          ) : (
            <ChatTable chats={chats} sel={sel} busy={busy} onToggle={(id) => tg(sel, setSel, id)} onAll={(v) => setSel(v ? new Set(chats.map((c) => c.id)) : new Set())} />)}
        </div>
      </div>
      <label className={`ack-opt ${ack ? 'on' : ''}`}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
        <i><MailCheck size={18} /></i><span><b>«Tanishdim» tugmasi</b><small>Xabar tagida tugma chiqadi; kim va qachon bosgani «Xabar yuborish → Jurnal» bo'limida ko'rinadi</small></span></label>
      {job && (
        <div className="send-prog">
          <div className="progress"><div className="bar" style={{ width: `${job.progress}%` }} /><span>{Math.round(job.progress)}%</span></div>
          <div className="send-log">{job.log.split('\n').filter(Boolean).map((l, i) => (
            <div key={i} className={l.startsWith('✗') ? 'bad' : 'ok'}>{l.startsWith('✗') ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}<span>{l.slice(2)}</span></div>))}
            {job.status === 'running' && <div className="mut">Yuborilmoqda…</div>}</div>
        </div>)}
    </Modal>
  )
}
