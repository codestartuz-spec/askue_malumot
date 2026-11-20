import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bot, Megaphone, Users, Plus, Trash2, Send, PlugZap, Unplug, KeyRound, BookOpen, RefreshCw, ShieldAlert, Settings2, Activity, DatabaseBackup } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Confirm, Spinner, useToast } from '../ui'
import TgBotLink from '../TgBot'
import SystemStatus from './SystemStatus'
import Backup from './Backup'

export default function Settings() {
  const { user, can, reload } = useAuth()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const [d, setD] = useState(null)
  const [token, setToken] = useState('')
  const [chat, setChat] = useState('')
  const [busy, setBusy] = useState('')
  const [ask, setAsk] = useState(null)       // tasdiqlash oynasi: { title, text, ok, run }
  const load = () => api.get('/telegram').then(setD).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t) }, [])

  const TABS = [
    can('settings.manage') && { k: 'bot', label: 'Bot va guruh sozlamalari', icon: Settings2 },
    can('system.view') && { k: 'tizim', label: 'Tizim va server holati', icon: Activity },
    can('backup.manage') && { k: 'zaxira', label: 'Zaxira nusxa', icon: DatabaseBackup },
  ].filter(Boolean)
  const tab = TABS.find((t) => t.k === sp.get('t'))?.k || TABS[0].k

  const run = async (name, fn, ok) => {
    setBusy(name)
    try { const r = await fn(); if (ok) toast(typeof ok === 'function' ? ok(r) : ok); await load(); reload(); return r }
    catch (e) { toast(e.message, 'err') } finally { setBusy('') }
  }
  const saveToken = () => run('token', () => api.put('/telegram/token', { token }), (r) => `Bot ulandi: @${r.bot_username}`).then(() => setToken(''))
  const addChat = () => run('chat', async () => { const r = await api.post('/telegram/chats', { chat }); setChat(''); if (r.warning) toast(r.warning, 'err'); return r }, (r) => `Qo'shildi: ${r.title}`)
  const delChat = (c) => setAsk({ title: 'Kanalni olib tashlash', text: `«${c.title}» ro'yxatdan olib tashlansinmi?`, ok: 'Olib tashlash', run: () => run('del' + c.id, () => api.del(`/telegram/chats/${c.id}`), "O'chirildi") })

  if (!d) return <Spinner />
  return (
    <div className="settings">
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Sozlamalar</h2>
          <p className="sub">Telegram bot, kanal va guruhlar, tizim holati va zaxira nusxa.</p></div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.k} role="tab" aria-selected={t.k === tab} className={`tab ${t.k === tab ? 'on' : ''}`} onClick={() => setSp({ t: t.k }, { replace: true })}>
            <t.icon size={18} /><span>{t.label}</span></button>))}
        <i className="tab-glow" style={{ '--i': TABS.findIndex((t) => t.k === tab), '--n': TABS.length }} />
      </div>

      {tab === 'tizim' && <SystemStatus />}
      {tab === 'zaxira' && <Backup />}

      {tab === 'bot' && (
        <div className="set-halves">
          <section className="card pad set-card">
            <h3><Bot size={20} />Telegram bot <span className="grow" /><TgBotLink label="Botga o'tish" /></h3>
            <div className={`bot-state ${d.configured ? 'ok' : 'off'}`}>
              {d.configured ? <><PlugZap size={20} /><div><b>@{d.bot_username}</b><small>{d.bot_name} • token: {d.token}</small></div></> : <><Unplug size={20} /><div><b>Bot ulanmagan</b><small>Token kiritib ulang</small></div></>}
              {d.configured && <span className={`tag ${d.poll_alive ? 'green' : 'amber'}`}>{d.poll_alive ? 'Bot javob bermoqda' : 'Worker kutilmoqda'}</span>}
            </div>
            {user.is_super ? (
              <>
                <label className="field"><span><KeyRound size={14} />Bot tokeni (@BotFather beradi)</span>
                  <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456789:AA..." autoComplete="off" /></label>
                <div className="row-btns">
                  <button className="btn primary" disabled={!token.trim() || busy === 'token'} onClick={saveToken}><PlugZap size={16} />{d.configured ? 'Tokenni almashtirish' : 'Ulash'}</button>
                  {d.configured && <button className="btn ghost" onClick={() => setAsk({ title: 'Botni uzish', text: 'Bot uzilsinmi? Hisobot yuborish va parolni tiklash to‘xtaydi.', ok: 'Uzish', run: () => run('un', () => api.del('/telegram/token'), 'Bot uzildi') })}><Unplug size={16} />Uzish</button>}
                </div>
              </>) : <p className="hint">Tokenni faqat sadmin o'zgartira oladi.</p>}
            <div className="howto grow-fill"><BookOpen size={16} /><div>
              <b>Qanday ulanadi?</b>
              <ol>
                <li>Telegram'da <b>@BotFather</b> orqali bot yarating va tokenni shu yerga kiriting.</li>
                <li>Botni kerakli <b>kanal yoki guruhga admin</b> qilib qo'shing (kanalda «Xabar yuborish» huquqi bilan).</li>
                <li>Bot qo'shilgach kanal/guruh o'ng tomondagi ro'yxatda o'zi paydo bo'ladi. Paydo bo'lmasa, chat ID yoki <code>@nom</code> orqali qo'lda qo'shing.</li>
                <li>Xodimlar botga <b>/start</b> bosib chat ID'sini oladi va profiliga kiritadi — parolni shu orqali tiklaydi.</li>
              </ol></div></div>
          </section>

          <section className="card pad set-card">
            <h3><Megaphone size={20} />Kanal va guruhlar <span className="grow" /><button className="icon-btn" title="Yangilash" onClick={load}><RefreshCw size={16} /></button></h3>
            {d.chats.length === 0 ? <div className="empty sm grow-fill"><Megaphone size={32} /><div>Hali kanal yoki guruh yo'q</div><small>Botni kanalga admin qilib qo'shing — u shu yerda paydo bo'ladi</small></div> : (
              <div className="chat-list grow-fill">{d.chats.map((c) => (
                <div key={c.id} className={`chat static ${c.is_active ? '' : 'off'}`}>
                  <i>{c.kind === 'kanal' ? <Megaphone size={18} /> : <Users size={18} />}</i>
                  <span><b>{c.title}</b><small>{c.kind}{c.username ? ` • @${c.username}` : ''} • {c.source === 'auto' ? 'avtomatik aniqlangan' : "qo'lda qo'shilgan"} • <span className="mono">{c.chat_id}</span>{!c.is_active ? " • bot chiqarib yuborilgan" : ''}</small></span>
                  {can('settings.manage') && <button className="icon-btn danger" onClick={() => delChat(c)} title="Olib tashlash"><Trash2 size={17} /></button>}
                </div>))}</div>)}
            {d.configured && can('settings.manage') && (
              <div className="add-chat">
                <input value={chat} onChange={(e) => setChat(e.target.value)} placeholder="@kanal_nomi yoki -100123456789" onKeyDown={(e) => e.key === 'Enter' && chat.trim() && addChat()} />
                <button className="btn primary" disabled={!chat.trim() || busy === 'chat'} onClick={addChat}><Plus size={16} />Qo'shish</button>
              </div>)}
            {!d.configured && <p className="hint warn-hint"><ShieldAlert size={14} /> Avval botni ulang.</p>}
          </section>
        </div>)}
      {ask && <Confirm title={ask.title} ok={ask.ok} danger onOk={() => { const r = ask.run; setAsk(null); r() }} onCancel={() => setAsk(null)}>{ask.text}</Confirm>}
    </div>
  )
}
