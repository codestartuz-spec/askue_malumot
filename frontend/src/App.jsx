import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './Layout'
import Login from './pages/Login'
import EnergyBackground from './bg'
import { Spinner } from './ui'

const Dynamics = lazy(() => import('./pages/Dynamics'))
const MapPage = lazy(() => import('./pages/MapPage'))
const Republic = lazy(() => import('./pages/Republic'))
const Ag = lazy(() => import('./pages/Ag'))
const Home = lazy(() => import('./pages/Home'))
const Messages = lazy(() => import('./pages/Messages'))
const Settings = lazy(() => import('./pages/Settings'))
const Brigades = lazy(() => import('./pages/Brigades'))
const Devices = lazy(() => import('./pages/Devices'))
const Upload = lazy(() => import('./pages/Upload'))
const Users = lazy(() => import('./pages/Users'))
const Audit = lazy(() => import('./pages/Audit'))
const Daily = lazy(() => import('./pages/Daily'))

function Guard({ perm, any, sadmin, children }) {
  const { can, user } = useAuth()
  if (sadmin ? !user?.is_super : any ? !any.some(can) : perm && !can(perm)) return <div className="card pad denied">Bu sahifaga kirish uchun ruxsat berilmagan.</div>
  return children
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return (<><EnergyBackground /><div className="boot"><Spinner label="Tizim yuklanmoqda…" /></div></>)
  if (!user) return <Login />
  return (
    <Layout>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/xabarlar" element={<Guard any={['telegram.message', 'telegram.journal']}><Messages /></Guard>} />
          <Route path="/dinamika" element={<Dynamics />} />
          <Route path="/konsentratorlar" element={<Navigate to="/dinamika?t=konsentrator" replace />} />
          <Route path="/aloqa" element={<Navigate to="/dinamika?t=aloqa" replace />} />
          <Route path="/obxod" element={<Navigate to="/dinamika?t=obxod" replace />} />
          <Route path="/kunlik-topshiriq" element={<Guard perm="daily.view"><Daily /></Guard>} />
          <Route path="/xarita" element={<Guard perm="map.view"><MapPage /></Guard>} />
          <Route path="/respublika" element={<Guard perm="republic.view"><Republic /></Guard>} />
          <Route path="/ag" element={<Guard perm="ag.view"><Ag /></Guard>} />
          <Route path="/sozlamalar" element={<Guard any={['settings.manage', 'system.view', 'backup.manage']}><Settings /></Guard>} />
          <Route path="/brigadalar" element={<Guard perm="brigade.view"><Brigades /></Guard>} />
          <Route path="/yuklash" element={<Guard any={['data.upload', 'republic.upload', 'ag.upload']}><Upload /></Guard>} />
          <Route path="/xodimlar" element={<Guard sadmin><Users /></Guard>} />
          <Route path="/qurilmalar" element={<Guard sadmin><Devices /></Guard>} />
          <Route path="/jurnal" element={<Guard perm="audit.view"><Audit /></Guard>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}
