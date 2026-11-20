import { useEffect, useMemo, useState } from 'react'
import { UserPlus, Pencil, ShieldCheck, Ban, CheckCircle2, KeyRound, Crown, Phone, Send, Trash2, Search, Clock, ChevronDown, Users as UsersIcon, UserCheck, UserX, Wand2, X } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Modal, Spinner, useToast } from '../ui'
import { dt } from '../fmt'

// Tayyor ruxsat to'plamlari (tez belgilash uchun)
const PRESETS = [
  { name: 'Kuzatuvchi', hint: 'Faqat jadvallarni ko\'radi', codes: ['view.konsentrator', 'view.aloqa', 'view.obxod', 'republic.view'] },
  { name: 'Operator', hint: "Jadval, xarita, ro'yxat va Excel/PDF", codes: ['view.konsentrator', 'view.aloqa', 'view.obxod', 'republic.view', 'map.view', 'drill.view', 'export', 'dynamics.compare', 'report.download', 'republic.original'] },
  { name: 'Brigadir', hint: 'Brigadalar va xarita', codes: ['view.konsentrator', 'view.aloqa', 'view.obxod', 'map.view', 'brigade.view', 'brigade.edit', 'brigade.assign', 'drill.view', 'export'] },
  { name: "Ma'lumot kiritish", hint: 'Fayl yuklaydi va o\'chiradi', codes: ['view.konsentrator', 'view.aloqa', 'view.obxod', 'republic.view', 'data.upload', 'republic.upload', 'data.delete', 'republic.original'] },
  { name: 'Telegram operatori', hint: 'Hisobot va xabar yuboradi', codes: ['view.konsentrator', 'view.aloqa', 'view.obxod', 'republic.view', 'report.download', 'telegram.send', 'telegram.message', 'telegram.journal'] },
]

const initials = (u) => (u.full_name || u.username || '?').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
const hue = (s) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7)

function PermEditor({ catalog, value, onChange }) {
  const groups = useMemo(() => [...new Set(catalog.map((p) => p.group))], [catalog])
  const [open, setOpen] = useState(() => new Set(groups))
  const set = new Set(value)
  const name = (c) => catalog.find((x) => x.code === c)?.name
  const toggle = (p) => {
    const v = new Set(value)
    if (v.has(p.code)) {
      v.delete(p.code)
      catalog.filter((x) => x.needs === p.code).forEach((x) => v.delete(x.code))
    } else {
      v.add(p.code)
      if (p.needs) v.add(p.needs)
    }
    onChange([...v])
  }
  const group = (g, on) => {
    const v = new Set(value)
    catalog.filter((p) => p.group === g).forEach((p) => { if (on) { v.add(p.code); if (p.needs) v.add(p.needs) } else v.delete(p.code) })
    if (!on) catalog.filter((p) => v.has(p.code) && p.needs && !v.has(p.needs)).forEach((p) => v.delete(p.code))
    onChange([...v])
  }
  const preset = (codes) => {
    const v = new Set(codes)
    catalog.forEach((p) => { if (v.has(p.code) && p.needs) v.add(p.needs) })
    onChange([...v])
  }
  return (
    <>
      <div className="perm-title"><ShieldCheck size={17} />Ruxsatlar <span className="perm-count">{value.length} / {catalog.length}</span></div>
      <div className="presets">
        <span><Wand2 size={14} />Tez belgilash:</span>
        {PRESETS.map((p) => <button key={p.name} className="chip" title={p.hint} onClick={() => preset(p.codes)}>{p.name}</button>)}
        <button className="chip" onClick={() => preset(catalog.map((p) => p.code))}>Hammasi</button>
        <button className="chip danger" onClick={() => preset([])}><X size={12} />Tozalash</button>
      </div>
      <div className="perm-acc">
        {groups.map((g) => {
          const items = catalog.filter((p) => p.group === g)
          const n = items.filter((p) => set.has(p.code)).length
          const isOpen = open.has(g)
          return (
            <div key={g} className={`pa ${isOpen ? 'open' : ''} ${n ? 'has' : ''}`}>
              <button className="pa-h" onClick={() => setOpen((s) => { const x = new Set(s); x.has(g) ? x.delete(g) : x.add(g); return x })}>
                <b>{g}</b><span className={`pa-n ${n === items.length ? 'all' : n ? 'some' : ''}`}>{n} / {items.length}</span><ChevronDown size={16} className="pa-ch" /></button>
              {isOpen && (
                <div className="pa-b">
                  <div className="pa-tools"><button onClick={() => group(g, true)}>Hammasini belgilash</button><button onClick={() => group(g, false)}>Olib tashlash</button></div>
                  {items.map((p) => (
                    <label key={p.code} className="check perm"><input type="checkbox" checked={set.has(p.code)} onChange={() => toggle(p)} />
                      <span><b>{p.name}</b><small>{p.desc}{p.needs ? ` • «${name(p.needs)}» ruxsati ham kerak` : ''}</small></span></label>))}
                </div>)}
            </div>)
        })}
      </div>
    </>
  )
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
        <PermEditor catalog={catalog} value={f.perms} onChange={(perms) => setF({ ...f, perms })} /></>)}
      <small className="hint">Bog'liq ruxsatlar avtomatik belgilanadi (masalan, brigadani tahrirlash uchun «Brigadalar sahifasi» kerak). Ruxsat berilmasa — sahifa menyuda ko'rinmaydi va server ham so'rovni rad etadi.</small>
    </Modal>
  )
}

