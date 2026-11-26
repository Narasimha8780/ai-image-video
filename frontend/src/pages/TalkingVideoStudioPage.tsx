import { useMutation } from '@tanstack/react-query'
import { Mic, Upload } from 'lucide-react'
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, newIdempotencyKey } from '../api/client'
import { useAuth } from '../context/AuthContext'

export function TalkingVideoStudioPage() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()

  const [portraitPath, setPortraitPath] = useState<string>('')
  const [audioPath, setAudioPath] = useState<string | null>(null)
  const [scriptText, setScriptText] = useState('')
  const [ttsVoice, setTtsVoice] = useState('en-US-Studio-O')
  const [language, setLanguage] = useState('en-US')
  const [duration, setDuration] = useState(10)
  const [orientation, setOrientation] = useState<'vertical' | 'landscape'>('vertical')
  const [rightsConfirmed, setRightsConfirmed] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const estCredits = 8 * Math.max(1, Math.ceil(duration / 10))
  const wordCount = scriptText.trim() ? scriptText.trim().split(/\s+/).length : 0

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, purpose: 'portrait' | 'audio') => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const path = await api.uploadFile(file, purpose)
      if (purpose === 'portrait') setPortraitPath(path)
      else setAudioPath(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.createJob({
        job_type: 'talking_video',
        engine: 'liveportrait_musetalk',
        idempotency_key: newIdempotencyKey(),
        params: {
          portrait_path: portraitPath,
          script_text: scriptText || null,
          audio_path: audioPath,
          tts_voice: ttsVoice,
          language,
          duration_seconds: duration,
          orientation,
          rights_confirmed: rightsConfirmed,
        },
      }),
    onSuccess: async (job) => {
      await refreshUser()
      navigate(`/jobs/${job.id}`)
    },
    onError: (err) => setError(err instanceof Error ? err.message : 'Submission failed'),
  })

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Talking Video Studio</h1>
        <p className="text-sm text-slate-400 mt-1">
          Audio-driven portrait animation (LivePortrait + MuseTalk) encoded to 1080p MP4 (25 FPS).
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">{error}</div>
      )}

      <div className="p-6 rounded-2xl bg-studio-900 border border-slate-800 space-y-5">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">1. Portrait Image (Required)</label>
            <label className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-studio-950 border border-dashed border-slate-700 hover:border-emerald-500 cursor-pointer text-xs text-slate-300">
              <Upload className="w-4 h-4 text-emerald-400" />
              <span>{portraitPath ? `Uploaded: ${portraitPath.split('/').pop()}` : 'Upload portrait PNG/JPG'}</span>
              <input type="file" accept="image/*" onChange={(e) => handleUpload(e, 'portrait')} className="hidden" />
            </label>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">2. Custom Audio (Optional if using Script)</label>
            <label className="flex items-center gap-2 px-3.5 py-2.5 rounded-lg bg-studio-950 border border-dashed border-slate-700 hover:border-emerald-500 cursor-pointer text-xs text-slate-300">
              <Upload className="w-4 h-4 text-emerald-400" />
              <span>{audioPath ? `Uploaded: ${audioPath.split('/').pop()}` : 'Upload WAV/MP3 audio'}</span>
              <input type="file" accept="audio/*" onChange={(e) => handleUpload(e, 'audio')} className="hidden" />
            </label>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-slate-300">Script (TTS) — ~60–75 words for 30s</label>
            <span className="text-[11px] text-slate-400">{wordCount} words</span>
          </div>
          <textarea
            rows={4}
            value={scriptText}
            onChange={(e) => setScriptText(e.target.value)}
            placeholder="Hey everyone! Welcome back to the studio. Today we're testing our new 1080p AI talking-head pipeline..."
            className="w-full px-3.5 py-2.5 rounded-lg bg-studio-950 border border-slate-700 text-sm focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">TTS Voice</label>
            <select
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="en-US-Studio-O">Studio Female (en-US-O)</option>
              <option value="en-US-Studio-Q">Studio Male (en-US-Q)</option>
              <option value="en-GB-Neural2-A">British Female (en-GB-A)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="en-US">English (US)</option>
              <option value="en-GB">English (UK)</option>
              <option value="es-ES">Spanish</option>
              <option value="fr-FR">French</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Target Duration ({duration}s)</label>
            <input
              type="range"
              min={5}
              max={30}
              step={5}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full mt-2 accent-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Output Orientation</label>
            <select
              value={orientation}
              onChange={(e) => setOrientation(e.target.value as typeof orientation)}
              className="w-full px-3 py-2 rounded-lg bg-studio-950 border border-slate-700 text-sm"
            >
              <option value="vertical">Vertical 1080×1920 (Reels)</option>
              <option value="landscape">Landscape 1920×1080</option>
            </select>
          </div>
        </div>

        <label className="flex items-start gap-2.5 text-xs text-slate-300 pt-2">
          <input
            type="checkbox"
            checked={rightsConfirmed}
            onChange={(e) => setRightsConfirmed(e.target.checked)}
            className="mt-0.5 rounded accent-emerald-500"
          />
          <span>
            I confirm I have rights/consent to use the uploaded portrait likeness and voice/audio, and understand generated outputs are synthetic media.
          </span>
        </label>

        <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Estimated cost: <span className="text-emerald-300 font-semibold">{estCredits} credits</span> · Queue time varies by L4 load
          </div>
          <button
            type="button"
            disabled={!portraitPath || (!scriptText.trim() && !audioPath) || !rightsConfirmed || uploading || createMutation.isPending}
            onClick={() => createMutation.mutate()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 font-medium text-sm transition"
          >
            <Mic className="w-4 h-4" />
            {createMutation.isPending ? 'Submitting...' : 'Generate Talking Video'}
          </button>
        </div>
      </div>
    </div>
  )
}
