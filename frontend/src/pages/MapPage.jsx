import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Search, Layers, SlidersHorizontal, X, MapPinned, Crosshair, Info } from 'lucide-react'
import { api, qs } from '../api'
import { useAuth } from '../auth'
import { METRIC_TITLES } from '../tables'
import { useDebounced, useToast } from '../ui'
import { num } from '../fmt'
import { KIND_NAME, METER_ST, TR_ST, TR_LV, clusterIcon, glyph, meterState, pinIcon, trState } from '../mapIcons'

const TILES = {
  osm: { name: 'Xarita', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attr: '© OpenStreetMap', max: 19 },
  sat: { name: "Sun'iy yo'ldosh", url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr: 'Tiles © Esri', max: 19 },
  dark: { name: "Qorong'u", url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attr: '© OpenStreetMap', max: 19, cls: 'tiles-dark' },
}
const KINDS = [
  { k: 'aholi', c: '#1d6fff' }, { k: 'ulgurji', c: '#7a3fb0' }, { k: 'balans', c: '#b46f00' }, { k: 'tr', c: '#0b2a6b' },
]
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const row = (k, v) => (v === null || v === undefined || v === '' ? '' : `<div class="tip-r"><span>${k}</span><b>${esc(v)}</b></div>`)
const LV = ['', '0%', '1-30%', '30-50%', '50-80%', '80-100%']

function metricKinds(metric) {
  if (!metric) return null
  if (['tp_total', 'cas_loaded', 'online', 'offline', 'offline3', 'unattached'].includes(metric) || /^lv\d$/.test(metric)) return ['tr']
  if (metric.includes('aholi') || metric.startsWith('a_')) return ['aholi']
  if (metric.includes('ulgurji') || metric.startsWith('u_')) return ['ulgurji']
  if (metric.includes('balans') || metric.startsWith('b_')) return ['balans']
  return ['aholi', 'ulgurji', 'balans']
}

function tipHtml(p) {
  if (p.t === 'm') {
    const kind = p.ct === 2 ? 'aholi' : p.ct === 1 ? 'ulgurji' : 'balans'
    const st = meterState(p.b)
    return `<div class="tip"><div class="tip-h" style="background:${st.color}">${glyph(kind, 18)}<div><b>${KIND_NAME[kind]}</b><small>${st.label}${p.dr ? " • To'g'ridan-to'g'ri ulangan" : ''}</small></div></div>
      <div class="tip-b">${row('Hisoblagich №', p.id)}${row('Hisob raqam', p.acc)}${row('Abonent', p.name)}${row('Manzil', p.addr)}
      ${row('TP', p.tp)}${row('Tuman', p.esp)}${row('Brigada', p.brig || 'Biriktirilmagan')}${row('Turi', [p.mt, p.ln].filter(Boolean).join(' • '))}
      ${row('Oxirgi obxod', p.last || "yo'q")}${row('Obxod bermagan kun', p.days)}${row('Koordinata', `${p.la.toFixed(6)}, ${p.lo.toFixed(6)}`)}</div></div>`
  }
  const st = trState(p)
  return `<div class="tip"><div class="tip-h" style="background:${st.color}">${glyph('tr', 18)}<div><b>Konsentrator (TP ${esc(p.tp)})</b><small>${st.label}</small></div></div>
    <div class="tip-b">${row('TP', p.tp)}${row('DCU raqami', p.dcu)}${row('Podstansiya', p.sub)}${row('Fider', p.feeder)}${row('Tuman', p.esp)}${row('Brigada', p.brig || 'Biriktirilmagan')}
    ${row('Obxod olish', p.obx !== null && p.obx !== undefined ? `${p.obx}%${p.lv ? ` (${LV[p.lv]})` : ''}` : '')}${row('Hisoblagichlar', p.mc)}${row('Shundan aloqadan chiqqan', p.mout)}
    ${row('Biriktirilgan', p.att ? 'Ha (CAS ga yuklangan)' : "Yo'q")}${row('Koordinata', `${p.la.toFixed(6)}, ${p.lo.toFixed(6)}`)}
    <div class="tip-n">Koordinata TP ga biriktirilgan hisoblagichlar markazi bo‘yicha aniqlangan</div></div></div>`
}

