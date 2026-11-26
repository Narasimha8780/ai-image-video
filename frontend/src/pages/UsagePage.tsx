import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function UsagePage() {
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: api.getUsage })

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Usage & Credits</h1>
        <p className="text-sm text-slate-400 mt-1">Track your credit balance, daily generation quota, and transaction ledger.</p>
      </div>

      <div className="grid sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Available Credits</div>
          <div className="text-2xl font-bold text-indigo-300 mt-1">{usage?.credits ?? 0}</div>
        </div>
        <div className="p-5 rounded-2xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Daily Generations</div>
          <div className="text-2xl font-bold mt-1">
            {usage?.daily_used ?? 0} / {usage?.daily_quota ?? 0}
          </div>
        </div>
        <div className="p-5 rounded-2xl bg-studio-900 border border-slate-800">
          <div className="text-xs text-slate-400">Active Concurrent Jobs</div>
          <div className="text-2xl font-bold mt-1">
            {usage?.active_jobs ?? 0} / {usage?.max_active_jobs ?? 0}
          </div>
        </div>
      </div>

      <div className="rounded-2xl bg-studio-900 border border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 font-semibold text-sm">Credit Ledger</div>
        <div className="divide-y divide-slate-800/80">
          {(usage?.transactions ?? []).map((tx) => (
            <div key={tx.id} className="px-6 py-3.5 flex items-center justify-between text-xs">
              <div>
                <div className="font-medium text-slate-200">{tx.reason}</div>
                <div className="text-slate-500">
                  {new Date(tx.created_at).toLocaleString()} {tx.job_id ? `· ${tx.job_id}` : ''}
                </div>
              </div>
              <span className={`font-semibold ${tx.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {tx.delta >= 0 ? `+${tx.delta}` : tx.delta}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
