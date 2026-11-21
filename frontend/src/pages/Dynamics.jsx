import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Radio, WifiOff, Gauge, Download, FileSpreadsheet, FileText, Send, ChevronDown } from 'lucide-react'
import { download, qs } from '../api'
import { useAuth } from '../auth'
import { useToast } from '../ui'
import DynPage from './DynPage'
import SendReport from './SendReport'

const TABS = [
  { k: 'konsentrator', label: 'Konsentratorlar', icon: Radio, perm: 'view.konsentrator' },
  { k: 'aloqa', label: 'Aloqadan chiqib ketgan hisoblagichlar', icon: WifiOff, perm: 'view.aloqa' },
  { k: 'obxod', label: '48 soat obxod', icon: Gauge, perm: 'view.obxod' },
]

export default function Dynamics() {
  const { can } = useAuth()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const [open, setOpen] = useState(false)
  const [send, setSend] = useState(null)
  const [busy, setBusy] = useState('')
  const tabs = TABS.filter((t) => can(t.perm))
  const table = tabs.find((t) => t.k === sp.get('t'))?.k || tabs[0]?.k
  const esp = sp.get('esp') || '', from = sp.get('from') || '', to = sp.get('to') || ''
  const set = (k, v) => setSp((o) => { const p = new URLSearchParams(o); if (v) p.set(k, v); else p.delete(k); return p }, { replace: true })
  if (!table) return <div className="card pad denied">Dinamika jadvallarini ko'rish uchun ruxsat berilmagan.</div>

  const dl = async (fmt, data) => {
    setOpen(false); setBusy(fmt)
    try { await download(`/reports/download${qs({ kind: esp ? 'district' : 'region', esp_id: esp, fmt, date_from: data?.base, date_to: data?.to })}`, `dinamika.${fmt}`) }
    catch (e) { toast(e.message, 'err') } finally { setBusy('') }
  }

  const tabBar = (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.k} role="tab" aria-selected={t.k === table} className={`tab ${t.k === table ? 'on' : ''}`} onClick={() => set('t', t.k)}>
          <t.icon size={18} /><span>{t.label}</span>
        </button>))}
      <i className="tab-glow" style={{ '--i': tabs.findIndex((t) => t.k === table), '--n': tabs.length }} />
    </div>
  )

  const actions = (data) => (can('report.download') || can('telegram.send')) && (
    <div className="dl-wrap">
      {can('report.download') && (
        <div className="dl">
          <button className="btn ghost" disabled={!data?.rows?.length || !!busy} onClick={() => setOpen(!open)}>
            <Download size={16} />{busy ? 'Tayyorlanmoqda…' : 'Yuklab olish'}<ChevronDown size={15} /></button>
          {open && (
            <div className="dl-menu" onMouseLeave={() => setOpen(false)}>
              <small>{esp ? `${data?.esp?.label} — brigadalar kesimida` : 'Butun viloyat — tumanlar kesimida'}</small>
              <button onClick={() => dl('xlsx', data)}><FileSpreadsheet size={17} />Excel (.xlsx)</button>
              <button onClick={() => dl('pdf', data)}><FileText size={17} />PDF</button>
            </div>)}
        </div>)}
      {can('telegram.send') && <button className="btn primary" disabled={!data?.rows?.length} onClick={() => setSend({ from: data?.base, to: data?.to })}><Send size={16} />Telegramga yuborish</button>}
    </div>
  )

  return (
    <>
      <DynPage table={table} esp={esp} setEsp={(v) => set('esp', v)} from={from} setFrom={(v) => set('from', v)}
        to={to} setTo={(v) => set('to', v)} tabs={tabBar} actions={actions} />
      {send && <SendReport espId={esp} dates={send} onClose={() => setSend(null)} />}
    </>
  )
}
