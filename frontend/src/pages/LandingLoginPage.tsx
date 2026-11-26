import React, { useState } from 'react'
import { Sparkles, ShieldCheck, Video, Image as ImageIcon, Mic } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export function LandingLoginPage() {
  const { login, register, googleSignIn } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('creator@example.com')
  const [password, setPassword] = useState('creator123')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, displayName || email.split('@')[0])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  const handleGoogleDemo = async () => {
    setError('')
    setBusy(true)
    try {
      await googleSignIn(`demo-google:${email || 'google-creator@example.com'}`, email)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-studio-950 text-slate-100 flex flex-col lg:flex-row">
      {/* Left Hero */}
      <div className="flex-1 p-8 lg:p-16 flex flex-col justify-between bg-gradient-to-br from-indigo-950/40 via-studio-950 to-studio-900 border-b lg:border-b-0 lg:border-r border-slate-800/80">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-medium mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            AI Creator Studio · Cloud Run GPU + Hybrid API
          </div>
          <h1 className="text-4xl lg:text-5xl font-bold tracking-tight text-white max-w-xl leading-tight">
            Create AI influencer portraits, talking-head reels & cinematic clips.
          </h1>
          <p className="mt-4 text-slate-400 max-w-lg text-base leading-relaxed">
            Built on on-demand NVIDIA L4 Cloud Run GPU Jobs with ComfyUI, private Cloud Storage signed URLs, and optional Seedance & Kling premium engines.
          </p>

          <div className="mt-10 grid sm:grid-cols-3 gap-4 max-w-2xl">
            <div className="p-4 rounded-xl bg-studio-900/80 border border-slate-800">
              <ImageIcon className="w-5 h-5 text-indigo-400 mb-2" />
              <div className="font-medium text-sm">Influencer Images</div>
              <div className="text-xs text-slate-400 mt-1">FLUX.1-schnell & SDXL 1.0 with seed & reference control.</div>
            </div>
            <div className="p-4 rounded-xl bg-studio-900/80 border border-slate-800">
              <Mic className="w-5 h-5 text-emerald-400 mb-2" />
              <div className="font-medium text-sm">Talking Portraits</div>
              <div className="text-xs text-slate-400 mt-1">LivePortrait + MuseTalk up to 30s at 1080p MP4.</div>
            </div>
            <div className="p-4 rounded-xl bg-studio-900/80 border border-slate-800">
              <Video className="w-5 h-5 text-amber-400 mb-2" />
              <div className="font-medium text-sm">Cinematic Clips</div>
              <div className="text-xs text-slate-400 mt-1">Wan 2.2 TI2V-5B open GPU or Seedance & Kling APIs.</div>
            </div>
          </div>
        </div>

        <div className="mt-12 flex items-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 text-slate-400" />
          <span>
            Terms & Privacy: All generated characters are synthetic. Users must hold rights to uploaded likenesses and voices.
          </span>
        </div>
      </div>

      {/* Right Auth Card */}
      <div className="w-full lg:w-[460px] p-8 lg:p-12 flex items-center justify-center bg-studio-900/60">
        <div className="w-full max-w-sm space-y-6">
          <div>
            <h2 className="text-2xl font-semibold">
              {mode === 'login' ? 'Sign in to Studio' : 'Create Creator Account'}
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              {mode === 'login'
                ? 'Access your studios, job queue, and private gallery.'
                : 'Start with 100 free studio credits.'}
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Display Name</label>
                <input
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Alex Creator"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-medium text-sm transition"
            >
              {busy ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <button
            type="button"
            disabled={busy}
            onClick={handleGoogleDemo}
            className="w-full py-2.5 px-4 rounded-lg bg-studio-800 hover:bg-studio-700 border border-slate-700 text-sm font-medium transition"
          >
            Continue with Google
          </button>

          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <span>{mode === 'login' ? 'New to AI Creator Studio?' : 'Already have an account?'}</span>
            <button
              type="button"
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-indigo-400 hover:text-indigo-300 font-medium"
            >
              {mode === 'login' ? 'Register' : 'Sign in'}
            </button>
          </div>

          <div className="p-3 rounded-lg bg-studio-950/80 border border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="font-medium text-slate-300">Demo Accounts (Local Mode)</div>
            <div className="flex justify-between">
              <span>Customer: creator@example.com / creator123</span>
              <button
                type="button"
                onClick={() => {
                  setMode('login')
                  setEmail('creator@example.com')
                  setPassword('creator123')
                }}
                className="text-indigo-400 hover:underline"
              >
                Use
              </button>
            </div>
            <div className="flex justify-between">
              <span>Admin: admin@example.com / admin123</span>
              <button
                type="button"
                onClick={() => {
                  setMode('login')
                  setEmail('admin@example.com')
                  setPassword('admin123')
                }}
                className="text-amber-400 hover:underline"
              >
                Use
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
