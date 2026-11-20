import { useEffect, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { api } from '../api'
import { Empty, Pager, Spinner } from '../ui'
import { dt } from '../fmt'

const NAMES = { upload: "Ma'lumot yuklash", brigada_tahrir: 'Brigada tahriri', tp_biriktirish: 'TP biriktirish', "brigada_qo'shildi": "Brigada qo'shildi",
  "xodim_qo'shildi": "Xodim qo'shildi", "xodim_o'zgardi": "Xodim o'zgardi", parol: 'Parol' }

export default function Audit() {
  const [page, setPage] = useState(1)
  const [d, setD] = useState(null)
  useEffect(() => { api.get(`/audit?page=${page}&size=50`).then(setD) }, [page])
  return (
    <div className="aud">
      <div className="card head-card"><div className="titles"><h2 className="ttl">Harakatlar jurnali</h2><p className="sub">Yuklashlar, brigada va ruxsatlardagi barcha o'zgarishlar shu yerda saqlanadi.</p></div></div>
      <div className="card tcard">
        {!d ? <Spinner /> : d.items.length === 0 ? <Empty icon={ScrollText}>Jurnal bo'sh</Empty> : (
          <div className="tbl-scroll"><table className="list">
            <thead><tr><th>Vaqt</th><th>Foydalanuvchi</th><th>Amal</th><th>Tafsilot</th></tr></thead>
            <tbody>{d.items.map((r) => <tr key={r.id}><td className="mut nowrap">{dt(r.created_at)}</td><td className="b">{r.username}</td><td><span className="tag">{NAMES[r.action] || r.action}</span></td><td className="wrap">{r.detail}</td></tr>)}</tbody>
          </table></div>)}
        {d && <div className="pager-wrap"><Pager page={page} size={50} total={d.total} onPage={setPage} /></div>}
      </div>
    </div>
  )
}
