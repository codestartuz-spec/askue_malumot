import { useMemo } from 'react'
import { FileBarChart2 } from 'lucide-react'
import { useAuth } from '../auth'
import { Spinner } from '../ui'
import { dmy, num } from '../fmt'
import { SendModal } from './Republic'
import { PdfEmpty, PdfFilters, isBlocked, usePdfDyn } from './pdfDyn'

const G = 9
const BAR = { 4: 'ag-b4', 7: 'ag-b7', 8: 'ag-b7' }                      // foizli chiziqcha: guruh → rang sinfi
const VAL_T = ['ag-grn', 'ag-grn', 'ag-grn', 'ag-grn', 'ag-red', 'ag-dkr', 'ag-dkr', 'ag-red', 'ag-red']
const VAL_D = ['', '', '', '', 'ag-red', 'ag-big', 'ag-big', 'ag-red', 'ag-red']

const Dl = ({ cur, base, g }) => {
  const dv = (cur[`c${g}`] || 0) - (base[`c${g}`] || 0)
  if (!dv) return null
  return <span className={`agd ${dv > 0 ? 'up' : 'dn'}`}><b>{dv > 0 ? '↑' : '↓'}</b>{dv > 0 ? num(dv) : `-${num(Math.abs(dv))}`}</span>
}

function AgTable({ d }) {
  const mx = useMemo(() => Object.fromEntries(Object.keys(BAR).map((g) => [g, Math.max(0, ...d.rows.map((r) => r.cur[`c${g}`] || 0))])), [d])
  return (
    <table className="ag-table">
      <thead>
        <tr>
          <th rowSpan={3} className="agh ag-nm">Hudud</th>
          <th colSpan={8} rowSpan={2} className="agh ag-big">CAS dasturidagi hodisalar</th>
          <th colSpan={6} className="agh ag-red ag-s">Aloqadan chiqib ketgan hisoblagichlar</th>
          <th colSpan={2} rowSpan={3} className="agh ag-red ag-m">Kirish va chiqish simlari tutashtirilgan <i className="ag-sky">(перемичка)</i></th>
          <th colSpan={2} rowSpan={3} className="agh ag-red ag-m">Aloqaga chiqmagan hisoblagichlar</th>
        </tr>
        <tr>
          <th colSpan={2} rowSpan={2} className="agh ag-s">Jami Soni</th>
          <th colSpan={4} className="agh ag-pk ag-it ag-s">shundan</th>
        </tr>
        <tr>
          <th colSpan={2} className="agh ag-xs">Kirish va chiqish <b className="ag-rd">quvvati</b> orasidagi nomutanosiblik</th>
          <th colSpan={2} className="agh ag-s">Hisoblagich qutisi ochilgan</th>
          <th colSpan={2} className="agh ag-s">Klemmasi ochilgan</th>
          <th colSpan={2} className="agh ag-s">Kuchlanishsiz tok oqib o'tayotgan</th>
          <th colSpan={2} className="agh ag-pk ag-it ag-s">1-3 oy</th>
          <th colSpan={2} className="agh ag-pk ag-it ag-s">3 oydan ortiq</th>
        </tr>
      </thead>
      <tbody>
        <tr className="ag-total">
          <td className="ag-name">Jami</td>
          {Array.from({ length: G }, (_, g) => [
            <td key={`v${g}`} className={`ag-v ${VAL_T[g]}`}>{d.cur[`c${g}`] ? num(d.cur[`c${g}`]) : '-'}</td>,
            <td key={`d${g}`} className="ag-dl"><Dl cur={d.cur} base={d.base} g={g} /></td>])}
        </tr>
        {d.rows.map((r) => (
          <tr key={r.id}>
            <td className="ag-name">{r.name}</td>
            {Array.from({ length: G }, (_, g) => {
              const v = r.cur[`c${g}`] || 0
              const p = BAR[g] && mx[g] > 0 ? Math.max((v / mx[g]) * 100, 1) : 0
              return [
                <td key={`v${g}`} className={`ag-v ${VAL_D[g]} ${BAR[g] && v ? BAR[g] : ''}`} style={p ? { '--p': p } : undefined}><span>{v ? num(v) : ''}</span></td>,
                <td key={`d${g}`} className="ag-dl"><Dl cur={r.cur} base={r.base} g={g} /></td>]
            })}
          </tr>))}
      </tbody>
    </table>
  )
}

export default function Ag() {
  const { boot } = useAuth()
  const st = usePdfDyn('/ag', 'AG_dinamikasi')
  const { data, mode } = st
  return (
    <div className="dyn rep ag">
      <div className="card head-card">
        <div className="titles">
          <h2 className="ttl">{data?.title || ''}</h2>
          <div className="ag-mal">Ma'lumot</div>
        </div>
        <PdfFilters st={st} region={data?.region || boot?.region_name || ''} perm="ag" firstLabel="Boshidan" origHint="AG markazi yuborgan asl PDF fayl" />
      </div>
      {!data && !st.err ? <Spinner /> : isBlocked(st) ? <PdfEmpty st={st} perm="ag" tab="ag" icon={FileBarChart2} /> : (
        <div className="card tcard">
          <div className="ag-farq">Farq: <b>{dmy(data.from)} - {dmy(data.to)}</b></div>
          <div className="tbl-scroll"><AgTable d={data} /></div>
          <div className="note">{data.a ? <>Kunlik farq (↑↓): oxirgi ikki yuklangan PDF — <b>{dmy(data.a)}</b> bilan <b>{dmy(data.b)}</b> o'rtasidagi o'zgarish.</> : <>Farq (↑↓): boshlang'ich sana <b>{dmy(data.start)}</b> dan <b>{dmy(data.b)}</b> gacha (AG PDF'i bo'yicha). Oxirgi ikki PDF'ni solishtirish uchun «Kunlik» ni tanlang.</>}</div>
        </div>)}
      {st.send && data && <SendModal a={data.a} b={data.b} mode={mode} base="/ag" title="AG dinamikasini Telegram'ga yuborish" origHint="AG markazi yuborgan fayl, o'zgartirishsiz" onClose={() => st.setSend(false)} />}
    </div>
  )
}
