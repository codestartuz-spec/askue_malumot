import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Send, ScrollText, FileText, Image as ImageIcon, CheckCircle2, AlertTriangle, Users, Megaphone, ChevronRight, MailCheck, Globe2, Table2, RefreshCw, FileBarChart2 } from 'lucide-react'
import { api, qs } from '../api'
import { Empty, Modal, Pager, Spinner, useToast } from '../ui'
import { dt } from '../fmt'
import { useAuth } from '../auth'
import Compose from './Compose'

const KIND = { xabar: { label: 'Xabar', icon: Send, cls: 'blue' }, hisobot: { label: 'Kunlik hisobot', icon: Table2, cls: 'green' }, respublika: { label: 'Qashqadaryo', icon: Globe2, cls: 'amber' }, republic: { label: 'Qashqadaryo', icon: Globe2, cls: 'amber' }, nation: { label: 'Respublika', icon: Globe2, cls: 'teal' }, ag: { label: 'AG', icon: FileBarChart2, cls: 'purple' } }

function PostModal({ id, onClose }) {
  const [p, setP] = useState(null)
  const toast = useToast()
  useEffect(() => { api.get(`/posts/${id}`).then(setP).catch((e) => { toast(e.message, 'err'); onClose() }) }, [id])
  return (
    <Modal wide icon={ScrollText} title={p ? p.title || 'Xabar' : 'Xabar'} onClose={onClose}>
      {!p ? <Spinner /> : (
        <div className="post-d">
          <div className="post-meta">
            <span className={`tag ${KIND[p.kind]?.cls || 'blue'}`}>{KIND[p.kind]?.label}</span>
            <span>{dt(p.created_at)}</span><span>Yuboruvchi: <b>{p.created_by}</b></span>
            <span className={`tag ${p.ack ? 'green' : 'amber'}`}>{p.ack ? '«Tanishdim» tugmasi bor' : 'Tugmasiz'}</span>
          </div>
          {p.body && <div className="post-body" dangerouslySetInnerHTML={{ __html: p.body.replace(/<(?!\/?(b|i|u|s|code|pre|a)\b)[^>]*>/g, '').replace(/\n/g, '<br>') }} />}
          {p.files?.length > 0 && <div className="post-files">{p.files.map((f) => <span key={f}><FileText size={14} />{f}</span>)}</div>}
          <h4>Kanal va guruhlar</h4>
          {p.items.map((it) => (
            <div key={it.id} className={`post-item ${it.status}`}>
              <div className="pi-h">
                {it.status === 'ok' ? <CheckCircle2 size={17} /> : it.status === 'err' ? <AlertTriangle size={17} /> : <RefreshCw size={16} />}
                <b>{it.chat}</b>
                <span className="mut">{it.sent_at ? dt(it.sent_at) : 'kutilmoqda'}</span>
                {p.ack && <span className="tag green ml"><MailCheck size={13} />{it.acks.length} ta tanishdi</span>}
              </div>
              {it.error && <div className="pi-err">{it.error}</div>}
              {it.acks.length > 0 && (
                <table className="list slim"><thead><tr><th>№</th><th>Kim</th><th>Telegram</th><th>Qachon</th></tr></thead>
                  <tbody>{it.acks.map((a, i) => <tr key={i}><td className="mut">{i + 1}</td><td><b>{a.name || '—'}</b></td><td>{a.username ? `@${a.username}` : ''}</td><td>{dt(a.at)}</td></tr>)}</tbody></table>)}
              {p.ack && it.status === 'ok' && it.acks.length === 0 && <div className="mut sm">Hali hech kim tanishmagan</div>}
            </div>))}
        </div>)}
    </Modal>
  )
}

