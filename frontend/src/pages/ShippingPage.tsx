import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCcw, Save, Ship, CheckSquare, Square } from 'lucide-react'
import { api, Source } from '../api'
import { EmptyState, LoadingState, MetricCard, SectionCard, StatusDot, cx } from '../components/admin/AdminUI'

function formatCurrencyPreview(value: string | null) {
  if (!value) return 'Not set'
  const amount = Number(value)
  if (Number.isNaN(amount)) return value
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'NOK' }).format(amount)
}

export default function ShippingPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['sources'],
    queryFn: api.sources.list,
    refetchInterval: 15000,
  })

  const sources = data?.items ?? []
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkMode, setBulkMode] = useState(false)
  const [feeInput, setFeeInput] = useState('')
  const [localError, setLocalError] = useState('')

  const selectedSource = useMemo<Source | undefined>(() => sources.find((src) => src.id === selectedSourceId), [selectedSourceId, sources])
  const selectedSources = useMemo(() => sources.filter((source) => selectedIds.has(source.id)), [selectedIds, sources])

  useEffect(() => {
    if (sources.length && selectedSourceId === null) {
      setSelectedSourceId(sources[0].id)
    }
  }, [sources, selectedSourceId])

  useEffect(() => {
    if (!bulkMode) {
      setSelectedIds(new Set())
      return
    }
    if (!selectedSourceId) return
    setSelectedIds((prev) => {
      if (prev.size > 0) return prev
      return new Set([selectedSourceId])
    })
  }, [bulkMode, selectedSourceId])

  useEffect(() => {
    if (bulkMode) {
      setFeeInput('')
      return
    }
    if (!selectedSource) {
      setFeeInput('')
      return
    }
    setFeeInput(selectedSource.shipping_fee ?? '')
  }, [bulkMode, selectedSource])

  const updateMutation = useMutation({
    mutationFn: ({ id, fee }: { id: number; fee: number | null }) => api.sources.update(id, { shipping_fee: fee }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      setLocalError('')
    },
    onError: (err: Error) => setLocalError(err.message),
  })

  const handleSaveSingle = () => {
    if (!selectedSource) return
    if (feeInput.trim() === '') {
      updateMutation.mutate({ id: selectedSource.id, fee: null })
      return
    }
    const parsed = Number(feeInput)
    if (Number.isNaN(parsed)) {
      setLocalError('Please enter a numeric fee (use dot for decimals).')
      return
    }
    updateMutation.mutate({ id: selectedSource.id, fee: parsed })
  }

  const handleSaveBulk = () => {
    const ids = Array.from(selectedIds)
    if (!ids.length) return
    const parsed = feeInput.trim() === '' ? null : Number(feeInput)
    if (parsed !== null && Number.isNaN(parsed)) {
      setLocalError('Please enter a numeric fee (use dot for decimals).')
      return
    }
    ids.reduce(
      (promise, id) =>
        promise.then(() =>
          updateMutation.mutateAsync({ id, fee: parsed }).then(() => undefined),
        ),
      Promise.resolve(),
    )
  }

  if (isLoading) return <LoadingState label="Loading shipping settings" />
  if (error) return <div className="rounded-3xl border border-rose-500/30 bg-rose-950/40 p-4 text-rose-200">Failed to load sources: {(error as Error).message}</div>
  if (!sources.length) {
    return <EmptyState icon={Ship} title="No sources available" description="Add a source first to configure shipping fees." />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.32em] text-slate-500">Logistics</p>
          <h1 className="mt-1 text-3xl font-semibold text-slate-100">Shipping Fees</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Attach a manual shipping fee per source and apply the same fee to multiple retailers at once.</p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['sources'] })}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-slate-300 hover:bg-slate-800"
        >
          <RefreshCcw className="h-4 w-4" />
          Refresh list
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Sources" value={sources.length.toLocaleString()} sublabel="Available for fee edits" tone="violet" />
        <MetricCard label="Configured" value={sources.filter((source) => source.shipping_fee !== null && source.shipping_fee !== '').length.toLocaleString()} sublabel="Has a manual fee" tone="emerald" />
        <MetricCard label="Bulk mode" value={bulkMode ? 'On' : 'Off'} sublabel="Apply one fee to multiple sources" tone="amber" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px,1fr]">
        <SectionCard eyebrow="Sources" title="Select retailer" description="Pick one source for a single edit or switch on bulk mode for multiple sources." action={<button onClick={() => setBulkMode((prev) => !prev)} className={cx('rounded-xl border px-3 py-2 text-sm transition-colors', bulkMode ? 'border-violet-500/30 bg-violet-500/15 text-violet-100' : 'border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800')}>{bulkMode ? 'Bulk mode on' : 'Bulk mode off'}</button>}>
          <div className="space-y-2">
            {sources.map((source) => {
              const selected = bulkMode ? selectedIds.has(source.id) : selectedSourceId === source.id
              return (
                <button
                  key={source.id}
                  onClick={() => {
                    if (bulkMode) {
                      setSelectedIds((prev) => {
                        const next = new Set(prev)
                        if (next.has(source.id)) next.delete(source.id)
                        else next.add(source.id)
                        return next
                      })
                    } else {
                      setSelectedSourceId(source.id)
                    }
                  }}
                  className={cx('flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition-colors', selected ? 'border-violet-500/30 bg-violet-950/30' : 'border-slate-800 bg-slate-950/40 hover:bg-slate-900')}
                >
                  {bulkMode ? selected ? <CheckSquare className="h-4 w-4 text-violet-300" /> : <Square className="h-4 w-4 text-slate-500" /> : <StatusDot tone="emerald" />}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-100">{source.name || source.domain}</div>
                    <div className="truncate text-xs text-slate-500">{source.domain}</div>
                  </div>
                  <div className="text-right text-xs text-slate-500">{formatCurrencyPreview(source.shipping_fee)}</div>
                </button>
              )
            })}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Editor" title={bulkMode ? 'Bulk shipping edit' : 'Shipping fee details'} description={bulkMode ? `${selectedIds.size} source(s) selected` : 'Edit the selected source and keep a quick overview of the other fees.'}>
          <div className="grid gap-6 lg:grid-cols-[1fr,280px]">
            <div className="space-y-4">
              {bulkMode && (
                <div className="rounded-3xl border border-violet-500/20 bg-violet-950/20 p-4 text-sm text-violet-100">
                  Bulk edits will apply the same fee to every selected source.
                </div>
              )}

              <label className="space-y-2">
                <span className="text-sm text-slate-300">Shipping fee (NOK)</span>
                <input
                  type="number"
                  step="0.01"
                  inputMode="decimal"
                  value={feeInput}
                  onChange={(e) => setFeeInput(e.target.value)}
                  className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-slate-100 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                  placeholder="e.g. 99"
                />
                <p className="text-xs text-slate-500">Leave empty to clear the manual fee.</p>
              </label>

              {localError && <div className="rounded-2xl border border-rose-500/30 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{localError}</div>}

              <button
                onClick={bulkMode ? handleSaveBulk : handleSaveSingle}
                disabled={updateMutation.isPending || (!bulkMode && !selectedSource) || (bulkMode && !selectedIds.size)}
                className="inline-flex items-center gap-2 rounded-2xl bg-violet-600 px-4 py-3 font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save fee
              </button>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Current selection</p>
              {bulkMode ? (
                <div className="mt-3 space-y-2 text-sm text-slate-300">
                  {selectedSources.length ? (
                    selectedSources.map((source) => (
                      <div key={source.id} className="flex items-center justify-between rounded-2xl border border-slate-800 px-3 py-2">
                        <span>{source.name || source.domain}</span>
                        <span className="text-slate-500">{formatCurrencyPreview(source.shipping_fee)}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-500">Select one or more sources to begin.</p>
                  )}
                </div>
              ) : selectedSource ? (
                <div className="mt-3 space-y-3 text-sm text-slate-300">
                  <div className="rounded-2xl border border-slate-800 px-3 py-2">
                    <div className="font-medium text-slate-100">{selectedSource.name || selectedSource.domain}</div>
                    <div className="text-xs text-slate-500">{selectedSource.domain}</div>
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-slate-800 px-3 py-2">
                    <span>Manual fee</span>
                    <span className="text-slate-100">{formatCurrencyPreview(selectedSource.shipping_fee)}</span>
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-slate-800 px-3 py-2">
                    <span>Products</span>
                    <span className="text-slate-100">{selectedSource.product_count}</span>
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">Select a source to inspect its current shipping fee.</p>
              )}
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
