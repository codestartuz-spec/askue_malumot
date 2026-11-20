import { useState } from 'react'
import { LogIn, User, Lock, Eye, EyeOff, Zap, Send, KeyRound, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Logo } from '../ui'
import EnergyBackground from '../bg'

function Forgot({ onBack }) {
  const [step, setStep] = useState(1)
  const [u, setU] = useState('')
  const [code, setCode] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setErr(''); setBusy(true); try { await fn() } catch (x) { setErr(x.message) } finally { setBusy(false) } }
  const sendCode = (e) => { e?.preventDefault(); run(async () => { await api.post('/auth/forgot', { username: u.trim() }); setStep(2) }) }
  const reset = (e) => { e.preventDefault(); run(async () => { await api.post('/auth/reset', { username: u.trim(), code: code.trim(), new_password: pw }); setOk("Parol almashtirildi. Endi yangi parol bilan kiring."); setTimeout(onBack, 1800) }) }
  return (
    <form className="login-card" onSubmit={step === 1 ? sendCode : reset}>
      <div className="login-title"><KeyRound size={18} /><span>Parolni tiklash</span></div>
      <p className="login-sub">{step === 1 ? "Loginingizni kiriting — Telegram botingizga bir martalik kod yuboramiz." : "Telegram'ga kelgan 6 xonali kodni va yangi parolni kiriting."}</p>
      <label className="input-ic"><User size={18} /><input autoFocus placeholder="Login" value={u} onChange={(e) => setU(e.target.value)} disabled={step === 2} /></label>
      {step === 2 && (<>
        <label className="input-ic"><ShieldCheck size={18} /><input placeholder="Telegram kodi" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <label className="input-ic"><Lock size={18} /><input placeholder="Yangi parol (kamida 6 belgi)" type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /></label>
      </>)}
      {err && <div className="login-err">{err}</div>}
      {ok && <div className="login-ok">{ok}</div>}
      <button className="btn primary big" disabled={busy || !u || (step === 2 && (code.length < 6 || pw.length < 6))}>
        {step === 1 ? <><Send size={18} />Kod yuborish</> : <><KeyRound size={18} />Parolni almashtirish</>}</button>
      {step === 2 && <button type="button" className="link-btn" onClick={sendCode} disabled={busy}>Kodni qayta yuborish</button>}
      <button type="button" className="link-btn" onClick={onBack}>← Kirish sahifasiga qaytish</button>
      <p className="login-hint">Botdan foydalanish: Telegram'da botga <b>/start</b> bosing, chat ID'ni profilingizga kiriting. Bot orqali <b>/parol</b> yuborib ham yangi parol olish mumkin.</p>
    </form>)
}

export default function Login() {
  const [forgot, setForgot] = useState(false)
  const { login } = useAuth()
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [show, setShow] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await login(u.trim(), p) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <div className="login-wrap">
      <EnergyBackground intensity={1.25} />
      {forgot ? <Forgot onBack={() => setForgot(false)} /> : (
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo"><Logo theme="dark" height={78} /></div>
        <div className="login-title"><Zap size={18} /><span>ASKUE ma'lumot</span></div>
        <p className="login-sub">Qashqadaryo hududiy filiali</p>
        <label className="input-ic"><User size={18} /><input autoFocus placeholder="Login" value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" /></label>
        <label className="input-ic"><Lock size={18} />
          <input placeholder="Parol" type={show ? 'text' : 'password'} value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
          <button type="button" className="eye" onClick={() => setShow(!show)} tabIndex={-1}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
        </label>
        {err && <div className="login-err">{err}</div>}
        <button className="btn primary big" disabled={busy || !u || !p}><LogIn size={18} />{busy ? 'Kirilmoqda…' : 'Kirish'}</button>
        <button type="button" className="link-btn" onClick={() => setForgot(true)}>Parolni unutdingizmi?</button>
      </form>)}
    </div>
  )
}
