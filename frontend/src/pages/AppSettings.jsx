import { useEffect, useState } from 'react'
import { RotateCcw, Save, SlidersHorizontal } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Spinner, useToast } from '../ui'

/** Fayl nomi shabloni: o'rin belgilar tugmalari, namuna (server hisoblaydi), standartga qaytarish. */
function FileNameField({ x, value, onChange }) {
  const [pv, setPv] = useState({ ok: true, name: x.example, error: '' })
  useEffect(() => {
    const t = setTimeout(() => {
      api.post('/appsettings/preview', { key: x.key, value }).then(setPv).catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [value]) // eslint-disable-line
  return (
    <div className="field fn-field"><span>{x.label}</span>
      <div className="fn-row">
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={x.default} maxLength={120} />
        <button type="button" className="btn ghost" title="Standart nomga qaytarish" disabled={value === x.default} onClick={() => onChange(x.default)}><RotateCcw size={15} />Standart</button>
      </div>
      <div className="fn-chips">{Object.entries(x.placeholders).map(([k, d]) => (
        <button type="button" key={k} className="fn-chip" title={d} onClick={() => onChange(`${value}{${k}}`)}>{`{${k}}`}</button>))}</div>
      <div className={`fn-ex ${pv.ok ? '' : 'bad'}`}>{pv.ok ? <>Namuna: <b>{pv.name}</b></> : pv.error}</div>
    </div>
  )
}

export default function AppSettings() {
  const toast = useToast()
  const { reload } = useAuth()
  const [items, setItems] = useState(null)
  const [vals, setVals] = useState({})
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.get('/appsettings').then((r) => { setItems(r); setVals(Object.fromEntries(r.map((x) => [x.key, x.value]))) }).catch((e) => toast(e.message, 'err')) }, []) // eslint-disable-line
  if (!items) return <Spinner />
  const groups = [...new Set(items.map((x) => x.group))]
  const save = async () => {
    setBusy(true)
    try { await api.put('/appsettings', { values: vals }); toast('Saqlandi'); reload() } catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <section className="card pad set-card">
      <h3><SlidersHorizontal size={20} />Umumiy sozlamalar</h3>
      {groups.map((g) => (
        <div key={g} className="set-group"><h4>{g}</h4>
          {g === 'Fayl nomlari' && <p className="mut fn-help">Telegramga yuboriladigan va yuklab olinadigan fayllar nomi. Kengaytma (.pdf / .xlsx) avtomatik qo'shiladi. O'rin belgini bosib qo'shing yoki qo'lda yozing. Telegramga faqat fayl yuboriladi (izohsiz).</p>}
          {items.filter((x) => x.group === g).map((x) => (x.type === 'filename'
            ? <FileNameField key={x.key} x={x} value={vals[x.key] || ''} onChange={(v) => setVals({ ...vals, [x.key]: v })} />
            : (
              <label key={x.key} className="field"><span>{x.label}</span>
                <input type={x.type === 'date' ? 'date' : 'text'} value={vals[x.key] || ''} onChange={(e) => setVals({ ...vals, [x.key]: e.target.value })} placeholder={x.default} /></label>)))}
        </div>))}
      <div className="row-btns"><button className="btn primary" disabled={busy} onClick={save}><Save size={16} />Saqlash</button></div>
    </section>
  )
}
