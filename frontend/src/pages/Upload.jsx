import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Eye, Download, UploadCloud, FileArchive, CheckCircle2, XCircle, Clock, Loader2, AlertTriangle, CalendarDays, X, Rocket, Server, Globe2, FileText, Trash2, FileBarChart2 } from 'lucide-react'
import { api, download, openFile, qs, uploadForm } from '../api'
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

const STATUS = {
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

// Qashqadaryo, Respublika va AG PDF'larini yuklash (hammasi bir xil jarayon)
const PDF_KINDS = {
  resp: { base: '/republic', icon: Globe2, label: 'Qashqadaryo dinamikasi', noun: 'respublika', unit: 'jadval', col: 'Jadvallar', perm: 'republic.original',
    hint: 'Qashqadaryo_HETK_dynamic-01.11.2026--20.11.2026.pdf — oy boshidan oxirgi sanagacha',
    info: "PDF ichidagi viloyat «Жами» qatori va sana avtomatik o'qiladi. Har bir sana uchun bitta fayl saqlanadi; shu sana qayta yuklansa — yangilanadi. Kunma-kun solishtirish uchun har kuni yangi PDF yuklang." },
  nation: { base: '/nation', icon: Globe2, label: 'Respublika dinamikasi', noun: 'respublika', unit: 'viloyat', col: 'Jadvallar', perm: 'nation.original',
    hint: 'R-Dynamic_01.11.2026--27.11.2026.pdf — oy boshidan oxirgi sanagacha (barcha viloyatlar)',
    info: "PDF ichidagi «Жами» va 14 viloyat qatori hamda sana avtomatik o'qiladi (1, 2, 3, 4, 6, 7 va 9-sahifalar; diagramma va SmartApp sahifalari o'tkazib yuboriladi). Har bir sana uchun bitta fayl saqlanadi; shu sana qayta yuklansa — yangilanadi. Kunma-kun solishtirish uchun har kuni yangi PDF yuklang." },
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
    can('republic.upload') && { k: 'resp', icon: Globe2, label: 'Qashqadaryo dinamikasi' },
    can('nation.upload') && { k: 'nation', icon: Globe2, label: 'Respublika dinamikasi' },
    can('ag.upload') && { k: 'ag', icon: FileBarChart2, label: 'AG dinamikasi' },
  ].filter(Boolean)
  const want = sp.get('t') || 'kunlik'
  const tab = (tabs.find((t) => t.k === want) || tabs[0] || { k: 'kunlik' }).k
  const sub = { nation: "Respublika markazi tayyorlagan R-Dynamic PDF'ini (barcha viloyatlar, oy boshidan oxirgi sanagacha) yuklang.",
    resp: "Qashqadaryo HETK dinamikasi PDF'ini (tumanlar kesimida, oy boshidan oxirgi sanagacha) yuklang.",
    ag: "AG (Aloqadan chiqib ketgan hisoblagichlar va hodisalar) dinamikasi PDF'ini yuklang: «Farq: 20.02.2023 - …»." }
  return (
    <div className="upl">
      {tabs.length > 1 && <div className="tabs" role="tablist">
        {tabs.map((t) => <button key={t.k} role="tab" className={`tab ${tab === t.k ? 'on' : ''}`} onClick={() => setSp(t.k === 'kunlik' ? {} : { t: t.k }, { replace: true })}><t.icon size={18} /><span>{t.label}</span></button>)}
      </div>}
      {tab === 'resp' || tab === 'ag' || tab === 'nation' ? <><div className="card head-card"><div className="titles"><h2 className="ttl">{PDF_KINDS[tab].label}</h2><p className="sub">{sub[tab]}</p></div></div><PdfUpload key={tab} kind={tab} /></> : <DailyUpload />}
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
  const [details, setDetails] = useState(null)
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
  const send = async () => {
    const f = new FormData()
    if (area) f.append('area', area)
    if (details) f.append('details', details)
    if (date) f.append('snap_date', date)
    setSending(0)
    try {
      await uploadForm('/uploads', f, setSending)
      toast("Fayllar qabul qilindi. Jarayon orqa fonda bajariladi — sahifani yopsangiz ham bo'ladi")
      setArea(null); setDetails(null); poll()
    } catch (e) { toast(e.message, 'err') } finally { setSending(null) }
  }
  return (
    <>
      <div className="card head-card">
        <div className="titles"><h2 className="ttl">Ma'lumot yuklash</h2>
          <p className="sub">Generator tayyorlagan <b>Area_…csv.gz</b> va <b>Details_…csv.gz</b> fayllarini yuklang. Yuklash navbat orqali orqa fonda bajariladi, kutib o'tirish shart emas.</p></div>
      </div>
      {!alive && <div className="alert"><Server size={18} />Worker (orqa fon jarayoni) ishlamayapti. <code>start.bat</code> orqali ishga tushiring — aks holda yuklangan fayllar navbatda turib qoladi.</div>}
      <div className="card pad">
        <div className="drops">
          <Drop icon={UploadCloud} label="Area fayli (konsentratorlar)" hint="Area_Qashqadaryo_HETK-…csv.gz" file={area} onFile={pick(setArea)} />
          <Drop icon={UploadCloud} label="Details fayli (hisoblagichlar)" hint="Details_Qashqadaryo_HETK-…csv.gz" file={details} onFile={pick(setDetails)} />
        </div>
        <div className="upl-row">
          <label className="field inline"><span><CalendarDays size={15} />Ma'lumot sanasi</span><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <small className="hint">Sana fayl nomidan olinadi. Shu sana uchun dinamika jadvali avtomatik saqlanadi; xuddi shu sana qayta yuklansa, u yangilanadi.</small>
          <div className="spacer" />
          <button className="btn primary big" disabled={(!area && !details) || sending !== null} onClick={send}>
            <Rocket size={18} />{sending !== null ? `Yuborilmoqda ${Math.round(sending * 100)}%` : 'Yuklashni boshlash'}</button>
        </div>
        {sending !== null && <div className="progress"><div className="bar" style={{ width: `${sending * 100}%` }} /></div>}
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
