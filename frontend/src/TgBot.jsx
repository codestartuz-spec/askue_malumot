import { Send } from 'lucide-react'
import { useAuth } from './auth'

// Telegram botga o'tish tugmasi (t.me havolasi)
export default function TgBotLink({ className = 'btn tg', label = "Telegram botga o'tish" }) {
  const { boot } = useAuth()
  const u = boot?.bot_username
  if (!u) return <span className="btn tg disabled" title="Bot hali ulanmagan (Sozlamalar)"><Send size={16} />{label}</span>
  return <a className={className} href={`https://t.me/${u}`} target="_blank" rel="noreferrer" title={`@${u}`}><Send size={16} />{label}</a>
}
