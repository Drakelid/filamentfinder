import type React from 'react'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertCircle,
  Database,
  Globe,
  Package,
  Server,
  TrendingUp,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDistanceToNow } from 'date-fns'
import { api, HealthData, StatsData } from '../api'
import {
  AnimatedCounter,
  MiniSparkline,
  SectionHeader,
  Surface,
  formatCompactNumber,
} from '../components/analytics/AnalyticsPrimitives'

const SOURCE_BAR_COLORS = ['#8b5cf6', '#a855f7', '#c084fc', '#f59e0b', '#fb7185', '#38bdf8']

function StatTile({
  title,
  value,
  subtitle,
  icon: Icon,
  accent,
}: {
  title: string
  value: number
  subtitle: string
  icon: React.ComponentType<{ className?: string }>
  accent: string
}) {
  return (
    <Surface className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-slate-50">
            <AnimatedCounter value={value} formatter={formatCompactNumber} />
          </p>
          <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
        </div>
        <div className={`rounded-2xl border px-3 py-3 ${accent}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Surface>
  )
}

function SystemStatusPanel({ data }: { data: HealthData }) {
  const workerActive = data.worker.status === 'active'
  const lastScan = data.latest_scan_at
    ? formatDistanceToNow(new Date(data.latest_scan_at), { addSuffix: true })
    : 'Never'
  const migrationsPending = data.migrations.pending

  return (
    <details open className="group">
      <summary className="list-none cursor-pointer">
        <Surface className="p-4 transition-colors hover:border-slate-700">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-slate-500">System status</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-100">Admin snapshot</h2>
              <p className="mt-1 text-sm text-slate-400">Worker, scan, and migration health in one place.</p>
            </div>
            <div className={`rounded-full px-3 py-1 text-xs font-semibold ${workerActive ? 'bg-emerald-500/15 text-emerald-200 ring-1 ring-inset ring-emerald-400/20' : 'bg-amber-500/15 text-amber-200 ring-1 ring-inset ring-amber-400/20'}`}>
              {workerActive ? 'Worker active' : 'Worker idle'}
            </div>
          </div>
        </Surface>
      </summary>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Surface className="p-4">
          <div className="flex items-center gap-3">
            <div className={`rounded-xl p-3 ${workerActive ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-300'}`}>
              <Server className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Worker</p>
              <p className="text-base font-medium text-slate-100">
                {workerActive ? `${data.worker.active_crawls} crawl(s) running` : 'Standing by'}
              </p>
            </div>
          </div>
        </Surface>

        <Surface className="p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/10 p-3 text-sky-300">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Last scan</p>
              <p className="text-base font-medium text-slate-100">{lastScan}</p>
            </div>
          </div>
        </Surface>

        <Surface className="p-4">
          <div className="flex items-center gap-3">
            <div className={`rounded-xl p-3 ${migrationsPending > 0 ? 'bg-amber-500/10 text-amber-300' : 'bg-slate-800 text-slate-300'}`}>
              <Database className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Migrations</p>
              <p className="text-base font-medium text-slate-100">
                {migrationsPending > 0 ? `${migrationsPending} pending` : 'Up to date'}
              </p>
              {migrationsPending > 0 && (
                <p className="text-xs text-amber-200/80">
                  Current {data.migrations.current_revision ?? 'unknown'} {'->'} Head {data.migrations.head_revision ?? 'unknown'}
                </p>
              )}
            </div>
          </div>
        </Surface>
      </div>
    </details>
  )
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
}

function SourceChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { name: string; products: number } }>
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-950/95 px-3 py-2 text-sm text-slate-200 shadow-2xl">
      <p className="font-medium">{point.name}</p>
      <p className="text-slate-400">{point.products.toLocaleString()} products tracked</p>
    </div>
  )
}

function TrendTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { label: string; tracked: number } }>
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-950/95 px-3 py-2 text-sm text-slate-200 shadow-2xl">
      <p className="font-medium">{point.label}</p>
      <p className="text-slate-400">{point.tracked.toLocaleString()} tracked products</p>
    </div>
  )
}