function DeleteModal({ u, onClose, onDone }) {
  const toast = useToast()
  const [t, setT] = useState('')
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    try { await api.del(`/users/${u.id}`); toast(`«${u.username}» o'chirildi`); onDone(); onClose() }
    catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  return (
    <Modal icon={Trash2} title="Xodimni to'liq o'chirish" onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Bekor qilish</button>
        <button className="btn danger" disabled={busy || t.trim().toLowerCase() !== u.username} onClick={go}><Trash2 size={16} />Butunlay o'chirish</button></>}>
      <div className="confirm-body">
        <b>{u.full_name || u.username}</b> (<code>{u.username}</code>) tizimdan butunlay o'chiriladi va u qayta kira olmaydi. Qaytarib bo'lmaydi.
        <small className="hint">Harakatlar jurnalidagi oldingi yozuvlar saqlanib qoladi. Vaqtincha to'xtatish kerak bo'lsa, o'chirmasdan «Bloklash» tugmasidan foydalaning.</small>
        <label className="field" style={{ marginTop: 12 }}><span>Tasdiqlash uchun loginni yozing: <b>{u.username}</b></span>
          <input value={t} onChange={(e) => setT(e.target.value)} autoFocus autoComplete="off" /></label>
      </div>
    </Modal>
  )
}

