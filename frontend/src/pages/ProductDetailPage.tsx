import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Loader2, TrendingUp, TrendingDown, Minus, Package } from 'lucide-react'
import { api, createAlert, deleteAlert, listAlerts, PriceChange } from '../api'
import { format, formatDistanceToNow } from 'date-fns'
import PriceHistoryChart from '../components/PriceHistoryChart'

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

function ChangeIcon({ type }: { type: string }) {
  if (type === 'price_decrease') {
    return <TrendingDown className="w-4 h-4 text-green-600" />
  }
  if (type === 'price_increase') {
    return <TrendingUp className="w-4 h-4 text-red-600" />
  }
  return <Minus className="w-4 h-4 text-gray-400" />
}

function ChangeTypeBadge({ type, percent }: { type: string; percent: number | null }) {
  const styles: Record<string, string> = {
    price_decrease: 'bg-green-900 text-green-300',
    price_increase: 'bg-red-900 text-red-300',
    price_change: 'bg-blue-900 text-blue-300',
    price_removed: 'bg-gray-700 text-gray-300',
    price_added: 'bg-purple-900 text-purple-300',
  }
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${styles[type] || styles.price_change}`}>
      <ChangeIcon type={type} />
      {percent !== null ? `${percent > 0 ? '+' : ''}${percent.toFixed(1)}%` : type.replace('_', ' ')}
    </span>
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
  
  if (productLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }
  
  if (productError || !product) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load product: {(productError as Error)?.message || 'Not found'}
      </div>
    )
  }
  
  return (
    <div>
      <Link
        to="/products"
        className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-200 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Products
      </Link>
      
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <div className="md:flex">
              <div className="md:w-1/3 bg-gray-900 p-4">
                {product.image_url ? (
                  <img
                    src={product.image_url}
                    alt={product.name}
                    className="w-full h-48 object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <div className="w-full h-48 flex items-center justify-center">
                    <Package className="w-16 h-16 text-gray-700" />
                  </div>
                )}
              </div>
              
              <div className="p-6 flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      product.category === 'filament' ? 'bg-purple-900 text-purple-300' : 'bg-amber-900 text-amber-300'
                    }`}>
                      {product.category}
                      {product.product_type && ` - ${product.product_type}`}
                    </span>
                    <h1 className="text-2xl font-bold text-gray-100 mt-2">{product.name}</h1>
                    {product.brand && (
                      <p className="text-gray-400 mt-1">{product.brand}</p>
                    )}
                  </div>
                </div>
                
                <div className="mt-4 grid grid-cols-2 gap-4">
                  {product.sku && (
                    <div>
                      <span className="text-sm text-gray-500">SKU</span>
                      <p className="font-medium text-gray-200">{product.sku}</p>
                    </div>
                  )}
                  {product.variant && (
                    <div>
                      <span className="text-sm text-gray-500">Variant</span>
                      <p className="font-medium text-gray-200">{product.variant}</p>
                    </div>
                  )}
                  {product.color && (
                    <div>
                      <span className="text-sm text-gray-500">Color</span>
                      <p className="font-medium text-gray-200">{product.color}</p>
                    </div>
                  )}
                  {product.size && (
                    <div>
                      <span className="text-sm text-gray-500">Size</span>
                      <p className="font-medium text-gray-200">{product.size}</p>
                    </div>
                  )}
                </div>
                
                <div className="mt-6 pt-4 border-t border-gray-700">
                  <a
                    href={product.canonical_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300"
                  >
                    View on {product.source_domain || 'store'}
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Price Changes</h2>
            
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              </div>
            ) : history?.changes && history.changes.length > 0 ? (
              <div className="space-y-3">
                {history.changes.map((change: PriceChange) => (
                  <div
                    key={change.id}
                    className="flex items-center justify-between p-3 bg-gray-900 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <ChangeTypeBadge type={change.change_type} percent={change.change_percent} />
                      <div>
                        <span className="text-gray-500 line-through mr-2">
                          {formatPrice(change.old_price, change.old_currency)}
                        </span>
                        <span className="font-medium text-gray-200">
                          {formatPrice(change.new_price, change.new_currency)}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm text-gray-400">
                      {format(new Date(change.changed_at), 'MMM d, yyyy HH:mm')}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">No price changes recorded yet</p>
            )}
          </div>
        </div>
        
        <div className="space-y-6">
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Current Price</h2>
            
            {product.latest_price ? (
              <div>
                <div className="text-3xl font-bold text-gray-100">
                  {formatPrice(product.latest_price.price_amount, product.latest_price.currency)}
                </div>

                {product.price_per_kg != null && (
                  <div className="text-sm text-gray-400 mt-1">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: product.latest_price.currency || 'USD' }).format(product.price_per_kg)}/kg
                  </div>
                )}

                {product.latest_price.list_price_amount &&
                 product.latest_price.list_price_amount !== product.latest_price.price_amount && (
                  <div className="text-lg text-gray-500 line-through mt-1">
                    {formatPrice(product.latest_price.list_price_amount, product.latest_price.currency)}
                  </div>
                )}
                
                <div className="mt-4">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    product.latest_price.in_stock === true
                      ? 'bg-green-900 text-green-300'
                      : product.latest_price.in_stock === false
                      ? 'bg-red-900 text-red-300'
                      : 'bg-gray-700 text-gray-300'
                  }`}>
                    {product.latest_price.in_stock === true
                      ? 'In Stock'
                      : product.latest_price.in_stock === false
                      ? 'Out of Stock'
                      : 'Unknown'}
                  </span>
                </div>
                
                <p className="text-sm text-gray-500 mt-4">
                  Last updated {formatDistanceToNow(new Date(product.latest_price.observed_at), { addSuffix: true })}
                </p>
              </div>
            ) : (
              <p className="text-gray-500">No price data available</p>
            )}
          </div>
          
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Price History</h2>
            
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              </div>
            ) : history?.observations && history.observations.length > 0 ? (
              <PriceHistoryChart
                observations={history.observations}
                currency={product.latest_price?.currency || history.observations[0]?.currency || 'USD'}
              />
            ) : (
              <p className="text-gray-500 text-center py-4">No observations yet</p>
            )}
          </div>

          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Set Price Alert</h2>

            {alertError && (
              <div className="mb-4 rounded-lg bg-red-900/40 border border-red-700 px-3 py-2 text-sm text-red-200">
                {alertError}
              </div>
            )}

            {activeAlert ? (
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm text-gray-400">Active threshold</div>
                  <div className="text-lg font-semibold text-gray-100">
                    {formatPrice(activeAlert.target_price, activeAlert.currency)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => deleteAlertMutation.mutate(activeAlert.id)}
                  disabled={deleteAlertMutation.isPending}
                  className="px-3 py-2 rounded-lg bg-gray-700 text-gray-200 hover:bg-gray-600 disabled:opacity-50"
                >
                  {deleteAlertMutation.isPending ? 'Removing...' : 'Remove alert'}
                </button>
              </div>
            ) : latestPriceAmount !== null && latestCurrency ? (
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <label className="block text-sm text-gray-400 mb-1">Target price</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={alertTarget}
                      onChange={(e) => setAlertTarget(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-100"
                    />
                    <span className="text-sm text-gray-400">{latestCurrency}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => createAlertMutation.mutate()}
                  disabled={!alertTarget || createAlertMutation.isPending}
                  className="px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createAlertMutation.isPending ? 'Setting...' : 'Set alert'}
                </button>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Price alerts become available once this product has a recorded price.</p>
            )}
          </div>
          
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Details</h2>
            
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Confidence</dt>
                <dd className="font-medium text-gray-200">{Math.round(product.confidence * 100)}%</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">First seen</dt>
                <dd className="font-medium text-gray-200">
                  {format(new Date(product.created_at), 'MMM d, yyyy')}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Last seen</dt>
                <dd className="font-medium text-gray-200">
                  {product.last_seen_at
                    ? formatDistanceToNow(new Date(product.last_seen_at), { addSuffix: true })
                    : 'Never'}
                </dd>
              </div>
              {product.gtin && (
                <div className="flex justify-between">
                  <dt className="text-gray-500">GTIN</dt>
                  <dd className="font-medium text-gray-200">{product.gtin}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
