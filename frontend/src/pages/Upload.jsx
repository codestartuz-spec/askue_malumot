import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Eye, Download, UploadCloud, FileArchive, CheckCircle2, XCircle, Clock, Loader2, AlertTriangle, CalendarDays, X, Rocket, Server, Globe2, FileText, Trash2, FileBarChart2 } from 'lucide-react'
import { api, download, openFile, putBlob, qs, uploadForm } from '../api'
import { useAuth } from '../auth'
import { Confirm, useToast } from '../ui'
import { dmy, dt, num } from '../fmt'

const dateFromName = (n = '') => {
  const m = n.match(/(\d{2})-(\d{2})-(\d{4})/)
  return m ? `${m[3]}-${m[2]}-${m[1]}` : ''
}

function Drop({ label, hint, file, onFile, icon: Icon, accept = '.gz,.csv' }) {
  const ref = useRef(null)
  const [over, setOver] = useState(false)
  return (
    <div className={`drop ${over ? 'over' : ''} ${file ? 'has' : ''}`}
      onClick={() => ref.current.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); e.dataTransfer.files[0] && onFile(e.dataTransfer.files[0]) }}>
      <input ref={ref} type="file" accept={accept} hidden onChange={(e) => e.target.files[0] && onFile(e.target.files[0])} />
      <div className="drop-ic"><Icon size={30} /></div>
      <b>{label}</b>
      {file ? (<><span className="fname"><FileArchive size={15} />{file.name}</span><small>{(file.size / 1048576).toFixed(1)} MB</small>
        <button className="icon-btn x" onClick={(e) => { e.stopPropagation(); onFile(null) }} title="Olib tashlash"><X size={16} /></button></>)
        : <small>{hint}</small>}
    </div>
  )
}

// Generator yozgan bo'laklar: Details_Qashqadaryo HETK-25-11-2026.part003-of-008.csv.gz (+ .manifest.json)
const PART_RE = /^(.*)\.part(\d{3})-of-(\d{3})\.csv\.gz$/i
const mb = (b) => (b / 1048576).toFixed(1)

// Tanlangan fayllarni tahlil qiladi: bo'laklar to'plami / bitta fayl / xato
function analyze(list) {
  const files = [...list]
  const man = files.find((f) => /\.manifest\.json$/i.test(f.name) || /\.json$/i.test(f.name))
  const data = files.filter((f) => f !== man)
  if (!data.length) return { error: "Details fayllari (.csv.gz) tanlanmadi" }
  const parsed = data.map((f) => ({ f, m: f.name.match(PART_RE) }))
  if (data.length === 1 && !parsed[0].m) return { mode: 'single', file: data[0], man }
  if (parsed.some((x) => !x.m)) return { error: "Bo'laklar bilan birga oddiy fayl tanlangan. Faqat «…part001-of-00N.csv.gz» bo'laklarini tanlang" }
  const stems = new Set(parsed.map((x) => x.m[1])), totals = new Set(parsed.map((x) => +x.m[3]))
  if (stems.size > 1 || totals.size > 1) return { error: "Turli sana yoki turli to'plamdagi bo'laklar aralashib qolgan" }
  const total = [...totals][0]
  const byN = new Map()
  parsed.forEach((x) => byN.set(+x.m[2], x.f))
  const missing = []
  for (let n = 1; n <= total; n++) if (!byN.has(n)) missing.push(n)
  return { mode: 'parts', stem: [...stems][0], total, byN, man, missing, bytes: data.reduce((s, f) => s + f.size, 0), name: data[0].name }
}

