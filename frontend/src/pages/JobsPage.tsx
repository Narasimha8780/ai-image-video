import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

export function JobsPage() {
  const qc = useQueryClient()
  const [typeFilter, setTypeFilter] = useState('')
  const [stateFilter, setStateFilter] = useState('')

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs', typeFilter, stateFilter],
    queryFn: () =>
      api.listJobs({
        job_type: typeFilter || undefined,
        state: stateFilter || undefined,
      }),
    refetchInterval: 2500,
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => api.retryJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Job Centre</h1>
          <p className="text-sm text-slate-400 mt-1">
            Live queue status, progress events, retries, and cancellations.
          </p>
        </div>

        <div className="flex gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 rounded-lg bg-studio-900 border border-slate-800 text-xs"
          >
            <option value="">All Types</option>
            <option value="image">Image</option>
            <option value="talking_video">Talking Video</option>
            <option value="cinematic_video">Cinematic Video</option>
          </select>

          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="px-3 py-2 rounded-lg bg-studio-900 border border-slate-800 text-xs"
          >
            <option value="">All States</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-slate-400">Loading jobs...</div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">No jobs match the selected filters.</div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {jobs.map((job) => (
              <div key={job.id} className="p-5 flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <Link to={`/jobs/${job.id}`} className="font-medium text-sm hover:text-indigo-400 transition">
                      {job.id}
                    </Link>
                    <StatusBadge state={job.state} />
                    <span className="text-xs text-slate-400 capitalize">{job.job_type.replace('_', ' ')}</span>
                    <span className="text-xs text-slate-500">· {job.engine}</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1 truncate max-w-2xl">
                    {job.status_message} — {String(job.params.prompt || job.params.script_text || '')}
                  </div>
                  {['queued', 'starting', 'running', 'uploading'].includes(job.state) && (
                    <div className="mt-2 w-full max-w-md h-1.5 bg-studio-950 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 transition-all" style={{ width: `${job.progress}%` }} />
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {job.state === 'failed' && (
                    <button
                      onClick={() => retryMutation.mutate(job.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 text-xs hover:bg-indigo-600/30"
                    >
                      <RefreshCw className="w-3.5 h-3.5" /> Retry
                    </button>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(job.id)}
                    title="Cancel or delete outputs"
                    className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
