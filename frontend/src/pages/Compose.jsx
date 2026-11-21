import { useEffect, useMemo, useRef, useState } from 'react'
import { Bold, Italic, Underline, Strikethrough, Code2, Link2, ImagePlus, Film, X, Send, Megaphone, Users, CheckCircle2, AlertTriangle, Eye, Smartphone, Play, MailCheck } from 'lucide-react'
import { api, uploadForm } from '../api'
import { ChatTable, useToast } from '../ui'

const MAX_FILES = 10
const MAX_MB = 50

// Serverdagi clean_html bilan bir xil qoidalar: faqat b, i, u, s, code, pre, a
const ALLOWED = /<(\/?)(b|i|u|s|code|pre)>|<a href="(https?:\/\/[^"\s<>]+)">|<\/a>/g
const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
export function cleanHtml(t) {
  let out = '', pos = 0
  for (const m of t.matchAll(ALLOWED)) {
    out += esc(t.slice(pos, m.index)) + m[0]
    pos = m.index + m[0].length
  }
  return out + esc(t.slice(pos))
}
const fmtTime = () => new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
const size = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

function Preview({ title, text, files, ack }) {
  const html = useMemo(() => cleanHtml(text).replace(/\n/g, '<br>'), [text])
  const media = files.filter((f) => f.kind !== 'doc')
  const docs = files.filter((f) => f.kind === 'doc')
  const cls = media.length >= 4 ? 'g4' : `g${media.length}`
  return (
    <div className="tgp">
      <div className="tgp-head">
        <div className="tgp-ava">{(title || 'K').slice(0, 1).toUpperCase()}</div>
        <div><b>{title || 'Kanal yoki guruh'}</b><small>{title ? 'kanal / guruh' : 'tanlanmagan'}</small></div>
      </div>
      <div className="tgp-body">
        {(text.trim() || files.length > 0) ? (
          <div className="tgp-msg">
            {media.length > 0 && (
              <div className={`tgp-media ${cls}`}>
                {media.slice(0, 10).map((f) => (
                  <div key={f.id} className="tgp-m">
                    {f.kind === 'image' ? <img src={f.url} alt="" /> : <><video src={f.url} muted preload="metadata" /><span className="tgp-play"><Play size={22} fill="#fff" /></span></>}
                  </div>))}
              </div>)}
            {docs.map((f) => <div key={f.id} className="tgp-doc"><i><Send size={15} /></i><span><b>{f.file.name}</b><small>{size(f.file.size)}</small></span></div>)}
            {text.trim() && <div className="tgp-text" dangerouslySetInnerHTML={{ __html: html }} />}
            <div className="tgp-meta"><Eye size={12} /> 1 <span>{fmtTime()}</span></div>
            {ack && <div className="tgp-btn">✅ Tanishdim</div>}
          </div>
        ) : <div className="tgp-empty"><Smartphone size={30} /><div>Xabar matnini yozing yoki rasm / video tanlang — shu yerda Telegram'dagi ko'rinishi chiqadi</div></div>}
      </div>
    </div>
  )
}

