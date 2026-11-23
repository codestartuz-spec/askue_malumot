// «Kunlik topshiriq» — alohida bo'lim: 5 ta Excel fayl → jadvallar va nomma-nom topshiriq fayli.
// Tablar: Fayl yuklash · Arxiv · Sozlamalar (boshqa bo'limlardan mustaqil).
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Archive, ArrowDown, ArrowUp, CheckCircle2, ClipboardList, Download, Eye, FileArchive, FileSpreadsheet, Loader2, Megaphone, Package, RefreshCw, Save, Send, Settings2, Trash2, UploadCloud, X, AlertTriangle, MailCheck } from 'lucide-react'
import { api, download, uploadForm } from '../api'
import { useAuth } from '../auth'
import { ChatTable, Confirm, Empty, Modal, Spinner, useToast } from '../ui'
import { dmy, dt, num } from '../fmt'

const KINDS = [
  { k: 'area', label: 'AreaInformationReport', hint: 'area' },
  { k: 'status', label: 'CommissioningStatus', hint: 'commissioning' },
  { k: 'direct', label: 'DirectMeter', hint: 'directmeter' },
  { k: 'nometer', label: 'NoMeterData', hint: 'nometer' },
  { k: 'online', label: 'Online_Device_Monitoring', hint: 'online_device' },
]
const kindOf = (name = '') => {
  const n = name.toLowerCase().replace(/[^a-z0-9_]/g, '')
  return KINDS.find((x) => n.includes(x.hint))?.k || ''
}
const OUT = [{ k: 't1', t: 't1_title' }, { k: 't2', t: 't2_title' }, { k: 'task', t: 'task_title' }]
const CATS = [['aholi', 'Aholi'], ['ulgurji', 'Ulgurji'], ['balans', 'Balans']]
const mb = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

