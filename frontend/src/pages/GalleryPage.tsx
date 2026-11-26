import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export function GalleryPage() {
  const qc = useQueryClient()
  const [typeFilter, setTypeFilter] = useState('')
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({})

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs', 'gallery', typeFilter],
    queryFn: () => api.listJobs({ job_type: typeFilter || undefined, state: 'completed' }),
  })

  const jobsWithOutputs = jobs.filter((j) => j.output_refs.length > 0)

  useEffect(() => {
    const assets = jobsWithOutputs.flatMap((j) => j.output_refs)
    if (assets.length === 0) return
    Promise.all(
      assets.map(async (a) => {
        if (signedUrls[a.asset_id]) return [a.asset_id, signedUrls[a.asset_id]] as const
        const res = await api.getAssetDownloadUrl(a.asset_id)
        return [a.asset_id, res.download_url] as const
      })
    ).then((pairs) => setSignedUrls((prev) => ({ ...prev, ...Object.fromEntries(pairs) })))
  }, [jobsWithOutputs.length])

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteJob(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Private Gallery</h1>
          <p className="text-sm text-slate-400 mt-1">
            Short-lived signed previews. Outputs are retained for 14 days before lifecycle cleanup.
          </p>
        </div>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-studio-900 border border-slate-800 text-xs"
        >
          <option value="">All Media</option>
          <option value="image">Images</option>
          <option value="talking_video">Talking Videos</option>
          <option value="cinematic_video">Cinematic Videos</option>
        </select>
      </div>

      {jobsWithOutputs.length === 0 ? (
        <div className="p-12 rounded-2xl bg-studio-900 border border-slate-800 text-center text-sm text-slate-500">
          No completed outputs yet.
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {jobsWithOutputs.flatMap((job) =>
            job.output_refs.map((asset) => {
              const url = signedUrls[asset.asset_id]
              return (
                <div key={asset.asset_id} className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden flex flex-col">
                  <Link to={`/jobs/${job.id}`} className="bg-studio-950 h-56 flex items-center justify-center overflow-hidden">
                    {url ? (
                      asset.content_type.startsWith('video/') ? (
                        <video src={url} controls className="h-full w-full object-cover" />
                      ) : (
                        <img src={url} alt={asset.filename} className="h-full w-full object-cover" />
                      )
                    ) : (
                      <span className="text-xs text-slate-500">Loading...</span>
                    )}
                  </Link>
                  <div className="p-4 flex items-center justify-between gap-2 text-xs">
                    <div className="min-w-0">
                      <div className="font-medium truncate">{asset.filename}</div>
                      <div className="text-slate-500">
                        {job.engine} · Expires {job.expires_at ? new Date(job.expires_at).toLocaleDateString() : '14d'}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {url && (
                        <a
                          href={url}
                          download={asset.filename}
                          className="p-2 rounded-lg bg-studio-800 hover:bg-studio-700 text-slate-200"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      )}
                      <button
                        onClick={() => deleteMutation.mutate(job.id)}
                        className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
