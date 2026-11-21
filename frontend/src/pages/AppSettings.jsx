import { useEffect, useState } from 'react'
import { Save, SlidersHorizontal } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Spinner, useToast } from '../ui'

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
          {items.filter((x) => x.group === g).map((x) => (
            <label key={x.key} className="field"><span>{x.label}</span>
              <input type={x.type === 'date' ? 'date' : 'text'} value={vals[x.key] || ''} onChange={(e) => setVals({ ...vals, [x.key]: e.target.value })} placeholder={x.default} /></label>))}
        </div>))}
      <div className="row-btns"><button className="btn primary" disabled={busy} onClick={save}><Save size={16} />Saqlash</button></div>
    </section>
  )
}
