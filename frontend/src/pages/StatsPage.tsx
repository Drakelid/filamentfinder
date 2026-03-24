import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  Loader2, 
  Activity, 
  Package, 
  Globe, 
  TrendingUp, 
  Clock, 
  CheckCircle, 
  XCircle,
  AlertCircle,
  BarChart3,
  Server,
  ActivitySquare,
  Database
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { api, HealthData, StatsData } from '../api'

type RunSortKey = 'started_at' | 'duration_seconds' | 'pages_visited' | 'price_changes_detected' | 'errors_count'

function RunsTimeline({ runs }: { runs: StatsData['recent_runs'] }) {
  const [sortKey, setSortKey] = useState<RunSortKey>('started_at')
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc')

  const sortedRuns = useMemo(() => {
    const list = [...runs]
    return list.sort((a, b) => {
      const getValue = (run: typeof a) => {
        switch (sortKey) {
          case 'duration_seconds':
            return run.duration_seconds ?? 0
          case 'pages_visited':
            return run.pages_visited
          case 'price_changes_detected':
            return run.price_changes_detected
          case 'errors_count':
            return run.errors_count
          case 'started_at':
          default:
            return run.started_at ? new Date(run.started_at).getTime() : 0
        }
      }
      const aVal = getValue(a)
      const bVal = getValue(b)
      if (aVal === bVal) return 0
      const multiplier = direction === 'asc' ? 1 : -1
      return aVal > bVal ? multiplier : -multiplier
    })
  }, [runs, sortKey, direction])

  const toggleSort = (key: RunSortKey) => {
    if (key === sortKey) {
      setDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDirection('desc')
    }
  }

  const SortButton = ({ label, keyName }: { label: string; keyName: RunSortKey }) => (
    <button
      onClick={() => toggleSort(keyName)}
      className={`flex items-center gap-1 text-xs font-medium px-3 py-1 rounded-full border transition ${sortKey === keyName ? 'border-blue-500 text-blue-300' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}
    >
      {label}
      {sortKey === keyName && (direction === 'asc' ? '↑' : '↓')}
    </button>
  )

  return (
    <div className="bg-gray-900 rounded-3xl border border-gray-800 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Run Timeline</h2>
          <p className="text-sm text-gray-400">Review the last {runs.length} crawler runs</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <SortButton label="Time" keyName="started_at" />
          <SortButton label="Duration" keyName="duration_seconds" />
          <SortButton label="Pages" keyName="pages_visited" />
          <SortButton label="Changes" keyName="price_changes_detected" />
          <SortButton label="Errors" keyName="errors_count" />
        </div>
      </div>
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-700/60" aria-hidden />
        <div className="space-y-6">
          {sortedRuns.map((run) => (
            <div key={run.id} className="relative pl-10">
              <div className={`absolute left-3 top-2 h-3 w-3 rounded-full border-2 ${run.status === 'completed' ? 'bg-emerald-400 border-emerald-200' : run.status === 'failed' ? 'bg-red-400 border-red-200' : 'bg-blue-400 border-blue-200'}`} />
              <div className="bg-gray-800/70 border border-gray-700 rounded-2xl p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm text-gray-400">{run.source_name}</p>
                    <p className="text-lg font-semibold text-gray-100 capitalize">{run.status}</p>
                  </div>
                  <div className="text-sm text-gray-400 text-right">
                    <p>{run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'Unknown start'}</p>
                    <p>Duration {formatDuration(run.duration_seconds)}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-sm">
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-wide">Pages</p>
                    <p className="text-gray-100 font-medium">{run.pages_visited}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-wide">Products</p>
                    <p className="text-gray-100 font-medium">{run.products_found} / {run.products_updated} upd</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-wide">Price changes</p>
                    <p className="text-orange-300 font-medium">{run.price_changes_detected}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-wide">Errors</p>
                    <p className={run.errors_count > 0 ? 'text-red-300 font-medium' : 'text-gray-400'}>{run.errors_count}</p>
                  </div>
                </div>
                {run.errors_count > 0 && run.errors_count <= 3 && run.error_messages && (
                  <ul className="mt-3 text-xs text-red-300 list-disc list-inside space-y-1">
                    {run.error_messages.slice(0, 3).map((msg, idx) => (
                      <li key={idx} className="truncate">{msg}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  color = 'blue' 
}: { 
  title: string
  value: number | string
  subtitle?: string
  icon: React.ElementType
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red'
}) {
  const colors = {
    blue: 'bg-blue-900/50 text-blue-400 border-blue-800',
    green: 'bg-green-900/50 text-green-400 border-green-800',
    purple: 'bg-purple-900/50 text-purple-400 border-purple-800',
    orange: 'bg-orange-900/50 text-orange-400 border-orange-800',
    red: 'bg-red-900/50 text-red-400 border-red-800',
  }
  
  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <Icon className="w-8 h-8 opacity-50" />
      </div>
    </div>
  )
}

function SystemHealthWidget({ data }: { data: HealthData }) {
  const workerActive = data.worker.status === 'active'
  const lastScan = data.latest_scan_at
    ? formatDistanceToNow(new Date(data.latest_scan_at), { addSuffix: true })
    : 'Never'
  const migrationsPending = data.migrations.pending

  return (
    <div className="bg-gradient-to-r from-slate-900 to-slate-950 border border-slate-800 rounded-3xl p-4 flex flex-col gap-4 shadow-xl shadow-slate-950/30">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">System health</p>
          <h2 className="text-lg font-semibold text-white">Worker & database status</h2>
        </div>
        <div className={`px-3 py-1 rounded-full text-xs font-semibold ${workerActive ? 'bg-emerald-900/40 text-emerald-200 border border-emerald-700/60' : 'bg-amber-900/40 text-amber-200 border border-amber-700/60'}`}>
          {workerActive ? 'Worker active' : 'Worker idle'}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-slate-300">
        <div className="flex items-center gap-3 p-3 rounded-2xl bg-slate-900/60 border border-slate-800">
          <span className={`p-2 rounded-xl ${workerActive ? 'bg-emerald-900/50 text-emerald-300' : 'bg-amber-900/50 text-amber-300'}`}>
            <Server className="w-4 h-4" />
          </span>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Worker</p>
            <p className="text-base text-white">{workerActive ? `${data.worker.active_crawls} crawl(s) running` : 'Standing by'}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 p-3 rounded-2xl bg-slate-900/60 border border-slate-800">
          <span className="p-2 rounded-xl bg-sky-900/40 text-sky-300">
            <ActivitySquare className="w-4 h-4" />
          </span>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Last scan</p>
            <p className="text-base text-white">{lastScan}</p>
          </div>
        </div>
        <div className={`flex items-center gap-3 p-3 rounded-2xl border ${migrationsPending > 0 ? 'bg-amber-950/40 border-amber-800 text-amber-200' : 'bg-slate-900/60 border-slate-800 text-slate-200'}`}>
          <span className={`p-2 rounded-xl ${migrationsPending > 0 ? 'bg-amber-900/60 text-amber-200' : 'bg-slate-800 text-slate-200'}`}>
            <Database className="w-4 h-4" />
          </span>
          <div>
            <p className={`text-xs uppercase tracking-[0.3em] ${migrationsPending > 0 ? 'text-amber-300' : 'text-slate-500'}`}>Migrations</p>
            <p className="text-base text-white">{migrationsPending > 0 ? `${migrationsPending} pending` : 'Up to date'}</p>
            {migrationsPending > 0 && (
              <p className="text-xs text-amber-200/80">Current {data.migrations.current_revision ?? 'unknown'} → Head {data.migrations.head_revision ?? 'unknown'}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-gray-700 text-gray-300',
    scanning: 'bg-blue-900 text-blue-300',
    running: 'bg-blue-900 text-blue-300',
    completed: 'bg-green-900 text-green-300',
    failed: 'bg-red-900 text-red-300',
  }
  
  const icons: Record<string, React.ReactNode> = {
    pending: <Clock className="w-3 h-3" />,
    scanning: <Loader2 className="w-3 h-3 animate-spin" />,
    running: <Loader2 className="w-3 h-3 animate-spin" />,
    completed: <CheckCircle className="w-3 h-3" />,
    failed: <XCircle className="w-3 h-3" />,
  }
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
      {icons[status]}
      {status}
    </span>
  )
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
}

export default function StatsPage() {
  const { data, isLoading, error } = useQuery<StatsData>({
    queryKey: ['stats'],
    queryFn: api.stats.get,
    refetchInterval: (query) =>
      (query.state.data as StatsData | undefined)?.overview?.running_crawls ?? 0 > 0
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
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="bg-red-900/50 text-red-300 p-4 rounded-lg">
        Failed to load statistics: {(error as Error).message}
      </div>
    )
  }
  
  if (!data) return null
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Crawler Statistics</h1>
        <p className="text-gray-400 mt-1">Monitor crawler progress, status, and activity</p>
      </div>

      {healthData && (
        <SystemHealthWidget data={healthData} />)
      }
      
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Products"
          value={data.overview.total_products.toLocaleString()}
          subtitle={`${data.overview.active_products.toLocaleString()} active`}
          icon={Package}
          color="blue"
        />
        <StatCard
          title="Sources"
          value={data.overview.total_sources}
          subtitle={`${data.overview.scanning_sources} scanning`}
          icon={Globe}
          color="green"
        />
        <StatCard
          title="Observations (24h)"
          value={data.activity.observations_24h.toLocaleString()}
          subtitle={`${data.activity.observations_7d.toLocaleString()} in 7 days`}
          icon={Activity}
          color="purple"
        />
        <StatCard
          title="Price Changes (24h)"
          value={data.activity.changes_24h}
          subtitle={`${data.activity.changes_7d} in 7 days`}
          icon={TrendingUp}
          color="orange"
        />
      </div>
      
      {/* Products by Category */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Products by Category
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(data.products_by_category).map(([category, count]: [string, number]) => (
            <div key={category} className="bg-gray-700/50 rounded-lg p-3">
              <p className="text-sm text-gray-400 capitalize">{category}</p>
              <p className="text-xl font-bold text-gray-100">{count.toLocaleString()}</p>
            </div>
          ))}
        </div>
      </div>
      
      {/* Source Status */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">Source Status</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Source</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Products</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Last Run</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Pages</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Found</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {data.sources.map((source) => (
                <tr key={source.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-medium text-gray-100">{source.name}</div>
                      <div className="text-sm text-gray-500">{source.domain}</div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={source.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {source.product_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-sm">
                    {source.last_scan_at
                      ? formatDistanceToNow(new Date(source.last_scan_at), { addSuffix: true })
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {source.latest_run?.pages_visited || '-'}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {source.latest_run?.products_found || '-'}
                  </td>
                  <td className="px-4 py-3">
                    {source.latest_run?.errors_count ? (
                      <span className="text-red-400 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        {source.latest_run.errors_count}
                      </span>
                    ) : (
                      <span className="text-gray-500">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      <RunsTimeline runs={data.recent_runs} />

      {/* Activity Summary */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Activity Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-3xl font-bold text-blue-400">{data.activity.runs_24h}</p>
            <p className="text-sm text-gray-400">Runs (24h)</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-green-400">{data.activity.runs_7d}</p>
            <p className="text-sm text-gray-400">Runs (7d)</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-purple-400">{data.activity.total_runs}</p>
            <p className="text-sm text-gray-400">Total Runs</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-orange-400">{data.overview.running_crawls}</p>
            <p className="text-sm text-gray-400">Running Now</p>
          </div>
        </div>
      </div>
    </div>
  )
}
