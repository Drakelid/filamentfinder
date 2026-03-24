import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCcw, Save, Truck } from 'lucide-react'
import { api, Source } from '../api'

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
  const [feeInput, setFeeInput] = useState('')
  const [localError, setLocalError] = useState('')

  const selectedSource = useMemo<Source | undefined>(() => {
    if (selectedSourceId === null) return undefined
    return sources.find((src) => src.id === selectedSourceId)
  }, [selectedSourceId, sources])

  useEffect(() => {
    if (sources.length && selectedSourceId === null) {
      setSelectedSourceId(sources[0].id)
    }
  }, [sources, selectedSourceId])

  useEffect(() => {
    if (!selectedSource) {
      setFeeInput('')
      return
    }
    setFeeInput(selectedSource.shipping_fee ?? '')
  }, [selectedSource])

  const updateMutation = useMutation({
    mutationFn: ({ id, fee }: { id: number; fee: number | null }) =>
      api.sources.update(id, { shipping_fee: fee }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      setLocalError('')
    },
    onError: (err: Error) => {
      setLocalError(err.message)
    },
  })

  const handleSave = () => {
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-xl">
        Failed to load sources: {(error as Error).message}
      </div>
    )
  }

  if (!sources.length) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-8 text-center space-y-4">
        <Truck className="w-12 h-12 text-slate-500 mx-auto" />
        <div className="text-lg text-slate-200">No sources available</div>
        <p className="text-sm text-slate-400">Add a source first to configure shipping fees.</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Logistics</p>
          <h1 className="text-3xl font-semibold text-white">Shipping Fees</h1>
          <p className="text-sm text-slate-400 mt-2">Attach a manual shipping fee per source. This fee will be added to scraped shipping on the comparison page.</p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['sources'] })}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800"
        >
          <RefreshCcw className="w-4 h-4" />
          Refresh list
        </button>
      </div>

      <div className="grid lg:grid-cols-[320px,1fr] gap-6">
        <div className="bg-slate-900/70 border border-slate-800 rounded-3xl p-5 space-y-4">
          <div>
            <label className="text-sm text-slate-400">Select source</label>
            <select
              value={selectedSourceId ?? ''}
              onChange={(e) => setSelectedSourceId(Number(e.target.value))}
              className="mt-2 w-full bg-slate-950/60 border border-slate-800 rounded-2xl px-3 py-2 text-slate-100"
            >
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name || source.domain}
                </option>
              ))}
            </select>
          </div>

          {selectedSource && (
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400">Shipping fee (NOK)</label>
                <input
                  type="number"
                  step="0.01"
                  inputMode="decimal"
                  value={feeInput}
                  onChange={(e) => setFeeInput(e.target.value)}
                  className="mt-2 w-full bg-slate-950/60 border border-slate-800 rounded-2xl px-3 py-2 text-slate-100 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/40"
                  placeholder="e.g. 99"
                />
                <p className="text-xs text-slate-500 mt-1">Leave empty to clear the manual fee.</p>
              </div>

              {localError && (
                <div className="text-sm text-red-300 bg-red-900/30 border border-red-700 rounded-2xl px-3 py-2">
                  {localError}
                </div>
              )}

              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-2xl bg-blue-600 text-white font-medium hover:bg-blue-500 disabled:opacity-60"
              >
                {updateMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                <Save className="w-4 h-4" />
                Save fee
              </button>
            </div>
          )}
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 uppercase text-xs tracking-widest">
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Domain</th>
                  <th className="px-3 py-2">Manual fee</th>
                  <th className="px-3 py-2">Products</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {sources.map((source) => (
                  <tr key={source.id} className="hover:bg-slate-900/80">
                    <td className="px-3 py-3">
                      <div className="font-medium text-slate-100">{source.name || source.domain}</div>
                    </td>
                    <td className="px-3 py-3 text-slate-400 text-xs">{source.domain}</td>
                    <td className="px-3 py-3 text-slate-100">
                      <div className="text-sm">{formatCurrencyPreview(source.shipping_fee)}</div>
                      {source.shipping_fee && (
                        <div className="text-xs text-slate-500">Stored: {source.shipping_fee}</div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-slate-300">{source.product_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
