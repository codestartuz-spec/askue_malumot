import { useEffect, useState } from 'react'
import { UserPlus, Pencil, ShieldCheck, Ban, CheckCircle2, KeyRound, Users as UsersIcon, Crown, Phone, Send } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Modal, Spinner, useToast } from '../ui'
import { dt } from '../fmt'

function PermGrid({ catalog, value, onChange }) {
  const groups = [...new Set(catalog.map((p) => p.group))]
  const toggle = (p) => {
    let v = new Set(value)
    if (v.has(p.code)) {
      v.delete(p.code)
      catalog.filter((x) => x.needs === p.code).forEach((x) => v.delete(x.code))     // bog'liq ruxsatlar ham olinadi
    } else {
      v.add(p.code)
      if (p.needs) v.add(p.needs)                                                       // kerakli ruxsat avtomatik qo'shiladi
    }
    onChange([...v])
  }
  const name = (c) => catalog.find((x) => x.code === c)?.name
  return groups.map((g) => (
    <div key={g} className="perm-group">
      <div className="pg-title">{g}</div>
      {catalog.filter((p) => p.group === g).map((p) => (
        <label key={p.code} className="check perm"><input type="checkbox" checked={value.includes(p.code)} onChange={() => toggle(p)} />
          <span><b>{p.name}</b><small>{p.desc}{p.needs ? ` • «${name(p.needs)}» ruxsati ham kerak` : ''}</small></span></label>))}
    </div>))
}

function UserModal({ u, catalog, onClose, onSaved }) {
  const toast = useToast()
  const isNew = !u
  const [starters, setStarters] = useState([])
  useEffect(() => { api.get('/telegram/starters').then(setStarters).catch(() => {}) }, [])
  const [f, setF] = useState({ username: '', full_name: u?.full_name || '', password: '', phone: u?.phone || '', chat_id: u?.chat_id || '', perms: u?.perms || ['view.konsentrator', 'view.aloqa', 'view.obxod'] })
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try {
      if (isNew) await api.post('/users', f)
      else await api.patch(`/users/${u.id}`, { full_name: f.full_name, phone: f.phone, chat_id: f.chat_id, ...(u.is_super ? {} : { perms: f.perms }), ...(f.password ? { password: f.password } : {}) })
      toast('Saqlandi'); onSaved(); onClose()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <Modal wide icon={isNew ? UserPlus : Pencil} title={isNew ? "Yangi xodim qo'shish" : `Xodim: ${u.username}`} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Bekor qilish</button><button className="btn primary" disabled={busy || (isNew && (!f.username || !f.password))} onClick={save}>Saqlash</button></>}>
      <div className="two">
        {isNew && <label className="field"><span>Login</span><input value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} autoComplete="off" /></label>}
        <label className="field"><span>F.I.Sh.</span><input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
        <label className="field"><span><Phone size={14} />Telefon raqami</span><input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="+998 90 123 45 67" inputMode="tel" /></label>
        <label className="field"><span><Send size={14} />Telegram chat ID</span><input value={f.chat_id} onChange={(e) => setF({ ...f, chat_id: e.target.value })} placeholder="Botga /start bosganda keladi" inputMode="numeric" />
          {starters.length > 0 && <select className="sel-sm" value="" onChange={(e) => e.target.value && setF({ ...f, chat_id: e.target.value })}><option value="">Botga /start bosganlardan tanlash…</option>{starters.map((s) => <option key={s.chat_id} value={s.chat_id}>{s.name || s.username || s.chat_id} ({s.chat_id})</option>)}</select>}</label>
        <label className="field"><span><KeyRound size={14} />{isNew ? 'Parol' : 'Yangi parol (ixtiyoriy)'}</span><input type="text" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} autoComplete="new-password" /></label>
      </div>
      {u?.is_super ? <small className="hint">Sadmin barcha ruxsatlarga ega — ularni o'zgartirib bo'lmaydi.</small> : (<>
      <div className="perm-title"><ShieldCheck size={17} />Ruxsatlar — xodim nimani ko'ra oladi va nima qila oladi</div>
      <div className="perm-grid"><PermGrid catalog={catalog} value={f.perms} onChange={(perms) => setF({ ...f, perms })} /></div></>)}
      <small className="hint">Bog'liq ruxsatlar avtomatik belgilanadi (masalan, brigadani tahrirlash uchun «Brigadalar sahifasi» kerak). Ruxsat berilmasa — sahifa menyuda ko'rinmaydi va server ham so'rovni rad etadi.</small>
    </Modal>
  )
}

export default function Users() {
  const { boot } = useAuth()
  const toast = useToast()
  const [list, setList] = useState(null)
  const [edit, setEdit] = useState(undefined)   // undefined = yopiq, null = yangi
  const load = () => api.get('/users').then(setList).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load() }, [])
  const toggle = async (u) => { try { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); load() } catch (e) { toast(e.message, 'err') } }
  const label = (c) => boot.perms.find((p) => p.code === c)?.name || c
  return (
    <div className="usr">
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Xodimlar va ruxsatlar</h2><p className="sub">Sadmin har bir xodim qaysi sahifalarni ko'rishi va qaysi amallarni bajarishini belgilaydi.</p></div>
        <div className="filters"><div className="spacer" /><button className="btn primary" onClick={() => setEdit(null)}><UserPlus size={17} />Xodim qo'shish</button></div>
      </div>
      {!list ? <Spinner /> : (
        <div className="card tcard"><div className="tbl-scroll">
          <table className="list users">
            <thead><tr><th>Login</th><th>F.I.Sh.</th><th>Ruxsatlar</th><th>Telefon / Telegram</th><th>Oxirgi kirish</th><th>Holati</th><th></th></tr></thead>
            <tbody>{list.map((u) => (
              <tr key={u.id} className={u.is_active ? '' : 'off'}>
                <td className="b">{u.is_super && <Crown size={15} className="crown" />} {u.username}</td><td>{u.full_name}</td>
                <td>{u.is_super ? <span className="tag blue">Barcha ruxsatlar</span> : u.perms.length ? <div className="tags">{u.perms.map((p) => <span key={p} className="tag">{label(p)}</span>)}</div> : <em className="mut">Ruxsat berilmagan</em>}</td>
                <td className="nowrap">{u.phone || <em className="mut">—</em>}<br /><small className="mut mono">{u.chat_id ? `TG: ${u.chat_id}` : 'chat ID yo\'q'}</small></td>
                <td className="mut">{dt(u.last_login)}</td>
                <td>{u.is_active ? <span className="tag green"><CheckCircle2 size={13} />Faol</span> : <span className="tag red"><Ban size={13} />Bloklangan</span>}</td>
                <td className="acts"><button className="btn ghost sm" onClick={() => setEdit(u)}><Pencil size={15} />Tahrirlash</button>{!u.is_super && (<>
                  <button className="btn ghost sm" onClick={() => toggle(u)}>{u.is_active ? 'Bloklash' : 'Faollashtirish'}</button></>)}</td>
              </tr>))}</tbody>
          </table></div></div>)}
      {edit !== undefined && <UserModal u={edit} catalog={boot.perms} onClose={() => setEdit(undefined)} onSaved={load} />}
    </div>
  )
}
