import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { api, type CrawlRules } from '../../api'
import { cx } from '../admin/AdminUI'
import type { ScrapeTemplate } from '../../data/scrapeTemplates'

const DAY_OPTIONS = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
]

function buildInitialRules(templatePreset?: ScrapeTemplate | null) {
  return {
    maxPages: templatePreset?.crawlRules?.max_pages ?? 100,
    maxDepth: templatePreset?.crawlRules?.max_depth ?? 3,
    scheduleStart: templatePreset?.crawlRules?.schedule_start_hour ?? '',
    scheduleEnd: templatePreset?.crawlRules?.schedule_end_hour ?? '',
    scheduleTimezone: templatePreset?.crawlRules?.schedule_timezone ?? '',
    scheduleDays: templatePreset?.crawlRules?.schedule_days ?? [],
  }
}

export default function AddSourceModal({
  onClose,
  onSuccess,
  templatePreset = null,
}: {
  onClose: () => void
  onSuccess: () => void
  templatePreset?: ScrapeTemplate | null
}) {
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [maxPages, setMaxPages] = useState(buildInitialRules(templatePreset).maxPages)
  const [maxDepth, setMaxDepth] = useState(buildInitialRules(templatePreset).maxDepth)
  const [scheduleStart, setScheduleStart] = useState(buildInitialRules(templatePreset).scheduleStart)
  const [scheduleEnd, setScheduleEnd] = useState(buildInitialRules(templatePreset).scheduleEnd)
  const [scheduleTimezone, setScheduleTimezone] = useState(buildInitialRules(templatePreset).scheduleTimezone)
  const [scheduleDays, setScheduleDays] = useState<string[]>(buildInitialRules(templatePreset).scheduleDays)
  const [error, setError] = useState('')

  useEffect(() => {
    const next = buildInitialRules(templatePreset)
    setUrl('')
    setName('')
    setMaxPages(next.maxPages)
    setMaxDepth(next.maxDepth)
    setScheduleStart(next.scheduleStart)
    setScheduleEnd(next.scheduleEnd)
    setScheduleTimezone(next.scheduleTimezone)
    setScheduleDays(next.scheduleDays)
    setError('')
  }, [templatePreset])

  const mutation = useMutation({
    mutationFn: () => {
      const crawlRules: Partial<CrawlRules> = {
        same_domain_only: templatePreset?.crawlRules?.same_domain_only ?? true,
        url_patterns: templatePreset?.crawlRules?.url_patterns ?? [],
        exclude_patterns: templatePreset?.crawlRules?.exclude_patterns ?? [],
        respect_robots_txt: templatePreset?.crawlRules?.respect_robots_txt ?? true,
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
        selector_overrides: templatePreset?.selectorOverrides,
      })
    },
    onSuccess: () => {
      onSuccess()
      onClose()
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-3xl border border-slate-800 bg-slate-900 shadow-2xl shadow-black/40">
        <div className="border-b border-slate-800 px-6 py-4">
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">
            {templatePreset ? 'Template setup' : 'Source setup'}
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-100">
            {templatePreset ? `Add Source from ${templatePreset.name}` : 'Add Source'}
          </h2>
          {templatePreset && (
            <p className="mt-2 text-sm text-slate-400">
              Starts with the built-in <span className="font-medium text-slate-200">{templatePreset.parser}</span> strategy and its recommended crawl defaults.
            </p>
          )}
        </div>
        <div className="space-y-5 px-6 py-5">
          {error && <div className="rounded-2xl border border-rose-500/30 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</div>}

          {templatePreset && (
            <div className="rounded-3xl border border-violet-500/20 bg-violet-950/20 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-200">
                  Priority {templatePreset.priority}
                </span>
                <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-xs text-slate-300">
                  {templatePreset.parser}
                </span>
              </div>
              <p className="mt-3 text-sm text-slate-200">{templatePreset.description}</p>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">URL *</span>
              <input value={url} onChange={(e) => setUrl(e.target.value)} type="url" placeholder="https://store.example.com/filaments" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30" />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} type="text" placeholder="My Favorite Store" className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30" />
            </label>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Max pages</span>
              <input type="number" value={maxPages} onChange={(e) => setMaxPages(parseInt(e.target.value, 10) || 100)} min={1} max={10000} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30" />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-300">Max depth</span>
              <input type="number" value={maxDepth} onChange={(e) => setMaxDepth(parseInt(e.target.value, 10) || 3)} min={1} max={10} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30" />
            </label>
          </div>
          <div className="rounded-3xl border border-slate-800 bg-slate-950/30 p-4">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm text-slate-300">Start time</span>
                <input type="time" value={scheduleStart} onChange={(e) => setScheduleStart(e.target.value)} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100" />
              </label>
              <label className="space-y-2">
                <span className="text-sm text-slate-300">End time</span>
                <input type="time" value={scheduleEnd} onChange={(e) => setScheduleEnd(e.target.value)} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100" />
              </label>
              <label className="space-y-2">
                <span className="text-sm text-slate-300">Timezone</span>
                <input type="text" placeholder="Europe/Oslo" value={scheduleTimezone} onChange={(e) => setScheduleTimezone(e.target.value)} className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100" />
              </label>
              <div className="space-y-2">
                <span className="text-sm text-slate-300">Days allowed</span>
                <div className="flex flex-wrap gap-2">
                  {DAY_OPTIONS.map((day) => {
                    const active = scheduleDays.includes(day.value)
                    return (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => setScheduleDays((prev) => (prev.includes(day.value) ? prev.filter((currentDay) => currentDay !== day.value) : [...prev, day.value]))}
                        className={cx('rounded-full border px-3 py-1.5 text-xs transition-colors', active ? 'border-violet-500/40 bg-violet-500/15 text-violet-100' : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200')}
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
        <div className="flex justify-end gap-3 border-t border-slate-800 px-6 py-4">
          <button onClick={onClose} className="rounded-xl px-4 py-2 text-slate-300 hover:bg-slate-800">Cancel</button>
          <button onClick={() => mutation.mutate()} disabled={!url || mutation.isPending} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50">
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {templatePreset ? 'Create Source from Template' : 'Add Source'}
          </button>
        </div>
      </div>
    </div>
  )
}
