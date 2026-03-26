import { Fragment, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Clock, Loader2, RotateCcw, XCircle } from 'lucide-react'
import { format } from 'date-fns'
import { api, CrawlRun } from '../api'
import { EmptyState, LoadingState, SectionCard, cx } from '../components/admin/AdminUI'

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: 'bg-sky-500/15 text-sky-200 ring-sky-500/20',
    completed: 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/20',
    failed: 'bg-rose-500/15 text-rose-200 ring-rose-500/20',
  }
  const icons: Record<string, ReactNode> = {
    running: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    completed: <CheckCircle className="h-3.5 w-3.5" />,
    failed: <XCircle className="h-3.5 w-3.5" />,
  }
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1', styles[status] || 'bg-slate-800 text-slate-300 ring-slate-700/70')}>
      {icons[status] || <Clock className="h-3.5 w-3.5" />}
      {status}
    </span>
  )
}

function formatDuration(start: string, end: string | null): { label: string; tone: 'emerald' | 'amber' | 'rose' | 'slate' } {
  if (!end) return { label: 'In progress...', tone: 'slate' }
  const seconds = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (seconds < 60) return { label: `${seconds}s`, tone: 'emerald' }
  if (seconds < 600) return { label: `${Math.floor(seconds / 60)}m`, tone: 'emerald' }
  if (seconds < 1800) return { label: `${Math.floor(seconds / 60)}m`, tone: 'amber' }
  return { label: `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`, tone: 'rose' }
}

