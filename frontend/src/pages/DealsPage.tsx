import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ExternalLink, Filter, Package, TrendingDown } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { DealProduct, fetchDeals } from '../api'
import { EmptyState, Surface } from '../components/analytics/AnalyticsPrimitives'

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
    filament: 'bg-violet-500/15 text-violet-200 border-violet-500/20',
    resin: 'bg-amber-500/15 text-amber-200 border-amber-500/20',
    unknown: 'bg-slate-700/70 text-slate-300 border-slate-600',
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${styles[category] || styles.unknown}`}>
      {category}
    </span>
  )
}

function DealSkeleton() {
  return (
    <Surface className="overflow-hidden">
      <div className="h-40 bg-slate-800/80 animate-pulse" />
      <div className="space-y-3 p-5">
        <div className="h-4 w-24 rounded bg-slate-700 animate-pulse" />
        <div className="h-5 w-4/5 rounded bg-slate-700 animate-pulse" />
        <div className="h-4 w-2/3 rounded bg-slate-700 animate-pulse" />
        <div className="flex items-end justify-between pt-2">
          <div className="space-y-2">
            <div className="h-4 w-20 rounded bg-slate-700 animate-pulse" />
            <div className="h-6 w-28 rounded bg-slate-700 animate-pulse" />
          </div>
          <div className="h-8 w-20 rounded-full bg-slate-700 animate-pulse" />
        </div>
      </div>
    </Surface>
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

  const deals = data || []

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <TrendingDown className="h-8 w-8 text-amber-300" />
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Best Deals</h1>
            <p className="text-sm text-slate-400">Scanning the last 48 hours for price drops</p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <DealSkeleton key={index} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <Surface className="p-6">
        <div className="text-red-300">Failed to load deals: {(error as Error).message}</div>
      </Surface>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-amber-500/10 bg-gradient-to-br from-slate-900 via-slate-900 to-amber-950/40 p-6 shadow-lg shadow-black/20">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-200">
              <TrendingDown className="h-3.5 w-3.5" />
              Price drops in the last 48 hours
            </div>
            <h1 className="text-3xl font-semibold text-slate-50">Best Deals</h1>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Attention-grabbing offers from the retailers we track. The list refreshes automatically every few minutes.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Visible deals</p>
            <p className="mt-1 text-3xl font-semibold text-amber-200">{deals.length}</p>
          </div>
        </div>
      </div>

      <Surface className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 rounded-2xl border border-slate-800 bg-slate-950/60 p-1">
            {[
              { value: '', label: 'All' },
              { value: 'filament', label: 'Filament' },
              { value: 'resin', label: 'Resin' },
            ].map((option) => (
              <button
                key={option.label}
                type="button"
                onClick={() => setCategory(option.value)}
                className={`rounded-xl px-3 py-2 text-sm transition-colors ${
                  category === option.value
                    ? 'bg-violet-500/15 text-violet-100 ring-1 ring-inset ring-violet-400/30'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-400">
            Min drop
            <select
              value={minDrop}
              onChange={(e) => setMinDrop(parseInt(e.target.value, 10))}
              className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-slate-100 outline-none"
            >
              {[5, 10, 20, 50].map((value) => (
                <option key={value} value={value}>
                  {value}%
                </option>
              ))}
            </select>
          </label>

          <div className="ml-auto flex items-center gap-2 text-sm text-slate-500">
            <Filter className="h-4 w-4" />
            Refined by category and minimum drop
          </div>
        </div>
      </Surface>

      {deals.length === 0 ? (
        <EmptyState
          title="No price drops spotted yet"
          description="We check prices every few hours. Deals will show up here automatically when a retailer cuts a price."
          primaryAction={
            <Link
              to="/products"
              className="rounded-lg bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-400"
            >
              Browse all products
            </Link>
          }
          secondaryAction={
            <Link
              to="/products"
              className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-slate-600 hover:bg-slate-800"
            >
              Set a price alert
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {deals.map((deal: DealProduct) => {
            const currency = deal.latest_price?.currency || 'USD'
            const observedAt = deal.detected_at || deal.latest_price?.observed_at || null

            return (
              <article
                key={`${deal.id}-${deal.detected_at}`}
                className="group overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/80 shadow-lg shadow-black/20 transition-all duration-200 hover:-translate-y-1 hover:border-amber-500/30 hover:shadow-amber-950/20"
              >
                <div className="relative h-44 overflow-hidden bg-slate-950">
                  {deal.image_url ? (
                    <img
                      src={deal.image_url}
                      alt={deal.name}
                      className="h-full w-full object-contain p-4 transition-transform duration-300 group-hover:scale-[1.02]"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.20),_transparent_45%),linear-gradient(135deg,_rgba(30,41,59,0.95),_rgba(15,23,42,0.95))]">
                      <div className="rounded-2xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-center">
                        <Package className="mx-auto h-7 w-7 text-amber-300" />
                        <p className="mt-2 text-xs uppercase tracking-[0.3em] text-slate-500">Retailer card</p>
                      </div>
                    </div>
                  )}
                  <div className="absolute left-4 top-4">
                    <CategoryBadge category={deal.category} />
                  </div>
                  <div className="absolute right-4 top-4 rounded-full bg-rose-500/15 px-3 py-1 text-sm font-semibold text-rose-200 ring-1 ring-inset ring-rose-400/20">
                    -{deal.pct_drop.toFixed(1)}%
                  </div>
                </div>

                <div className="space-y-4 p-5">
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Best deal</div>
                    <h3 className="mt-2 line-clamp-2 text-lg font-semibold text-slate-50">{deal.name}</h3>
                    <p className="mt-1 text-sm text-slate-400">{deal.brand || 'Unknown brand'}</p>
                  </div>

                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Before</div>
                      <div className="font-mono text-sm text-slate-500 line-through">
                        {formatPrice(deal.old_price, currency)}
                      </div>
                      <div className="mt-1 font-mono text-2xl font-bold text-slate-50">
                        {formatPrice(deal.new_price, currency)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Source</div>
                      <div className="text-sm font-medium text-slate-200">{deal.source_name || 'Unknown source'}</div>
                      {observedAt && (
                        <div className="mt-1 text-xs text-slate-500">
                          Detected {formatDistanceToNow(new Date(observedAt), { addSuffix: true })}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-3 border-t border-slate-800 pt-4">
                    <Link
                      to={`/products/${deal.id}`}
                      className="rounded-lg bg-violet-500/15 px-3 py-2 text-sm font-medium text-violet-100 transition-colors hover:bg-violet-500/20"
                    >
                      View product
                    </Link>
                    <a
                      href={deal.canonical_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-amber-200 transition-colors hover:text-amber-100"
                    >
                      Retailer link
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