function Journal() {
  const [kind, setKind] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const toast = useToast()
  const load = () => api.get(`/posts${qs({ kind, page })}`).then(setData).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load() }, [kind, page])
  useEffect(() => { const t = setInterval(load, 20000); return () => clearInterval(t) }, [kind, page])
  return (
    <div className="card pad journal">
      <div className="jr-top">
        <div className="chips">{[['', 'Hammasi'], ['xabar', 'Xabarlar'], ['hisobot', 'Kunlik hisobotlar'], ['republic', 'Qashqadaryo dinamikasi'], ['nation', 'Respublika dinamikasi'], ['ag', 'AG']].map(([k, l]) => (
          <button key={k} className={`chip ${kind === k ? 'on' : ''}`} onClick={() => { setKind(k); setPage(1) }}>{l}</button>))}</div>
        <button className="icon-btn" title="Yangilash" onClick={load}><RefreshCw size={16} /></button>
      </div>
      {!data ? <Spinner /> : data.items.length === 0 ? <Empty icon={ScrollText}>Hali hech narsa yuborilmagan.</Empty> : (
        <div className="tbl-scroll"><table className="list jr-table">
          <thead><tr><th>№</th><th>Turi</th><th>Mazmuni</th><th>Kimga</th><th>Tanishdi</th><th>Yuboruvchi</th><th>Vaqti</th><th></th></tr></thead>
          <tbody>{data.items.map((r, i) => {
            const K = KIND[r.kind] || KIND.xabar
            return (
              <tr key={r.id} className="clickable" onClick={() => setOpen(r.id)}>
                <td className="mut">{(page - 1) * data.size + i + 1}</td>
                <td><span className={`tag ${K.cls}`}><K.icon size={13} />{K.label}</span></td>
                <td className="jr-title"><b>{r.title || '—'}</b>{r.files.length > 0 && <small><ImageIcon size={12} />{r.files.length} ta fayl</small>}</td>
                <td>{r.ok}{r.err > 0 && <span className="bad-n"> / {r.err} xato</span>} <small className="mut">/ {r.chats} ta</small></td>
                <td>{r.ack ? <span className="tag green"><MailCheck size={13} />{r.acks}</span> : <span className="mut">—</span>}</td>
                <td>{r.created_by}</td>
                <td>{dt(r.created_at)}</td>
                <td><ChevronRight size={16} /></td>
              </tr>)
          })}</tbody></table></div>)}
      {data && data.total > data.size && <div className="jr-pg"><Pager page={page} size={data.size} total={data.total} onPage={setPage} /></div>}
      {open && <PostModal id={open} onClose={() => setOpen(null)} />}
    </div>
  )
}

export default function Messages() {
  const [sp, setSp] = useSearchParams()
  const { can } = useAuth()
  const cm = can('telegram.message'), cj = can('telegram.journal')
  const tab = (sp.get('t') === 'jurnal' && cj) || !cm ? 'jurnal' : 'yangi'
  const [chats, setChats] = useState(null)
  useEffect(() => { api.get('/telegram/chats').then(setChats).catch(() => setChats([])) }, [])
  const TABS = [cm && { k: 'yangi', label: 'Yangi xabar', icon: Send }, cj && { k: 'jurnal', label: 'Yuborilganlar jurnali', icon: ScrollText }].filter(Boolean)
  return (
    <div className="settings msgs">
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Xabar yuborish</h2>
          <p className="sub">Telegram kanal va guruhlarga xabar, rasm va video yuboring. Har bir yuborilgan xabar jurnalga yoziladi — kim, qachon va kimlar «Tanishdim» tugmasini bosgani ko'rinadi.</p></div>
      </div>
      {TABS.length > 1 && <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.k} role="tab" aria-selected={t.k === tab} className={`tab ${t.k === tab ? 'on' : ''}`} onClick={() => setSp({ t: t.k }, { replace: true })}>
            <t.icon size={18} /><span>{t.label}</span></button>))}
      </div>}
      {tab === 'jurnal' ? <Journal /> : chats ? <Compose chats={chats} onSent={() => {}} /> : <Spinner />}
    </div>
  )
}
