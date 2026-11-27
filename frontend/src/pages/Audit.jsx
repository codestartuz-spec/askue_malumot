import { useEffect, useState } from 'react'
import { ScrollText, Search, Download, FileSpreadsheet, X } from 'lucide-react'
import { api, download, qs } from '../api'
import { useAuth } from '../auth'
import { Empty, Pager, Spinner, useDebounced, useToast } from '../ui'
import { dt } from '../fmt'

const NAMES = { upload: "Ma'lumot yuklash", brigada_tahrir: 'Brigada tahriri', tp_biriktirish: 'TP biriktirish', "brigada_qo'shildi": "Brigada qo'shildi",
  "xodim_qo'shildi": "Xodim qo'shildi", "xodim_o'zgardi": "Xodim o'zgardi", parol: 'Parol', kirish: 'Tizimga kirdi', chiqish: 'Tizimdan chiqdi',
  kirish_xato: 'Kirish xatosi', qurilma_blok: 'Qurilma bloklandi', qurilma_ochildi: 'Qurilma ochildi', qurilma_chiqarish: 'Qurilmadan chiqarildi',
  ag_yuklash: 'AG PDF yuklandi', ag_ochirish: "AG ma'lumoti o'chirildi", telegram_ag: 'AG Telegramga yuborildi',
  nation_yuklash: 'Respublika PDF yuklandi', nation_ochirish: "Respublika ma'lumoti o'chirildi", telegram_nation: 'Respublika Telegramga yuborildi',
  audit_eksport: 'Jurnal eksporti', sozlama: "Sozlama o'zgardi" }
const label = (a) => NAMES[a] || a
const EMPTY = { q: '', user: '', action: '', ip: '', date_from: '', date_to: '' }

export default function Audit() {
  const { can } = useAuth()
  const toast = useToast()
  const [page, setPage] = useState(1)
  const [f, setF] = useState(EMPTY)
  const [facets, setFacets] = useState({ actions: [], users: [] })
  const [d, setD] = useState(null)
  const q = useDebounced(f.q)
  const filters = { ...f, q }
  const key = JSON.stringify(filters)
  useEffect(() => { api.get('/audit/facets').then(setFacets).catch(() => {}) }, [])
  useEffect(() => { setPage(1) }, [key])
  useEffect(() => {
    let alive = true
    api.get(`/audit${qs({ page, size: 50, ...filters })}`).then((r) => alive && setD(r)).catch((e) => toast(e.message, 'err'))
    return () => { alive = false }
  }, [page, key]) // eslint-disable-line
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const dirty = Object.values(f).some(Boolean)
  const exp = (fmt) => download(`/audit/export${qs({ fmt, ...filters })}`, `audit.${fmt}`).catch((e) => toast(e.message, 'err'))
  return (
    <div className="aud">
      <div className="card head-card"><div className="titles"><h2 className="ttl">Harakatlar jurnali</h2><p className="sub">Yuklashlar, brigada va ruxsatlardagi barcha o'zgarishlar shu yerda saqlanadi.</p></div></div>
      <div className="card aud-filters">
        <label className="aud-search"><Search size={16} /><input value={f.q} onChange={set('q')} placeholder="Qidirish: tafsilot, login, IP, amal…" /></label>
        <select value={f.user} onChange={set('user')} aria-label="Foydalanuvchi"><option value="">Barcha foydalanuvchilar</option>{facets.users.map((u) => <option key={u}>{u}</option>)}</select>
        <select value={f.action} onChange={set('action')} aria-label="Amal"><option value="">Barcha amallar</option>{facets.actions.map((a) => <option key={a} value={a}>{label(a)}</option>)}</select>
        <input value={f.ip} onChange={set('ip')} placeholder="IP manzil" className="aud-ip" aria-label="IP manzil" />
        <input type="date" value={f.date_from} onChange={set('date_from')} aria-label="Sanadan" />
        <input type="date" value={f.date_to} onChange={set('date_to')} aria-label="Sanagacha" />
        {dirty && <button className="btn ghost" onClick={() => setF(EMPTY)}><X size={15} />Tozalash</button>}
        {can('report.download') && <span className="aud-exp"><button className="btn" onClick={() => exp('csv')}><Download size={15} />CSV</button>
          <button className="btn" onClick={() => exp('xlsx')}><FileSpreadsheet size={15} />Excel</button></span>}
      </div>
      <div className="card tcard">
        {!d ? <Spinner /> : d.items.length === 0 ? <Empty icon={ScrollText}>{dirty ? 'Filtrga mos yozuv topilmadi' : "Jurnal bo'sh"}</Empty> : (
          <div className="tbl-scroll"><table className="list">
            <thead><tr><th>Vaqt</th><th>Foydalanuvchi</th><th>Amal</th><th>IP manzil</th><th>Tafsilot</th></tr></thead>
            <tbody>{d.items.map((r) => <tr key={r.id}><td className="mut nowrap">{dt(r.created_at)}</td><td className="b">{r.username}</td><td><span className="tag">{label(r.action)}</span></td><td className="mono nowrap">{r.ip || '—'}</td><td className="wrap">{r.detail}</td></tr>)}</tbody>
          </table></div>)}
        {d && <div className="pager-wrap"><span className="mut">Jami: {d.total.toLocaleString('uz')}</span><Pager page={page} size={50} total={d.total} onPage={setPage} /></div>}
      </div>
    </div>
  )
}
