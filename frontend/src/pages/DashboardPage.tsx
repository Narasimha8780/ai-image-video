import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Clapperboard, Coins, Image as ImageIcon, Mic } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'
import { useAuth } from '../context/AuthContext'

export function DashboardPage() {
  const { user } = useAuth()
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.listJobs(),
    refetchInterval: 3000,
  })

  const activeCount = jobs.filter((j) => ['queued', 'starting', 'running', 'uploading'].includes(j.state)).length

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Welcome back, {user?.display_name}</h1>
          <p className="text-sm text-slate-400 mt-1">
            Launch a new generation or monitor your active Cloud Run GPU and hosted API jobs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-xl bg-studio-900 border border-slate-800 flex items-center gap-2.5">
            <Coins className="w-4 h-4 text-indigo-400" />
            <div className="text-xs">
              <div className="text-slate-400">Available Credits</div>
              <div className="font-semibold text-sm">{user?.credits ?? 0}</div>
            </div>
          </div>
          <div className="px-4 py-2 rounded-xl bg-studio-900 border border-slate-800 text-xs">
            <div className="text-slate-400">Active Jobs</div>
            <div className="font-semibold text-sm">
              {activeCount} / {user?.max_active_jobs ?? 5}
            </div>
          </div>
        </div>
      </div>

      {/* Studio Quick Launch Cards */}
      <div className="grid md:grid-cols-3 gap-5">
        <Link
          to="/image-studio"
          className="group p-6 rounded-2xl bg-studio-900 border border-slate-800 hover:border-indigo-500/50 transition flex flex-col justify-between"
        >
          <div>
            <div className="h-10 w-10 rounded-xl bg-indigo-500/15 text-indigo-400 flex items-center justify-center mb-4">
              <ImageIcon className="w-5 h-5" />
            </div>
            <h2 className="font-semibold text-lg">Create Image</h2>
            <p className="text-sm text-slate-400 mt-1">
              Generate AI influencer portraits with FLUX.1-schnell or SDXL 1.0.
            </p>
          </div>
          <div className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 group-hover:translate-x-1 transition">
            Open Image Studio <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>

        <Link
          to="/talking-studio"
          className="group p-6 rounded-2xl bg-studio-900 border border-slate-800 hover:border-emerald-500/50 transition flex flex-col justify-between"
        >
          <div>
            <div className="h-10 w-10 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center mb-4">
              <Mic className="w-5 h-5" />
            </div>
            <h2 className="font-semibold text-lg">Talking Video</h2>
            <p className="text-sm text-slate-400 mt-1">
              Animate a portrait with TTS or custom audio up to 30s at 1080p.
            </p>
          </div>
          <div className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 group-hover:translate-x-1 transition">
            Open Talking Studio <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>

        <Link
          to="/video-studio"
          className="group p-6 rounded-2xl bg-studio-900 border border-slate-800 hover:border-amber-500/50 transition flex flex-col justify-between"
        >
          <div>
            <div className="h-10 w-10 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center mb-4">
              <Clapperboard className="w-5 h-5" />
            </div>
            <h2 className="font-semibold text-lg">Cinematic Video</h2>
            <p className="text-sm text-slate-400 mt-1">
              Text-to-video or image-to-video via Wan 2.2, Seedance, or Kling.
            </p>
          </div>
          <div className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium text-amber-400 group-hover:translate-x-1 transition">
            Open Video Studio <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </Link>
      </div>

      {/* Recent Jobs */}
      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="font-semibold">Recent Jobs</h3>
          <Link to="/jobs" className="text-xs text-indigo-400 hover:underline">
            View all jobs
          </Link>
        </div>
        {jobs.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            No jobs yet. Pick a studio above to start your first generation.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {jobs.slice(0, 6).map((job) => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="px-6 py-4 flex items-center justify-between hover:bg-slate-800/40 transition"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm font-medium capitalize">{job.job_type.replace('_', ' ')}</span>
                    <span className="text-xs text-slate-500">· {job.engine}</span>
                  </div>
                  <div className="text-xs text-slate-400 truncate max-w-xl mt-0.5">
                    {String(job.params.prompt || job.params.script_text || job.status_message)}
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className="text-xs text-slate-400">{job.estimated_credits} credits</span>
                  <StatusBadge state={job.state} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
