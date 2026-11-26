import {
  Activity,
  Clapperboard,
  Coins,
  Film,
  Image as ImageIcon,
  LayoutDashboard,
  LogOut,
  Mic,
  Shield,
  Sparkles,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/image-studio', label: 'Image Studio', icon: ImageIcon },
  { to: '/talking-studio', label: 'Talking Video', icon: Mic },
  { to: '/video-studio', label: 'Cinematic Video', icon: Clapperboard },
  { to: '/jobs', label: 'Job Centre', icon: Activity },
  { to: '/gallery', label: 'Gallery', icon: Film },
  { to: '/usage', label: 'Usage & Credits', icon: Coins },
]

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen flex bg-studio-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-slate-800/80 bg-studio-900/90 flex flex-col">
        <div className="p-5 border-b border-slate-800/80 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight">AI Creator Studio</div>
            <div className="text-[11px] text-slate-400">Cloud Run L4 + Hybrid API</div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                  isActive
                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 font-medium'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}

          {user?.role === 'admin' && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition mt-4 ${
                  isActive
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 font-medium'
                    : 'text-amber-400/80 hover:text-amber-300 hover:bg-slate-800/60'
                }`
              }
            >
              <Shield className="w-4 h-4" />
              Admin Console
            </NavLink>
          )}
        </nav>

        <div className="p-4 border-t border-slate-800/80 space-y-3">
          <div className="rounded-lg bg-studio-800/80 p-3 border border-slate-700/50">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Credits</span>
              <span className="font-semibold text-indigo-300">{user?.credits ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400 mt-1">
              <span>Daily Quota</span>
              <span>
                {user?.daily_used ?? 0} / {user?.daily_quota ?? 0}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-xs font-medium truncate">{user?.display_name}</div>
              <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-slate-800/80 bg-studio-900/50 px-6 flex items-center justify-between text-xs text-slate-400">
          <div>
            Synthetic Media Notice: Generated characters are AI-synthesized. Ensure you hold rights to any uploaded likeness or voice.
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
            <span>us-central1</span>
          </div>
        </header>
        <main className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
