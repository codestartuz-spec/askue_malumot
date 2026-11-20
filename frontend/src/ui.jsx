import { useEffect, useRef, useState, createContext, useContext, useCallback } from 'react'
import { Users, X, Loader2, CheckCircle2, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react'
import { createPortal } from 'react-dom'
import P from './logoPaths'

export function Logo({ variant = 'full', theme = 'light', height = 44, animated = true, className = '' }) {
  const dark = theme === 'dark'
  const vb = variant === 'mark' ? '6 14 295 337' : '0 0 646 371'
  const ratio = variant === 'mark' ? 295 / 337 : 646 / 371
  return (
    <svg className={`logo ${animated ? 'logo-anim' : ''} ${className}`} viewBox={vb} height={height}
      width={height * ratio} role="img" aria-label="Hududiy Elektr Tarmoqlari">
      <path className="l-ring" fill="#E31E24" fillRule="evenodd" d={P.red} />
      <path className="l-bolt" fill={dark ? '#4C8DFF' : '#0B3F94'} fillRule="evenodd" d={P.bolt} />
      <path className="l-spark" fill="#1FA24A" fillRule="evenodd" d={P.green} />
      {variant === 'full' && <path fill={dark ? '#FFFFFF' : '#0B3F94'} fillRule="evenodd" d={P.text} />}
    </svg>
  )
}

export function Spinner({ label = 'Yuklanmoqda…' }) {
  return <div className="spinner"><Loader2 className="spin" size={22} /><span>{label}</span></div>
}

export function Empty({ icon: Icon, children }) {
  return <div className="empty">{Icon && <Icon size={34} />}<div>{children}</div></div>
}

export function Modal({ title, onClose, children, wide, footer, icon: Icon }) {
  useEffect(() => {
    const f = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', f)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', f); document.body.style.overflow = '' }
  }, [onClose])
  return createPortal(
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <div className="modal-title">{Icon && <Icon size={20} />}<span>{title}</span></div>
          <button className="icon-btn" onClick={onClose} aria-label="Yopish"><X size={20} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}

export function Pager({ page, size, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / size))
  return (
    <div className="pager">
      <button className="btn ghost sm" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /></button>
      <span>{page} / {pages.toLocaleString('ru')}</span>
      <button className="btn ghost sm" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight size={16} /></button>
    </div>
  )
}

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((msg, type = 'ok') => {
    const id = Math.random()
    setItems((a) => [...a, { id, msg, type }])
    setTimeout(() => setItems((a) => a.filter((x) => x.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            {t.type === 'err' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}<span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useDebounced(v, ms = 350) {
  const [x, setX] = useState(v)
  useEffect(() => { const t = setTimeout(() => setX(v), ms); return () => clearTimeout(t) }, [v, ms])
  return x
}

export function useCountUp(target, ms = 700) {
  const [v, setV] = useState(target)
  const prev = useRef(target)
  useEffect(() => {
    const from = prev.current, to = target
    if (from === to || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setV(to); prev.current = to; return }
    let raf, t0
    const step = (t) => {
      t0 ??= t
      const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3)
      setV(Math.round(from + (to - from) * e))
      if (k < 1) raf = requestAnimationFrame(step); else prev.current = to
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

export function Confirm({ title, children, ok = 'Ha', cancel = 'Bekor qilish', danger, onOk, onCancel, icon }) {
  return (
    <Modal icon={icon} title={title} onClose={onCancel}
      footer={<><button className="btn ghost" onClick={onCancel}>{cancel}</button>
        <button className={`btn ${danger ? 'danger' : 'primary'}`} autoFocus onClick={onOk}>{ok}</button></>}>
      <div className="confirm-body">{children}</div>
    </Modal>
  )
}

// Kanal/guruh a'zolari soni nishoni
export function Members({ c }) {
  const n = c.members
  return <span className="members" title={c.members_at ? `A'zolar soni (yangilangan: ${new Date(c.members_at).toLocaleString('ru-RU')})` : "A'zolar soni hali aniqlanmagan"}>
    <Users size={13} />{n === null || n === undefined ? '—' : n.toLocaleString('ru-RU')}</span>
}
