import { useEffect, useState } from 'react'
import { DatabaseBackup, Play, Download, Send, Trash2, CheckCircle2, XCircle, AlertTriangle, Clock, Save, Info } from 'lucide-react'
import { api, download } from '../api'
import { Confirm, Spinner, useToast } from '../ui'
import { dt } from '../fmt'

const size = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

export default function Backup() {
  const toast = useToast()
  const [d, setD] = useState(null)
  const [f, setF] = useState(null)
  const [busy, setBusy] = useState('')
  const [ask, setAsk] = useState(null)
  const load = () => api.get('/system/backups').then((r) => { setD(r); setF((x) => x || r.settings) }).catch((e) => toast(e.message, 'err'))
  useEffect(() => { load() }, [])
  const run = async (name, fn, ok) => { setBusy(name); try { const r = await fn(); if (ok) toast(typeof ok === 'function' ? ok(r) : ok); await load() } catch (e) { toast(e.message, 'err') } finally { setBusy('') } }
  if (!d || !f) return <Spinner />
  const dirty = f.enabled !== d.settings.enabled || f.time !== d.settings.time || Number(f.keep) !== d.settings.keep
  return (
    <div className="bk">
      <div className="set-halves">
        <section className="card pad set-card">
          <h3><DatabaseBackup size={20} />Avtomatik zaxira nusxa</h3>
          <label className="switch"><input type="checkbox" checked={f.enabled} onChange={(e) => setF({ ...f, enabled: e.target.checked })} /><i /><span>Har kuni avtomatik zaxira nusxa olish</span></label>
          <div className="two">
            <label className="field"><span><Clock size={14} />Vaqti (har kuni)</span><span className="hm"><select value={f.time.slice(0, 2)} onChange={(e) => setF({ ...f, time: `${e.target.value}:${f.time.slice(3, 5)}` })}>{Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0')).map((h) => <option key={h}>{h}</option>)}</select><b>:</b>
            <select value={f.time.slice(3, 5)} onChange={(e) => setF({ ...f, time: `${f.time.slice(0, 2)}:${e.target.value}` })}>{['00', '05', '10', '15', '20', '30', '40', '45', '50'].map((m) => <option key={m}>{m}</option>)}</select></span></label>
            <label className="field"><span>Serverda saqlanadigan nusxalar soni</span><input type="number" min="1" max="90" value={f.keep} onChange={(e) => setF({ ...f, keep: e.target.value })} /></label>
          </div>
          <div className="row-btns">
            <button className="btn primary" disabled={!dirty || busy === 'save'} onClick={() => run('save', () => api.put('/system/backups/settings', { enabled: f.enabled, time: f.time, keep: Number(f.keep) }).then((r) => { setF(r); return r }), 'Saqlandi')}><Save size={16} />Saqlash</button>
            <button className="btn ghost" disabled={busy === 'run'} onClick={() => run('run', () => api.post('/system/backups/run'), (r) => r.sent ? 'Zaxira nusxa olindi va Telegram orqali sadminga yuborildi' : 'Zaxira nusxa olindi (Telegram\'ga yuborilmadi — pastdagi izohga qarang)')}>
              {busy === 'run' ? <Clock size={16} className="spin" /> : <Play size={16} />}Hozir nusxa olish</button>
          </div>
          {!d.bot && <div className="alert"><AlertTriangle size={16} />Telegram bot ulanmagan — nusxa faqat serverda saqlanadi.</div>}
          {d.bot && !d.sadmin_chat && <div className="alert"><AlertTriangle size={16} />Sadminning Telegram chat ID si kiritilmagan. Profil (yoki Xodimlar) bo'limida chat ID ni kiriting — shunda har kuni nusxa o'sha chatga keladi.</div>}
          <small className="hint"><Info size={13} /> Nusxaga: xodimlar va ruxsatlar, tumanlar, brigadalar va xodimlari, TP'larning brigadaga biriktirilishi, barcha kunlik dinamika (snapshot), respublika dinamikasi, Telegram sozlamalari va harakatlar jurnali kiradi. Hisoblagichlar ro'yxati — Area/Details fayllaridan qayta tiklanadi.</small>
        </section>
        <section className="card pad set-card">
          <h3><Clock size={20} />Nusxalar tarixi</h3>
          {d.items.length === 0 ? <div className="mut">Hali zaxira nusxa olinmagan.</div> : (
            <div className="tbl-scroll"><table className="list">
              <thead><tr><th>Vaqti</th><th>Hajmi</th><th>Telegram</th><th /></tr></thead>
              <tbody>{d.items.map((b) => (
                <tr key={b.id}>
                  <td><b>{dt(b.at)}</b><br /><small className="mut">{b.kind === 'auto' ? 'avtomatik' : "qo'lda"}</small></td>
                  <td>{b.status === 'ok' ? size(b.size) : <span className="tag red"><XCircle size={13} />Xato</span>}</td>
                  <td>{b.sent ? <span className="tag green"><CheckCircle2 size={13} />Yuborilgan</span> : <span className="tag amber" title={b.note}>Yuborilmagan</span>}</td>
                  <td className="acts">
                    {b.exists && <button className="icon-btn" title="Yuklab olish" onClick={() => download(`/system/backups/${b.id}/download`, b.filename).catch((e) => toast(e.message, 'err'))}><Download size={16} /></button>}
                    {b.exists && <button className="icon-btn" title="Sadminga Telegram orqali yuborish" disabled={busy === 's' + b.id} onClick={() => run('s' + b.id, () => api.post(`/system/backups/${b.id}/send`), 'Telegram orqali yuborildi')}><Send size={16} /></button>}
                    <button className="icon-btn danger" title="O'chirish" onClick={() => setAsk(b)}><Trash2 size={16} /></button>
                  </td>
                </tr>))}</tbody></table></div>)}
        </section>
      </div>
      {ask && <Confirm danger title="Nusxani o'chirish" ok="O'chirish" onCancel={() => setAsk(null)} onOk={() => { const b = ask; setAsk(null); run('d' + b.id, () => api.del(`/system/backups/${b.id}`), "O'chirildi") }}>
        {ask.filename} serverdan o'chiriladi. Davom etasizmi?</Confirm>}
    </div>
  )
}
