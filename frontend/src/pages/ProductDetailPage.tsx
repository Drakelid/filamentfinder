import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ExternalLink,
  Info,
  Loader2,
  Package,
  TrendingDown,
  TrendingUp,
  Minus,
} from 'lucide-react'
import { api, createAlert, deleteAlert, listAlerts, PriceChange, Product } from '../api'
import { format, formatDistanceToNow } from 'date-fns'
import PriceHistoryChart from '../components/PriceHistoryChart'
import {
  Breadcrumbs,
  CategoryBadge,
  MatchBadge,
  ProductEmptyState,
  ProductSkeletonGrid,
  StockBadge,
  formatNumberCurrency,
  formatPrice,
} from '../components/products/ProductUI'

function ChangeIcon({ type }: { type: string }) {
  if (type === 'price_decrease') {
    return <TrendingDown className="h-4 w-4 text-emerald-400" />
  }
  if (type === 'price_increase') {
    return <TrendingUp className="h-4 w-4 text-rose-400" />
  }
  return <Minus className="h-4 w-4 text-slate-400" />
}

function ChangeTypeBadge({ type, percent }: { type: string; percent: number | null }) {
  const styles: Record<string, string> = {
    price_decrease: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-100',
    price_increase: 'border-rose-500/20 bg-rose-500/10 text-rose-100',
    price_change: 'border-sky-500/20 bg-sky-500/10 text-sky-100',
    price_removed: 'border-slate-700 bg-slate-900/60 text-slate-300',
    price_added: 'border-violet-500/20 bg-violet-500/10 text-violet-100',
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${styles[type] || styles.price_change}`}>
      <ChangeIcon type={type} />
      {percent !== null ? `${percent > 0 ? '+' : ''}${percent.toFixed(1)}%` : type.replace('_', ' ')}
    </span>
  )
}

function ProductMedia({ product }: { product: Product }) {
  if (product.image_url) {
    return (
      <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-950/70 shadow-lg shadow-black/20">
        <img
          src={product.image_url}
          alt={product.name}
          className="h-64 w-full object-contain p-6"
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
      </div>
    )
  }

  return (
    <div className="flex h-64 items-center justify-center rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 shadow-lg shadow-black/20">
      <div className="text-center">
        <Package className="mx-auto h-12 w-12 text-slate-500" />
        <p className="mt-3 text-sm text-slate-500">No image available</p>
      </div>
    </div>
  )
}

function SimilarProductCard({ product, highlight }: { product: Product; highlight?: boolean }) {
  return (
    <Link
      to={`/products/${product.id}`}
      className={`group block rounded-2xl border bg-slate-900/70 p-4 shadow-lg shadow-black/15 transition-all hover:-translate-y-0.5 hover:bg-slate-900 ${
        highlight ? 'border-amber-500/30' : 'border-slate-800 hover:border-violet-500/30'
      }`}
    >
      <div className="flex items-start gap-3">
        {product.image_url ? (
          <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/60">
            <img
              src={product.image_url}
              alt={product.name}
              className="h-full w-full object-contain p-1.5"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
          </div>
        ) : (
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-slate-800 bg-slate-950/60 text-slate-500">
            <Package className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={product.category} />
            <MatchBadge confidence={product.confidence} />
          </div>
          <h3 className="line-clamp-2 text-sm font-semibold text-slate-50 group-hover:text-white">{product.name}</h3>
          <p className="line-clamp-1 text-xs text-slate-400">{product.brand || product.source_name || 'Unknown source'}</p>
          <div className="flex items-center justify-between gap-2 text-sm">
            <span className="font-mono font-semibold text-slate-100">
              {formatPrice(product.latest_price?.price_amount ?? null, product.latest_price?.currency ?? null)}
            </span>
            <StockBadge inStock={product.latest_price?.in_stock ?? null} />
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const productId = parseInt(id || '0')
  const queryClient = useQueryClient()
  const [alertTarget, setAlertTarget] = useState('')
  const [alertError, setAlertError] = useState<string | null>(null)

  const { data: product, isLoading: productLoading, error: productError } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => api.products.get(productId),
    enabled: !!productId,
  })

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['product-history', productId],
    queryFn: () => api.products.history(productId),
    enabled: !!productId,
  })

  const { data: alerts } = useQuery({
    queryKey: ['alerts', productId],
    queryFn: () => listAlerts(productId, true),
    enabled: !!productId,
  })

  const { data: similarData, isLoading: similarLoading } = useQuery({
    queryKey: ['similar-products', productId, product?.category, product?.product_type, product?.brand],
    queryFn: () =>
      api.products.list({
        category: product?.category || undefined,
        product_type: product?.product_type || undefined,
        brand: product?.brand || undefined,
        limit: 12,
      }),
    enabled: !!product,
    staleTime: 60_000,
  })

  const activeAlert = alerts?.items.find((alert) => alert.active) || null
  const latestPriceAmount = product?.latest_price?.price_amount ? parseFloat(product.latest_price.price_amount) : null
  const latestCurrency = product?.latest_price?.currency || null

  useEffect(() => {
    if (!activeAlert && latestPriceAmount !== null) {
      setAlertTarget((latestPriceAmount * 0.9).toFixed(2))
    }
  }, [activeAlert, latestPriceAmount, productId])

  const createAlertMutation = useMutation({
    mutationFn: () => {
      if (!latestCurrency || !alertTarget) {
        throw new Error('Current price is required before an alert can be created')
      }
      return createAlert(productId, parseFloat(alertTarget), latestCurrency)
    },
    onMutate: () => setAlertError(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['alerts', productId] })
    },
    onError: (error: Error) => {
      setAlertError(error.message)
    },
  })

  const deleteAlertMutation = useMutation({
    mutationFn: (alertId: string) => deleteAlert(alertId),
    onMutate: () => setAlertError(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['alerts', productId] })
    },
    onError: (error: Error) => {
      setAlertError(error.message)
    },
  })

  const sortedSimilar = useMemo(() => {
    const items = similarData?.items ?? []
    const currentPrice = latestPriceAmount
    return items
      .filter((item) => item.id !== productId)
      .sort((a, b) => {
        const aSameBrand = a.brand && product?.brand && a.brand === product.brand ? 1 : 0
        const bSameBrand = b.brand && product?.brand && b.brand === product.brand ? 1 : 0
        if (aSameBrand !== bSameBrand) return bSameBrand - aSameBrand

        const aSameType = a.product_type && product?.product_type && a.product_type === product.product_type ? 1 : 0
        const bSameType = b.product_type && product?.product_type && b.product_type === product.product_type ? 1 : 0
        if (aSameType !== bSameType) return bSameType - aSameType

        if (currentPrice === null) {
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        }

        const aPrice = a.latest_price?.price_amount ? parseFloat(a.latest_price.price_amount) : null
        const bPrice = b.latest_price?.price_amount ? parseFloat(b.latest_price.price_amount) : null
        const aDistance = aPrice === null ? Number.POSITIVE_INFINITY : Math.abs(aPrice - currentPrice)
        const bDistance = bPrice === null ? Number.POSITIVE_INFINITY : Math.abs(bPrice - currentPrice)
        return aDistance - bDistance
      })
      .slice(0, 6)
  }, [latestPriceAmount, product?.brand, product?.product_type, productId, similarData?.items])

  if (productLoading) {
    return (
      <div className="space-y-6">
        <div className="h-5 w-56 rounded bg-slate-800 animate-pulse" />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)]">
          <div className="space-y-6">
            <div className="h-96 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
            <ProductSkeletonGrid />
          </div>
          <div className="space-y-6">
            <div className="h-72 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
            <div className="h-72 rounded-3xl border border-slate-800 bg-slate-900/70 animate-pulse" />
          </div>
        </div>
      </div>
    )
  }

  if (productError || !product) {
    return (
      <div className="rounded-2xl border border-rose-800 bg-rose-950/40 p-4 text-rose-200">
        Failed to load product: {(productError as Error)?.message || 'Not found'}
      </div>
    )
  }

  const breadcrumbItems = [
    { label: 'Products', href: '/products' },
    { label: product.category === 'filament' ? 'Filament' : product.category === 'resin' ? 'Resin' : product.category },
    { label: product.product_type || product.brand || product.name },
  ]

  return (
    <div className="space-y-6">
      <Link to="/products" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft className="h-4 w-4" />
        Back to Products
      </Link>

      <Breadcrumbs items={breadcrumbItems} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)]">
        <div className="space-y-6">
          <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/80 shadow-lg shadow-black/20">
            <div className="grid gap-0 md:grid-cols-[220px_1fr]">
              <div className="border-b border-slate-800 bg-slate-950/60 md:border-b-0 md:border-r">
                <ProductMedia product={product} />
              </div>

              <div className="p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <CategoryBadge category={product.category} />
                  {product.product_type && (
                    <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-300">
                      {product.product_type}
                    </span>
                  )}
                  <MatchBadge confidence={product.confidence} />
                </div>

                <h1 className="mt-4 text-3xl font-semibold leading-tight text-slate-50">{product.name}</h1>
                {product.brand && <p className="mt-2 text-lg text-slate-400">{product.brand}</p>}

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {product.sku && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">SKU</div>
                      <div className="mt-1 font-mono text-sm text-slate-200">{product.sku}</div>
                    </div>
                  )}
                  {product.variant && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Variant</div>
                      <div className="mt-1 text-sm text-slate-200">{product.variant}</div>
                    </div>
                  )}
                  {product.color && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Color</div>
                      <div className="mt-1 text-sm text-slate-200">{product.color}</div>
                    </div>
                  )}
                  {product.size && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Size</div>
                      <div className="mt-1 text-sm text-slate-200">{product.size}</div>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <a
                    href={product.canonical_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-xl bg-violet-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-400"
                  >
                    View on {product.source_domain || 'store'}
                    <ExternalLink className="h-4 w-4" />
                  </a>
                  {product.latest_price?.in_stock !== null && (
                    <StockBadge inStock={product.latest_price?.in_stock ?? null} />
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Price history</p>
                <h2 className="text-xl font-semibold text-slate-50">Tracked price movement</h2>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs text-slate-400">
                {history?.observations?.length ?? 0} observations
              </span>
            </div>

            {historyLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
              </div>
            ) : history?.observations && history.observations.length > 0 ? (
              <div className="min-h-[420px]">
                <PriceHistoryChart
                  observations={history.observations}
                  currency={product.latest_price?.currency || history.observations[0]?.currency || 'USD'}
                />
              </div>
            ) : (
              <ProductEmptyState
                title="No observations yet"
                description="We will show price history here once the crawler has collected data for this product."
              />
            )}
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Price changes</p>
                <h2 className="text-xl font-semibold text-slate-50">Recent deltas</h2>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs text-slate-400">
                {history?.changes?.length ?? 0} changes
              </span>
            </div>

            {historyLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
              </div>
            ) : history?.changes && history.changes.length > 0 ? (
              <div className="space-y-3">
                {history.changes.map((change: PriceChange) => (
                  <div
                    key={change.id}
                    className="grid gap-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 lg:grid-cols-[minmax(0,1fr)_auto]"
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <ChangeTypeBadge type={change.change_type} percent={change.change_percent} />
                      <div>
                        <div className="text-sm text-slate-400 line-through">
                          {formatPrice(change.old_price, change.old_currency)}
                        </div>
                        <div className="font-mono text-base font-semibold text-slate-50">
                          {formatPrice(change.new_price, change.new_currency)}
                        </div>
                      </div>
                    </div>
                    <div className="text-sm text-slate-400 lg:text-right">
                      {format(new Date(change.changed_at), 'MMM d, yyyy HH:mm')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <ProductEmptyState
                title="No price changes recorded"
                description="The product is being tracked, but no price deltas have been detected yet."
              />
            )}
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Similar products</p>
                <h2 className="text-xl font-semibold text-slate-50">More like this</h2>
              </div>
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs text-slate-400">
                {similarLoading ? 'Loading...' : `${sortedSimilar.length} suggestions`}
              </span>
            </div>

            {similarLoading ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <ProductSkeletonGrid />
              </div>
            ) : sortedSimilar.length > 0 ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {sortedSimilar.map((item, index) => (
                  <SimilarProductCard key={item.id} product={item} highlight={index === 0} />
                ))}
              </div>
            ) : (
              <ProductEmptyState
                title="No close matches yet"
                description="We could not find similar items in the current catalog using the same category and type."
              />
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Current price</p>
                <h2 className="text-xl font-semibold text-slate-50">Live snapshot</h2>
              </div>
              {product.latest_price?.in_stock !== null && <StockBadge inStock={product.latest_price?.in_stock ?? null} />}
            </div>

            {product.latest_price ? (
              <div className="mt-5 space-y-4">
                <div className="font-mono text-4xl font-semibold text-slate-50">
                  {formatPrice(product.latest_price.price_amount, product.latest_price.currency)}
                </div>

                {product.price_per_kg != null && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                    <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Price per kg</div>
                    <div className="mt-1 font-mono text-lg text-slate-100">
                      {formatNumberCurrency(product.price_per_kg, product.latest_price.currency)}
                    </div>
                  </div>
                )}

                {product.latest_price.list_price_amount &&
                  product.latest_price.list_price_amount !== product.latest_price.price_amount && (
                    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                      <div className="text-xs uppercase tracking-[0.24em] text-slate-500">List price</div>
                      <div className="mt-1 font-mono text-base text-slate-400 line-through">
                        {formatPrice(product.latest_price.list_price_amount, product.latest_price.currency)}
                      </div>
                    </div>
                  )}

                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                  <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Last updated</div>
                  <div className="mt-1 text-sm text-slate-200">
                    {formatDistanceToNow(new Date(product.latest_price.observed_at), { addSuffix: true })}
                  </div>
                </div>
              </div>
            ) : (
              <ProductEmptyState
                title="No price data"
                description="This product has not been observed with a live price yet."
              />
            )}
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Price alert</p>
                <h2 className="text-xl font-semibold text-slate-50">Set a threshold</h2>
              </div>
              <Info className="h-4 w-4 text-slate-500" />
            </div>

            {alertError && (
              <div className="mb-4 rounded-2xl border border-rose-700 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
                {alertError}
              </div>
            )}

            {activeAlert ? (
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Active threshold</div>
                  <div className="mt-1 font-mono text-lg font-semibold text-slate-50">
                    {formatPrice(activeAlert.target_price, activeAlert.currency)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => deleteAlertMutation.mutate(activeAlert.id)}
                  disabled={deleteAlertMutation.isPending}
                  className="rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-800 disabled:opacity-50"
                >
                  {deleteAlertMutation.isPending ? 'Removing...' : 'Remove alert'}
                </button>
              </div>
            ) : latestPriceAmount !== null && latestCurrency ? (
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <label className="mb-1 block text-xs uppercase tracking-[0.24em] text-slate-500">Target price</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={alertTarget}
                      onChange={(e) => setAlertTarget(e.currentTarget.value)}
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2.5 font-mono text-slate-100 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                    />
                    <span className="text-sm text-slate-400">{latestCurrency}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => createAlertMutation.mutate()}
                  disabled={!alertTarget || createAlertMutation.isPending}
                  className="rounded-xl bg-violet-500 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-400 disabled:opacity-50"
                >
                  {createAlertMutation.isPending ? 'Setting...' : 'Set alert'}
                </button>
              </div>
            ) : (
              <ProductEmptyState
                title="Alerts need a price"
                description="Create an alert once the product has a recorded price."
              />
            )}
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg shadow-black/20">
            <h2 className="text-xl font-semibold text-slate-50">Details</h2>
            <dl className="mt-4 space-y-4 text-sm">
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                <dt className="text-slate-500">Confidence</dt>
                <dd className="font-medium text-slate-200">{Math.round(product.confidence * 100)}%</dd>
              </div>
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                <dt className="text-slate-500">First seen</dt>
                <dd className="font-medium text-slate-200">{format(new Date(product.created_at), 'MMM d, yyyy')}</dd>
              </div>
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                <dt className="text-slate-500">Last seen</dt>
                <dd className="font-medium text-slate-200">
                  {product.last_seen_at
                    ? formatDistanceToNow(new Date(product.last_seen_at), { addSuffix: true })
                    : 'Never'}
                </dd>
              </div>
              {product.gtin && (
                <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                  <dt className="text-slate-500">GTIN</dt>
                  <dd className="font-mono font-medium text-slate-200">{product.gtin}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