function buildTrackedTrend(runs: StatsData['recent_runs']) {
  const sorted = [...runs].sort((a, b) => new Date(a.started_at || 0).getTime() - new Date(b.started_at || 0).getTime())
  let tracked = 0
  return sorted.map((run) => {
    const increment = Math.max(run.products_found || 0, run.products_updated || 0)
    tracked += increment
    return {
      label: run.started_at ? new Date(run.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Unknown',
      tracked,
      status: run.status,
    }
  })
}

function RunRow({ run }: { run: StatsData['recent_runs'][number] }) {
  const severity =
    run.errors_count > 0 ? 'text-rose-200 bg-rose-500/10 ring-1 ring-inset ring-rose-400/20' :
    (run.duration_seconds ?? 0) < 10 ? 'text-emerald-200 bg-emerald-500/10 ring-1 ring-inset ring-emerald-400/20' :
    (run.duration_seconds ?? 0) < 60 ? 'text-amber-200 bg-amber-500/10 ring-1 ring-inset ring-amber-400/20' :
    'text-slate-200 bg-slate-800'

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">{run.source_name}</p>
          <p className="text-lg font-semibold text-slate-100 capitalize">{run.status}</p>
        </div>
        <div className={`rounded-full px-3 py-1 text-xs font-semibold ${severity}`}>
          {formatDuration(run.duration_seconds)}
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Pages</p>
          <p className="mt-1 text-slate-100">{run.pages_visited}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Products</p>
          <p className="mt-1 text-slate-100">{run.products_found} / {run.products_updated} upd</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Changes</p>
          <p className="mt-1 text-amber-200">{run.price_changes_detected}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Errors</p>
          <p className={`mt-1 ${run.errors_count > 0 ? 'text-rose-200' : 'text-slate-400'}`}>{run.errors_count}</p>
        </div>
      </div>
      {run.errors_count > 0 && run.error_messages && (
        <div className="mt-3 space-y-1 rounded-xl border border-rose-500/10 bg-rose-500/5 p-3 text-xs text-rose-200">
          {run.error_messages.slice(0, 3).map((message, index) => (
            <p key={index} className="truncate">{message}</p>
          ))}
        </div>
      )}
    </div>
  )
}

