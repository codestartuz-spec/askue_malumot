import { useEffect, useState } from 'react'
import { Activity, Database, Cpu, MemoryStick, HardDrive, Bot, Cog, CalendarClock, ShieldCheck, RefreshCw, Server, CheckCircle2, AlertTriangle, XCircle, Clock } from 'lucide-react'
import { api } from '../api'
import { Spinner } from '../ui'
import { num } from '../fmt'

const ICON = { db: Database, worker: Cog, tg: Bot, data: CalendarClock, backup: ShieldCheck, cpu: Cpu, ram: MemoryStick, disk: HardDrive }
const STATE = { ok: { c: 'ok', t: 'Yaxshi', i: CheckCircle2 }, warn: { c: 'warn', t: "E'tibor bering", i: AlertTriangle }, bad: { c: 'bad', t: 'Muammo bor', i: XCircle } }
const HEAD = { ok: 'Tizim va server me\'yorida ishlayapti', warn: "Tizimda e'tibor talab qiladigan holatlar bor", bad: 'Tizimda muammo aniqlandi' }

export default function SystemStatus() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const load = async () => {
    setBusy(true)
    try { setD(await api.get('/system/status')); setErr('') } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t) }, [])
  if (err && !d) return <div className="card pad denied">{err}</div>
  if (!d) return <Spinner />
  const O = STATE[d.overall]
  return (
    <div className="sys">
      <div className={`card sys-hero ${O.c}`}>
        <div className="pulse"><O.i size={30} /></div>
        <div><b>{HEAD[d.overall]}</b><small>Har 10 soniyada avtomatik tekshiriladi • {d.server.time}</small></div>
        <span className="grow" />
        <button className="btn ghost" onClick={load} disabled={busy}><RefreshCw size={16} className={busy ? 'spin' : ''} />Hozir tekshirish</button>
      </div>
      <div className="sys-grid">
        {d.checks.map((c) => {
          const Ic = ICON[c.key] || Activity, S = STATE[c.state]
          return (
            <div key={c.key} className={`card sys-card ${S.c}`}>
              <div className="sc-top"><i><Ic size={20} /></i><span>{c.title}</span><em className={`dot ${S.c}`} title={S.t} /></div>
              <b className="sc-val">{c.value}</b>
              {c.detail && <small>{c.detail}</small>}
              {['cpu', 'ram', 'disk'].includes(c.key) && <div className="meter"><i style={{ width: `${Math.min(parseFloat(c.value) || 0, 100)}%` }} /></div>}
            </div>)
        })}
      </div>
      <div className="card pad sys-info">
        <h3><Server size={19} />Server ma'lumotlari</h3>
        <dl>
          <div><dt>Operatsion tizim</dt><dd>{d.server.os}</dd></div>
          <div><dt>Kompyuter nomi</dt><dd>{d.server.host}</dd></div>
          <div><dt>Python</dt><dd>{d.server.python}</dd></div>
          <div><dt><Clock size={13} /> Server ishlash vaqti</dt><dd>{d.server.uptime}</dd></div>
          <div><dt>Ilova ishlash vaqti</dt><dd>{d.server.app_uptime}</dd></div>
          <div><dt>Ilova xotirasi</dt><dd>{d.server.api_mem_mb} MB</dd></div>
          <div><dt>Hisoblagichlar</dt><dd>{num(d.stats.meters)}</dd></div>
          <div><dt>Konsentratorlar (TP)</dt><dd>{num(d.stats.trs)}</dd></div>
          <div><dt>Faol xodimlar</dt><dd>{d.stats.users}</dd></div>
        </dl>
      </div>
    </div>
  )
}
