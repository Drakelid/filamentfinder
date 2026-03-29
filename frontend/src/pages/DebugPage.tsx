import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  Bug,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  Loader2,
  ServerCrash,
  ShieldAlert,
  Skull,
  XCircle,
} from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { api, CrawlRun, Source } from '../api'
import { SectionCard, cx } from '../components/admin/AdminUI'

// ─── helpers ────────────────────────────────────────────────────────────────

function AlertBadge({ count, label, tone }: { count: number; label: string; tone: 'rose' | 'amber' | 'emerald' | 'slate' }) {
  const styles = {
    rose: 'border-rose-500/30 bg-rose-950/40 text-rose-200',
    amber: 'border-amber-500/30 bg-amber-950/40 text-amber-200',
    emerald: 'border-emerald-500/30 bg-emerald-950/40 text-emerald-200',
    slate: 'border-slate-700 bg-slate-900/60 text-slate-300',
  }
  return (
    <div className={cx('flex flex-col gap-1 rounded-2xl border p-4', styles[tone])}>
      <p className="text-[11px] uppercase tracking-[0.28em] opacity-70">{label}</p>
      <p className="text-3xl font-semibold">{count}</p>
    </div>
  )
}

function SeverityDot({ tone }: { tone: 'rose' | 'amber' | 'slate' }) {
  const colors = { rose: 'bg-rose-400', amber: 'bg-amber-400', slate: 'bg-slate-500' }
  return <span className={cx('mt-1 h-2 w-2 shrink-0 rounded-full', colors[tone])} />
}

// ─── source issues panel ─────────────────────────────────────────────────────

