import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Home, Table2, MapPinned, HardHat, UploadCloud, Users, ScrollText, LogOut, KeyRound, Menu, Database, X, ChevronDown, Zap, Settings as Cog, Globe2, UserRound, Phone, Send } from 'lucide-react'
import { useAuth } from './auth'
import { Confirm, Logo, Modal, useToast } from './ui'
import EnergyBackground from './bg'
import { api } from './api'
import { dmy, dt } from './fmt'

const NAV = [
  { to: '/', icon: Home, label: 'Bosh sahifa', end: true },
  { group: "Ma'lumotlar" },
  { to: '/dinamika', icon: Table2, label: 'Kunlik dinamika', any: ['view.konsentrator', 'view.aloqa', 'view.obxod'] },
  { to: '/respublika', icon: Globe2, label: 'Respublika dinamikasi', perm: 'republic.view' },
  { to: '/xarita', icon: MapPinned, label: 'Xarita', perm: 'map.view' },
  { group: 'Boshqaruv' },
  { to: '/xabarlar', icon: Send, label: 'Xabar yuborish', perm: 'telegram.send' },
  { to: '/brigadalar', icon: HardHat, label: 'Brigadalar', perm: 'brigade.view' },
  { to: '/yuklash', icon: UploadCloud, label: "Ma'lumot yuklash", perm: 'data.upload' },
  { to: '/sozlamalar', icon: Cog, label: 'Sozlamalar', any: ['settings.manage', 'system.view', 'backup.manage'] },
  { to: '/xodimlar', icon: Users, label: 'Xodimlar va ruxsatlar', sadmin: true },
  { to: '/jurnal', icon: ScrollText, label: 'Harakatlar jurnali', sadmin: true },
]

function ProfileModal({ onClose }) {
  const { user, reload } = useAuth()
  const toast = useToast()
  const [f, setF] = useState({ full_name: user.full_name || '', phone: user.phone || '', chat_id: user.chat_id || '' })
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try { await api.patch('/auth/profile', f); await reload(); toast('Profil saqlandi'); onClose() }
    catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <Modal title="Mening profilim" icon={UserRound} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Bekor qilish</button><button className="btn primary" disabled={busy} onClick={save}>Saqlash</button></>}>
      <label className="field"><span>F.I.Sh.</span><input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></label>
      <label className="field"><span><Phone size={14} />Telefon raqami</span><input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="+998 90 123 45 67" inputMode="tel" /></label>
      <label className="field"><span><Send size={14} />Telegram chat ID</span><input value={f.chat_id} onChange={(e) => setF({ ...f, chat_id: e.target.value })} placeholder="Masalan: 123456789" inputMode="numeric" />
        <small className="hint">Chat ID'ni bilish uchun Telegram'da ASKUE botiga <b>/start</b> yuboring — bot chat ID'ni yozib beradi. Parolni unutsangiz, shu chat orqali tiklaysiz.</small></label>
    </Modal>
  )
}

function PasswordModal({ onClose }) {
  const toast = useToast()
  const [f, setF] = useState({ old_password: '', new_password: '' })
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try { await api.post('/auth/change-password', f); toast("Parol almashtirildi"); onClose() }
    catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <Modal title="Parolni almashtirish" icon={KeyRound} onClose={onClose}
      footer={<><button className="btn ghost" onClick={onClose}>Bekor qilish</button><button className="btn primary" disabled={busy} onClick={save}>Saqlash</button></>}>
      <label className="field"><span>Joriy parol</span><input type="password" value={f.old_password} onChange={(e) => setF({ ...f, old_password: e.target.value })} /></label>
      <label className="field"><span>Yangi parol</span><input type="password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></label>
    </Modal>
  )
}

export default function Layout({ children }) {
  const { user, can, boot, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  const [pw, setPw] = useState(false)
  const [prof, setProf] = useState(false)
  const [bye, setBye] = useState(false)
  const loc = useLocation()
  useEffect(() => { setOpen(false); setMenu(false) }, [loc.pathname])
  const items = NAV.filter((n) => n.group || (n.sadmin ? user.is_super : n.any ? n.any.some(can) : !n.perm || can(n.perm)))
  const shown = items.filter((n, i) => !n.group || (items[i + 1] && !items[i + 1].group))
  const title = NAV.find((n) => n.to && (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label || ''
  const lu = boot?.last_upload
  return (
    <div className="shell">
      <EnergyBackground />
      <aside className={`side ${open ? 'open' : ''}`}>
        <div className="side-logo">
          <Logo theme="dark" height={64} />
          <button className="icon-btn only-mobile" onClick={() => setOpen(false)}><X size={20} /></button>
        </div>
        <div className="side-brand"><Zap size={14} /><span>ASKUE ma'lumot</span></div>
        <nav>
          {shown.map((n, i) => n.group
            ? <div key={i} className="nav-group">{n.group}</div>
            : <NavLink key={n.to} to={n.to} end={n.end} className="nav-item"><n.icon size={19} /><span>{n.label}</span></NavLink>)}
        </nav>
        <div className="side-foot">
          <div className="foot-line"><span className="pulse-dot" />Qashqadaryo hududiy filiali</div>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="top">
          <button className="icon-btn only-mobile" onClick={() => setOpen(true)} aria-label="Menyu"><Menu size={22} /></button>
          <h1 className="top-title">{title}</h1>
          <div className="top-right">
            {lu && <div className="chip" title={`Yuklagan: ${lu.by}, ${dt(lu.finished_at)}`}><Database size={15} /><span>Ma'lumot: {dmy(lu.snap_date)}</span></div>}
            <div className="user" onClick={() => setMenu(!menu)}>
              <div className="avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</div>
              <div className="user-name"><b>{user.full_name || user.username}</b><small>{user.is_super ? 'Sadmin' : 'Xodim'}</small></div>
              <ChevronDown size={16} />
              {menu && (
                <div className="user-menu" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => { setProf(true); setMenu(false) }}><UserRound size={16} />Mening profilim</button>
                  <button onClick={() => { setPw(true); setMenu(false) }}><KeyRound size={16} />Parolni almashtirish</button>
                  <button onClick={() => { setBye(true); setMenu(false) }}><LogOut size={16} />Chiqish</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className={`content ${loc.pathname.startsWith('/xarita') ? 'content-map' : ''}`}>{children}</main>
      </div>
      {pw && <PasswordModal onClose={() => setPw(false)} />}
      {prof && <ProfileModal onClose={() => setProf(false)} />}
      {bye && <Confirm icon={LogOut} title="Tizimdan chiqish" ok="Ha, chiqish" cancel="Qolish" danger onOk={logout} onCancel={() => setBye(false)}>
        Haqiqatan ham tizimdan chiqmoqchimisiz? <small className="hint">Saqlanmagan o'zgarishlar bo'lsa, yo'qolishi mumkin.</small></Confirm>}
    </div>
  )
}
