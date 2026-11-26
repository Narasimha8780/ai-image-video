import { useMutation, useQuery } from '@tanstack/react-query'
import { Sparkles, Upload } from 'lucide-react'
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, newIdempotencyKey } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { EngineId } from '../types'

export function ImageStudioPage() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: api.listModels })
  const imageModels = models.filter((m) => m.job_type === 'image' && m.enabled)

  const [engine, setEngine] = useState<EngineId>('flux_schnell')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState('blurry, low quality, deformed hands')
  const [aspectRatio, setAspectRatio] = useState<'1:1' | '4:5' | '9:16' | '16:9'>('4:5')
  const [qualityPreset, setQualityPreset] = useState<'draft' | 'standard' | 'high'>('standard')
  const [numOutputs, setNumOutputs] = useState(1)
  const [seed, setSeed] = useState('')
  const [refPath, setRefPath] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const selectedModel = imageModels.find((m) => m.id === engine) || imageModels[0]
  const estCredits = (selectedModel?.base_credits ?? 2) * numOutputs * (qualityPreset === 'high' ? 2 : 1)

  const createMutation = useMutation({
    mutationFn: () =>
      api.createJob({
        job_type: 'image',
        engine,
        idempotency_key: newIdempotencyKey(),
        params: {
          prompt,
          negative_prompt: negativePrompt,
          aspect_ratio: aspectRatio,
          quality_preset: qualityPreset,
          num_outputs: numOutputs,
          seed: seed ? Number(seed) : null,
          reference_image_path: refPath,
        },
      }),
    onSuccess: async (job) => {
      await refreshUser()
      navigate(`/jobs/${job.id}`)
    },
    onError: (err) => setError(err instanceof Error ? err.message : 'Failed to submit job'),
  })

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Image Studio</h1>
        <p className="text-sm text-slate-400 mt-1">
          Generate AI influencer portraits using FLUX.1-schnell or SDXL 1.0 on Cloud Run L4.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">{error}</div>
      )}

      <div className="p-6 rounded-2xl bg-studio-900 border border-slate-800 space-y-5">
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Prompt</label>
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Editorial portrait of a fashion creator in Tokyo at golden hour, 85mm f/1.4, natural skin texture..."
            className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Negative Prompt</label>
          <input
            type="text"
            value={negativePrompt}
            onChange={(e) => setNegativePrompt(e.target.value)}
            className="w-full px-3.5 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Model</label>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as EngineId)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              {imageModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.base_credits} cr)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Aspect Ratio</label>
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value as typeof aspectRatio)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="4:5">4:5 (Instagram Portrait)</option>
              <option value="1:1">1:1 (Square)</option>
              <option value="9:16">9:16 (Vertical Story)</option>
              <option value="16:9">16:9 (Landscape)</option>
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

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Outputs (1-4)</label>
            <input
              type="number"
              min={1}
              max={4}
              value={numOutputs}
              onChange={(e) => setNumOutputs(Math.max(1, Math.min(4, Number(e.target.value))))}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Seed (optional)</label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="Random"
              className="w-full px-3.5 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Optional Reference Image</label>
            <label className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-studio-950 border border-dashed border-slate-700 hover:border-indigo-500 cursor-pointer text-xs text-slate-300">
              <Upload className="w-4 h-4 text-indigo-400" />
              <span>{uploading ? 'Uploading...' : refPath ? `Uploaded: ${refPath.split('/').pop()}` : 'Upload reference image'}</span>
              <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
            </label>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Estimated cost: <span className="text-indigo-300 font-semibold">{estCredits} credits</span> · Estimated time: ~{12 * numOutputs}s
          </div>
          <button
            type="button"
            disabled={!prompt.trim() || createMutation.isPending || uploading}
            onClick={() => createMutation.mutate()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-medium text-sm transition"
          >
            <Sparkles className="w-4 h-4" />
            {createMutation.isPending ? 'Submitting...' : 'Generate Image'}
          </button>
        </div>
      </div>
    </div>
  )
}