export default function Compose({ chats }) {
  const toast = useToast()
  const [sel, setSel] = useState(new Set())
  const [msg, setMsg] = useState('')
  const [files, setFiles] = useState([])
  const [link, setLink] = useState(null)       // null | string (havola kiritish maydoni)
  const [busy, setBusy] = useState(false)
  const [up, setUp] = useState(0)
  const [job, setJob] = useState(null)
  const [drag, setDrag] = useState(false)
  const [ack, setAck] = useState(true)
  const ta = useRef(null), fi = useRef(null), timer = useRef(null)
  const filesRef = useRef(files)
  filesRef.current = files
  useEffect(() => () => { clearInterval(timer.current); filesRef.current.forEach((f) => URL.revokeObjectURL(f.url)) }, [])

  const active = chats.filter((c) => c.is_active)
  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const first = active.find((c) => sel.has(c.id))
  const hasMedia = files.some((f) => f.kind !== 'doc')
  const limit = hasMedia ? 1024 : 4096

  const add = (list) => {
    const arr = [...list]
    const room = MAX_FILES - files.length
    if (arr.length > room) toast(`Bir vaqtda ${MAX_FILES} tagacha fayl yuboriladi`, 'err')
    const ok = []
    arr.slice(0, Math.max(room, 0)).forEach((file) => {
      if (file.size > MAX_MB * 1048576) { toast(`«${file.name}» ${MAX_MB} MB dan katta`, 'err'); return }
      const kind = file.type.startsWith('image/') && file.type !== 'image/gif' ? 'image' : file.type.startsWith('video/') ? 'video' : 'doc'
      ok.push({ id: `${file.name}-${file.size}-${Math.random()}`, file, kind, url: URL.createObjectURL(file) })
    })
    setFiles((f) => [...f, ...ok])
  }
  const del = (id) => setFiles((f) => { const x = f.find((a) => a.id === id); if (x) URL.revokeObjectURL(x.url); return f.filter((a) => a.id !== id) })

  const wrap = (open, close = open.replace('<', '</')) => {
    const el = ta.current
    if (!el) return
    const { selectionStart: s, selectionEnd: e } = el
    const mid = msg.slice(s, e) || 'matn'
    const next = msg.slice(0, s) + open + mid + close + msg.slice(e)
    setMsg(next)
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(s + open.length, s + open.length + mid.length) })
  }
  const addLink = () => {
    const u = (link || '').trim()
    if (/^https?:\/\/\S+$/.test(u)) { wrap(`<a href="${u}">`, '</a>'); setLink(null) } else toast("To'g'ri havola kiriting (https://…)", 'err')
  }

  const poll = (id) => {
    clearInterval(timer.current)
    timer.current = setInterval(async () => {
      try {
        const j = await api.get(`/reports/send/${id}`)
        setJob(j)
        if (j.status !== 'running') {
          clearInterval(timer.current); setBusy(false)
          if (j.status === 'done') { toast('Xabar yuborildi'); setMsg(''); setFiles((f) => { f.forEach((x) => URL.revokeObjectURL(x.url)); return [] }) }
        }
      } catch { /* */ }
    }, 1000)
  }
  const send = async () => {
    setBusy(true); setUp(0); setJob(null)
    try {
      const form = new FormData()
      form.append('chat_ids', [...sel].join(','))
      form.append('message', msg)
      form.append('ack', ack ? 'true' : 'false')
      files.forEach((f) => form.append('files', f.file, f.file.name))
      const r = await uploadForm('/telegram/send', form, setUp)
      setJob({ status: 'running', progress: 0, log: '' }); poll(r.id)
    } catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  const ready = (msg.trim() || files.length) && sel.size && !busy && msg.length <= 4096

  if (active.length === 0) {
    return <div className="card pad set-card"><p className="hint">Xabar yuborish uchun kamida bitta kanal yoki guruh bo'lishi kerak. Sozlamalar → «Bot va guruh sozlamalari» bo'limidan qo'shing.</p></div>
  }
  return (
    <div className="compose">
      <section className="card pad set-card">
        <h3><Send size={20} />Yangi xabar </h3>
        <div className="mp-sec dark">1. Qaysi kanal / guruhga</div>
        <ChatTable chats={active} sel={sel} busy={busy} onToggle={toggle} onAll={(v) => setSel(v ? new Set(active.map((c) => c.id)) : new Set())} />
        <div className="mp-sec dark">2. Rasm yoki video <small>(ixtiyoriy, {MAX_FILES} tagacha, har biri {MAX_MB} MB gacha)</small></div>
        <div className={`cdrop ${drag ? 'over' : ''}`} onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files) }} onClick={() => !busy && fi.current?.click()}>
          <span className="cdrop-ic"><ImagePlus size={26} /><Film size={26} /></span>
          <div><b>Fayllarni shu yerga tashlang</b><small>yoki bosib tanlang — JPG, PNG, MP4, MOV…</small></div>
          <input ref={fi} type="file" accept="image/*,video/*" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} />
        </div>
        {files.length > 0 && (
          <div className="thumbs">{files.map((f) => (
            <div key={f.id} className="thumb">
              {f.kind === 'image' ? <img src={f.url} alt="" /> : f.kind === 'video' ? <><video src={f.url} muted preload="metadata" /><span className="tgp-play sm"><Play size={14} fill="#fff" /></span></> : <div className="doc-ic"><Send size={18} /></div>}
              <small>{size(f.file.size)}</small>
              <button className="x" onClick={() => del(f.id)} disabled={busy} title="Olib tashlash"><X size={13} /></button>
            </div>))}</div>)}

        <div className="mp-sec dark">3. Xabar matni</div>
        <div className="fmt-bar">
          <button title="Qalin" onClick={() => wrap('<b>')}><Bold size={16} /></button>
          <button title="Kursiv" onClick={() => wrap('<i>')}><Italic size={16} /></button>
          <button title="Tagiga chizilgan" onClick={() => wrap('<u>')}><Underline size={16} /></button>
          <button title="Ustiga chizilgan" onClick={() => wrap('<s>')}><Strikethrough size={16} /></button>
          <button title="Kod" onClick={() => wrap('<code>')}><Code2 size={16} /></button>
          <button title="Havola" onClick={() => setLink(link === null ? 'https://' : null)}><Link2 size={16} /></button>
          <span className={`cnt ${msg.length > limit ? 'bad' : ''}`}>{msg.length} / {limit}</span>
        </div>
        {link !== null && <div className="link-row"><input autoFocus value={link} onChange={(e) => setLink(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addLink()} placeholder="https://…" /><button className="btn primary sm" onClick={addLink}>Qo'shish</button></div>}
        <textarea ref={ta} rows={6} value={msg} onChange={(e) => setMsg(e.target.value)} disabled={busy} maxLength={4096} placeholder="Xabarni yozing…" />
        {hasMedia && msg.length > 1024 && <p className="hint warn-hint"><AlertTriangle size={14} /> Rasm/video izohi 1024 belgigacha. Matn uzunroq bo'lgani uchun alohida xabar bo'lib yuboriladi.</p>}

        <label className={`ack-opt ${ack ? 'on' : ''}`}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
          <i><MailCheck size={18} /></i><span><b>«Tanishdim» tugmasi</b><small>Xabar tagida tugma chiqadi. Kim va qachon bosgani jurnalga yoziladi; har bir foydalanuvchi bir marta tasdiqlay oladi.</small></span></label>
        <div className="row-btns"><button className="btn primary" disabled={!ready} onClick={send}><Send size={16} />{busy ? 'Yuborilmoqda…' : `Yuborish (${sel.size})`}</button>
          <span className="hint">Hisobot fayllarini «Kunlik dinamika» va «Respublika dinamikasi» sahifalaridagi «Telegramga yuborish» tugmasi orqali yuborasiz.</span></div>
        {busy && !job && up < 1 && <div className="progress sm"><div className="bar" style={{ width: `${Math.round(up * 100)}%` }} /><span>Yuklanmoqda {Math.round(up * 100)}%</span></div>}
        {job && (
          <div className="send-prog">
            <div className="progress"><div className="bar" style={{ width: `${job.progress}%` }} /><span>{Math.round(job.progress)}%</span></div>
            <div className="send-log">{job.log.split('\n').filter(Boolean).map((l, i) => (
              <div key={i} className={l.startsWith('✗') ? 'bad' : 'ok'}>{l.startsWith('✗') ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}<span>{l.slice(2)}</span></div>))}
              {job.status === 'running' && <div className="mut">Yuborilmoqda…</div>}</div>
          </div>)}
      </section>

      <section className="card pad set-card prev-card">
        <h3><Eye size={20} />Jonli ko'rinish <small className="mut">Telegram'da shunday chiqadi</small></h3>
        <Preview title={first?.title} text={msg} files={files} ack={ack} />
        {sel.size > 1 && <p className="hint">Tanlangan {sel.size} ta kanal/guruhning hammasiga bir xil xabar yuboriladi.</p>}
      </section>
    </div>
  )
}