function RunDetails({ run }: { run: CrawlRun }) {
  const stats = run.stats_json as Record<string, unknown> | null
  return (
    <div className="grid gap-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 md:grid-cols-3">
      <div>
        <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Crawler summary</p>
        <div className="mt-3 space-y-2 text-sm text-slate-300">
          <div className="flex justify-between gap-4"><span>Pages visited</span><span className="text-slate-100">{run.pages_visited}</span></div>
          <div className="flex justify-between gap-4"><span>Products found</span><span className="text-slate-100">{run.products_found}</span></div>
          <div className="flex justify-between gap-4"><span>Products updated</span><span className="text-slate-100">{run.products_updated}</span></div>
          <div className="flex justify-between gap-4"><span>Price changes</span><span className="text-slate-100">{run.price_changes_detected}</span></div>
          <div className="flex justify-between gap-4"><span>Errors</span><span className="text-slate-100">{run.errors_count}</span></div>
        </div>
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Source note</p>
        <p className="mt-3 text-sm text-slate-300">
          {run.status === 'failed'
            ? 'This scan failed. Use retry to enqueue another run for the same source.'
            : 'This is a run-level summary. The backend does not expose per-source breakdown rows here, so the expansion focuses on crawl telemetry and errors.'}
        </p>
        {run.error_messages?.length ? (
          <ul className="mt-3 space-y-2 text-sm text-rose-200">
            {run.error_messages.slice(0, 4).map((message, index) => (
              <li key={index} className="rounded-xl border border-rose-500/20 bg-rose-950/30 px-3 py-2">
                {message}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Stats payload</p>
        <pre className="mt-3 overflow-auto rounded-2xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
          {JSON.stringify(stats ?? {}, null, 2)}
        </pre>
      </div>
    </div>
  )
}

export default function RunsPage() {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.runs.list(),
    refetchInterval: 5000,
  })

  const retryMutation = useMutation({
    mutationFn: (sourceId: number) => api.sources.scan(sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['runs'] }),
  })

  const runs = data?.items || []
  const summary = useMemo(
    () => ({
      completed: runs.filter((run) => run.status === 'completed').length,
      failed: runs.filter((run) => run.status === 'failed').length,
      running: runs.filter((run) => run.status === 'running').length,
    }),
    [runs],
  )

  if (isLoading) return <LoadingState label="Loading scan history" />
  if (error) return <div className="rounded-3xl border border-rose-500/30 bg-rose-950/40 p-4 text-rose-200">Failed to load runs: {(error as Error).message}</div>
  if (!runs.length) {
    return (
      <EmptyState
        icon={Clock}
        title="No scan runs yet"
        description="Add a source and trigger a scan to start building scan history."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Operations</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-100">Scan History</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">Review crawler runs, inspect errors, and retry failed scans from the same source.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-xs uppercase tracking-[0.28em] text-slate-500">Completed</p><p className="mt-2 text-3xl font-semibold text-emerald-200">{summary.completed}</p></div>
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-xs uppercase tracking-[0.28em] text-slate-500">Running</p><p className="mt-2 text-3xl font-semibold text-sky-200">{summary.running}</p></div>
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-xs uppercase tracking-[0.28em] text-slate-500">Failed</p><p className="mt-2 text-3xl font-semibold text-rose-200">{summary.failed}</p></div>
      </div>

      <SectionCard eyebrow="Run log" title="Recent crawl runs" description="Click a row to expand the crawl payload and error details.">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-[0.28em] text-slate-500">
              <tr>
                <th className="px-4 py-3" />
                <th className="px-4 py-3">Run</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3 text-right">Pages</th>
                <th className="px-4 py-3 text-right">Products</th>
                <th className="px-4 py-3 text-right">Changes</th>
                <th className="px-4 py-3 text-right">Errors</th>
                <th className="px-4 py-3 text-right">Retry</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {runs.map((run) => {
                const expanded = expandedId === run.id
                const duration = formatDuration(run.started_at, run.finished_at)
                const retryable = run.status === 'failed'
                return (
                  <Fragment key={run.id}>
                    <tr key={run.id} className="hover:bg-slate-900/70">
                      <td className="px-4 py-4">
                        <button
                          type="button"
                          onClick={() => setExpandedId(expanded ? null : run.id)}
                          className="rounded-lg border border-slate-700 bg-slate-950/50 p-1 text-slate-300 transition-colors hover:bg-slate-800"
                        >
                          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                      </td>
                      <td className="px-4 py-4 font-medium text-slate-100">#{run.id}</td>
                      <td className="px-4 py-4"><StatusBadge status={run.status} /></td>
                      <td className="px-4 py-4 text-slate-300">
                        <div>{format(new Date(run.started_at), 'MMM d, yyyy')}</div>
                        <div className="text-xs text-slate-500">{format(new Date(run.started_at), 'HH:mm:ss')}</div>
                      </td>
                      <td className="px-4 py-4">
                        <span className={cx('inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium ring-1', duration.tone === 'emerald' ? 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/20' : duration.tone === 'amber' ? 'bg-amber-500/15 text-amber-200 ring-amber-500/20' : duration.tone === 'rose' ? 'bg-rose-500/15 text-rose-200 ring-rose-500/20' : 'bg-slate-800 text-slate-300 ring-slate-700/70')}>
                          {duration.label}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-right text-slate-300">{run.pages_visited}</td>
                      <td className="px-4 py-4 text-right text-slate-300">{run.products_found} new</td>
                      <td className="px-4 py-4 text-right text-slate-300">{run.price_changes_detected > 0 ? <span className="inline-flex items-center gap-1 text-amber-300"><AlertTriangle className="h-4 w-4" />{run.price_changes_detected}</span> : '0'}</td>
                      <td className="px-4 py-4 text-right text-slate-300">{run.errors_count > 0 ? <span className="text-rose-300">{run.errors_count}</span> : '0'}</td>
                      <td className="px-4 py-4 text-right">
                        {retryable ? (
                          <button
                            type="button"
                            onClick={() => retryMutation.mutate(run.source_id)}
                            disabled={retryMutation.isPending}
                            className="inline-flex items-center gap-1 rounded-full border border-violet-500/30 px-3 py-1.5 text-xs text-violet-100 transition-colors hover:bg-violet-500/10 disabled:opacity-50"
                          >
                            {retryMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                            Retry
                          </button>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${run.id}-details`}>
                        <td colSpan={10} className="px-4 pb-4">
                          <RunDetails run={run} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  )
}
