import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { UploadCloud, FileArchive, CheckCircle2, XCircle, Clock, Loader2, AlertTriangle, CalendarDays, X, Rocket, Server, Globe2, FileText, Trash2 } from 'lucide-react'
import { api, uploadForm } from '../api'
import { useAuth } from '../auth'
import { useToast } from '../ui'
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

function JobCard({ j }) {
  const S = STATUS[j.status]
  const active = j.status === 'queued' || j.status === 'running'
  return (
    <div className={`job ${j.status}`}>
      <div className="job-top">
        <span className={`tag ${S.c}`}><S.i size={14} className={j.status === 'running' ? 'spin' : ''} />{S.t}</span>
        <b>#{j.id}</b><span className="mut"><CalendarDays size={14} /> {dmy(j.snap_date)}</span>
        <span className="mut right">{dt(j.created_at)} • {j.created_by}</span>
      </div>
      <div className="job-files">{[j.area_name, j.details_name].filter(Boolean).join('  +  ')}</div>
      {(active || j.status === 'done') && (
        <div className="progress"><div className="bar" style={{ width: `${j.progress}%` }} /><span>{Math.round(j.progress)}%</span></div>)}
      {active && <div className="stage">{j.stage}</div>}
      {j.status === 'error' && <div className="job-err"><AlertTriangle size={16} />{j.message}</div>}
      {j.status === 'done' && j.stats && (
        <div className="stats">
          {j.stats.area_rows != null && <span>TP: <b>{num(j.stats.area_rows)}</b></span>}
          {j.stats.new_brigades > 0 && <span>Yangi brigada: <b>{j.stats.new_brigades}</b></span>}
          {j.stats.tp_removed > 0 && <span>O'chirilgan TP: <b>{num(j.stats.tp_removed)}</b></span>}
          {j.stats.meters != null && <span>Hisoblagich: <b>{num(j.stats.meters)}</b></span>}
          {j.stats.meters_removed > 0 && <span>O'chirilgan: <b>{num(j.stats.meters_removed)}</b></span>}
          {j.stats.meters_without_tp > 0 && <span className="warn">TP topilmagan: <b>{num(j.stats.meters_without_tp)}</b></span>}
        </div>)}
    </div>
  )
}

function RepUpload() {
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [pct, setPct] = useState(null)
  const [list, setList] = useState(null)
  const load = () => api.get('/republic').then(setList).catch(() => setList([]))
  useEffect(() => { load() }, [])
  const go = async () => {
    const f = new FormData(); f.append('file', file); setPct(0)
    try {
      const r = await uploadForm('/republic/upload', f, setPct)
      toast(`Qabul qilindi: ${dmy(r.end)} (${r.pages} ta jadval)${r.replaced ? ' — oldingisi yangilandi' : ''}`)
      setFile(null); load()
    } catch (e) { toast(e.message, 'err') } finally { setPct(null) }
  }
  const del = async (r) => { if (!window.confirm(`${dmy(r.end)} sanadagi respublika ma'lumoti o'chirilsinmi?`)) return; try { await api.del(`/republic/${r.id}`); load() } catch (e) { toast(e.message, 'err') } }
  return (<>
    <div className="card pad">
      <div className="drops one"><Drop icon={Globe2} label="Respublika dinamikasi (PDF)" hint="Qashqadaryo_HETK_dynamic-01.11.2026--20.11.2026.pdf — oy boshidan oxirgi sanagacha" accept=".pdf" file={file} onFile={setFile} /></div>
      <div className="upl-row">
        <small className="hint">PDF ichidagi viloyat «Жами» qatori va sana avtomatik o'qiladi. Har bir sana uchun bitta fayl saqlanadi; shu sana qayta yuklansa — yangilanadi. Kunma-kun solishtirish uchun har kuni yangi PDF yuklang.</small>
        <div className="spacer" />
        <button className="btn primary big" disabled={!file || pct !== null} onClick={go}><Rocket size={18} />{pct !== null ? `Yuborilmoqda ${Math.round(pct * 100)}%` : 'Yuklash'}</button>
      </div>
      {pct !== null && <div className="progress"><div className="bar" style={{ width: `${pct * 100}%` }} /></div>}
    </div>
    <h3 className="sec-title">Yuklangan sanalar</h3>
    {!list ? null : list.length === 0 ? <div className="card pad mut">Hali respublika PDF'i yuklanmagan.</div> : (
      <div className="card tcard"><div className="tbl-scroll"><table className="list"><thead><tr><th>Sana</th><th>Davr</th><th>Fayl</th><th>Jadvallar</th><th>Yuklagan</th><th /></tr></thead>
        <tbody>{list.map((r) => (<tr key={r.id}><td className="b">{dmy(r.end)}</td><td>{dmy(r.start)} – {dmy(r.end)}</td><td className="mut"><FileText size={14} /> {r.filename}</td><td>{r.pages}</td><td className="mut">{r.by} • {dt(r.at)}</td>
          <td className="acts"><button className="icon-btn danger" title="O'chirish" onClick={() => del(r)}><Trash2 size={16} /></button></td></tr>))}</tbody></table></div></div>)}
  </>)
}

export default function Upload() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('t') === 'resp' ? 'resp' : 'kunlik'
  return (
    <div className="upl">
      <div className="tabs" role="tablist">
        <button role="tab" className={`tab ${tab === 'kunlik' ? 'on' : ''}`} onClick={() => setSp({}, { replace: true })}><UploadCloud size={18} /><span>Kunlik ma'lumot (Area / Details)</span></button>
        <button role="tab" className={`tab ${tab === 'resp' ? 'on' : ''}`} onClick={() => setSp({ t: 'resp' }, { replace: true })}><Globe2 size={18} /><span>Respublika dinamikasi</span></button>
        <i className="tab-glow" style={{ '--i': tab === 'resp' ? 1 : 0, '--n': 2 }} />
      </div>
      {tab === 'resp' ? <><div className="card head-card"><div className="titles"><h2 className="ttl">Respublika dinamikasi</h2><p className="sub">Respublika markazi tayyorlagan dinamika PDF'ini (oy boshidan oxirgi sanagacha) yuklang.</p></div></div><RepUpload /></> : <DailyUpload />}
    </div>
  )
}

function DailyUpload() {
  const { reload } = useAuth()
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
      <div className="jobs">{jobs.length === 0 ? <div className="card pad mut">Hali yuklash bo'lmagan.</div> : jobs.map((j) => <JobCard key={j.id} j={j} />)}</div>
    </>
  )
}
