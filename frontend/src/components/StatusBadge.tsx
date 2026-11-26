import type { JobState } from '../types'

const STATE_STYLES: Record<JobState, string> = {
  queued: 'bg-slate-700/60 text-slate-300 border-slate-600/60',
  starting: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  running: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
  uploading: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  completed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  failed: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  cancelled: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
}

export function StatusBadge({ state }: { state: JobState }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border capitalize ${
        STATE_STYLES[state]
      }`}
    >
      {state}
    </span>
  )
}