export default function StatsPage() {
  const { data, isLoading, error, dataUpdatedAt } = useQuery<StatsData>({
    queryKey: ['stats'],
    queryFn: api.stats.get,
    refetchInterval: (query) =>
      ((query.state.data as StatsData | undefined)?.overview?.running_crawls ?? 0) > 0
        ? 5000
        : 60_000,
  })

  const { data: healthData } = useQuery<HealthData>({
    queryKey: ['stats-health'],
    queryFn: api.stats.health,
    refetchInterval: (query) =>
      (query.state.data as HealthData | undefined)?.worker?.status === 'active'
        ? 5000
        : 60_000,
  })

  const sourceChartData = useMemo(
    () =>
      (data?.sources || [])
        .slice()
        .sort((a, b) => b.product_count - a.product_count)
        .slice(0, 8)
          .map((source) => ({
          name: source.name.length > 16 ? `${source.name.slice(0, 16)}...` : source.name,
          products: source.product_count,
        })),
    [data],
  )

  const trendData = useMemo(() => buildTrackedTrend(data?.recent_runs || []), [data])

  const sourceState = useMemo(() => {
    const active = (data?.sources || []).filter((source) => source.status === 'completed' || source.status === 'running').length
    const warning = (data?.sources || []).filter((source) => source.status === 'pending' || source.status === 'scanning').length
    const failed = (data?.sources || []).filter((source) => source.status === 'failed').length
    return { active, warning, failed }
  }, [data])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-24 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-32 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
          ))}
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="h-80 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
          <div className="h-80 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <Surface className="p-6">
        <div className="text-rose-200">Failed to load statistics: {(error as Error).message}</div>
      </Surface>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-violet-500/10 bg-gradient-to-br from-slate-900 via-slate-900 to-violet-950/40 p-6 shadow-lg shadow-black/20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Analytics</p>
            <h1 className="mt-1 text-3xl font-semibold text-slate-50">Crawler Statistics</h1>
            <p className="mt-2 text-sm text-slate-400">A cleaner view of system health, product volume, and source activity.</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Last refreshed</p>
            <p className="mt-1 text-sm font-medium text-slate-100">
              {formatDistanceToNow(new Date(dataUpdatedAt || Date.now()), { addSuffix: true })}
            </p>
          </div>
        </div>
      </div>

      {healthData && <SystemStatusPanel data={healthData} />}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatTile
          title="Total products"
          value={data.overview.total_products}
          subtitle={`${data.overview.active_products.toLocaleString()} active`}
          icon={Package}
          accent="bg-violet-500/10 text-violet-200 border-violet-500/20"
        />
        <StatTile
          title="Sources"
          value={data.overview.total_sources}
          subtitle={`${sourceState.active} healthy, ${sourceState.warning} warming up, ${sourceState.failed} failed`}
          icon={Globe}
          accent="bg-sky-500/10 text-sky-200 border-sky-500/20"
        />
        <StatTile
          title="Observations"
          value={data.activity.observations_24h}
          subtitle={`${data.activity.observations_7d.toLocaleString()} in 7 days`}
          icon={Activity}
          accent="bg-emerald-500/10 text-emerald-200 border-emerald-500/20"
        />
        <StatTile
          title="Price changes"
          value={data.activity.changes_24h}
          subtitle={`${data.activity.changes_7d} in 7 days`}
          icon={TrendingUp}
          accent="bg-amber-500/10 text-amber-200 border-amber-500/20"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Surface className="p-5">
          <SectionHeader
            eyebrow="Data overview"
            title="Products per source"
            description="Current product counts by retailer."
          />
          <div className="mt-6 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceChartData} margin={{ top: 10, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
                <Tooltip content={<SourceChartTooltip />} />
                <Bar dataKey="products" radius={[10, 10, 0, 0]}>
                  {sourceChartData.map((_, index) => (
                    <Cell key={index} fill={SOURCE_BAR_COLORS[index % SOURCE_BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Surface>

        <Surface className="p-5">
          <SectionHeader
            eyebrow="Data overview"
            title="Tracked products over recent scans"
            description="A cumulative trend derived from recent run output."
          />
          <div className="mt-6 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 10, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} tickFormatter={(value) => formatCompactNumber(value)} />
                <Tooltip content={<TrendTooltip />} />
                <Line
                  type="monotone"
                  dataKey="tracked"
                  stroke="#f59e0b"
                  strokeWidth={3}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Surface>
      </div>

      <Surface className="overflow-hidden">
        <div className="border-b border-slate-800 px-5 py-4">
          <SectionHeader
            eyebrow="Source health"
            title="Retailer snapshot"
            description="Status and recent run characteristics for each source."
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-950/60">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Source</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Health</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Products</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Last run</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Trend</th>
                <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-[0.3em] text-slate-500">Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data.sources.map((source) => {
                const health =
                  source.status === 'failed'
                    ? 'failed'
                    : source.latest_run?.errors_count
                      ? 'warning'
                      : 'healthy'
                const trendValues = [
                  source.latest_run?.pages_visited || 0,
                  source.latest_run?.products_found || 0,
                  Math.max((source.latest_run?.products_found || 0) - (source.latest_run?.errors_count || 0), 0),
                ]

                return (
                  <tr key={source.id} className="transition-colors hover:bg-slate-900/60">
                    <td className="px-5 py-4">
                      <div>
                        <div className="font-medium text-slate-100">{source.name}</div>
                        <div className="text-sm text-slate-500">{source.domain}</div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium ${
                        health === 'failed'
                          ? 'bg-rose-500/15 text-rose-200'
                          : health === 'warning'
                            ? 'bg-amber-500/15 text-amber-200'
                            : 'bg-emerald-500/15 text-emerald-200'
                      }`}>
                        <span className={`h-2 w-2 rounded-full ${
                          health === 'failed' ? 'bg-rose-400' : health === 'warning' ? 'bg-amber-400' : 'bg-emerald-400'
                        }`} />
                        {source.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-slate-200">{source.product_count.toLocaleString()}</td>
                    <td className="px-5 py-4 text-sm text-slate-400">
                      {source.last_scan_at ? formatDistanceToNow(new Date(source.last_scan_at), { addSuffix: true }) : 'Never'}
                    </td>
                    <td className="px-5 py-4">
                      <div className="h-10 w-24">
                        <MiniSparkline
                          values={trendValues}
                          stroke={health === 'failed' ? '#fb7185' : health === 'warning' ? '#f59e0b' : '#34d399'}
                        />
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      {source.latest_run?.errors_count ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2.5 py-1 text-xs font-medium text-rose-200">
                          <AlertCircle className="h-3 w-3" />
                          {source.latest_run.errors_count}
                        </span>
                      ) : (
                        <span className="text-sm text-slate-500">0</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Surface>

      <Surface className="p-5">
        <SectionHeader eyebrow="Recent activity" title="Run timeline" description="The most recent crawler runs sorted by recency." />
        <div className="mt-5 space-y-4">
          {[...data.recent_runs]
            .sort((a, b) => new Date(b.started_at || 0).getTime() - new Date(a.started_at || 0).getTime())
            .slice(0, 8)
            .map((run) => (
              <RunRow key={run.id} run={run} />
            ))}
        </div>
      </Surface>
    </div>
  )
}
