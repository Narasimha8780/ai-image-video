import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useAuth } from './context/AuthContext'
import { AdminPage } from './pages/AdminPage'
import { DashboardPage } from './pages/DashboardPage'
import { GalleryPage } from './pages/GalleryPage'
import { ImageStudioPage } from './pages/ImageStudioPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { JobsPage } from './pages/JobsPage'
import { LandingLoginPage } from './pages/LandingLoginPage'
import { TalkingVideoStudioPage } from './pages/TalkingVideoStudioPage'
import { UsagePage } from './pages/UsagePage'
import { VideoStudioPage } from './pages/VideoStudioPage'

export function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-studio-950 text-slate-400 flex items-center justify-center text-sm">
        Loading AI Creator Studio...
      </div>
    )
  }

  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<LandingLoginPage />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/image-studio" element={<ImageStudioPage />} />
        <Route path="/talking-studio" element={<TalkingVideoStudioPage />} />
        <Route path="/video-studio" element={<VideoStudioPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/gallery" element={<GalleryPage />} />
        <Route path="/usage" element={<UsagePage />} />
        {user.role === 'admin' && <Route path="/admin" element={<AdminPage />} />}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App
