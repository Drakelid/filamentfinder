import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Loader2, Package, TrendingDown } from 'lucide-react'
import { DealProduct, fetchDeals } from '../api'

function formatPrice(amount: string | null, currency: string | null): string {
  if (!amount) return '-'
  const num = parseFloat(amount)
  const curr = currency || 'USD'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: curr }).format(num)
  } catch {
    return `${curr} ${num.toFixed(2)}`
  }
}

function CategoryBadge({ category }: { category: string }) {
  const styles: Record<string, string> = {
    filament: 'bg-purple-900 text-purple-300',
    resin: 'bg-amber-900 text-amber-300',
    unknown: 'bg-gray-700 text-gray-300',
  }

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[category] || styles.unknown}`}>
      {category}
    </span>
  )
}

export default function DealsPage() {
  const [category, setCategory] = useState('')
  const [minDrop, setMinDrop] = useState(5)

  const { data, isLoading, error } = useQuery({
    queryKey: ['deals', category, minDrop],
    queryFn: () =>
      fetchDeals({
        category: category || undefined,
        min_pct_drop: minDrop,
        limit: 20,
      }),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
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
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load deals: {(error as Error).message}
      </div>
    )
  }

  const deals = data || []

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <TrendingDown className="w-8 h-8 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Best Deals</h1>
          <p className="text-gray-400 mt-1">Recent price drops from the last 48 hours</p>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          {[
            { value: '', label: 'All' },
            { value: 'filament', label: 'Filament' },
            { value: 'resin', label: 'Resin' },
          ].map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => setCategory(option.value)}
              className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                category === option.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <label className="text-sm text-gray-400 flex items-center gap-2">
          Min drop
          <select
            value={minDrop}
            onChange={(e) => setMinDrop(parseInt(e.target.value, 10))}
            className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-100"
          >
            {[5, 10, 20, 50].map((value) => (
              <option key={value} value={value}>
                {value}%
              </option>
            ))}
          </select>
        </label>
      </div>

      {deals.length === 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center text-gray-400">
          No deals found in the last 48 hours — check back after the next scan.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {deals.map((deal: DealProduct) => (
            <Link
              key={`${deal.id}-${deal.detected_at}`}
              to={`/products/${deal.id}`}
              className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden hover:border-gray-600 transition-colors"
            >
              <div className="aspect-video bg-gray-900 relative">
                {deal.image_url ? (
                  <img
                    src={deal.image_url}
                    alt={deal.name}
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      ;(e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Package className="w-12 h-12 text-gray-700" />
                  </div>
                )}
                <div className="absolute top-2 left-2">
                  <CategoryBadge category={deal.category} />
                </div>
              </div>

              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-gray-100 line-clamp-2 mb-1">{deal.name}</h3>
                    {deal.brand && <p className="text-sm text-gray-400">{deal.brand}</p>}
                  </div>
                  <span className="px-2 py-1 rounded-full bg-green-900 text-green-300 text-xs font-medium">
                    -{deal.pct_drop.toFixed(1)}%
                  </span>
                </div>

                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <div className="text-sm text-slate-500 line-through">
                      {formatPrice(deal.old_price, deal.latest_price?.currency || null)}
                    </div>
                    <div className="text-lg font-bold text-white">
                      {formatPrice(deal.new_price, deal.latest_price?.currency || null)}
                    </div>
                  </div>
                  <div className="text-right text-sm text-gray-400">
                    <div>{deal.source_name || 'Unknown source'}</div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
