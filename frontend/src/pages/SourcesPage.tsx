import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  ExternalLink,
  Loader2,
  MoreVertical,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Ship,
  Sparkles,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { api, Source, getSourcesExportUrl, importSources } from '../api'
import { ActionMenu, EmptyState, LoadingState, MiniSparkline, MetricCard, SectionCard, StatusDot, cx } from '../components/admin/AdminUI'
import AddSourceModal from '../components/sources/AddSourceModal'

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-slate-800 text-slate-300 ring-slate-700/70',
    scanning: 'bg-sky-500/15 text-sky-200 ring-sky-500/20',
    completed: 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/20',
    failed: 'bg-rose-500/15 text-rose-200 ring-rose-500/20',
  }
  const icons: Record<string, ReactNode> = {
    pending: <Clock className="h-3.5 w-3.5" />,
    scanning: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    completed: <CheckCircle className="h-3.5 w-3.5" />,
    failed: <XCircle className="h-3.5 w-3.5" />,
  }
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1', styles[status] || styles.pending)}>
      {icons[status]}
      {status}
    </span>
  )
}

export default function SourcesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery<{ items: Source[]; total: number }>({
    queryKey: ['sources'],
    queryFn: api.sources.list,
    refetchInterval: 5000,
  })
  const { data: healthData } = useQuery<import('../api').HealthData>({
    queryKey: ['stats-health'],
    queryFn: api.stats.health,
    refetchInterval: 15000,
  })

  const sources = data?.items ?? []
  const alertingSources = useMemo(
    () => sources.filter((source) => source.status === 'failed' || (source.failure_streak ?? 0) > 0 || source.status_message?.toLowerCase().startsWith('stale')),
    [sources],
  )
  const alertingIds = useMemo(() => new Set(alertingSources.map((source) => source.id)), [alertingSources])
  const allSelected = sources.length > 0 && selectedIds.size === sources.length

  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev
      const next = new Set<number>()
      sources.forEach((source) => {
        if (prev.has(source.id)) next.add(source.id)
      })
      return next.size === prev.size ? prev : next
    })
  }, [sources])

  const scanMutation = useMutation({
    mutationFn: (id: number) => api.sources.scan(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      setToast('Scan started')
      setTimeout(() => setToast(null), 2500)
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.sources.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  })
  const importMutation = useMutation({
    mutationFn: (file: File) => importSources(file),
    onMutate: () => {
      setImportMessage(null)
      setImportError(null)
    },
    onSuccess: async (result) => {
      setImportMessage(`Imported ${result.imported}, skipped ${result.skipped}`)
      if (result.errors.length) setImportError(result.errors[0].reason)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
    },
    onError: (err: Error) => setImportError(err.message),
  })

  const runBulk = async (action: (id: number) => Promise<unknown>) => {
    const ids = Array.from(selectedIds)
    if (!ids.length) return
    setBulkLoading(true)
    try {
      for (const id of ids) await action(id)
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      setSelectedIds(new Set())
    } finally {
      setBulkLoading(false)
    }
  }

  if (isLoading) return <LoadingState label="Loading sources" />
  if (error) return <div className="rounded-3xl border border-rose-500/30 bg-rose-950/40 p-4 text-rose-200">Failed to load sources: {(error as Error).message}</div>

  return (
    <div className="space-y-6">
      {toast && <div className="fixed bottom-6 right-6 z-30 rounded-2xl border border-violet-500/30 bg-slate-900/95 px-4 py-3 text-sm text-slate-100 shadow-xl shadow-black/30">{toast}</div>}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Monitoring</p>
          <h1 className="mt-1 text-3xl font-semibold text-slate-100">Sources</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Manage tracked retailers, inspect scrape health, and keep import/export operations clean.</p>
          {importMessage && <p className="mt-3 text-sm text-emerald-300">{importMessage}</p>}
          {importError && <p className="mt-1 text-sm text-rose-300">{importError}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={() => navigate('/templates')} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-200 hover:bg-slate-800">
            <Sparkles className="h-4 w-4" />
            Templates
          </button>
          <a href={getSourcesExportUrl()} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-200 hover:bg-slate-800">
            <Download className="h-4 w-4" />
            Export JSON
          </a>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (!file) return
              importMutation.mutate(file)
              event.target.value = ''
            }}
          />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={importMutation.isPending} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-200 hover:bg-slate-800 disabled:opacity-50">
            <Upload className="h-4 w-4" />
            {importMutation.isPending ? 'Importing...' : 'Import JSON'}
          </button>
          <button onClick={() => setShowAddModal(true)} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500">
            <Plus className="h-4 w-4" />
            Add Source
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Tracked sources" value={sources.length.toLocaleString()} sublabel={`${alertingSources.length} need attention`} tone="violet" />
        <MetricCard label="Healthy" value={sources.filter((source) => source.status === 'completed').length.toLocaleString()} sublabel="Last successful scrapes" tone="emerald" />
        <MetricCard label="Failures" value={sources.filter((source) => source.status === 'failed' || (source.failure_streak ?? 0) > 0).length.toLocaleString()} sublabel="Requires follow-up" tone="rose" />
      </div>

      {healthData && (
        <SectionCard eyebrow="System" title="Worker status" description="Live crawler state and recent scan activity.">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <StatusDot tone={healthData.worker.status === 'active' ? 'emerald' : 'amber'} />
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Worker</p>
                <p className="text-sm text-slate-100">{healthData.worker.status === 'active' ? `${healthData.worker.active_crawls} crawl(s) running` : 'Idle'}</p>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Last scan</p>
              <p className="mt-1 text-sm text-slate-100">{healthData.latest_scan_at ? formatDistanceToNow(new Date(healthData.latest_scan_at), { addSuffix: true }) : 'Never'}</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Migrations</p>
              <p className="mt-1 text-sm text-slate-100">{healthData.migrations.pending > 0 ? `${healthData.migrations.pending} pending` : 'Up to date'}</p>
            </div>
          </div>
        </SectionCard>
      )}

      {alertingSources.length > 0 && (
        <div className="rounded-3xl border border-amber-400/20 bg-amber-950/20 p-4 text-sm text-amber-100">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" />
            {alertingSources.length} source{alertingSources.length > 1 ? 's' : ''} need attention
          </div>
          <div className="mt-1 text-xs text-amber-200/80">
            {alertingSources.filter((s) => (s.failure_streak ?? 0) > 0 || s.status === 'failed').length} with failures, {alertingSources.filter((s) => s.status_message?.toLowerCase().startsWith('stale')).length} stale
          </div>
        </div>
      )}

      {selectedIds.size > 0 && (
        <div className="rounded-3xl border border-violet-500/20 bg-violet-950/25 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm font-semibold text-violet-100">{selectedIds.size} source{selectedIds.size > 1 ? 's' : ''} selected</div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => runBulk((id) => api.sources.scan(id))} disabled={bulkLoading} className="inline-flex items-center gap-1 rounded-full bg-violet-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"><RefreshCw className="h-4 w-4" />Run scans</button>
              <button onClick={() => runBulk((id) => api.sources.update(id, { active: false }))} disabled={bulkLoading} className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 px-3 py-1.5 text-sm text-amber-200 disabled:opacity-50"><Pause className="h-4 w-4" />Pause</button>
              <button onClick={() => runBulk((id) => api.sources.update(id, { active: true }))} disabled={bulkLoading} className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 px-3 py-1.5 text-sm text-emerald-200 disabled:opacity-50"><Play className="h-4 w-4" />Resume</button>
              <button
                onClick={() => {
                  if (!window.confirm('Delete selected sources? This cannot be undone.')) return
                  runBulk((id) => api.sources.delete(id))
                }}
                disabled={bulkLoading}
                className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 px-3 py-1.5 text-sm text-rose-200 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {sources.length === 0 ? (
        <EmptyState
          icon={Ship}
          title="No sources added yet"
          description="Add your first retailer source to start tracking filament and resin prices."
          action={<button onClick={() => setShowAddModal(true)} className="rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500">Add your first source</button>}
        />
      ) : (
        <SectionCard eyebrow="Source inventory" title="Tracked sites" description="Hover rows for subtle actions and use the menu for less clutter.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-[0.28em] text-slate-500">
                <tr>
                  <th className="px-3 py-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-600 bg-slate-950"
                      checked={allSelected}
                      onChange={() => setSelectedIds(() => (allSelected ? new Set() : new Set(sources.map((source) => source.id))))}
                    />
                  </th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Products</th>
                  <th className="px-4 py-3">Trend</th>
                  <th className="px-4 py-3">Last scan</th>
                  <th className="px-4 py-3">Last successful</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {sources.map((source) => {
                  const isSelected = selectedIds.has(source.id)
                  const trend = [
                    source.scrape_stats?.last_1h ?? 0,
                    source.scrape_stats?.last_12h ?? 0,
                    source.scrape_stats?.last_24h ?? 0,
                    Math.round((source.success_rate_24h ?? 0) * 100),
                  ]
                  const lastSuccessful = source.latest_run?.status === 'completed' && source.latest_run.finished_at
                    ? formatDistanceToNow(new Date(source.latest_run.finished_at), { addSuffix: true })
                    : source.last_scan_at
                    ? formatDistanceToNow(new Date(source.last_scan_at), { addSuffix: true })
                    : 'Never'
                  const retryEta = source.next_retry_at ? formatDistanceToNow(new Date(source.next_retry_at), { addSuffix: true }) : null
                  return (
                    <tr key={source.id} className={cx('border-l-2 border-transparent transition-colors hover:bg-slate-900/70', isSelected && 'bg-violet-950/25 border-violet-500', alertingIds.has(source.id) && 'bg-rose-950/15')}>
                      <td className="px-3 py-4">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-600 bg-slate-950"
                          checked={isSelected}
                          onChange={() =>
                            setSelectedIds((prev) => {
                              const next = new Set(prev)
                              if (next.has(source.id)) next.delete(source.id)
                              else next.add(source.id)
                              return next
                            })
                          }
                        />
                      </td>
                      <td className="px-4 py-4">
                        <div className="font-medium text-slate-100">{source.name || source.domain}</div>
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-violet-300">
                          {source.domain}
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <StatusDot tone={source.status === 'failed' || (source.failure_streak ?? 0) > 0 ? 'rose' : source.status_message?.toLowerCase().startsWith('stale') ? 'amber' : 'emerald'} />
                          <div>
                            <StatusBadge status={source.status} />
                            {source.status_message && <div className="mt-2 text-xs text-slate-500">{source.status_message}</div>}
                            {retryEta && <div className="mt-1 text-xs text-violet-200">Retry {retryEta}</div>}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-slate-200">{source.product_count.toLocaleString()}</td>
                      <td className="px-4 py-4 text-violet-300"><MiniSparkline values={trend} /></td>
                      <td className="px-4 py-4 text-slate-400">{source.last_scan_at ? formatDistanceToNow(new Date(source.last_scan_at), { addSuffix: true }) : 'Never'}</td>
                      <td className="px-4 py-4 text-slate-400">{lastSuccessful}</td>
                      <td className="px-4 py-4 text-right">
                        <ActionMenu label={<MoreVertical className="h-4 w-4" />}>
                          <div className="flex flex-col text-left">
                            <button onClick={() => navigate(`/shipping?source=${source.id}`)} className="flex items-center gap-2 px-4 py-3 text-sm text-slate-200 hover:bg-slate-900">
                              <Ship className="h-4 w-4 text-emerald-300" />
                              Shipping
                            </button>
                            <button onClick={() => scanMutation.mutate(source.id)} disabled={source.status === 'scanning' || scanMutation.isPending} className="flex items-center gap-2 px-4 py-3 text-sm text-slate-200 hover:bg-slate-900 disabled:opacity-50">
                              {source.status === 'scanning' ? <Loader2 className="h-4 w-4 animate-spin text-sky-300" /> : <Play className="h-4 w-4 text-sky-300" />}
                              Scan now
                            </button>
                            <button onClick={() => { if (window.confirm('Delete this source?')) deleteMutation.mutate(source.id) }} className="flex items-center gap-2 px-4 py-3 text-sm text-slate-200 hover:bg-slate-900">
                              <Trash2 className="h-4 w-4 text-rose-300" />
                              Delete
                            </button>
                          </div>
                        </ActionMenu>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {showAddModal && <AddSourceModal onClose={() => setShowAddModal(false)} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['sources'] })} />}
    </div>
  )
}