function PartsDrop({ label, hint, info, onFiles, icon: Icon }) {
  const ref = useRef(null)
  const [over, setOver] = useState(false)
  const pick = (fl) => fl && fl.length && onFiles([...fl])
  return (
    <div className={`drop ${over ? 'over' : ''} ${info && !info.error ? 'has' : ''}`}
      onClick={() => ref.current.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files) }}>
      <input ref={ref} type="file" multiple accept=".gz,.csv,.json" hidden onChange={(e) => { pick(e.target.files); e.target.value = '' }} />
      <div className="drop-ic"><Icon size={30} /></div>
      <b>{label}</b>
      {!info ? <small>{hint}</small> : info.error ? <small className="err">{info.error}</small>
        : info.mode === 'single' ? (<><span className="fname"><FileArchive size={15} />{info.file.name}</span><small>{mb(info.file.size)} MB (bitta fayl)</small></>)
          : (<><span className="fname"><FileArchive size={15} />{info.total} ta bo'lak{info.man ? ' + manifest' : ''}</span>
            <small>{mb(info.bytes)} MB{info.missing.length ? ` • yetishmaydi: ${info.missing.slice(0, 8).join(', ')}${info.missing.length > 8 ? ' …' : ''}` : ''}{!info.man ? ' • manifest tanlanmagan (tekshiruv kamroq)' : ''}</small></>)}
      {info && <button className="icon-btn x" onClick={(e) => { e.stopPropagation(); onFiles(null) }} title="Olib tashlash"><X size={16} /></button>}
    </div>
  )
}

const STATUS = {
  uploading: { t: 'Yuklanmoqda', c: 'amber', i: Loader2 },
  queued: { t: 'Navbatda', c: 'amber', i: Clock },
  running: { t: 'Bajarilmoqda', c: 'blue', i: Loader2 },
  done: { t: 'Tayyor', c: 'green', i: CheckCircle2 },
  error: { t: 'Xatolik', c: 'red', i: XCircle },
}