/* ------------------------------------------------------------------ jadval (skrinshotdagi dizayn) */
function DailyTable({ tb, region, date }) {
  const cls = (h) => [...(h.c || '').split(' ').filter(Boolean).map((x) => 'h-' + x), h.rot && 'rot', h.it && 'it'].filter(Boolean).join(' ')
  return (
    <div className="card tcard daily-card">
      <div className="daily-top"><span>Hudud nomi: <b>{region}</b></span><b>{dmy(date)}</b></div>
      <div className="tbl-scroll">
        <table className={`dyn-table daily-table dt-${tb.key}`}>
          <thead>{tb.head.map((hr, i) => (
            <tr key={i}>{hr.map((h, j) => <th key={j} rowSpan={h.rs} colSpan={h.cs} className={cls(h)}><span>{h.l}</span></th>)}</tr>))}</thead>
          <tbody>
            <tr className="total"><td className="name">Jami</td>{tb.cols.map((c) => <td key={c.k} className={`n ${c.c ? 'c-' + c.c : ''}`}>{num(tb.total[c.k]) === '0' ? '' : num(tb.total[c.k])}</td>)}</tr>
            {tb.rows.map((r) => (
              <tr key={r.name}><td className="name">{r.name}</td>
                {tb.cols.map((c) => <td key={c.k} className={`n ${c.c ? 'c-' + c.c : ''} ${c.cream ? 'cream' : ''}`}>{r.v[c.k] ? num(r.v[c.k]) : ''}</td>)}</tr>))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ Telegramga yuborish */
function SendModal({ b, titles, defaults, onClose }) {
  const toast = useToast()
  const [chats, setChats] = useState(null)
  const [files, setFiles] = useState(new Set(OUT.map((o) => o.k)))
  const [sel, setSel] = useState(null)
  const [ack, setAck] = useState(false)
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)
  useEffect(() => {
    api.get('/daily/chats').then((c) => { setChats(c); setSel(new Set(c.filter((x) => OUT.some((o) => (defaults[o.k] || []).includes(x.id))).map((x) => x.id))) })
      .catch((e) => { toast(e.message, 'err'); setChats([]); setSel(new Set()) })
    return () => clearInterval(timer.current)
  }, [])
  const flip = (setter, k) => setter((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const go = async () => {
    setBusy(true)
    try {
      const r = await api.post(`/daily/${b.id}/send`, { files: OUT.map((o) => o.k).filter((k) => files.has(k)), chat_ids: [...sel], ack })
      setJob({ status: 'running', progress: 0, log: '' })
      timer.current = setInterval(async () => {
        try {
          const j = await api.get(`/reports/send/${r.id}`)
          setJob(j)
          if (j.status !== 'running') { clearInterval(timer.current); setBusy(false); if (j.status === 'done') toast('Yuborish yakunlandi') }
        } catch { /* */ }
      }, 1200)
    } catch (e) { toast(e.message, 'err'); setBusy(false) }
  }
  return (
    <Modal wide icon={Send} title={`Telegramga yuborish — ${dmy(b.date)}`} onClose={busy ? () => {} : onClose}
      footer={<><div className="foot-info">{files.size} ta fayl{sel?.size ? ` → ${sel.size} ta kanal` : ''}</div>
        <button className="btn ghost" onClick={onClose} disabled={busy}>Yopish</button>
        <button className="btn primary" disabled={busy || !files.size || !sel?.size} onClick={go}><Send size={16} />Yuborish</button></>}>
      <div className="send-grid">
        <div>
          <div className="mp-sec dark">1. Qaysi fayllar</div>
          <div className="opts">{OUT.map((o) => (
            <label key={o.k} className={`opt ${files.has(o.k) ? 'on' : ''}`}><input type="checkbox" checked={files.has(o.k)} onChange={() => flip(setFiles, o.k)} disabled={busy} />
              <i><FileSpreadsheet size={20} /></i><span><b>{titles[o.t]}</b><small>Excel fayl</small></span></label>))}</div>
        </div>
        <div>
          <div className="mp-sec dark">2. Qaysi kanal yoki guruhga</div>
          {!chats ? <Spinner /> : chats.length === 0 ? (
            <div className="empty sm"><Megaphone size={30} /><div>Hali kanal yoki guruh qo'shilmagan. <Link to="/sozlamalar" onClick={onClose}>Sozlamalar</Link> bo'limidan qo'shing.</div></div>
          ) : <ChatTable chats={chats} sel={sel} busy={busy} onToggle={(id) => flip(setSel, id)} onAll={(v) => setSel(v ? new Set(chats.map((c) => c.id)) : new Set())} />}
        </div>
      </div>
      <label className={`ack-opt ${ack ? 'on' : ''}`}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={busy} />
        <i><MailCheck size={18} /></i><span><b>«Tanishdim» tugmasi</b><small>Oxirgi fayl tagida tugma chiqadi; kim bosgani «Xabar yuborish → Jurnal» da ko'rinadi</small></span></label>
      {job && (<div className="send-prog"><div className="progress"><div className="bar" style={{ width: `${job.progress}%` }} /><span>{Math.round(job.progress)}%</span></div>
        <div className="send-log">{job.log.split('\n').filter(Boolean).map((l, i) => (
          <div key={i} className={l.startsWith('✗') ? 'bad' : 'ok'}>{l.startsWith('✗') ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}<span>{l.slice(2)}</span></div>))}</div></div>)}
    </Modal>
  )
}

/* ------------------------------------------------------------------ bitta kun: holat, jadvallar, amallar */
function Batch({ id, onChanged, onDeleted, titles, defaults }) {
  const { can } = useAuth()
  const toast = useToast()
  const [b, setB] = useState(null)
  const [send, setSend] = useState(false)
  const [del, setDel] = useState(false)
  const [map, setMap] = useState({})
  const [busy, setBusy] = useState('')
  const live = b && (b.status === 'queued' || b.status === 'running')
  const load = useCallback(() => api.get(`/daily/${id}`).then((d) => { setB(d); onChanged?.(d) }).catch((e) => toast(e.message, 'err')), [id])
  useEffect(() => { setB(null); load() }, [id])
  useEffect(() => { if (!live) return undefined; const t = setInterval(load, 1200); return () => clearInterval(t) }, [live, load])
  useEffect(() => { if (b?.status === 'ask') setMap(Object.fromEntries(b.ask.map((a) => [a.value, '']))) }, [b?.status])
  if (!b) return <Spinner />
  const run = async (name, fn, ok) => { setBusy(name); try { await fn(); if (ok) toast(ok); await load() } catch (e) { toast(e.message, 'err') } finally { setBusy('') } }
  const dl = (which, fallback) => run(which, () => download(`/daily/${id}/file/${which}`, fallback))
  const zip = (what) => run('zip' + what, () => download(`/daily/${id}/zip/${what}`, `Kunlik_${what}.zip`))
  return (
    <div className="daily-batch">
      <div className="daily-head">
        <h3><ClipboardList size={20} />{dmy(b.date)} <small className="mut">· {b.by}, {dt(b.at)}</small></h3>
        <div className="row-btns">
          {b.status === 'done' && can('daily.send') && can('telegram.send') && <button className="btn primary" onClick={() => setSend(true)}><Send size={16} />Telegramga yuborish</button>}
          {can('daily.upload') && !live && <button className="btn ghost" disabled={!!busy} onClick={() => run('re', () => api.post(`/daily/${id}/recompute`), 'Qayta hisoblash boshlandi')} title="Sozlamalar o'zgargan bo'lsa"><RefreshCw size={16} />Qayta hisoblash</button>}
          {can('daily.delete') && <button className="btn ghost danger" onClick={() => setDel(true)}><Trash2 size={16} />O'chirish</button>}
        </div>
      </div>
      <div className="daily-files">{KINDS.map((x) => { const f = b.files[x.k]; return (
        <div key={x.k} className={`dfile ${f ? 'ok' : ''}`}><FileArchive size={16} /><span><b>{x.label}</b><small>{f ? `${f.name} · ${mb(f.size)}${f.rows != null ? ` · ${num(f.rows)} qator` : ''}` : '—'}</small></span>
          {f && can('daily.original') && <button className="icon-btn" title="Asl faylni yuklab olish" onClick={() => dl(x.k, f.name)}><Download size={15} /></button>}</div>) })}
        {can('daily.original') && <button className="btn ghost sm" disabled={!!busy} onClick={() => zip('orig')}><Package size={15} />Asl fayllar (ZIP)</button>}
      </div>
      {live && <div className="send-prog"><div className="progress"><div className="bar" style={{ width: `${Math.max(b.progress, 4)}%` }} /><span>{Math.round(b.progress)}%</span></div><div className="mut"><Loader2 size={14} className="spin" /> {b.message || 'Navbatda…'}</div></div>}
      {b.status === 'error' && <div className="alert"><AlertTriangle size={16} />{b.message}</div>}
      {b.status === 'ask' && (
        <div className="card pad ask-card">
          <h4><AlertTriangle size={17} />Iste'molchi turini belgilang</h4>
          <p className="mut">Fayldagi quyidagi turlar qaysi guruhga kirishini ko'rsating. Javob saqlanadi — keyingi yuklashlarda qayta so'ralmaydi.</p>
          {b.ask.map((a) => (
            <label key={a.value} className="ask-row"><span><b>{a.value}</b><small className="mut"> · {num(a.count)} ta hisoblagich</small></span>
              <select value={map[a.value] || ''} onChange={(e) => setMap({ ...map, [a.value]: e.target.value })}><option value="">— tanlang —</option>{CATS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>))}
          {can('daily.upload')
            ? <button className="btn primary" disabled={!!busy || b.ask.some((a) => !map[a.value])} onClick={() => run('types', () => api.post(`/daily/${id}/types`, { map }), 'Saqlandi, hisoblanmoqda')}><Save size={16} />Saqlash va davom etish</button>
            : <div className="mut">Buni «5 ta Excel faylni yuklash» ruxsati bor xodim belgilaydi.</div>}
        </div>)}
      {b.status === 'done' && (<>
        <div className="row-btns daily-dl">
          {OUT.map((o) => <button key={o.k} className="btn ghost" disabled={!!busy} onClick={() => dl(o.k, `${titles[o.t]}.xlsx`)}><FileSpreadsheet size={16} />{titles[o.t]}</button>)}
          <button className="btn ghost" disabled={!!busy} onClick={() => zip('out')}><Package size={16} />Hammasi (ZIP)</button>
        </div>
        <div className="daily-counts mut">Topshiriq fayli: offline kontsentratorlar <b>{num(b.counts.offline)}</b> · aloqasiz hisoblagichlar <b>{num(b.counts.nometer)}</b> · primichka <b>{num(b.counts.direct)}</b></div>
        {b.tables.map((tb) => <DailyTable key={tb.key} tb={tb} region={b.region} date={b.date} />)}
      </>)}
      {send && <SendModal b={b} titles={titles} defaults={defaults} onClose={() => setSend(false)} />}
      {del && <Confirm icon={Trash2} title="Kunni o'chirish" ok="Ha, o'chirish" danger onOk={() => run('del', async () => { await api.del(`/daily/${id}`); setDel(false); onDeleted?.() }, "O'chirildi")} onCancel={() => setDel(false)}>
        {dmy(b.date)} sanasidagi yuklangan fayllar, jadvallar va tayyor Excel fayllar serverdan o'chiriladi. <small className="hint">Buni qaytarib bo'lmaydi.</small></Confirm>}
    </div>
  )
}

/* ------------------------------------------------------------------ Fayl yuklash tabi */
function UploadTab({ titles, defaults }) {
  const toast = useToast()
  const { can } = useAuth()
  const [files, setFiles] = useState([])
  const [day, setDay] = useState('')
  const [pr, setPr] = useState(null)
  const [cur, setCur] = useState(null)
  const ref = useRef(null)
  const [over, setOver] = useState(false)
  const add = (list) => setFiles((old) => {
    const m = new Map(old.map((f) => [f.name, f]))
    ;[...list].forEach((f) => m.set(f.name, f))
    return [...m.values()]
  })
  const by = Object.fromEntries(files.map((f) => [kindOf(f.name), f]))
  const ok = files.length === 5 && KINDS.every((x) => by[x.k])
  const go = async () => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('day', day)
    setPr(0)
    try { const r = await uploadForm('/daily/upload', form, setPr); setCur(r.id); setFiles([]); toast(r.replaced ? 'Shu sana qayta yuklandi — jadvallar tayyorlanmoqda' : 'Fayllar yuklandi — jadvallar tayyorlanmoqda') }
    catch (e) { toast(e.message, 'err') } finally { setPr(null) }
  }
  if (!can('daily.upload')) return <div className="card pad"><Empty icon={UploadCloud}>Fayl yuklash uchun ruxsat berilmagan. Arxivdan tayyor fayllarni ko'rishingiz mumkin.</Empty></div>
  return (
    <div className="daily-upload">
      <div className="card pad">
        <h3 className="sec-h"><UploadCloud size={20} />Bugungi 5 ta yangi Excel fayl</h3>
        <div className={`drop ${over ? 'over' : ''} ${files.length ? 'has' : ''}`} onClick={() => ref.current.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files) }}>
          <input ref={ref} type="file" accept=".xlsx" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} />
          <div className="drop-ic"><UploadCloud size={30} /></div>
          <b>5 ta faylni bir vaqtda tashlang yoki tanlang</b>
          <small>AreaInformationReport · CommissioningStatus · DirectMeter · NoMeterData · Online_Device_Monitoring (.xlsx)</small>
        </div>
        <div className="daily-files">{KINDS.map((x) => { const f = by[x.k]; return (
          <div key={x.k} className={`dfile ${f ? 'ok' : ''}`}>{f ? <CheckCircle2 size={16} /> : <FileArchive size={16} />}<span><b>{x.label}</b><small>{f ? `${f.name} · ${mb(f.size)}` : 'tanlanmagan'}</small></span>
            {f && <button className="icon-btn" onClick={() => setFiles(files.filter((y) => y !== f))} title="Olib tashlash"><X size={15} /></button>}</div>) })}</div>
        {files.some((f) => !kindOf(f.name)) && <small className="hint">Ba'zi fayl nomlari tanish emas — server fayl turini sarlavhasi bo'yicha o'zi aniqlaydi.</small>}
        <div className="daily-go">
          <label className="field"><span>Sana (bo'sh qoldirsangiz — bugungi kun)</span><input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></label>
          <button className="btn primary" disabled={files.length !== 5 || pr !== null} onClick={go}>{pr !== null ? <Loader2 size={16} className="spin" /> : <UploadCloud size={16} />}Yuklash va jadvallarni tayyorlash{pr !== null ? ` · ${Math.round(pr * 100)}%` : ''}</button>
        </div>
        {files.length > 0 && !ok && files.length === 5 && <small className="hint">Bir xil turdagi ikkita fayl bor bo'lishi mumkin — server tekshiradi.</small>}
      </div>
      {cur && <Batch id={cur} titles={titles} defaults={defaults} onDeleted={() => setCur(null)} />}
    </div>
  )
}

/* ------------------------------------------------------------------ Arxiv tabi */
const ST = { queued: ['Navbatda', 'amber'], running: ['Hisoblanmoqda', 'blue'], ask: ['Javob kutilmoqda', 'amber'], done: ['Tayyor', 'green'], error: ['Xatolik', 'red'] }

function ArchiveTab({ titles, defaults }) {
  const [list, setList] = useState(null)
  const [open, setOpen] = useState(null)
  const toast = useToast()
  const load = () => api.get('/daily').then(setList).catch((e) => { toast(e.message, 'err'); setList([]) })
  useEffect(() => { load() }, [])
  if (!list) return <Spinner />
  return (
    <div>
      {list.length === 0 ? <div className="card pad"><Empty icon={Archive}>Arxiv bo'sh. «Fayl yuklash» tabidan birinchi kunni yuklang.</Empty></div> : (
        <div className="card tcard"><div className="tbl-scroll"><table className="list">
          <thead><tr><th>Sana</th><th>Holat</th><th>Qatorlar (aloqasiz / offline / primichka)</th><th>Yuklagan</th><th /></tr></thead>
          <tbody>{list.map((x) => { const s = ST[x.status] || ST.error; return (
            <tr key={x.id}><td className="b nowrap-d">{dmy(x.date)}</td>
              <td><span className={`tag ${s[1]}`}>{s[0]}</span>{x.status === 'error' && <div className="job-err mut">{x.message}</div>}</td>
              <td className="mut">{x.ready ? `${num(x.counts.nometer)} / ${num(x.counts.offline)} / ${num(x.counts.direct)}` : '—'}</td>
              <td className="mut">{x.by}<div>{dt(x.at)}</div></td>
              <td className="acts"><button className="btn ghost sm" onClick={() => setOpen(x.id)}><Eye size={15} />Ochish</button></td></tr>) })}</tbody></table></div></div>)}
      {open && <Modal wide icon={Archive} title="Kunlik topshiriq" onClose={() => { setOpen(null); load() }}>
        <Batch id={open} titles={titles} defaults={defaults} onChanged={() => {}} onDeleted={() => { setOpen(null); load() }} /></Modal>}
    </div>
  )
}

/* ------------------------------------------------------------------ Sozlamalar tabi */
function SettingsTab({ onSaved }) {
  const toast = useToast()
  const [s, setS] = useState(null)
  const [f, setF] = useState(null)
  const [chats, setChats] = useState([])
  const [busy, setBusy] = useState(false)
  const load = () => api.get('/daily/settings').then((r) => { setS(r); setF({ ...r, time_edges_txt: r.time_edges.join(', '), esp_txt: r.esp_order.join('\n') }) }).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load(); api.get('/daily/chats').then(setChats).catch(() => {}) }, [])
  if (!f) return <Spinner />
  const set = (k, v) => setF({ ...f, [k]: v })
  const move = (i, d) => { const a = f.esp_txt.split('\n').filter(Boolean); const j = i + d; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; set('esp_txt', a.join('\n')) }
  const esps = f.esp_txt.split('\n').map((x) => x.trim()).filter(Boolean)
  const edges = f.time_edges_txt.split(/[,\s]+/).filter(Boolean).map(Number)
  const save = async () => {
    setBusy(true)
    try {
      const body = { region: f.region, t1_title: f.t1_title, t2_title: f.t2_title, task_title: f.task_title, offline_days: Number(f.offline_days), time_edges: edges,
        esp_order: esps, types: f.types, fn_t1: f.fn_t1, fn_t2: f.fn_t2, fn_task: f.fn_task, chats: f.chats }
      const r = await api.put('/daily/settings', body)
      toast('Saqlandi. Mavjud kunlar uchun «Qayta hisoblash» ni bosing'); onSaved?.(r); await load()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  const chatSet = (k, id) => { const cur = new Set(f.chats[k] || []); cur.has(id) ? cur.delete(id) : cur.add(id); set('chats', { ...f.chats, [k]: [...cur] }) }
  const types = Object.entries(f.types || {})
  return (
    <div className="daily-set">
      <section className="card pad set-card">
        <h3><ClipboardList size={20} />Jadvallar va fayl nomlari</h3>
        <label className="field"><span>Hudud nomi (jadval tepasida)</span><input value={f.region} onChange={(e) => set('region', e.target.value)} /></label>
        {[['t1', 'Birinchi jadval'], ['t2', 'Ikkinchi jadval'], ['task', 'Nomma-nom topshiriq fayli']].map(([k, lbl]) => (
          <div key={k} className="two set-pair">
            <label className="field"><span>{lbl} — nomi</span><input value={f[`${k}_title`]} onChange={(e) => set(`${k}_title`, e.target.value)} /></label>
            <label className="field"><span>Fayl nomi shabloni</span><input value={f[`fn_${k}`]} onChange={(e) => set(`fn_${k}`, e.target.value)} />
              <small className="hint">Namuna: <b>{s.examples[k]}</b></small></label>
          </div>))}
        <small className="hint">Shablon o'rin belgilari: {Object.entries(s.placeholders).map(([k, v]) => <span key={k} className="fn-ph"><code>{`{${k}}`}</code> {v}</span>)}. Fayl nomidagi o'zgarish keyingi yuklab olish/yuborishdan kuchga kiradi.</small>
      </section>
      <section className="card pad set-card">
        <h3><RefreshCw size={20} />Hisoblash qoidalari</h3>
        <div className="two">
          <label className="field"><span>Offline: oxirgi necha kun chiqarib tashlanadi</span><input type="number" min="1" max="60" value={f.offline_days} onChange={(e) => set('offline_days', e.target.value)} />
            <small className="hint">3 bo'lsa — bugun, kecha va undan oldingi kun (21, 22, 23.11) offlinelari «shundan {f.offline_days} kundan ortiq» ga kirmaydi.</small></label>
          <label className="field"><span>Aloqasiz hisoblagich: kun oraliqlari</span><input value={f.time_edges_txt} onChange={(e) => set('time_edges_txt', e.target.value)} placeholder="2, 7, 30, 90" />
            <small className="hint">Ustunlar: {edges.length >= 2 && edges.every((x, i) => Number.isInteger(x) && (i === 0 || x > edges[i - 1])) ? labelsOf(edges).join(' · ') : 'o\'sib boruvchi butun sonlar kiriting'}</small></label>
        </div>
        <small className="hint">Obxod oraliqlari: 0% → «0%»; 0 dan 50 gacha (50 kiradi); 50–80; 80–100. Iste'molchi biriktirilmagan — hisoblagichi yo'q kontsentrator.</small>
      </section>
      <section className="card pad set-card">
        <h3><Settings2 size={20} />Rayonlar tartibi</h3>
        <div className="esp-list">{esps.map((e, i) => (
          <div key={e} className="esp-row"><span className="mut">{i + 1}.</span><b>{e}</b>
            <button className="icon-btn" onClick={() => move(i, -1)} disabled={i === 0} title="Yuqoriga"><ArrowUp size={15} /></button>
            <button className="icon-btn" onClick={() => move(i, 1)} disabled={i === esps.length - 1} title="Pastga"><ArrowDown size={15} /></button>
            <button className="icon-btn danger" onClick={() => set('esp_txt', esps.filter((x) => x !== e).join('\n'))} title="Ro'yxatdan olib tashlash"><X size={15} /></button></div>))}</div>
        <label className="field"><span>Qo'lda tahrirlash (har qatorda bitta rayon)</span><textarea rows={4} value={f.esp_txt} onChange={(e) => set('esp_txt', e.target.value)} /></label>
        <small className="hint">Fayllarda uchragan, lekin bu ro'yxatda yo'q rayonlar avtomatik oxiriga qo'shiladi. Nomlar fayldagidek yoziladi (ShETK / TETK).</small>
      </section>
      <section className="card pad set-card">
        <h3><Megaphone size={20} />Standart kanal va guruhlar</h3>
        <small className="hint">Telegramga yuborishda har bir fayl uchun shu kanallar oldindan belgilanadi (yuborishda o'zgartirish mumkin). Bot va kanallar — umumiy: Sozlamalar → Telegram.</small>
        {chats.length === 0 ? <div className="mut" style={{ marginTop: 10 }}>Hali kanal yoki guruh qo'shilmagan.</div> : (
          <div className="chat-pick">{OUT.map((o) => (
            <div key={o.k}><b>{f[o.t]}</b>{chats.map((c) => <label key={c.id} className="chk"><input type="checkbox" checked={(f.chats[o.k] || []).includes(c.id)} onChange={() => chatSet(o.k, c.id)} />{c.title}</label>)}</div>))}</div>)}
      </section>
      <section className="card pad set-card">
        <h3><Archive size={20} />Iste'molchi turlari (saqlangan javoblar)</h3>
        {types.length === 0 ? <div className="mut">Hozircha saqlangan javob yo'q. Fayldagi tur tushunarsiz bo'lsa, yuklashda bir marta so'raladi.</div> : types.map(([k, v]) => (
          <div key={k} className="ask-row"><b>{k}</b>
            <select value={v} onChange={(e) => set('types', { ...f.types, [k]: e.target.value })}>{CATS.map(([c, l]) => <option key={c} value={c}>{l}</option>)}</select>
            <button className="icon-btn danger" onClick={() => { const n = { ...f.types }; delete n[k]; set('types', n) }} title="Olib tashlash"><Trash2 size={15} /></button></div>))}
        <small className="hint">Бытовые → Aholi, Промышленные → Ulgurji, Индикатор баланса → Balans avtomatik taniladi.</small>
      </section>
      <div className="row-btns"><button className="btn primary" disabled={busy} onClick={save}><Save size={16} />Saqlash</button></div>
    </div>
  )
}

const labelsOf = (e) => [...e.slice(0, -1).map((a, i) => { const b = e[i + 1]; return b > 30 && a % 30 === 0 && b % 30 === 0 ? `${a / 30}-${b / 30} oy` : `${a}-${b} kun` }),
  e[e.length - 1] >= 30 && e[e.length - 1] % 30 === 0 ? `${e[e.length - 1] / 30} oydan ortiq` : `${e[e.length - 1]} kundan ortiq`]

/* ------------------------------------------------------------------ sahifa */
export default function Daily() {
  const { can } = useAuth()
  const [sp, setSp] = useSearchParams()
  const [cfg, setCfg] = useState(null)
  useEffect(() => { api.get('/daily/settings').then(setCfg).catch(() => setCfg({})) }, [])
  const tabs = [{ k: 'yuklash', label: 'Fayl yuklash', icon: UploadCloud }, { k: 'arxiv', label: 'Arxiv', icon: Archive },
    ...(can('daily.settings') ? [{ k: 'sozlamalar', label: 'Sozlamalar', icon: Settings2 }] : [])]
  const tab = (tabs.find((t) => t.k === sp.get('t')) || tabs[0]).k
  const titles = { t1_title: cfg?.t1_title || 'Konsentratorlar', t2_title: cfg?.t2_title || 'Aloqadan chiqib ketgan hisoblagichlar soni', task_title: cfg?.task_title || 'Kunlik topshiriq' }
  const defaults = cfg?.chats || {}
  if (!cfg) return <Spinner />
  return (
    <div className="daily">
      <div className="tabs" role="tablist">{tabs.map((t) => (
        <button key={t.k} role="tab" aria-selected={t.k === tab} className={`tab ${t.k === tab ? 'on' : ''}`} onClick={() => setSp(t.k === 'yuklash' ? {} : { t: t.k }, { replace: true })}><t.icon size={18} /><span>{t.label}</span></button>))}</div>
      {tab === 'yuklash' && <UploadTab titles={titles} defaults={defaults} />}
      {tab === 'arxiv' && <ArchiveTab titles={titles} defaults={defaults} />}
      {tab === 'sozlamalar' && <SettingsTab onSaved={setCfg} />}
    </div>
  )
}
