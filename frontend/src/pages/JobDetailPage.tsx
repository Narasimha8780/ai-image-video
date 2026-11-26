import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({})

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => api.getJob(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const state = query.state.data?.state
      return state && ['queued', 'starting', 'running', 'uploading'].includes(state) ? 1500 : false
    },
  })

  useEffect(() => {
    if (!job?.output_refs?.length) return
    let cancelled = false
    Promise.all(
      job.output_refs.map(async (a) => {
        const res = await api.getAssetDownloadUrl(a.asset_id)
        return [a.asset_id, res.download_url] as const
      })
    ).then((pairs) => {
      if (!cancelled) {
        setSignedUrls(Object.fromEntries(pairs))
      }
    })
    return () => {
      cancelled = true
    }
  }, [job?.output_refs])

  const retryMutation = useMutation({
    mutationFn: () => api.retryJob(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }),
  })

  if (isLoading || !job) {
    return <div className="p-8 text-sm text-slate-400">Loading job details...</div>
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Job Centre
      </Link>

      <div className="p-6 rounded-2xl bg-studio-900 border border-slate-800 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold">{job.id}</h1>
              <StatusBadge state={job.state} />
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Engine: {job.engine} ({job.model_version}) · Credits: {job.actual_credits ?? job.estimated_credits}
            </p>
          </div>

          {job.state === 'failed' && (
            <button
              onClick={() => retryMutation.mutate()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry Job
            </button>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-slate-400">
            <span>{job.status_message}</span>
            <span>{job.progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-studio-950 overflow-hidden">
            <div className="h-full bg-indigo-500 transition-all" style={{ width: `${job.progress}%` }} />
          </div>
        </div>

        {job.error_message && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            Error ({job.error_category}): {job.error_message}
          </div>
        )}

        <div className="grid sm:grid-cols-3 gap-4 text-xs text-slate-400 pt-2 border-t border-slate-800">
          <div>
            <span className="text-slate-500">Created:</span> {new Date(job.created_at).toLocaleString()}
          </div>
          <div>
            <span className="text-slate-500">Completed:</span>{' '}
            {job.completed_at ? new Date(job.completed_at).toLocaleString() : '—'}
          </div>
          <div>
            <span className="text-slate-500">Expires:</span>{' '}
            {job.expires_at ? new Date(job.expires_at).toLocaleDateString() : '—'}
          </div>
        </div>
      </div>

      {/* Outputs */}
      {job.output_refs.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-semibold">Generated Outputs</h2>
          <div className="grid sm:grid-cols-2 gap-5">
            {job.output_refs.map((asset) => {
              const url = signedUrls[asset.asset_id]
              return (
                <div key={asset.asset_id} className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
                  <div className="bg-studio-950 flex items-center justify-center min-h-[260px]">
                    {url ? (
                      asset.content_type.startsWith('video/') ? (
                        <video src={url} controls className="max-h-[420px] w-full object-contain" />
                      ) : (
                        <img src={url} alt={asset.filename} className="max-h-[420px] w-full object-contain" />
                      )
                    ) : (
                      <span className="text-xs text-slate-500">Issuing signed URL...</span>
                    )}
                  </div>
                  <div className="p-4 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-medium text-slate-200">{asset.filename}</div>
                      <div className="text-slate-500">
                        {asset.width && asset.height ? `${asset.width}×${asset.height}` : ''} ·{' '}
                        {Math.round(asset.size_bytes / 1024)} KB
                      </div>
                    </div>
                    {url && (
                      <a
                        href={url}
                        download={asset.filename}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-studio-800 hover:bg-studio-700 text-slate-200"
                      >
                        <Download className="w-3.5 h-3.5" /> Download
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
