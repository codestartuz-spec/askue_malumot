import { useCallback, useEffect, useState } from 'react'
import { Monitor, Smartphone, Tablet, Ban, ShieldCheck, LogOut, RefreshCw, Users as UsersIcon, Globe } from 'lucide-react'
import { api } from '../api'
import { Confirm, Empty, Spinner, useToast } from '../ui'
import { dt } from '../fmt'

const ICON = { desktop: Monitor, mobile: Smartphone, tablet: Tablet }

export default function Devices() {
  const [d, setD] = useState(null)
  const [ask, setAsk] = useState(null)
  const [q, setQ] = useState('')
  const [f, setF] = useState('all')
  const toast = useToast()
  const load = useCallback(() => api.get('/devices').then(setD).catch((e) => toast(e.message, 'err')), [toast])
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [load])

  const act = async () => {
    const { kind, dev } = ask
    try {
      if (kind === 'logout') { const r = await api.post(`/devices/${dev.id}/logout`); toast(`${r.closed} ta sessiya tugatildi`) }
      else { await api.post(`/devices/${dev.id}/block`, { blocked: kind === 'block' }); toast(kind === 'block' ? 'Qurilma bloklandi' : 'Qurilma ochildi') }
      setAsk(null); load()
    } catch (e) { toast(e.message, 'err'); setAsk(null) }
  }

  const rows = (d?.items || []).filter((x) => {
    if (f === 'online' && !x.online) return false
    if (f === 'blocked' && !x.is_blocked) return false
    const t = q.trim().toLowerCase()
    return !t || [x.name, x.ip, x.last_user, ...x.users.map((u) => u.username)].join(' ').toLowerCase().includes(t)
  })

  return (
    <div className="dev">
      <div className="card head-card"><div className="titles"><h2 className="ttl">Qurilmalar</h2>
        <p className="sub">Ilovadan foydalangan barcha qurilmalar, ularning IP manzili va qaysi foydalanuvchilar kirgani. Bitta login bir vaqtda faqat bitta qurilmada ishlaydi.</p></div></div>
      {!d ? <Spinner /> : (<>
        <div className="dev-stats">
          <div className="card pad"><b>{d.total}</b><span>Jami qurilma</span></div>
          <div className="card pad on"><b>{d.online}</b><span>Hozir onlayn</span></div>
          <div className="card pad bl"><b>{d.blocked}</b><span>Bloklangan</span></div>
        </div>
        <div className="card pad dev-bar">
          <input className="dev-q" placeholder="Qidirish: IP, qurilma yoki foydalanuvchi…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="seg">{[['all', 'Hammasi'], ['online', 'Onlayn'], ['blocked', 'Bloklangan']].map(([k, l]) => <button key={k} className={f === k ? 'on' : ''} onClick={() => setF(k)}>{l}</button>)}</div>
          <button className="icon-btn" onClick={load} title="Yangilash"><RefreshCw size={16} /></button>
        </div>
        <div className="card tcard">
          {rows.length === 0 ? <Empty icon={Monitor}>Qurilma topilmadi</Empty> : (
            <div className="tbl-scroll"><table className="list dev-table">
              <thead><tr><th>Qurilma</th><th>IP manzil</th><th>Foydalanuvchilar</th><th>Oxirgi faollik</th><th>Holat</th><th /></tr></thead>
              <tbody>{rows.map((x) => { const I = ICON[x.kind] || Monitor; return (
                <tr key={x.id} className={x.is_blocked ? 'blk' : ''}>
                  <td><div className="dev-name"><I size={20} /><div><b>{x.name}</b><small className="mut">Birinchi kirish: {dt(x.first_seen)}</small></div></div></td>
                  <td className="mono nowrap"><Globe size={12} /> {x.ip || '—'}</td>
                  <td>{x.users.length === 0 ? <span className="mut">Faqat ochgan (kirmagan)</span> : (
                    <div className="dev-users">{x.users.map((u) => (
                      <span key={u.username} className={`dev-u ${u.username === x.active_user ? 'act' : ''}`} title={`${u.logins} marta kirgan • oxirgi: ${dt(u.last)}`}>
                        <UsersIcon size={12} />{u.username}{u.username === x.active_user && <i> • hozir</i>}</span>))}</div>)}</td>
                  <td className="mut nowrap">{dt(x.last_seen)}</td>
                  <td>{x.is_blocked ? <span className="tag red"><Ban size={12} /> Bloklangan</span>
                    : x.online ? <span className="tag green">Onlayn</span> : x.active_user ? <span className="tag">Sessiya bor</span> : <span className="tag off">Oflayn</span>}
                    {x.is_blocked && <small className="mut db">{x.blocked_by} • {dt(x.blocked_at)}</small>}</td>
                  <td className="acts nowrap">
                    {x.active_user && !x.is_blocked && <button className="btn sm" onClick={() => setAsk({ kind: 'logout', dev: x })}><LogOut size={14} />Chiqarish</button>}{' '}
                    {x.is_blocked
                      ? <button className="btn sm" onClick={() => setAsk({ kind: 'unblock', dev: x })}><ShieldCheck size={14} />Ochish</button>
                      : <button className="btn sm danger" onClick={() => setAsk({ kind: 'block', dev: x })}><Ban size={14} />Bloklash</button>}
                  </td>
                </tr>) })}</tbody>
            </table></div>)}
        </div>
      </>)}
      {ask && (
        <Confirm danger={ask.kind !== 'unblock'} icon={ask.kind === 'unblock' ? ShieldCheck : Ban}
          title={ask.kind === 'block' ? 'Qurilmani bloklash' : ask.kind === 'logout' ? 'Qurilmadan chiqarish' : 'Qurilmani ochish'}
          ok={ask.kind === 'block' ? 'Bloklash' : ask.kind === 'logout' ? 'Chiqarish' : 'Ochish'} onOk={act} onCancel={() => setAsk(null)}>
          {ask.kind === 'block' && <>«{ask.dev.name}» ({ask.dev.ip}) bloklansa, undagi barcha foydalanuvchilar darhol chiqarib yuboriladi va qayta kira olmaydi. Ularga «Bu qurilma administrator tomonidan bloklangan. Administratorga murojaat qiling» xabari ko'rsatiladi.</>}
          {ask.kind === 'logout' && <>«{ask.dev.name}» qurilmasidagi <b>{ask.dev.active_user}</b> tizimdan chiqariladi (qurilma bloklanmaydi).</>}
          {ask.kind === 'unblock' && <>«{ask.dev.name}» qurilmasi yana tizimga kira oladi.</>}
        </Confirm>)}
    </div>
  )
}
