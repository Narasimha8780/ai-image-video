import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

export function AdminPage() {
  const qc = useQueryClient()
  const { data: overview } = useQuery({ queryKey: ['admin', 'overview'], queryFn: api.adminOverview })
  const { data: users = [] } = useQuery({ queryKey: ['admin', 'users'], queryFn: api.adminUsers })
  const { data: jobs = [] } = useQuery({ queryKey: ['admin', 'jobs'], queryFn: () => api.adminJobs() })
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: api.listModels })

  const toggleModel = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.adminToggleModel(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }),
  })

  const addCredits = useMutation({
    mutationFn: ({ userId, credits }: { userId: string; credits: number }) =>
      api.adminUpdateUser(userId, { credits }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'users'] }),
  })

  const retryJob = useMutation({
    mutationFn: (id: string) => api.retryJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'jobs'] }),
  })

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Admin Console</h1>
        <p className="text-sm text-slate-400 mt-1">
          Manage users, credit limits, model availability, queue depth, and failed-job retries.
        </p>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Users</div>
          <div className="text-xl font-bold mt-1">{overview?.total_users ?? 0}</div>
        </div>
        <div className="p-4 rounded-xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Queue Depth</div>
          <div className="text-xl font-bold text-indigo-300 mt-1">{overview?.active_queue_depth ?? 0}</div>
        </div>
        <div className="p-4 rounded-xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Completed</div>
          <div className="text-xl font-bold text-emerald-400 mt-1">{overview?.completed_jobs ?? 0}</div>
        </div>
        <div className="p-4 rounded-xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Failed</div>
          <div className="text-xl font-bold text-rose-400 mt-1">{overview?.failed_jobs ?? 0}</div>
        </div>
        <div className="p-4 rounded-xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Credits Consumed</div>
          <div className="text-xl font-bold text-amber-300 mt-1">{overview?.total_credits_consumed ?? 0}</div>
        </div>
      </div>

      {/* Model Availability */}
      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 font-semibold text-sm">Approved Model Registry</div>
        <div className="divide-y divide-slate-800/80">
          {models.map((m) => (
            <div key={m.id} className="px-6 py-4 flex items-center justify-between gap-4 text-xs">
              <div>
                <div className="font-medium text-sm text-slate-200">
                  {m.name} <span className="text-slate-500 font-normal">({m.version})</span>
                </div>
                <div className="text-slate-400 mt-0.5">{m.notes}</div>
                <div className="text-slate-500 mt-0.5">License: {m.license_note}</div>
              </div>
              <button
                onClick={() => toggleModel.mutate({ id: m.id, enabled: !m.enabled })}
                className={`px-3 py-1.5 rounded-lg font-medium border ${
                  m.enabled
                    ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                    : 'bg-slate-800 border-slate-700 text-slate-400'
                }`}
              >
                {m.enabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* User Management */}
      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 font-semibold text-sm">Users & Quotas</div>
        <div className="divide-y divide-slate-800/80">
          {users.map((u) => (
            <div key={u.id} className="px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 text-xs">
              <div>
                <div className="font-medium text-slate-200">
                  {u.display_name} <span className="text-slate-500">({u.email})</span>
                </div>
                <div className="text-slate-400">
                  Role: {u.role} · Credits: {u.credits} · Daily: {u.daily_used}/{u.daily_quota}
                </div>
              </div>
              <button
                onClick={() => addCredits.mutate({ userId: u.id, credits: u.credits + 100 })}
                className="px-3 py-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 hover:bg-indigo-600/30"
              >
                +100 Credits
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Recent System Jobs */}
      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 font-semibold text-sm">All System Jobs</div>
        <div className="divide-y divide-slate-800/80">
          {jobs.slice(0, 15).map((j) => (
            <div key={j.id} className="px-6 py-3.5 flex items-center justify-between gap-4 text-xs">
              <div>
                <span className="font-medium text-slate-200">{j.id}</span> ·{' '}
                <span className="text-slate-400">{j.engine}</span> ·{' '}
                <span className="text-slate-500">{j.user_id}</span>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge state={j.state} />
                {j.state === 'failed' && (
                  <button
                    onClick={() => retryJob.mutate(j.id)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-600/20 text-indigo-300"
                  >
                    <RefreshCw className="w-3 h-3" /> Retry
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