function UserCard({ u, catalog, onEdit, onToggle, onDelete }) {
  const [more, setMore] = useState(false)
  const groups = useMemo(() => {
    const g = {}
    catalog.forEach((p) => { if (u.perms.includes(p.code)) (g[p.group] ||= []).push(p) })
    return g
  }, [u, catalog])
  const h = hue(u.username)
  return (
    <div className={`ucard ${u.is_active ? '' : 'off'} ${u.is_super ? 'super' : ''}`}>
      <div className="uc-top">
        <div className="uc-av" style={{ '--h': h }}>{initials(u)}</div>
        <div className="uc-id">
          <b>{u.full_name || u.username}</b>
          <span>{u.is_super && <Crown size={13} className="crown" />}@{u.username}</span>
        </div>
        {u.is_active ? <span className="tag green"><CheckCircle2 size={13} />Faol</span> : <span className="tag red"><Ban size={13} />Bloklangan</span>}
      </div>
      <div className="uc-info">
        <div><Phone size={14} />{u.phone || <em>telefon kiritilmagan</em>}</div>
        <div><Send size={14} />{u.chat_id ? <span className="mono">{u.chat_id}</span> : <em>Telegram ulanmagan</em>}</div>
        <div><Clock size={14} />{u.last_login ? dt(u.last_login) : <em>hali kirmagan</em>}</div>
      </div>
      <div className="uc-perms">
        <div className="uc-ph"><ShieldCheck size={15} />{u.is_super ? <b>Barcha ruxsatlar</b> : <b>{u.perms.length} ta ruxsat</b>}
          {!u.is_super && u.perms.length > 0 && <button className="lnk" onClick={() => setMore(!more)}>{more ? 'Yig\'ish' : 'Batafsil'}</button>}</div>
        {u.is_super ? <small className="mut">Sadmin cheklanmagan, ruxsatlari o'zgarmaydi</small>
          : u.perms.length === 0 ? <em className="mut">Ruxsat berilmagan — faqat bosh sahifa</em>
          : <div className="uc-groups">{Object.entries(groups).map(([g, ps]) => (
            <div key={g} className="ucg"><span className="ucg-t">{g}</span>
              <div className="tags">{(more ? ps : ps.slice(0, 0)).map((p) => <span key={p.code} className="tag">{p.name}</span>)}
                {!more && <span className="tag blue">{ps.length} ta</span>}</div></div>))}</div>}
      </div>
      <div className="uc-acts">
        <button className="btn ghost sm" onClick={() => onEdit(u)}><Pencil size={15} />Tahrirlash</button>
        {!u.is_super && <>
          <button className="btn ghost sm" onClick={() => onToggle(u)}>{u.is_active ? <><Ban size={15} />Bloklash</> : <><UserCheck size={15} />Faollashtirish</>}</button>
          <button className="btn ghost sm del" onClick={() => onDelete(u)}><Trash2 size={15} />O'chirish</button></>}
      </div>
    </div>
  )
}

export default function Users() {
  const { boot } = useAuth()
  const toast = useToast()
  const [list, setList] = useState(null)
  const [edit, setEdit] = useState(undefined)   // undefined = yopiq, null = yangi
  const [del, setDel] = useState(null)
  const [q, setQ] = useState('')
  const [flt, setFlt] = useState('all')
  const load = () => api.get('/users').then(setList).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load() }, [])
  const toggle = async (u) => { try { await api.patch(`/users/${u.id}`, { is_active: !u.is_active }); load() } catch (e) { toast(e.message, 'err') } }
  const shown = (list || []).filter((u) => (flt === 'all' || (flt === 'on' ? u.is_active : !u.is_active)) &&
    (!q.trim() || `${u.username} ${u.full_name} ${u.phone}`.toLowerCase().includes(q.trim().toLowerCase())))
  const nOn = (list || []).filter((u) => u.is_active).length
  return (
    <div className="usr">
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Xodimlar va ruxsatlar</h2><p className="sub">Har bir xodim uchun alohida kartochka: sadmin qaysi sahifalarni ko'rishi va qaysi amallarni bajarishini belgilaydi.</p></div>
        <div className="filters">
          <div className="usr-stats">
            <button className={`us ${flt === 'all' ? 'on' : ''}`} onClick={() => setFlt('all')}><UsersIcon size={16} /><b>{list?.length ?? '…'}</b>Hammasi</button>
            <button className={`us green ${flt === 'on' ? 'on' : ''}`} onClick={() => setFlt('on')}><UserCheck size={16} /><b>{nOn}</b>Faol</button>
            <button className={`us red ${flt === 'off' ? 'on' : ''}`} onClick={() => setFlt('off')}><UserX size={16} /><b>{list ? list.length - nOn : '…'}</b>Bloklangan</button>
          </div>
          <div className="searchbar sm usr-search"><Search size={16} /><input placeholder="Login, ism yoki telefon…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div className="spacer" /><button className="btn primary" onClick={() => setEdit(null)}><UserPlus size={17} />Xodim qo'shish</button>
        </div>
      </div>
      {!list ? <Spinner /> : shown.length === 0 ? <div className="card pad mut">Xodim topilmadi.</div> : (
        <div className="ucards">{shown.map((u) => <UserCard key={u.id} u={u} catalog={boot.perms} onEdit={setEdit} onToggle={toggle} onDelete={setDel} />)}</div>)}
      {edit !== undefined && <UserModal u={edit} catalog={boot.perms} onClose={() => setEdit(undefined)} onSaved={load} />}
      {del && <DeleteModal u={del} onClose={() => setDel(null)} onDone={load} />}
    </div>
  )
}
