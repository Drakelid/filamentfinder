import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Play, Trash2, ExternalLink, Loader2, CheckCircle, XCircle, Clock, AlertTriangle, Ship, RefreshCw, Pause, Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api, Source, CrawlRules } from '../api'
import { formatDistanceToNow } from 'date-fns'

function formatDuration(seconds?: number | null) {
  if (!seconds || seconds <= 0) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-gray-700 text-gray-300',
    scanning: 'bg-blue-900 text-blue-300',
    completed: 'bg-green-900 text-green-300',
    failed: 'bg-red-900 text-red-300',
  }
  const icons: Record<string, React.ReactNode> = {
    pending: <Clock className="w-3 h-3" />,
    scanning: <Loader2 className="w-3 h-3 animate-spin" />,
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

const DAY_OPTIONS = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]

function AddSourceModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [maxPages, setMaxPages] = useState(100)
  const [maxDepth, setMaxDepth] = useState(3)
  const [scheduleStart, setScheduleStart] = useState('')
  const [scheduleEnd, setScheduleEnd] = useState('')
  const [scheduleTimezone, setScheduleTimezone] = useState('')
  const [scheduleDays, setScheduleDays] = useState<string[]>([])
  const [error, setError] = useState('')
  
  const mutation = useMutation({
    mutationFn: () => {
      const crawlRules: Partial<CrawlRules> = {
        max_pages: maxPages,
        max_depth: maxDepth,
      }
      if (scheduleStart) crawlRules.schedule_start_hour = scheduleStart
      if (scheduleEnd) crawlRules.schedule_end_hour = scheduleEnd
      if (scheduleTimezone) crawlRules.schedule_timezone = scheduleTimezone
      if (scheduleDays.length) crawlRules.schedule_days = scheduleDays

      return api.sources.create({
        url,
        name: name || undefined,
        crawl_rules: crawlRules,
      })
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })
  
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4 text-gray-100">Add Source</h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-900/50 text-red-300 rounded-lg text-sm">
            {error}
          </div>
        )}
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">URL *</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://store.example.com/filaments"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Favorite Store"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Max Pages</label>
              <input
                type="number"
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value) || 100)}
                min={1}
                max={10000}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Max Depth</label>
              <input
                type="number"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 3)}
                min={1}
                max={10}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
              />
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-200">Scheduling window (optional)</span>
              <span className="text-xs text-gray-500">Limit crawl times for polite scraping</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Start time</label>
                <input
                  type="time"
                  value={scheduleStart}
                  onChange={(e) => setScheduleStart(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">End time</label>
                <input
                  type="time"
                  value={scheduleEnd}
                  onChange={(e) => setScheduleEnd(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Timezone</label>
                <input
                  type="text"
                  placeholder="Europe/Oslo"
                  value={scheduleTimezone}
                  onChange={(e) => setScheduleTimezone(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Days allowed</label>
                <div className="flex flex-wrap gap-2">
                  {DAY_OPTIONS.map((day) => {
                    const active = scheduleDays.includes(day.value)
                    return (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => {
                          setScheduleDays((prev) => (
                            prev.includes(day.value)
                              ? prev.filter((d) => d !== day.value)
                              : [...prev, day.value]
                          ))
                        }}
                        className={`px-2 py-1 rounded-full text-xs border ${active ? 'bg-blue-600 text-white border-blue-500' : 'border-gray-600 text-gray-300 hover:border-gray-400'}`}
                      >
                        {day.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-300 hover:bg-gray-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!url || mutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Add Source
          </button>
        </div>
      </div>
    </div>
  )
}

export default function SourcesPage() {
  const navigate = useNavigate()
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [alertToasts, setAlertToasts] = useState<{ id: string; message: string; type: 'failure' | 'stale'; sourceId: number }[]>([])
  const alertSeenRef = useRef<Set<string>>(new Set())
  const queryClient = useQueryClient()
  
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
  
  const scanMutation = useMutation({
    mutationFn: (id: number) => api.sources.scan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  })
  
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.sources.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
  })

  const sources = data?.items || []
  const sourceIdsKey = useMemo(() => sources.map((source) => source.id).join(','), [sources])

  const enqueueToast = useCallback((toast: { id: string; message: string; type: 'failure' | 'stale'; sourceId: number }) => {
    setAlertToasts((prev) => [...prev, toast])
    setTimeout(() => {
      setAlertToasts((prev) => prev.filter((t) => t.id !== toast.id))
    }, 6000)
  }, [])

  useEffect(() => {
    sources.forEach((source) => {
      const failureStreak = source.failure_streak ?? 0
      if (source.status === 'failed' || failureStreak > 0) {
        const key = `failure-${source.id}-${failureStreak}`
        if (!alertSeenRef.current.has(key)) {
          alertSeenRef.current.add(key)
          enqueueToast({
            id: key,
            sourceId: source.id,
            type: 'failure',
            message: `${source.name || source.domain} failed ${failureStreak || 1}x in a row`,
          })
        }
      }

      if (source.status_message && source.status_message.toLowerCase().startsWith('stale')) {
        const key = `stale-${source.id}-${source.status_message}`
        if (!alertSeenRef.current.has(key)) {
          alertSeenRef.current.add(key)
          enqueueToast({
            id: key,
            sourceId: source.id,
            type: 'stale',
            message: `${source.name || source.domain} is stale (${source.status_message})`,
          })
        }
      }
    })
  }, [sources, enqueueToast])

  const alertingSources = useMemo(
    () =>
      sources.filter((source) => {
        const failureStreak = source.failure_streak ?? 0
        const stale = source.status_message?.toLowerCase().startsWith('stale')
        return source.status === 'failed' || failureStreak > 0 || stale
      }),
    [sources],
  )

  const alertingIds = useMemo(() => new Set(alertingSources.map((source) => source.id)), [alertingSources])

  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev
      const next = new Set<number>()
      sources.forEach((source) => {
        if (prev.has(source.id)) next.add(source.id)
      })
      if (next.size === prev.size) {
        return prev
      }
      return next
    })
  }, [sourceIdsKey])

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const allSelected = sources.length > 0 && selectedIds.size === sources.length
  const toggleSelectAll = () => {
    setSelectedIds(() => {
      if (allSelected) return new Set()
      return new Set(sources.map((source) => source.id))
    })
  }

  const runBulk = async (action: (id: number) => Promise<unknown>) => {
    const ids = Array.from(selectedIds)
    if (!ids.length) return
    setBulkLoading(true)
    try {
      for (const id of ids) {
        await action(id)
      }
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      setSelectedIds(new Set())
    } finally {
      setBulkLoading(false)
    }
  }

  const handleBulkScan = () => runBulk((id) => api.sources.scan(id))
  const handleBulkPause = () => runBulk((id) => api.sources.update(id, { active: false }))
  const handleBulkResume = () => runBulk((id) => api.sources.update(id, { active: true }))
  const handleBulkDelete = () => {
    if (!selectedIds.size) return
    if (!window.confirm('Delete selected sources? This cannot be undone.')) return
    runBulk((id) => api.sources.delete(id))
  }
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load sources: {(error as Error).message}
      </div>
    )
  }
  
  const selectedCount = selectedIds.size
  const formatRetryEta = (nextRetry?: string | null) => {
    if (!nextRetry) return null
    return formatDistanceToNow(new Date(nextRetry), { addSuffix: true })
  }

  return (
    <div>
      {alertToasts.length > 0 && (
        <div className="fixed top-20 right-6 z-30 space-y-2">
          {alertToasts.map((toast) => (
            <div
              key={toast.id}
              className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm shadow-lg backdrop-blur ${
                toast.type === 'failure'
                  ? 'border-red-500/40 bg-red-900/70 text-red-100'
                  : 'border-amber-400/40 bg-amber-900/70 text-amber-100'
              }`}
            >
              <Bell className="w-4 h-4" />
              <span>{toast.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Sources</h1>
          <p className="text-gray-400 mt-1">Manage websites to track for filament and resin prices</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          Add Source
        </button>
      </div>

      {alertingSources.length > 0 && (
        <div className="mb-4 rounded-2xl border border-amber-400/30 bg-amber-900/20 p-3 text-sm text-amber-100 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="w-4 h-4" />
            {alertingSources.length} source{alertingSources.length > 1 ? 's' : ''} need attention
          </div>
          <div className="text-amber-200/80 flex gap-3 flex-wrap text-xs">
            <span>
              {alertingSources.filter((s) => (s.failure_streak ?? 0) > 0 || s.status === 'failed').length} with failures
            </span>
            <span>
              {alertingSources.filter((s) => s.status_message?.toLowerCase().startsWith('stale')).length} stale
            </span>
          </div>
        </div>
      )}

      {healthData && (
        <div className="mb-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-3 flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-2 text-slate-200">
            <span className={`h-2.5 w-2.5 rounded-full ${healthData.worker.status === 'active' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            {healthData.worker.status === 'active'
              ? `${healthData.worker.active_crawls} crawl(s) running`
              : 'Worker idle'}
          </div>
          <div className="text-xs text-slate-400">
            Last scan {healthData.latest_scan_at ? formatDistanceToNow(new Date(healthData.latest_scan_at), { addSuffix: true }) : 'never'}
          </div>
        </div>
      )}

      {selectedCount > 0 && (
        <div className="mb-4 rounded-2xl border border-blue-900/60 bg-blue-950/30 p-3 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-blue-100 font-semibold">
            {selectedCount} source{selectedCount > 1 ? 's' : ''} selected
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <button
              onClick={handleBulkScan}
              disabled={bulkLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
            >
              <RefreshCw className="w-4 h-4" />
              Run scans
            </button>
            <button
              onClick={handleBulkPause}
              disabled={bulkLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-amber-500/50 text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"
            >
              <Pause className="w-4 h-4" />
              Pause
            </button>
            <button
              onClick={handleBulkResume}
              disabled={bulkLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-emerald-500/50 text-emerald-200 hover:bg-emerald-500/10 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              Resume
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={bulkLoading}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-red-500/50 text-red-200 hover:bg-red-500/10 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        </div>
      )}
      
      {sources.length === 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
          <p className="text-gray-400 mb-4">No sources added yet</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="text-blue-400 hover:text-blue-300 font-medium"
          >
            Add your first source
          </button>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                <th className="px-3 w-10">
                  <input
                    type="checkbox"
                    aria-label="Select all sources"
                    className="h-4 w-4 rounded border-gray-600 bg-gray-800"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Source</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Products</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Scraped</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Last Scan</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {sources.map((source: Source) => {
                const isSelected = selectedIds.has(source.id)
                const latestRun = source.latest_run
                const successPercent = source.success_rate_24h !== null && source.success_rate_24h !== undefined
                  ? Math.round(source.success_rate_24h * 100)
                  : null
                const hasAlert = alertingIds.has(source.id)
                const failureStreak = source.failure_streak ?? 0
                const retryEta = formatRetryEta(source.next_retry_at)
                return (
                  <tr
                    key={source.id}
                    className={`hover:bg-gray-700/50 ${isSelected ? 'bg-blue-900/20' : ''} ${hasAlert ? 'bg-red-900/10' : ''}`}
                  >
                    <td className="px-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${source.name || source.domain}`}
                        className="h-4 w-4 rounded border-gray-600 bg-gray-800"
                        checked={isSelected}
                        onChange={() => toggleSelect(source.id)}
                      />
                    </td>
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-medium text-gray-100">{source.name || source.domain}</div>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-gray-400 hover:text-blue-400 flex items-center gap-1"
                      >
                        {source.domain}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={source.status} />
                    {healthData && (
                      <div className="mt-1 flex items-center gap-2 text-xxs text-gray-500">
                        <span className={`h-2 w-2 rounded-full ${healthData.worker.status === 'active' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                        {healthData.worker.status === 'active'
                          ? `Crawler busy (${healthData.worker.active_crawls})`
                          : 'Crawler idle'}
                      </div>
                    )}
                    {latestRun && (
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-900/50 border border-gray-700 text-gray-200"
                          title={`Last run started ${latestRun.started_at ? formatDistanceToNow(new Date(latestRun.started_at), { addSuffix: true }) : 'unknown'}`}
                        >
                          <Clock className="w-3 h-3" />
                          {formatDuration(latestRun.duration_seconds)}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${latestRun.errors_count > 0 ? 'border-red-600 text-red-300 bg-red-900/40' : 'border-emerald-700 text-emerald-200 bg-emerald-900/30'}`}
                          title="Errors detected during last run"
                        >
                          {latestRun.errors_count > 0 ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
                          {latestRun.errors_count} err
                        </span>
                        {successPercent !== null && (
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-blue-700 text-blue-200 bg-blue-900/30"
                            title="Success rate across the last 24h"
                          >
                            <RefreshCw className="w-3 h-3" />
                            {successPercent}%
                          </span>
                        )}
                      </div>
                    )}
                    {source.status_message && (
                      <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-900/30 px-2 py-0.5 text-xs text-amber-100">
                        <AlertTriangle className="w-3 h-3" />
                        <span>{source.status_message}</span>
                      </div>
                    )}
                    {failureStreak > 0 && (
                      <div className="mt-1 inline-flex items-center gap-1 rounded-full border border-red-500/40 bg-red-900/30 px-2 py-0.5 text-xs text-red-100">
                        <XCircle className="w-3 h-3" />
                        <span>{failureStreak} consecutive fail{failureStreak > 1 ? 's' : ''}</span>
                      </div>
                    )}
                    {retryEta && (
                      <div className="mt-1 inline-flex items-center gap-1 rounded-full border border-blue-500/40 bg-blue-900/30 px-2 py-0.5 text-xs text-blue-100">
                        <Clock className="w-3 h-3" />
                        <span>Retry {retryEta}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-300">
                    {source.product_count}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500 w-8" title="Products scraped in the last 1 hour">1h:</span>
                        <span className={source.scrape_stats?.last_1h > 0 ? 'text-green-400' : 'text-gray-500'}>
                          {source.scrape_stats?.last_1h || 0}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500 w-8" title="Products scraped in the last 12 hours">12h:</span>
                        <span className={source.scrape_stats?.last_12h > 0 ? 'text-blue-400' : 'text-gray-500'}>
                          {source.scrape_stats?.last_12h || 0}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500 w-8" title="Products scraped in the last 24 hours">24h:</span>
                        <span className={source.scrape_stats?.last_24h > 0 ? 'text-purple-400' : 'text-gray-500'}>
                          {source.scrape_stats?.last_24h || 0}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-sm">
                    {source.last_scan_at
                      ? formatDistanceToNow(new Date(source.last_scan_at), { addSuffix: true })
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => navigate(`/shipping?source=${source.id}`)}
                        className="p-2 text-gray-400 hover:text-emerald-300 hover:bg-emerald-900/40 rounded-lg transition-colors"
                        title="Adjust shipping fee"
                      >
                        <Ship className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => scanMutation.mutate(source.id)}
                        disabled={source.status === 'scanning' || scanMutation.isPending}
                        className="p-2 text-gray-400 hover:text-blue-400 hover:bg-blue-900/50 rounded-lg transition-colors disabled:opacity-50"
                        title="Run scan"
                      >
                        {source.status === 'scanning' ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this source?')) {
                            deleteMutation.mutate(source.id)
                          }
                        }}
                        className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-900/50 rounded-lg transition-colors"
                        title="Delete source"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      
      {showAddModal && (
        <AddSourceModal
          onClose={() => setShowAddModal(false)}
          onSuccess={() => queryClient.invalidateQueries({ queryKey: ['sources'] })}
        />
      )}
    </div>
  )
}