function StGroup({ title, list, sel, counts, onToggle }) {
  return (
    <>
      <div className="mp-sec">{title} <small>(tanlanmasa — hammasi)</small></div>
      <div className="sts">{list.map(({ k, label, color }) => (
        <button key={k} className={`st ${sel.has(k) ? 'on' : ''}`} onClick={() => onToggle(k)}>
          <i style={{ background: color }} /><span>{label}</span>{counts && <b className="cnt">{num(counts[k] || 0)}</b>}</button>))}</div>
    </>
  )
}

export default function MapPage() {
  const { boot } = useAuth()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const esp = sp.get('esp') || ''
  const brig = sp.get('brig') ?? ''
  const metric = sp.get('metric') || ''
  const focusLa = parseFloat(sp.get('la')), focusLo = parseFloat(sp.get('lo'))
  const setParam = (k, v) => setSp((o) => { const n = new URLSearchParams(o); if (v === '' || v === null) n.delete(k); else n.set(k, v); return n }, { replace: true })

  const [kinds, setKinds] = useState(() => new Set(metricKinds(metric) || ['aholi', 'ulgurji', 'balans', 'tr']))
  const [status, setStatus] = useState(new Set())
  const [layer, setLayer] = useState(() => localStorage.getItem('askue_map_layer') || 'osm')
  const [panel, setPanel] = useState(() => window.innerWidth > 900)
  const [info, setInfo] = useState(null)
  const [stats, setStats] = useState(null)
  const [counts, setCounts] = useState(null)
  const [busy, setBusy] = useState(false)
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 300)
  const [found, setFound] = useState([])

  const mapEl = useRef(null), map = useRef(null), group = useRef(null), tile = useRef(null), focusMk = useRef(null)
  const reqRef = useRef(0), abort = useRef(null)
  const filt = useRef({})
  const brigs = useMemo(() => (boot.brigades || []).filter((b) => !esp || String(b.esp_id) === esp), [boot, esp])
  filt.current = { esp, brig, metric, kinds: [...kinds].join(','), status: [...status].join(',') }

  const load = useCallback(() => {
    const m = map.current
    if (!m) return
    const b = m.getBounds().pad(0.2)
    const f = filt.current
    const id = ++reqRef.current
    abort.current?.abort()
    abort.current = new AbortController()
    setBusy(true)
    api.get(`/map/points${qs({ kinds: f.kinds, status: f.status, metric: f.metric, esp_id: f.esp, brigade_id: f.brig,
      s: b.getSouth().toFixed(5), w: b.getWest().toFixed(5), n: b.getNorth().toFixed(5), e: b.getEast().toFixed(5), zoom: Math.round(m.getZoom()) })}`, abort.current.signal)
      .then((d) => {
        if (id !== reqRef.current) return
        setInfo({ meters: d.meters, trs: d.trs, mode: d.mode })
        const g = group.current
        g.clearLayers()
        const sel = (f.status || '').split(',').filter(Boolean)
        const oneColor = (t) => { const g = [...METER_ST, ...TR_ST, ...TR_LV].filter((x) => sel.includes(x.k) && (t === 'm' ? x.k.startsWith('m') : !x.k.startsWith('m'))); return g.length === 1 ? g[0].color : null }
        d.clusters.forEach((c) => {
          const mk = L.marker([c.la, c.lo], { icon: clusterIcon(c, oneColor(c.t)) })
          mk.bindTooltip(`<b>${num(c.n)} ta ${c.t === 't' ? 'konsentrator' : 'hisoblagich'}</b>${c.t === 'm' ? `<br>aloqadan chiqqan: ${num(c.bad)}` : `<br>offline: ${num(c.bad)}`}<br><small>Bosing — yaqinlashtirish</small>`, { direction: 'top', className: 'map-tip simple' })
          mk.on('click', () => m.flyTo([c.la, c.lo], Math.min(m.getZoom() + 2, 18), { duration: 0.5 }))
          g.addLayer(mk)
        })
        d.points.forEach((p) => {
          const kind = p.t === 't' ? 'tr' : p.ct === 2 ? 'aholi' : p.ct === 1 ? 'ulgurji' : 'balans'
          const st = p.t === 't' ? trState(p) : meterState(p.b)
          const bad = p.t === 't' ? p.st === 2 || p.off3 : p.b >= 4
          const mk = L.marker([p.la, p.lo], { icon: pinIcon(kind, st.color, { big: kind === 'tr', bad, direct: !!p.dr }), zIndexOffset: kind === 'tr' ? 500 : p.dr ? 300 : 0 })
          const html = tipHtml(p)
          const cp = m.latLngToContainerPoint([p.la, p.lo]), sz = m.getSize()
          const dir = cp.x > sz.x - 360 ? 'left' : 'right'
          const offY = cp.y < 190 ? 190 - cp.y : cp.y > sz.y - 190 ? -(190 - (sz.y - cp.y)) : 0
          mk.bindTooltip(html, { direction: dir, className: 'map-tip', opacity: 1, offset: [dir === 'right' ? 16 : -16, -(kind === 'tr' ? 24 : 18) + offY] })
          mk.bindPopup(html, { className: 'map-pop', maxWidth: 340, autoPanPadding: [30, 30] })
          g.addLayer(mk)
        })
        setBusy(false)
      })
      .catch((e) => { if (e.name !== 'AbortError') { setBusy(false); toast(e.message, 'err') } })
  }, [])

  // xaritani yaratish
  useEffect(() => {
    const m = L.map(mapEl.current, { center: [38.85, 66.0], zoom: 9, minZoom: 6, maxZoom: 19, zoomControl: false, preferCanvas: true })
    L.control.zoom({ position: 'bottomright', zoomInTitle: 'Yaqinlashtirish', zoomOutTitle: 'Uzoqlashtirish' }).addTo(m)
    L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(m)
    map.current = m
    group.current = L.layerGroup().addTo(m)
    let t
    m.on('moveend', () => { clearTimeout(t); t = setTimeout(load, 220) })
    if (Number.isFinite(focusLa) && Number.isFinite(focusLo)) m.setView([focusLa, focusLo], 18)
    else load()
    return () => { clearTimeout(t); abort.current?.abort(); m.remove(); map.current = null }
  }, [])

  // qatlam (xarita turi)
  useEffect(() => {
    const m = map.current
    if (!m) return
    if (tile.current) m.removeLayer(tile.current)
    const T = TILES[layer]
    tile.current = L.tileLayer(T.url, { attribution: T.attr, maxZoom: T.max, subdomains: 'abc', className: T.cls || '' }).addTo(m)
    tile.current.bringToBack()
    localStorage.setItem('askue_map_layer', layer)
  }, [layer])

  // filtr o'zgarsa qayta yuklash
  const key = `${esp}|${brig}|${metric}|${[...kinds].join()}|${[...status].join()}`
  useEffect(() => { load() }, [key])
  const firstFit = useRef(true)
  useEffect(() => {
    api.get(`/map/counts${qs({ esp_id: esp, brigade_id: brig })}`).then(setCounts).catch(() => {})
    api.get(`/map/stats${qs({ esp_id: esp, brigade_id: brig })}`).then((st) => {
      setStats(st)
      const hasFocus = Number.isFinite(focusLa) && Number.isFinite(focusLo)
      const skip = firstFit.current && (!esp && !brig || hasFocus)
      firstFit.current = false
      if (!skip && st.bounds && map.current) map.current.fitBounds(st.bounds, { padding: [60, 60], maxZoom: 15, animate: true })
    }).catch(() => {})
  }, [esp, brig])

  // tanlangan nuqtaga o'tish (ro'yxatdan "xaritada ko'rish")
  const flash = (la, lo) => {
    const m = map.current
    if (!m) return
    focusMk.current?.remove()
    focusMk.current = L.marker([la, lo], { interactive: false, zIndexOffset: -100,
      icon: L.divIcon({ className: 'pulse-wrap', html: '<div class="pulse"></div>', iconSize: [70, 70] }) }).addTo(m)
    setTimeout(() => { focusMk.current?.remove(); focusMk.current = null }, 9000)
  }
  useEffect(() => {
    if (Number.isFinite(focusLa) && Number.isFinite(focusLo) && map.current) { map.current.flyTo([focusLa, focusLo], 18, { duration: 0.7 }); flash(focusLa, focusLo) }
  }, [focusLa, focusLo])

  useEffect(() => {
    if (dq.trim().length < 2) { setFound([]); return }
    api.get(`/map/find${qs({ q: dq })}`).then(setFound).catch(() => setFound([]))
  }, [dq])
  const goto = (r) => {
    if (r.la === null) { toast("Bu qurilmaning koordinatasi kiritilmagan", 'err'); return }
    map.current.flyTo([r.la, r.lo], 18, { duration: 0.7 }); flash(r.la, r.lo)
    setFound([]); setQ('')
  }
  const toggle = (set, setter, k) => setter((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })
  const locate = () => map.current?.locate({ setView: true, maxZoom: 16 })
  useEffect(() => { setTimeout(() => map.current?.invalidateSize(), 320) }, [panel])
  const cov = stats && (stats.meters + stats.trs) ? stats : null

  return (
    <div className="map-page">
      <div ref={mapEl} className="map-el" />
      <button className="map-fab" onClick={() => setPanel(!panel)} title="Filtr">{panel ? <X size={20} /> : <SlidersHorizontal size={20} />}</button>
      <div className="map-layers">
        <Layers size={16} />
        {Object.entries(TILES).map(([k, t]) => <button key={k} className={layer === k ? 'on' : ''} onClick={() => setLayer(k)}>{t.name}</button>)}
        <button className="loc" onClick={locate} title="Mening joylashuvim"><Crosshair size={16} /></button>
      </div>
      {panel && (
        <aside className="map-panel">
          <div className="mp-title"><MapPinned size={19} /><b>Xarita filtri</b>{busy && <span className="mp-busy" />}</div>
          <div className="searchbar sm"><Search size={16} />
            <input placeholder="Hisoblagich №, hisob raqam, abonent, TP…" value={q} onChange={(e) => setQ(e.target.value)} />
            {q && <button className="icon-btn" onClick={() => setQ('')}><X size={15} /></button>}</div>
          {found.length > 0 && <div className="found">{found.map((r) => (
            <button key={r.t + r.id} onClick={() => goto(r)} className={r.la === null ? 'nogeo' : ''}>
              <span>{r.title}</span><small>{r.la === null ? "koordinata yo'q" : r.sub}</small></button>))}</div>}
          {metric && <div className="mp-chip"><span>{METRIC_TITLES[metric] || metric}</span><button onClick={() => { setParam('metric', ''); setKinds(new Set(['aholi', 'ulgurji', 'balans', 'tr'])) }}><X size={14} /></button></div>}
          <label className="field"><span>Tuman</span>
            <select value={esp} onChange={(e) => { setParam('esp', e.target.value); setParam('brig', '') }}>
              <option value="">Barcha tumanlar</option>{boot.esps.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}</select></label>
          <label className="field"><span>Brigada</span>
            <select value={brig} onChange={(e) => setParam('brig', e.target.value)}>
              <option value="">Barcha brigadalar</option><option value="0">Biriktirilmagan</option>
              {brigs.map((b) => <option key={b.id} value={b.id}>{b.name}{!esp ? ` — ${boot.esps.find((e) => e.id === b.esp_id)?.label}` : ''}</option>)}</select></label>
          <div className="mp-sec">Qurilma turi</div>
          <div className="kinds">{KINDS.map(({ k, c }) => (
            <button key={k} className={`kind ${kinds.has(k) ? 'on' : ''}`} style={{ '--kc': c }} onClick={() => toggle(kinds, setKinds, k)} disabled={!!metric && metricKinds(metric)?.indexOf(k) === -1}>
              <i dangerouslySetInnerHTML={{ __html: glyph(k, 17) }} /><span>{KIND_NAME[k]}</span></button>))}</div>
          <StGroup title="Hisoblagich holati" list={METER_ST} sel={status} counts={counts} onToggle={(k) => toggle(status, setStatus, k)} />
          <StGroup title="Konsentrator holati" list={TR_ST} sel={status} counts={counts} onToggle={(k) => toggle(status, setStatus, k)} />
          <StGroup title="Konsentrator obxod darajasi" list={TR_LV} sel={status} counts={counts} onToggle={(k) => toggle(status, setStatus, k)} />
          {status.size > 0 && <button className="btn ghost sm clr" onClick={() => setStatus(new Set())}><X size={14} />Holatlarni tozalash ({status.size})</button>}
          <div className="mp-info">
            {info && <div><Info size={14} />Ko‘rinishda: <b>{num(info.meters)}</b> hisoblagich, <b>{num(info.trs)}</b> konsentrator{info.mode === 'clusters' ? ' (guruhlangan — yaqinlashtiring)' : ''}</div>}
            {cov && <div className="mut">Koordinatasi kiritilgan: hisoblagich {num(cov.meters_geo)} / {num(cov.meters)}, konsentrator {num(cov.trs_geo)} / {num(cov.trs)}</div>}
          </div>
        </aside>)}
    </div>
  )
}
