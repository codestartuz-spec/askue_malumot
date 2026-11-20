import { useCallback, useEffect, useMemo, useState } from 'react'
import { HardHat, Pencil, Plus, Users, MapPin, Cpu, Gauge, Trash2, ArrowRightLeft, Search, AlertTriangle, UserPlus, Link2, X } from 'lucide-react'
import { api, qs } from '../api'
import { useAuth } from '../auth'
import { Empty, Modal, Pager, Spinner, useDebounced, useToast } from '../ui'
import { num } from '../fmt'

function EditModal({ brigade, espId, onClose, onSaved }) {
  const toast = useToast()
  const { boot } = useAuth()
  const isNew = !brigade
  const [espSel, setEspSel] = useState(espId ? String(espId) : '')
  const [name, setName] = useState(brigade?.name || '')
  const [members, setMembers] = useState(brigade?.members?.length ? brigade.members.map((m) => ({ ...m })) : [{ full_name: '', position: '' }])
  const [busy, setBusy] = useState(false)
  const set = (i, k, v) => setMembers((a) => a.map((m, j) => (j === i ? { ...m, [k]: v } : m)))
  const save = async () => {
    setBusy(true)
    try {
      const body = { name, members: members.filter((m) => m.full_name.trim()) }
      if (isNew) await api.post('/brigades', { esp_id: Number(espSel), ...body })
      else await api.patch(`/brigades/${brigade.id}`, body)
      toast('Saqlandi'); onSaved(); onClose()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <Modal icon={isNew ? Plus : Pencil} title={isNew ? 'Yangi brigada' : `Brigadani tahrirlash`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Bekor qilish</button><button className="btn primary" disabled={busy || !name.trim() || (isNew && !espSel)} onClick={save}>Saqlash</button></>}>
      {isNew && !espId && <label className="field"><span>Tuman</span><select value={espSel} onChange={(e) => setEspSel(e.target.value)}><option value="">Tumanni tanlang</option>{boot.esps.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}</select></label>}
      <label className="field"><span>Brigada nomi</span><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Masalan: 1-brigada" /></label>
      <div className="field"><span>Mas'ul xodimlar</span>
        <div className="members-edit">
          {members.map((m, i) => (
            <div key={i} className="m-row">
              <input placeholder="F.I.Sh." value={m.full_name} onChange={(e) => set(i, 'full_name', e.target.value)} />
              <input className="pos" placeholder="Lavozimi (ixtiyoriy)" value={m.position || ''} onChange={(e) => set(i, 'position', e.target.value)} />
              <button className="icon-btn danger" onClick={() => setMembers((a) => a.filter((_, j) => j !== i))} title="O'chirish"><Trash2 size={17} /></button>
            </div>))}
          <button className="btn ghost sm" onClick={() => setMembers((a) => [...a, { full_name: '', position: '' }])}><UserPlus size={16} />Xodim qo'shish</button>
        </div>
        {brigade?.source_name && <small className="hint">Fayldagi asl yozuv: {brigade.source_name}</small>}
      </div>
    </Modal>
  )
}

function TrModal({ brigade, espId, brigades, canAssign, onClose, onSaved }) {
  const toast = useToast()
  const bid = brigade ? brigade.id : 0
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const dq = useDebounced(q)
  const [data, setData] = useState(null)
  const [sel, setSel] = useState(new Set())
  const [all, setAll] = useState(false)
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const size = 50
  useEffect(() => { setPage(1) }, [dq])
  useEffect(() => {
    let live = true
    api.get(`/brigades/trs${qs({ esp_id: espId, brigade_id: bid, q: dq, page, size })}`).then((d) => live && setData(d)).catch((e) => toast(e.message, 'err'))
    return () => { live = false }
  }, [espId, bid, dq, page])
  const toggle = (id) => { setAll(false); setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n }) }
  const pageAll = data && data.items.length > 0 && data.items.every((r) => sel.has(r.id))
  const togglePage = () => { setAll(false); setSel((s) => { const n = new Set(s); data.items.forEach((r) => (pageAll ? n.delete(r.id) : n.add(r.id))); return n }) }
  const count = all ? data?.total || 0 : sel.size
  const apply = async () => {
    setBusy(true)
    try {
      const body = { esp_id: espId, brigade_id: Number(target) }
      if (all && !dq) { body.use_from = true; body.from_brigade_id = bid } else body.tr_ids = [...sel]
      const r = await api.post('/brigades/assign', body)
      toast(`${r.moved} ta TP ko'chirildi`); onSaved(); onClose()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const targets = brigades.filter((b) => b.id !== bid)
  return (
    <Modal wide icon={Cpu} title={brigade ? `${brigade.name} — TP'lar` : "Biriktirilmagan TP'lar"} onClose={onClose}
      footer={<>
        <div className="foot-info">Jami: {data ? num(data.total) : '…'} ta{count ? ` • tanlangan: ${num(count)}` : ''}</div>
        {canAssign && (<>
          <select value={target} onChange={(e) => setTarget(e.target.value)} className="sel-sm">
            <option value="">Qaysi brigadaga?</option>
            {targets.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            {bid !== 0 && <option value="0">Biriktirmaslik</option>}
          </select>
          <button className="btn primary" disabled={!count || target === '' || busy} onClick={apply}><ArrowRightLeft size={16} />Ko'chirish</button>
        </>)}
        {data && <Pager page={page} size={size} total={data.total} onPage={setPage} />}
      </>}>
      <div className="searchbar"><Search size={17} /><input placeholder="TP, DCU, podstansiya yoki fider…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      {canAssign && data && data.total > size && (
        <label className="check all"><input type="checkbox" checked={all} onChange={(e) => { setAll(e.target.checked); if (!e.target.checked) setSel(new Set()) }} disabled={!!dq} />
          <span>Barcha {num(data.total)} ta TP'ni tanlash{dq ? ' (qidiruvda mavjud emas)' : ''}</span></label>)}
      <div className="tbl-scroll">
        {!data ? <Spinner /> : data.items.length === 0 ? <Empty icon={Cpu}>TP topilmadi</Empty> : (
          <table className="list">
            <thead><tr>{canAssign && <th style={{ width: 36 }}><input type="checkbox" checked={pageAll || all} onChange={togglePage} /></th>}<th>TP</th><th>Podstansiya</th><th>Fider</th><th>DCU</th><th></th></tr></thead>
            <tbody>{data.items.map((r) => (
              <tr key={r.id} className={sel.has(r.id) || all ? 'sel' : ''}>
                {canAssign && <td><input type="checkbox" checked={sel.has(r.id) || all} onChange={() => toggle(r.id)} /></td>}
                <td className="b">{r.tp_no}</td><td>{r.substation}</td><td>{r.feeder}</td><td className="mono">{r.dcu}</td>
                <td>{r.manual ? <span className="tag amber" title="Qo'lda biriktirilgan">qo'lda</span> : ''}</td></tr>))}</tbody>
          </table>)}
      </div>
    </Modal>
  )
}

export default function Brigades() {
  const { boot, can, reload } = useAuth()
  const [esp, setEspS] = useState(() => localStorage.getItem('askue_b_esp') || '')
  const [bid, setBidS] = useState(() => localStorage.getItem('askue_b_brig') || '')
  const [data, setData] = useState(null)
  const [edit, setEdit] = useState(null)       // null | 'new' | brigade
  const [trs, setTrs] = useState(null)         // null | {brigade|null, espId}
  const toast = useToast()
  const setEsp = (v) => { setEspS(v); setBidS(''); localStorage.setItem('askue_b_esp', v); localStorage.removeItem('askue_b_brig') }
  const setBid = (v) => { setBidS(v); v ? localStorage.setItem('askue_b_brig', v) : localStorage.removeItem('askue_b_brig') }
  const load = useCallback(() => {
    api.get(`/brigades${qs({ esp_id: esp })}`).then(setData).catch((e) => toast(e.message, 'err'))
  }, [esp])
  useEffect(() => { setData(null); load() }, [load])
  const afterSave = () => { load(); reload() }
  const espLabel = (id) => boot.esps.find((e) => e.id === id)?.label
  const opts = useMemo(() => (data?.items || []), [data])
  useEffect(() => { if (data && bid && bid !== '0' && !data.items.some((b) => String(b.id) === bid)) setBid('') }, [data])

  const items = (data?.items || []).filter((b) => !bid || String(b.id) === bid)
  const unassigned = bid && bid !== '0' ? [] : (data?.unassigned || [])
  const showItems = bid === '0' ? [] : items
  // tumanlar bo'yicha guruhlash
  const groups = []
  const gmap = new Map()
  const grp = (id, label) => { if (!gmap.has(id)) { const g = { id, label, un: null, items: [] }; gmap.set(id, g); groups.push(g) } return gmap.get(id) }
  unassigned.forEach((u) => { grp(u.esp_id, u.esp).un = u })
  showItems.forEach((b) => grp(b.esp_id, b.esp).items.push(b))
  groups.sort((a, b) => boot.esps.findIndex((e) => e.id === a.id) - boot.esps.findIndex((e) => e.id === b.id))
  let n = 0

  return (
    <div className="brig">
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Brigadalar va mas'ul xodimlar</h2>
          <p className="sub">Brigada nomi, xodimlari va TP biriktirishlari saqlanib qoladi — yangi fayl yuklanganda ular o'zgarmaydi.</p></div>
        <div className="filters">
          <label className="filter"><span><MapPin size={15} />Hudud nomi:</span>
            <select value={esp} onChange={(e) => setEsp(e.target.value)}>
              <option value="">Barcha tumanlar</option>{boot.esps.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}</select></label>
          <label className="filter"><span><HardHat size={15} />Brigada:</span>
            <select value={bid} onChange={(e) => setBid(e.target.value)}>
              <option value="">Barcha brigadalar</option>
              {opts.map((b) => <option key={b.id} value={b.id}>{b.name}{!esp ? ` — ${b.esp}` : ''}</option>)}
              {(data?.unassigned?.length > 0) && <option value="0">Biriktirilmagan TP'lar</option>}</select></label>
          {(esp || bid) && <button className="btn ghost sm" onClick={() => setEsp('')}><X size={15} />Filtrni tozalash</button>}
          <div className="spacer" />
          {can('brigade.edit') && <button className="btn primary" onClick={() => setEdit('new')}><Plus size={17} />Yangi brigada</button>}
        </div>
      </div>

      {!data ? <Spinner /> : (
        <>
          {groups.map((g) => (
            <section key={g.id} className="b-sec">
              {!esp && <h3 className="b-sec-title"><MapPin size={17} />{g.label}<span>{g.items.length} ta brigada</span></h3>}
              <div className="b-grid">
                {g.un && (
                  <div className="b-card unassigned" style={{ animationDelay: '0ms' }}>
                    <div className="b-top"><div className="b-icon warn"><AlertTriangle size={22} /></div><div><h3>Biriktirilmagan</h3><small>{g.label}</small></div></div>
                    <div className="b-stats"><div><Cpu size={15} /><b>{num(g.un.tp_count)}</b> TP</div><div><Gauge size={15} /><b>{num(g.un.meter_count)}</b> hisoblagich</div></div>
                    <p className="b-note">Mas'ul xodimi ko'rsatilmagan TP'lar. Ularni brigadaga biriktirish mumkin.</p>
                    <div className="b-actions"><button className="btn amber" onClick={() => setTrs({ brigade: null, espId: g.id })}><Link2 size={16} />{can('brigade.assign') ? 'Biriktirish' : "Ko'rish"}</button></div>
                  </div>)}
                {g.items.map((b) => (
                  <div className="b-card" key={b.id} style={{ animationDelay: `${Math.min(++n, 20) * 35}ms` }}>
                    <div className="b-top"><div className="b-icon"><HardHat size={22} /></div><div><h3>{b.name}</h3><small>{b.esp}</small></div><span className="b-num">{b.number}</span></div>
                    <div className="b-stats"><div><Cpu size={15} /><b>{num(b.tp_count)}</b> TP</div><div><Gauge size={15} /><b>{num(b.meter_count)}</b> hisoblagich</div></div>
                    <div className="members">
                      {b.members.length ? b.members.map((m, j) => <span key={j} className="chip-m" title={m.position || ''}><Users size={13} />{m.full_name}{m.position ? <i> • {m.position}</i> : null}</span>) : <em className="mut">Xodim kiritilmagan</em>}
                    </div>
                    <div className="b-actions">
                      {can('brigade.edit') && <button className="btn ghost sm" onClick={() => setEdit(b)}><Pencil size={15} />Tahrirlash</button>}
                      <button className="btn ghost sm" onClick={() => setTrs({ brigade: b, espId: b.esp_id })}><Cpu size={15} />TP'lar</button>
                    </div>
                  </div>))}
              </div>
            </section>))}
          {groups.length === 0 && <div className="card"><Empty icon={HardHat}>Brigada topilmadi. Ma'lumot yuklangach avtomatik yaratiladi.</Empty></div>}
        </>)}
      {edit && <EditModal brigade={edit === 'new' ? null : edit} espId={edit !== 'new' ? edit.esp_id : (esp ? Number(esp) : 0)} onClose={() => setEdit(null)} onSaved={afterSave} />}
      {trs && data && <TrModal brigade={trs.brigade} espId={trs.espId} brigades={data.items.filter((b) => b.esp_id === trs.espId)} canAssign={can('brigade.assign')} onClose={() => setTrs(null)} onSaved={afterSave} />}
    </div>
  )
}
