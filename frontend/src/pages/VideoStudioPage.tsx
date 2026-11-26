import { useMutation, useQuery } from '@tanstack/react-query'
import { Clapperboard, Upload } from 'lucide-react'
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, newIdempotencyKey } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { EngineId } from '../types'

export function VideoStudioPage() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: api.listModels })
  const videoModels = models.filter((m) => m.job_type === 'cinematic_video' && m.enabled)

  const [mode, setMode] = useState<'text_to_video' | 'image_to_video'>('text_to_video')
  const [engine, setEngine] = useState<EngineId>('wan2_2')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('flicker, distortion, watermark')
  const [refPath, setRefPath] = useState<string | null>(null)
  const [duration, setDuration] = useState(5)
  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9' | '1:1'>('9:16')
  const [qualityPreset, setQualityPreset] = useState<'draft' | 'standard' | 'high'>('standard')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const selectedModel = videoModels.find((m) => m.id === engine) || videoModels[0]
  const estCredits = (selectedModel?.base_credits ?? 12) * Math.max(1, Math.ceil(duration / 5)) * (qualityPreset === 'high' ? 2 : 1)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const path = await api.uploadFile(file, 'reference_image')
      setRefPath(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createJob({
        job_type: 'cinematic_video',
        engine,
        idempotency_key: newIdempotencyKey(),
        params: {
          mode,
          prompt,
          negative_prompt: negativePrompt,
          reference_image_path: refPath,
          duration_seconds: duration,
          aspect_ratio: aspectRatio,
          quality_preset: qualityPreset,
        },
      }),
    onSuccess: async (job) => {
      await refreshUser()
      navigate(`/jobs/${job.id}`)
    },
    onError: (err) => setError(err instanceof Error ? err.message : 'Failed to create video job'),
  })

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Cinematic Video Studio</h1>
        <p className="text-sm text-slate-400 mt-1">
          Generate short cinematic clips with Wan 2.2 TI2V-5B (L4 GPU) or hosted Seedance & Kling APIs.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">{error}</div>
      )}

      <div className="p-6 rounded-2xl bg-studio-900 border border-slate-800 space-y-5">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode('text_to_video')}
            className={`px-4 py-2 rounded-lg text-xs font-medium border transition ${
              mode === 'text_to_video'
                ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                : 'bg-studio-950 border-slate-800 text-slate-400'
            }`}
          >
            Text-to-Video
          </button>
          <button
            type="button"
            onClick={() => setMode('image_to_video')}
            className={`px-4 py-2 rounded-lg text-xs font-medium border transition ${
              mode === 'image_to_video'
                ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                : 'bg-studio-950 border-slate-800 text-slate-400'
            }`}
          >
            Image-to-Video (Consistent Character)
          </button>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Scene Prompt</label>
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Slow dolly shot of a creator walking through neon-lit rain in Seoul, shallow depth of field, cinematic 24fps..."
            className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-amber-500"
          />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Engine</label>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as EngineId)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              {videoModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} {m.is_premium ? '(Premium)' : '(Open GPU)'}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Clip Duration ({duration}s)</label>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value={5}>5 seconds</option>
              <option value={10}>10 seconds</option>
              <option value={15}>15 seconds</option>
              <option value={30}>30 seconds (joined clips)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Aspect Ratio</label>
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value as typeof aspectRatio)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="9:16">9:16 Vertical</option>
              <option value="16:9">16:9 Landscape</option>
              <option value="1:1">1:1 Square</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Quality Preset</label>
            <select
              value={qualityPreset}
              onChange={(e) => setQualityPreset(e.target.value as typeof qualityPreset)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="draft">Draft</option>
              <option value="standard">Standard</option>
              <option value="high">High (2x credits)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            Reference Image {mode === 'image_to_video' ? '(Required)' : '(Optional)'}
          </label>
          <label className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-studio-950 border border-dashed border-slate-700 hover:border-amber-500 cursor-pointer text-xs text-slate-300">
            <Upload className="w-4 h-4 text-amber-400" />
            <span>{uploading ? 'Uploading...' : refPath ? `Uploaded: ${refPath.split('/').pop()}` : 'Upload character/scene reference'}</span>
            <input type="file" accept="image/*" onChange={handleUpload} className="hidden" />
          </label>
        </div>

        <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Estimated cost: <span className="text-amber-300 font-semibold">{estCredits} credits</span>
          </div>
          <button
            type="button"
            disabled={!prompt.trim() || (mode === 'image_to_video' && !refPath) || uploading || createMutation.isPending}
            onClick={() => createMutation.mutate()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:opacity-50 font-medium text-sm transition"
          >
            <Clapperboard className="w-4 h-4" />
            {createMutation.isPending ? 'Submitting...' : 'Generate Video'}
          </button>
        </div>
      </div>
    </div>
  )
}