function JobTable({ jobs, onDelete }) {
  return (
    <div className="card tcard"><div className="tbl-scroll"><table className="list jobs-table">
      <thead><tr><th>Holat</th><th>№</th><th>Sana</th><th>Fayllar</th><th>Natija</th><th>Yuklagan</th><th /></tr></thead>
      <tbody>{jobs.map((j) => {
        const S = STATUS[j.status]
        const active = j.status === 'queued' || j.status === 'running'
        const st = j.stats || {}
        return (
          <tr key={j.id} className={`job-row ${j.status}`}>
            <td><span className={`tag ${S.c}`}><S.i size={14} className={j.status === 'running' ? 'spin' : ''} />{S.t}</span></td>
            <td className="b">#{j.id}</td>
            <td className="nowrap-d">{dmy(j.snap_date)}</td>
            <td className="job-files-c mut">{[j.area_name, j.details_name].filter(Boolean).map((n, i) => <div key={i}>{n}</div>)}
              {active && <><div className={`progress st-${j.status}`}><div className="bar" style={{ width: `${Math.max(j.progress, j.status === 'queued' ? 4 : 0)}%` }} /><span>{j.status === 'queued' ? 'Navbat kutilmoqda' : `${Math.round(j.progress)}%`}</span></div><div className="stage">{j.stage}</div></>}
              {j.status === 'error' && <div className="job-err"><AlertTriangle size={15} />{j.message}</div>}</td>
            <td className="job-stats">{j.status === 'done' && j.stats ? <>
              {st.area_rows != null && <span>TP: <b>{num(st.area_rows)}</b></span>}
              {st.meters != null && <span>Hisoblagich: <b>{num(st.meters)}</b></span>}
              {st.new_brigades > 0 && <span>Yangi brigada: <b>{st.new_brigades}</b></span>}
              {st.tp_removed > 0 && <span>O'chirilgan TP: <b>{num(st.tp_removed)}</b></span>}
              {st.meters_removed > 0 && <span>O'chirilgan hisoblagich: <b>{num(st.meters_removed)}</b></span>}
              {st.meters_without_tp > 0 && <span className="warn">TP topilmagan: <b>{num(st.meters_without_tp)}</b></span>}</> : <span className="mut">—</span>}</td>
            <td className="mut nowrap-d">{dt(j.created_at)}<div>{j.created_by}</div></td>
            <td className="acts">{onDelete && j.status !== 'running' && <button className="icon-btn danger" title="Yuklashni o'chirish" onClick={() => onDelete(j)}><Trash2 size={16} /></button>}</td>
          </tr>)})}</tbody>
    </table></div></div>
  )
}

// Respublika va AG PDF'larini yuklash (ikkalasi bir xil jarayon)
const PDF_KINDS = {
  resp: { base: '/republic', icon: Globe2, label: 'Respublika dinamikasi', noun: 'respublika', unit: 'jadval', col: 'Jadvallar', perm: 'republic.original',
    hint: 'Qashqadaryo_HETK_dynamic-01.11.2026--20.11.2026.pdf — oy boshidan oxirgi sanagacha',
    info: "PDF ichidagi viloyat «Жами» qatori va sana avtomatik o'qiladi. Har bir sana uchun bitta fayl saqlanadi; shu sana qayta yuklansa — yangilanadi. Kunma-kun solishtirish uchun har kuni yangi PDF yuklang." },
  ag: { base: '/ag', icon: FileBarChart2, label: 'AG dinamikasi', noun: 'AG', unit: 'hudud', col: 'Hududlar', perm: 'ag.original',
    hint: 'Qashqadaryo_HETK_AG19-20.02.2023--17.11.2026.pdf — boshlang\'ich sanadan oxirgi sanagacha',
    info: "PDF ichidagi «Farq: 20.02.2023 - 17.11.2026» sanasi va barcha hududlar qatori avtomatik o'qiladi. Har bir sana uchun bitta fayl saqlanadi; shu sana qayta yuklansa — yangilanadi. Kunma-kun solishtirish uchun har kuni yangi PDF yuklang." },
}

function PdfUpload({ kind }) {
  const K = PDF_KINDS[kind]
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [pct, setPct] = useState(null)
  const [list, setList] = useState(null)
  const load = () => api.get(K.base).then(setList).catch(() => setList([]))
  useEffect(() => { load() }, [])
  const go = async () => {
    const f = new FormData(); f.append('file', file); setPct(0)
    try {
      const r = await uploadForm(`${K.base}/upload`, f, setPct)
      toast(`Qabul qilindi: ${dmy(r.end)} (${r.pages} ta ${K.unit})${r.replaced ? ' — oldingisi yangilandi' : ''}`)
      setFile(null); load()
    } catch (e) { toast(e.message, 'err') } finally { setPct(null) }
  }
  const { can } = useAuth()
  const [ask, setAsk] = useState(null)
  const del = async () => { const r = ask; setAsk(null); try { await api.del(`${K.base}/${r.id}`); toast(`${dmy(r.end)} o'chirildi`); load() } catch (e) { toast(e.message, 'err') } }
  const view = (r) => openFile(`${K.base}/${r.id}/file?inline=1`).catch((e) => toast(e.message, 'err'))
  const dl = (r) => download(`${K.base}/${r.id}/file`, r.filename).catch((e) => toast(e.message, 'err'))
  return (<>
    <div className="card pad">
      <div className="drops one"><Drop icon={K.icon} label={`${K.label} (PDF)`} hint={K.hint} accept=".pdf" file={file} onFile={setFile} /></div>
      <div className="upl-row">
        <small className="hint">{K.info}</small>
        <div className="spacer" />
        <button className="btn primary big" disabled={!file || pct !== null} onClick={go}><Rocket size={18} />{pct !== null ? `Yuborilmoqda ${Math.round(pct * 100)}%` : 'Yuklash'}</button>
      </div>
      {pct !== null && <div className="progress"><div className="bar" style={{ width: `${pct * 100}%` }} /></div>}
    </div>
    <h3 className="sec-title">Yuklangan sanalar</h3>
    {!list ? null : list.length === 0 ? <div className="card pad mut">Hali {K.noun} PDF'i yuklanmagan.</div> : (
      <div className="card tcard"><div className="tbl-scroll"><table className="list"><thead><tr><th>Sana</th><th>Davr</th><th>Fayl</th><th>{K.col}</th><th>Yuklagan</th><th /></tr></thead>
        <tbody>{list.map((r) => (<tr key={r.id}><td className="b">{dmy(r.end)}</td><td className="nowrap-d">{dmy(r.start)} – {dmy(r.end)}</td><td className="mut"><FileText size={14} /> {r.filename}</td><td>{r.pages}</td><td className="mut">{r.by} • {dt(r.at)}</td>
          <td className="acts">
          {can(K.perm) && r.has_file && <><button className="btn ghost sm" title="PDF'ni brauzerda ochish" onClick={() => view(r)}><Eye size={15} />Ko'rish</button>
            <button className="btn ghost sm" title="PDF'ni yuklab olish" onClick={() => dl(r)}><Download size={15} />Yuklab olish</button></>}
          {can(K.perm) && !r.has_file && <small className="mut">Fayl serverda yo'q</small>}
          {can('data.delete') && <button className="icon-btn danger" title="O'chirish" onClick={() => setAsk(r)}><Trash2 size={16} /></button>}</td></tr>))}</tbody></table></div></div>)}
    {ask && <Confirm icon={Trash2} danger title={`${K.label} ma'lumotini o'chirish`} ok="Ha, o'chirish" onOk={del} onCancel={() => setAsk(null)}>
      <b>{dmy(ask.end)}</b> sanadagi {K.label.toLowerCase()} ({ask.filename}) o'chiriladi: jadval ma'lumoti va serverdagi PDF fayl. Qaytarib bo'lmaydi.
      <small className="hint">Kunlik solishtirish endi oldingi sanalar bilan hisoblanadi.</small></Confirm>}
  </>)
}

export default function Upload() {
  const [sp, setSp] = useSearchParams()
  const { can } = useAuth()
  const tabs = [
    can('data.upload') && { k: 'kunlik', icon: UploadCloud, label: "Kunlik ma'lumot (Area / Details)" },
    can('republic.upload') && { k: 'resp', icon: Globe2, label: 'Respublika dinamikasi' },
    can('ag.upload') && { k: 'ag', icon: FileBarChart2, label: 'AG dinamikasi' },
  ].filter(Boolean)
  const want = sp.get('t') || 'kunlik'
  const tab = (tabs.find((t) => t.k === want) || tabs[0] || { k: 'kunlik' }).k
  const sub = { resp: "Respublika markazi tayyorlagan dinamika PDF'ini (oy boshidan oxirgi sanagacha) yuklang.",
    ag: "AG (Aloqadan chiqib ketgan hisoblagichlar va hodisalar) dinamikasi PDF'ini yuklang: «Farq: 20.02.2023 - …»." }
  return (
    <div className="upl">
      {tabs.length > 1 && <div className="tabs" role="tablist">
        {tabs.map((t) => <button key={t.k} role="tab" className={`tab ${tab === t.k ? 'on' : ''}`} onClick={() => setSp(t.k === 'kunlik' ? {} : { t: t.k }, { replace: true })}><t.icon size={18} /><span>{t.label}</span></button>)}
      </div>}
      {tab === 'resp' || tab === 'ag' ? <><div className="card head-card"><div className="titles"><h2 className="ttl">{PDF_KINDS[tab].label}</h2><p className="sub">{sub[tab]}</p></div></div><PdfUpload key={tab} kind={tab} /></> : <DailyUpload />}
    </div>
  )
}

function DailyUpload() {
  const { reload, can } = useAuth()
  const [ask, setAsk] = useState(null)
  const delJob = async () => {
    const j = ask; setAsk(null)
    try { const r = await api.del(`/uploads/jobs/${j.id}`); toast(r.snapshot_removed ? `#${j.id} va ${dmy(j.snap_date)} dinamikasi o'chirildi` : `#${j.id} o'chirildi`); poll(); reload() }
    catch (e) { toast(e.message, 'err') }
  }
  const toast = useToast()
  const [area, setArea] = useState(null)
  const [detFiles, setDetFiles] = useState(null)
  const details = detFiles && !detFiles.error ? detFiles : null
  const abortRef = useRef(null)
  const [sendInfo, setSendInfo] = useState('')
  const [date, setDate] = useState('')
  const [sending, setSending] = useState(null)   // 0..1
  const [jobs, setJobs] = useState([])
  const [alive, setAlive] = useState(true)
  const wasActive = useRef(false)

  const poll = useCallback(async () => {
    try {
      const r = await api.get('/uploads/jobs')
      setJobs(r.items); setAlive(r.worker_alive)
      const act = r.items.some((j) => j.status === 'queued' || j.status === 'running')
      if (wasActive.current && !act) reload()
      wasActive.current = act
    } catch { /* */ }
  }, [reload])
  useEffect(() => {
    poll()
    const id = setInterval(poll, jobs.some((j) => j.status === 'queued' || j.status === 'running') ? 1500 : 6000)
    return () => clearInterval(id)
  }, [poll, jobs.some((j) => j.status === 'queued' || j.status === 'running')])

  const pick = (setter) => (f) => { setter(f); const d = f && dateFromName(f.name); if (d) setDate(d) }
  const pickDetails = (list) => {
    if (!list) { setDetFiles(null); return }
    const a = analyze(list)
    setDetFiles(a)
    const n = a.mode === 'single' ? a.file.name : a.name
    const d = dateFromName(n || '')
    if (d) setDate(d)
  }
  const readManifest = async (f) => { try { return JSON.parse(await f.text()) } catch { throw new Error("Manifest fayli o'qilmadi (buzilgan JSON)") } }
  // Bitta fayl (eski usul) yoki bo'laklar to'plami (tavsiya etiladi: sekin internetda ham o'tadi)
  const send = async () => {
    if (details?.mode === 'parts') return sendParts()
    const f = new FormData()
    if (area) f.append('area', area)
    if (details?.mode === 'single') f.append('details', details.file)
    if (date) f.append('snap_date', date)
    setSending(0)
    try {
      await uploadForm('/uploads', f, setSending)
      toast("Fayllar qabul qilindi. Jarayon orqa fonda bajariladi — sahifani yopsangiz ham bo'ladi")
      setArea(null); setDetFiles(null); poll()
    } catch (e) { toast(e.message, 'err') } finally { setSending(null) }
  }

  const sendParts = async () => {
    const ctl = new AbortController(); abortRef.current = ctl
    const key = `askue_upl_${details.stem}_${details.total}`
    const total = (area ? area.size : 0) + details.bytes
    let sentBase = 0
    setSending(0); setSendInfo('Tayyorlanmoqda…')
    const upd = (cur = 0) => setSending(Math.min(1, (sentBase + cur) / Math.max(total, 1)))
    const opts = (what) => ({ signal: ctl.signal, onProgress: upd, onRetry: (i, ms, m) => setSendInfo(`${what}: ${m}. ${Math.round(ms / 1000)} soniyadan keyin qayta uriniladi (${i})`) })
    try {
      let jid = null, got = null
      try { jid = +localStorage.getItem(key) || null } catch { /* */ }
      if (jid) { try { got = await api.get(`/uploads/${jid}/received`) } catch { jid = null } }   // uzilgan yuklashni davom ettirish
      if (!jid) {
        const manifest = details.man ? await readManifest(details.man) : null
        const r = await api.post('/uploads/session', { snap_date: date || null, has_area: !!area, area_name: area?.name || null,
          details_name: details.name, details_parts: details.total, manifest })
        jid = r.id; got = { area: null, details: {} }
        try { localStorage.setItem(key, String(jid)) } catch { /* */ }
      }
      if (area) {
        if (got.area === area.size) sentBase += area.size
        else { setSendInfo('Area fayli yuborilmoqda…'); await putBlob(`/uploads/${jid}/area`, area, opts('Area')); sentBase += area.size }
        upd()
      }
      for (let n = 1; n <= details.total; n++) {
        const f = details.byN.get(n)
        if (got.details[n] === f.size) { sentBase += f.size; upd(); continue }
        setSendInfo(`Bo'lak ${n} / ${details.total} yuborilmoqda (${mb(f.size)} MB)`)
        await putBlob(`/uploads/${jid}/details/${n}`, f, opts(`Bo'lak ${n}`))
        sentBase += f.size; upd()
      }
      setSendInfo('Tekshirilmoqda…')
      await api.post(`/uploads/${jid}/finish`)
      try { localStorage.removeItem(key) } catch { /* */ }
      toast("Fayllar qabul qilindi. Jarayon orqa fonda bajariladi — sahifani yopsangiz ham bo'ladi")
      setArea(null); setDetFiles(null); poll()
    } catch (e) {
      if (ctl.signal.aborted) toast("Yuklash to'xtatildi. «Yuklashni boshlash» ni bossangiz, yetib borgan bo'laklar qayta yuborilmaydi")
      else toast(`${e.message}. «Yuklashni boshlash» ni qayta bossangiz — yuborilgan bo'laklar o'tkazib yuboriladi, qolgani davom etadi`, 'err')
      poll()
    } finally { abortRef.current = null; setSending(null); setSendInfo('') }
  }
  return (
    <>
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Ma'lumot yuklash</h2>
          <p className="sub">Generator tayyorlagan <b>Area_…csv.gz</b> va Details <b>…part001-of-00N.csv.gz</b> bo'laklarini (<b>.manifest.json</b> bilan) yuklang — bo'laklar ~5 MB, shuning uchun sekin internetda ham o'tadi; aloqa uzilsa, davom ettiriladi. Yuklash navbat orqali orqa fonda bajariladi, kutib o'tirish shart emas.</p></div>
      </div>
      {!alive && <div className="alert"><Server size={18} />Worker (orqa fon jarayoni) ishlamayapti. <code>start.bat</code> orqali ishga tushiring — aks holda yuklangan fayllar navbatda turib qoladi.</div>}
      <div className="card pad">
        <div className="drops">
          <Drop icon={UploadCloud} label="Area fayli (konsentratorlar)" hint="Area_Qashqadaryo_HETK-…csv.gz" file={area} onFile={pick(setArea)} />
          <PartsDrop icon={UploadCloud} label="Details fayli (hisoblagichlar)" hint="…part001-of-00N.csv.gz bo'laklari + .manifest.json (hammasini birdan tanlang)" info={detFiles} onFiles={pickDetails} />
        </div>
        <div className="upl-row">
          <label className="field inline"><span><CalendarDays size={15} />Ma'lumot sanasi</span><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <small className="hint">Sana fayl nomidan olinadi. Shu sana uchun dinamika jadvali avtomatik saqlanadi; xuddi shu sana qayta yuklansa, u yangilanadi.</small>
          <div className="spacer" />
          {sending !== null && abortRef.current && <button className="btn ghost" onClick={() => abortRef.current?.abort()}>To'xtatish</button>}
          <button className="btn primary big" disabled={(!area && !details) || sending !== null || (details?.mode === 'parts' && details.missing.length > 0)} onClick={send}>
            <Rocket size={18} />{sending !== null ? `Yuborilmoqda ${Math.round(sending * 100)}%` : 'Yuklashni boshlash'}</button>
        </div>
        {sending !== null && <><div className="progress"><div className="bar" style={{ width: `${sending * 100}%` }} /></div>{sendInfo && <div className="stage">{sendInfo}</div>}</>}
        {(area || details) && !(area && details) && <div className="hint warn-hint">Eslatma: dinamika to'g'ri bo'lishi uchun ikkala faylni birga yuklash tavsiya etiladi.</div>}
      </div>
      <h3 className="sec-title">Yuklashlar tarixi</h3>
      {jobs.length === 0 ? <div className="card pad mut">Hali yuklash bo'lmagan.</div> : <JobTable jobs={jobs} onDelete={can('data.delete') ? setAsk : null} />}
      {ask && <Confirm icon={Trash2} danger title="Yuklashni o'chirish" ok="Ha, o'chirish" onOk={delJob} onCancel={() => setAsk(null)}>
        <b>#{ask.id}</b> ({dmy(ask.snap_date)}) yuklash yozuvi va serverdagi fayllari o'chiriladi{ask.status === 'done' ? <>, shuningdek <b>{dmy(ask.snap_date)}</b> sanasining dinamika ma'lumoti ham (agar shu sana uchun boshqa yuklash bo'lmasa)</> : ''}.
        <small className="hint">Hozirgi hisoblagich va TP ro'yxatlari o'zgarmaydi — ular keyingi yuklash bilan yangilanadi. Qaytarib bo'lmaydi.</small></Confirm>}
    </>
  )
}