function SourceIssuesPanel({ sources }: { sources: Source[] }) {
  const problematic = sources.filter(
    (s) => (s.failure_streak && s.failure_streak > 0) || s.status === 'failed' || s.robots_txt_allowed === false,
  )

  if (!problematic.length) {
    return (
      <SectionCard eyebrow="Sources" title="Source Issues">
        <div className="flex items-center gap-3 text-sm text-emerald-300">
          <CheckCircle className="h-4 w-4 shrink-0" />
          No source issues detected.
        </div>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      eyebrow="Sources"
      title="Source Issues"
      description={`${problematic.length} source${problematic.length !== 1 ? 's' : ''} with warnings or failures`}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-[0.28em] text-slate-500">
            <tr>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Failure Streak</th>
              <th className="px-4 py-3">Robots.txt</th>
              <th className="px-4 py-3">Last Scan</th>
              <th className="px-4 py-3">Status Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {problematic.map((s) => (
              <tr key={s.id} className="hover:bg-slate-900/70">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-100">{s.name || s.domain}</p>
                  <p className="text-xs text-slate-500">{s.domain}</p>
                </td>
                <td className="px-4 py-3">
                  <span className={cx(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1',
                    s.status === 'failed'
                      ? 'bg-rose-500/15 text-rose-200 ring-rose-500/20'
                      : s.status === 'scanning'
                      ? 'bg-sky-500/15 text-sky-200 ring-sky-500/20'
                      : 'bg-slate-800 text-slate-300 ring-slate-700/70',
                  )}>
                    {s.status === 'failed' ? <XCircle className="h-3.5 w-3.5" /> : s.status === 'scanning' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clock className="h-3.5 w-3.5" />}
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {(s.failure_streak ?? 0) > 0 ? (
                    <span className="font-semibold text-rose-300">{s.failure_streak}</span>
                  ) : (
                    <span className="text-slate-500">0</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {s.robots_txt_allowed === false ? (
                    <span className="inline-flex items-center gap-1 text-xs text-amber-300">
                      <ShieldAlert className="h-3.5 w-3.5" /> Blocked
                    </span>
                  ) : (
                    <span className="text-slate-500 text-xs">OK</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {s.last_scan_at ? formatDistanceToNow(new Date(s.last_scan_at), { addSuffix: true }) : 'Never'}
                </td>
                <td className="px-4 py-3 max-w-xs">
                  {s.status_message ? (
                    <span className="text-xs text-rose-300 break-words">{s.status_message}</span>
                  ) : (
                    <span className="text-slate-600 text-xs">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}

// ─── run error list ──────────────────────────────────────────────────────────

function RunErrorRow({ run, sourceName }: { run: CrawlRun; sourceName?: string }) {
  const [expanded, setExpanded] = useState(false)
  const hasMessages = (run.error_messages?.length ?? 0) > 0

  return (
    <>
      <tr className="hover:bg-slate-900/70">
        <td className="px-4 py-3">
          {hasMessages ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="rounded-lg border border-slate-700 bg-slate-950/50 p-1 text-slate-300 transition-colors hover:bg-slate-800"
            >
              {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          ) : (
            <span className="px-2 text-slate-600">—</span>
          )}
        </td>
        <td className="px-4 py-3 font-medium text-slate-100">#{run.id}</td>
        <td className="px-4 py-3 text-slate-300">{sourceName ?? `Source #${run.source_id}`}</td>
        <td className="px-4 py-3">
          <span className={cx(
            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1',
            run.status === 'failed'
              ? 'bg-rose-500/15 text-rose-200 ring-rose-500/20'
              : 'bg-amber-500/15 text-amber-200 ring-amber-500/20',
          )}>
            {run.status === 'failed' ? <XCircle className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
            {run.status}
          </span>
        </td>
        <td className="px-4 py-3 text-slate-400 text-xs">
          <div>{format(new Date(run.started_at), 'MMM d, yyyy')}</div>
          <div className="text-slate-500">{format(new Date(run.started_at), 'HH:mm:ss')}</div>
        </td>
        <td className="px-4 py-3 text-right text-rose-300 font-medium">{run.errors_count}</td>
        <td className="px-4 py-3 text-right text-slate-400">{run.pages_visited}</td>
      </tr>
      {expanded && hasMessages && (
        <tr>
          <td colSpan={7} className="px-4 pb-4 pt-1">
            <ul className="space-y-1.5">
              {run.error_messages!.map((msg, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded-xl border border-rose-500/20 bg-rose-950/30 px-3 py-2 text-xs text-rose-200"
                >
                  <SeverityDot tone="rose" />
                  <span className="break-all">{msg}</span>
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  )
}

function RunsErrorPanel({
  runs,
  sourceNameById,
  title,
  eyebrow,
  description,
  emptyMessage,
}: {
  runs: CrawlRun[]
  sourceNameById: Record<number, string>
  title: string
  eyebrow: string
  description?: string
  emptyMessage: string
}) {
  if (!runs.length) {
    return (
      <SectionCard eyebrow={eyebrow} title={title}>
        <div className="flex items-center gap-3 text-sm text-emerald-300">
          <CheckCircle className="h-4 w-4 shrink-0" />
          {emptyMessage}
        </div>
      </SectionCard>
    )
  }

  return (
    <SectionCard eyebrow={eyebrow} title={title} description={description}>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-[0.28em] text-slate-500">
            <tr>
              <th className="px-4 py-3" />
              <th className="px-4 py-3">Run</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Started</th>
              <th className="px-4 py-3 text-right">Errors</th>
              <th className="px-4 py-3 text-right">Pages</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {runs.map((run) => (
              <RunErrorRow key={run.id} run={run} sourceName={sourceNameById[run.source_id]} />
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}

// ─── system alerts ───────────────────────────────────────────────────────────

function SystemAlertsPanel({
  healthData,
  queues,
}: {
  healthData: { worker: { status: string; active_crawls: number }; migrations: { pending: number; current_revision: string | null; head_revision: string | null } } | undefined
  queues: { pending: number | null; processing: number | null; dead_letter: number | null; deadLetterLatest: { failure_reason: string | null; source_id: number | null; failed_at: string | null } | null } | undefined
}) {
  const alerts: Array<{ tone: 'rose' | 'amber' | 'slate'; icon: typeof AlertTriangle; message: string; detail?: string }> = []

  if (healthData?.migrations.pending && healthData.migrations.pending > 0) {
    alerts.push({
      tone: 'rose',
      icon: Database,
      message: `${healthData.migrations.pending} pending database migration${healthData.migrations.pending !== 1 ? 's' : ''}`,
      detail: `Current: ${healthData.migrations.current_revision ?? 'unknown'} → Head: ${healthData.migrations.head_revision ?? 'unknown'}`,
    })
  }

  if (queues?.dead_letter && queues.dead_letter > 0) {
    alerts.push({
      tone: 'rose',
      icon: Skull,
      message: `${queues.dead_letter} item${queues.dead_letter !== 1 ? 's' : ''} in the dead-letter queue`,
      detail: queues.deadLetterLatest?.failure_reason
        ? `Last failure: ${queues.deadLetterLatest.failure_reason}${queues.deadLetterLatest.failed_at ? ` (${formatDistanceToNow(new Date(queues.deadLetterLatest.failed_at), { addSuffix: true })})` : ''}`
        : undefined,
    })
  }

  if (queues?.processing && queues.processing > 5) {
    alerts.push({
      tone: 'amber',
      icon: AlertTriangle,
      message: `${queues.processing} jobs stuck in processing queue`,
      detail: 'Jobs may be orphaned if the worker crashed mid-run.',
    })
  }

  if (!alerts.length) {
    return (
      <SectionCard eyebrow="System" title="System Alerts">
        <div className="flex items-center gap-3 text-sm text-emerald-300">
          <CheckCircle className="h-4 w-4 shrink-0" />
          No system-level alerts detected.
        </div>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      eyebrow="System"
      title="System Alerts"
      description={`${alerts.length} active alert${alerts.length !== 1 ? 's' : ''} require attention`}
    >
      <ul className="space-y-2">
        {alerts.map((alert, i) => {
          const Icon = alert.icon
          return (
            <li
              key={i}
              className={cx(
                'flex items-start gap-3 rounded-2xl border px-4 py-3',
                alert.tone === 'rose'
                  ? 'border-rose-500/20 bg-rose-950/30 text-rose-200'
                  : 'border-amber-500/20 bg-amber-950/30 text-amber-200',
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-0.5">
                <p className="text-sm font-medium">{alert.message}</p>
                {alert.detail && <p className="text-xs opacity-70">{alert.detail}</p>}
              </div>
            </li>
          )
        })}
      </ul>
    </SectionCard>
  )
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function DebugPage() {
  const runsQuery = useQuery({
    queryKey: ['debug', 'runs'],
    queryFn: () => api.runs.list({ limit: 200 }),
    refetchInterval: 15_000,
  })

  const sourcesQuery = useQuery({
    queryKey: ['debug', 'sources'],
    queryFn: () => api.sources.list(),
    refetchInterval: 30_000,
  })

  const healthQuery = useQuery({
    queryKey: ['debug', 'health'],
    queryFn: () => api.stats.health(),
    refetchInterval: 30_000,
  })

  const statsQuery = useQuery({
    queryKey: ['debug', 'stats'],
    queryFn: () => api.stats.get(),
    refetchInterval: 30_000,
  })

  const runs = runsQuery.data?.items ?? []
  const sources = sourcesQuery.data?.items ?? []

  const sourceNameById = Object.fromEntries(sources.map((s) => [s.id, s.name || s.domain]))

  const failedRuns = runs.filter((r) => r.status === 'failed')
  const runsWithErrors = runs.filter((r) => r.status !== 'failed' && r.errors_count > 0)

  const queueInfo = statsQuery.data?.queues
    ? {
        pending: statsQuery.data.queues.pending.length,
        processing: statsQuery.data.queues.processing.length,
        dead_letter: statsQuery.data.queues.dead_letter.length,
        deadLetterLatest: statsQuery.data.queues.dead_letter.latest,
      }
    : undefined

  const problematicSources = sources.filter(
    (s) => (s.failure_streak && s.failure_streak > 0) || s.status === 'failed' || s.robots_txt_allowed === false,
  )

  const totalIssues = failedRuns.length + runsWithErrors.length + problematicSources.length + (queueInfo?.dead_letter ?? 0)

  const isLoading = runsQuery.isLoading || sourcesQuery.isLoading || healthQuery.isLoading

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Developer Tools</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-100">Debug</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          Aggregated view of crawler errors, source failures, system alerts, and queue state.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-3 rounded-3xl border border-slate-800 bg-slate-900/60 py-10 text-slate-300">
          <Loader2 className="ml-6 h-5 w-5 animate-spin text-violet-400" />
          <span className="text-sm">Loading debug data…</span>
        </div>
      ) : (
        <>
          {/* summary badges */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <AlertBadge count={totalIssues} label="Total Issues" tone={totalIssues > 0 ? 'rose' : 'emerald'} />
            <AlertBadge count={failedRuns.length} label="Failed Runs" tone={failedRuns.length > 0 ? 'rose' : 'slate'} />
            <AlertBadge count={runsWithErrors.length} label="Runs with Errors" tone={runsWithErrors.length > 0 ? 'amber' : 'slate'} />
            <AlertBadge count={problematicSources.length} label="Source Issues" tone={problematicSources.length > 0 ? 'amber' : 'slate'} />
          </div>

          {totalIssues === 0 && (
            <div className="flex items-center gap-3 rounded-3xl border border-emerald-500/20 bg-emerald-950/30 px-5 py-4 text-emerald-300">
              <CheckCircle className="h-5 w-5 shrink-0" />
              <span className="text-sm font-medium">All systems healthy — no warnings or errors found.</span>
            </div>
          )}

          <SystemAlertsPanel healthData={healthQuery.data} queues={queueInfo} />

          <SourceIssuesPanel sources={sources} />

          <RunsErrorPanel
            runs={failedRuns}
            sourceNameById={sourceNameById}
            eyebrow="Crawler"
            title="Failed Runs"
            description={failedRuns.length ? `${failedRuns.length} run${failedRuns.length !== 1 ? 's' : ''} ended in failure — expand a row to see error messages` : undefined}
            emptyMessage="No failed runs."
          />

          <RunsErrorPanel
            runs={runsWithErrors}
            sourceNameById={sourceNameById}
            eyebrow="Crawler"
            title="Completed Runs with Errors"
            description={runsWithErrors.length ? `${runsWithErrors.length} completed run${runsWithErrors.length !== 1 ? 's' : ''} with non-zero error counts` : undefined}
            emptyMessage="No completed runs with errors."
          />

          {/* queue state */}
          {queueInfo && (
            <SectionCard eyebrow="Queue" title="Redis Queue State">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Pending</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-100">{queueInfo.pending ?? '—'}</p>
                  <p className="mt-1 text-xs text-slate-500">scan_queue</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Processing</p>
                  <p className={cx('mt-2 text-2xl font-semibold', (queueInfo.processing ?? 0) > 5 ? 'text-amber-300' : 'text-slate-100')}>
                    {queueInfo.processing ?? '—'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">scan_queue:processing</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                  <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Dead Letter</p>
                  <p className={cx('mt-2 text-2xl font-semibold', (queueInfo.dead_letter ?? 0) > 0 ? 'text-rose-300' : 'text-slate-100')}>
                    {queueInfo.dead_letter ?? '—'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">scan_queue:dead</p>
                  {queueInfo.deadLetterLatest?.failure_reason && (
                    <p className="mt-2 text-xs text-rose-300 break-words">{queueInfo.deadLetterLatest.failure_reason}</p>
                  )}
                </div>
              </div>
            </SectionCard>
          )}
        </>
      )}

      {(runsQuery.error || sourcesQuery.error || healthQuery.error) && (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-950/40 p-4 text-sm text-rose-200">
          <div className="flex items-center gap-2 font-medium">
            <ServerCrash className="h-4 w-4" />
            One or more data sources failed to load:
          </div>
          <ul className="mt-2 space-y-1 text-xs opacity-80">
            {runsQuery.error && <li>Runs: {(runsQuery.error as Error).message}</li>}
            {sourcesQuery.error && <li>Sources: {(sourcesQuery.error as Error).message}</li>}
            {healthQuery.error && <li>Health: {(healthQuery.error as Error).message}</li>}
          </ul>
        </div>
      )}
    </div>
  )
}
