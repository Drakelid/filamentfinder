import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { TrendingUp, TrendingDown, Loader2, Package, Filter, ArrowRightLeft, ExternalLink, ChevronDown, ChevronUp, Sparkles, Clock8, Link2, Tag, X, LineChart, Ship, Settings2 } from 'lucide-react'
import { api, Product, CrossSourceGroup, TypeSummary, VariantSummary, Source, PriceObservation, PriceChange } from '../api'
import { formatDistanceToNow } from 'date-fns'

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

type ComparisonProduct = CrossSourceGroup['products'][number]
type ComparisonLatestPrice = ComparisonProduct['latest_price']

type PriceBreakdown = {
  base: number | null
  shipping: number | null
  total: number | null
  currency: string | null
  shippingSource: 'actual' | 'derived' | 'unknown'
}

type BrandCheapest = {
  brand: string
  product: ComparisonProduct
  price: number
  currency: string | null
  breakdown: PriceBreakdown
}

type WeightInfo = {
  label: string
  grams: number
}

type WeightBucket = {
  key: string
  label: string
  grams: number | null
  products: ComparisonProduct[]
}

type BrandGroup = {
  brand: string
  products: ComparisonProduct[]
  minPrice: number | null
  maxPrice: number | null
}

type ProductHistoryResponse = {
  observations: PriceObservation[]
  changes: PriceChange[]
  total_observations: number
  total_changes: number
}

type WeightComparable = {
  name: string
  size: string | null
  variant?: string | null
}

const WEIGHT_PATTERNS: { regex: RegExp; multiplier: number }[] = [
  { regex: /([0-9]+(?:[.,][0-9]+)?)\s*(?:kg|kilogram|kilo)\b/, multiplier: 1000 },
  { regex: /([0-9]+(?:[.,][0-9]+)?)\s*(?:g|gram|grams)\b/, multiplier: 1 },
  { regex: /\(([0-9]+(?:[.,][0-9]+)?)\s*kg\)/, multiplier: 1000 },
  { regex: /\(([0-9]{3,4})\s*g?\)/, multiplier: 1 },
  { regex: /([0-9]{3,4})\s*g\b/, multiplier: 1 },
  { regex: /\b(250|500|750|1000|2000|3000)\b/, multiplier: 1 },
]

const WEIGHT_BUCKETS = [
  { min: 200, max: 400, grams: 250, label: '250g' },
  { min: 400, max: 650, grams: 500, label: '500g' },
  { min: 650, max: 900, grams: 750, label: '750g' },
  { min: 900, max: 1200, grams: 1000, label: '1000g' },
  { min: 1700, max: 2500, grams: 2000, label: '2000g' },
  { min: 2500, max: 3500, grams: 3000, label: '3000g' },
]

const WEIGHT_FILTER_OPTIONS = [
  { value: '', label: 'All weights' },
  ...WEIGHT_BUCKETS.map((bucket) => ({ value: bucket.label, label: bucket.label })),
  { value: 'unknown', label: 'Unknown weight' },
]

function normalizeWeight(grams: number): WeightInfo {
  for (const bucket of WEIGHT_BUCKETS) {
    if (grams >= bucket.min && grams <= bucket.max) {
      return { label: bucket.label, grams: bucket.grams }
    }
  }
  return { label: `${grams}g`, grams }
}

function parseWeightFromText(text?: string | null): WeightInfo | null {
  if (!text) return null
  const lower = text.toLowerCase()
  for (const { regex, multiplier } of WEIGHT_PATTERNS) {
    const match = lower.match(regex)
    if (match && match[1]) {
      const value = parseFloat(match[1].replace(',', '.'))
      if (!isNaN(value)) {
        const grams = Math.round(value * multiplier)
        if (grams >= 50 && grams <= 10000) {
          return normalizeWeight(grams)
        }
      }
    }
  }
  return null
}

function getProductWeight(product: WeightComparable): WeightInfo | null {
  return parseWeightFromText(product.size) 
    || parseWeightFromText(product.variant) 
    || parseWeightFromText(product.name)
}

function getProductWeightKey(product: WeightComparable): string {
  const weight = getProductWeight(product)
  return weight ? weight.label : 'unknown'
}

function matchesWeightFilter(product: WeightComparable, weightFilter: string): boolean {
  if (!weightFilter) return true
  return getProductWeightKey(product) === weightFilter
}

function filterProductsByWeight(products: ComparisonProduct[], weightFilter: string): ComparisonProduct[] {
  if (!weightFilter) return products
  return products.filter((product) => matchesWeightFilter(product, weightFilter))
}

function getDeliveredPrice(latest: ComparisonLatestPrice | null | undefined, extraFee = 0): number | null {
  if (!latest) return null
  if (latest.total_amount !== null && latest.total_amount !== undefined) {
    return latest.total_amount + extraFee
  }
  if (latest.amount === null || latest.amount === undefined) {
    return null
  }
  const shipping = latest.shipping_amount ?? 0
  return latest.amount + shipping + extraFee
}

function getPriceBreakdown(latest: ComparisonLatestPrice | null | undefined, extraFee = 0) {
  const base = latest?.amount ?? null
  const total = getDeliveredPrice(latest, extraFee)
  const shippingRaw = latest?.shipping_amount
  const hasActualShipping = shippingRaw !== null && shippingRaw !== undefined
  let shippingSource: PriceBreakdown['shippingSource'] = hasActualShipping ? 'actual' : 'unknown'
  let shipping: number | null = hasActualShipping ? shippingRaw! : null

  if (!hasActualShipping && total !== null && base !== null) {
    const derived = total - base
    if (Number.isFinite(derived) && Math.abs(derived) > 0.01) {
      shipping = derived
      shippingSource = 'derived'
    }
  }

  if (shipping !== null && extraFee) {
    shipping += extraFee
    if (shippingSource === 'unknown') {
      shippingSource = 'derived'
    }
  }

  return {
    base,
    shipping,
    total,
    currency: latest?.shipping_currency || latest?.currency || 'NOK',
    shippingSource,
  }
}

function formatShippingDisplay(breakdown: PriceBreakdown): string {
  if (breakdown.shipping === null) {
    return '—'
  }
  if (breakdown.shippingSource === 'derived') {
    return `Est. ${formatPriceNum(breakdown.shipping, breakdown.currency)}`
  }
  if (breakdown.shipping === 0) {
    return 'Free'
  }
  return formatPriceNum(breakdown.shipping, breakdown.currency)
}

function bucketProductsByWeight(products: ComparisonProduct[]): WeightBucket[] {
  const buckets = new Map<string, WeightBucket>()
  products.forEach(product => {
    const weightInfo = getProductWeight(product)
    const key = weightInfo ? weightInfo.label : 'unknown'
    if (!buckets.has(key)) {
      buckets.set(key, {
        key,
        label: weightInfo ? weightInfo.label : 'Unknown weight',
        grams: weightInfo?.grams ?? null,
        products: [],
      })
    }
    buckets.get(key)!.products.push(product)
  })

  return Array.from(buckets.values()).sort((a, b) => {
    if (a.grams === null && b.grams === null) return a.label.localeCompare(b.label)
    if (a.grams === null) return 1
    if (b.grams === null) return -1
    return a.grams - b.grams
  })
}

function buildBrandGroups(products: ComparisonProduct[], shippingFees: Record<number, number>): BrandGroup[] {
  const map = new Map<string, ComparisonProduct[]>()
  products.forEach(product => {
    const brand = (product.brand?.trim() || 'Unknown Brand')
    if (!map.has(brand)) {
      map.set(brand, [])
    }
    map.get(brand)!.push(product)
  })

  return Array.from(map.entries())
    .map(([brand, items]) => {
      const sortedProducts = [...items].sort((a, b) => (
        (getDeliveredPrice(a.latest_price, shippingFees[a.source_id] || 0) ?? Infinity) -
        (getDeliveredPrice(b.latest_price, shippingFees[b.source_id] || 0) ?? Infinity)
      ))
      const priceValues = sortedProducts
        .map(p => getDeliveredPrice(p.latest_price, shippingFees[p.source_id] || 0))
        .filter((value): value is number => typeof value === 'number')
      const minPrice = priceValues.length ? Math.min(...priceValues) : null
      const maxPrice = priceValues.length ? Math.max(...priceValues) : null
      return { brand, products: sortedProducts, minPrice, maxPrice }
    })
    .sort((a, b) => a.brand.localeCompare(b.brand))
}

function formatWeightBucketLabel(bucket: WeightBucket): string {
  if (bucket.grams === null) return bucket.label
  if (bucket.grams >= 1000) {
    const kg = bucket.grams / 1000
    return `${Number.isInteger(kg) ? kg : kg.toFixed(1)} kg spools`
  }
  return `${bucket.grams} g spools`
}

function collectProductsFromType(typeSummary: TypeSummary, weightFilter = ''): ComparisonProduct[] {
  const groups = typeSummary.variants && typeSummary.variants.length > 0
    ? typeSummary.variants.flatMap((variant) => variant.groups)
    : typeSummary.groups
  const products = groups.flatMap((group) => group.products)
  return filterProductsByWeight(products, weightFilter)
}

function getCheapestBrandListings(typeSummary: TypeSummary, weightFilter = '', shippingFees: Record<number, number>): BrandCheapest[] {
  const brandMap = new Map<string, BrandCheapest>()
  const products = collectProductsFromType(typeSummary, weightFilter)

  products.forEach((product) => {
    const fee = shippingFees[product.source_id] || 0
    const breakdown = getPriceBreakdown(product.latest_price, fee)
    const price = breakdown.total
    if (price === null || price === undefined) {
      return
    }
    const brandKey = (product.brand?.trim() || 'Unknown Brand').toLowerCase()
    const existing = brandMap.get(brandKey)
    if (!existing || price < existing.price) {
      brandMap.set(brandKey, {
        brand: product.brand?.trim() || 'Unknown Brand',
        product,
        price,
        currency: breakdown.currency || 'NOK',
        breakdown,
      })
    }
  })

  return Array.from(brandMap.values()).sort((a, b) => a.price - b.price)
}

function getTypeMeta(typeSummary: TypeSummary, weightFilter = '', shippingFees: Record<number, number> = {}) {
  const products = collectProductsFromType(typeSummary, weightFilter)
  const sourceCount = new Set(products.map((p) => p.source_id)).size
  const observationTimes = products
    .map((product) => product.latest_price?.observed_at ? new Date(product.latest_price.observed_at).getTime() : null)
    .filter((time): time is number => time !== null)
  const latestObservation = observationTimes.length ? new Date(Math.max(...observationTimes)) : null
  const priceValues = products
    .map((product) => getDeliveredPrice(product.latest_price, shippingFees[product.source_id] || 0))
    .filter((value): value is number => typeof value === 'number')
  const minPrice = priceValues.length ? Math.min(...priceValues) : null
  const maxPrice = priceValues.length ? Math.max(...priceValues) : null
  const priceSpread = minPrice !== null && maxPrice !== null && minPrice > 0
    ? ((maxPrice - minPrice) / minPrice) * 100
    : null
  return { sourceCount, latestObservation, priceSpread, minPrice, maxPrice }
}

function ChangeTypeBadge({ type, percent }: { type: string | null; percent: number | null }) {
  if (!type) return null
  
  const isDecrease = type === 'price_decrease'
  const isIncrease = type === 'price_increase'
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
      isDecrease ? 'bg-green-900 text-green-300' : 
      isIncrease ? 'bg-red-900 text-red-300' : 
      'bg-gray-700 text-gray-300'
    }`}>
      {isDecrease && <TrendingDown className="w-3 h-3" />}
      {isIncrease && <TrendingUp className="w-3 h-3" />}
      {percent !== null ? `${percent > 0 ? '+' : ''}${percent.toFixed(1)}%` : type.replace('_', ' ')}
    </span>
  )
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

function formatPriceNum(amount: number | null, currency: string | null): string {
  if (amount === null) return '-'
  const curr = currency || 'NOK'
  try {
    return new Intl.NumberFormat('nb-NO', { style: 'currency', currency: curr }).format(amount)
  } catch {
    return `${curr} ${amount.toFixed(2)}`
  }
}

function ComparisonGroup({
  group,
  isExpanded,
  onToggle,
  shippingFees,
  onInspect,
}: {
  group: CrossSourceGroup
  isExpanded: boolean
  onToggle: () => void
  shippingFees: Record<number, number>
  onInspect: (product: ComparisonProduct) => void
}) {
  const decoratedProducts = group.products.map((product) => {
    const extra = shippingFees[product.source_id] || 0
    const breakdown = getPriceBreakdown(product.latest_price, extra)
    return {
      product,
      breakdown,
      delivered: getDeliveredPrice(product.latest_price, extra),
    }
  })
  const sortedProducts = [...decoratedProducts].sort((a, b) => (
    (a.delivered ?? Infinity) - (b.delivered ?? Infinity)
  ))
  const priceValues = sortedProducts
    .map(({ delivered }) => delivered)
    .filter((value): value is number => typeof value === 'number')
  const minPrice = priceValues.length ? Math.min(...priceValues) : null
  const maxPrice = priceValues.length ? Math.max(...priceValues) : null
  const savings = minPrice !== null && maxPrice !== null ? maxPrice - minPrice : null
  
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gray-900 rounded-lg flex-shrink-0 overflow-hidden">
            {group.products[0]?.image_url ? (
              <img
                src={group.products[0].image_url}
                alt=""
                className="w-full h-full object-contain"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="w-5 h-5 text-gray-700" />
              </div>
            )}
          </div>
          <div className="text-left">
            <div className="font-medium text-gray-100 line-clamp-1">
              {group.display_name || group.products[0]?.name?.slice(0, 50)}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>{group.source_count} sources • {group.products.length} listings</span>
              {group.match_type === 'gtin' && (
                <span className="px-1.5 py-0.5 bg-green-900/50 text-green-400 rounded text-xs">GTIN match</span>
              )}
              {group.match_type === 'sku' && (
                <span className="px-1.5 py-0.5 bg-blue-900/50 text-blue-400 rounded text-xs">SKU match</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-sm text-gray-400">Price range</div>
            <div className="font-medium text-gray-100">
              {formatPriceNum(minPrice, 'NOK')} - {formatPriceNum(maxPrice, 'NOK')}
            </div>
          </div>
          {group.price_spread !== null && group.price_spread > 0 && (
            <div className="px-2 py-1 bg-green-900/50 text-green-300 rounded text-sm font-medium">
              {group.price_spread.toFixed(0)}% spread
            </div>
          )}
          {savings !== null && savings > 0 && (
            <div className="px-2 py-1 bg-blue-900/50 text-blue-300 rounded text-sm font-medium">
              Save {formatPriceNum(savings, 'NOK')}
            </div>
          )}
          {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-500" /> : <ChevronDown className="w-5 h-5 text-gray-500" />}
        </div>
      </button>
      
      {isExpanded && (
        <div className="border-t border-gray-700">
          <table className="w-full">
            <thead className="bg-gray-900/50">
              <tr>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-400">Store</th>
                <th className="text-left px-4 py-2 text-xs font-medium text-gray-400">Product</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-gray-400">Price</th>
                <th className="text-center px-4 py-2 text-xs font-medium text-gray-400">Stock</th>
                <th className="text-right px-4 py-2 text-xs font-medium text-gray-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/50">
              {sortedProducts.map(({ product, breakdown }, idx) => {
                return (
                  <tr key={product.id} className={idx === 0 ? 'bg-green-900/10' : ''}>
                    <td className="px-4 py-2">
                      <div className="font-medium text-gray-200">{product.source_name}</div>
                      <div className="text-xs text-gray-500">{product.source_domain}</div>
                    </td>
                    <td className="px-4 py-2">
                      <Link to={`/products/${product.id}`} className="text-gray-300 hover:text-blue-400 line-clamp-1">
                        {product.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-right">
                    <span className={`font-medium ${idx === 0 ? 'text-green-400' : 'text-gray-100'}`}>
                      {formatPriceNum(breakdown.total, breakdown.currency)}
                    </span>
                    <div className="text-xxs text-slate-500">
                      Base {breakdown.base !== null ? formatPriceNum(breakdown.base, breakdown.currency) : '—'} • Ship {formatShippingDisplay(breakdown)}
                    </div>
                    {idx === 0 && group.products.length > 1 && (
                      <div className="text-xs text-green-500">Lowest</div>
                    )}
                  </td>
                    <td className="px-4 py-2 text-center">
                    {product.latest_price?.in_stock === true && (
                      <span className="text-green-400 text-xs">In Stock</span>
                    )}
                    {product.latest_price?.in_stock === false && (
                      <span className="text-red-400 text-xs">Out of Stock</span>
                    )}
                    {product.latest_price?.in_stock === null && (
                      <span className="text-gray-500 text-xs">-</span>
                    )}
                  </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => onInspect(product)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full border border-emerald-500/40 text-emerald-300 hover:border-emerald-300"
                        >
                          Inspect
                        </button>
                        <a
                          href={product.canonical_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-500 hover:text-blue-400"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <InspectorPanel
        product={inspectorProduct}
        shippingFee={inspectorProduct ? shippingFees[inspectorProduct.source_id] || 0 : 0}
        history={inspectorHistory}
        isLoading={inspectorHistoryLoading}
        onClose={closeInspector}
        onOpenProduct={() => {
          if (inspectorProduct) {
            navigate(`/products/${inspectorProduct.id}`)
          }
        }}
        onOpenShipping={() => {
          if (inspectorProduct) {
            navigate(`/shipping?source=${inspectorProduct.source_id}`)
          } else {
            navigate('/shipping')
          }
        }}
      />
    </div>
  )
}

type InspectorPanelProps = {
  product: ComparisonProduct | null
  shippingFee: number
  history?: ProductHistoryResponse
  isLoading: boolean
  onClose: () => void
  onOpenProduct: () => void
  onOpenShipping: () => void
}

function InspectorPanel({ product, shippingFee, history, isLoading, onClose, onOpenProduct, onOpenShipping }: InspectorPanelProps) {
  if (!product) return null

  const breakdown = getPriceBreakdown(product.latest_price, shippingFee)
  const scrapedShipping = product.latest_price?.shipping_amount ?? null
  const observations = history?.observations ?? []
  const plottedValues = observations
    .map((obs) => (obs.price_amount ? Number.parseFloat(obs.price_amount) : null))
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
  const recentValues = plottedValues.slice(-20)
  const sparkWidth = 240
  const sparkHeight = 80
  let sparkPath = ''
  if (recentValues.length >= 2) {
    const min = Math.min(...recentValues)
    const max = Math.max(...recentValues)
    const range = max - min || 1
    const coords = recentValues.map((value, index) => {
      const x = (index / (recentValues.length - 1)) * sparkWidth
      const y = sparkHeight - ((value - min) / range) * sparkHeight
      return `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
    })
    sparkPath = coords.join(' ')
  }

  const latestObservation = product.latest_price?.observed_at
    ? formatDistanceToNow(new Date(product.latest_price.observed_at), { addSuffix: true })
    : 'Unknown'
  const latestChange = history?.changes?.[0]

  return (
    <>
      <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-slate-950/95 border-l border-slate-800 z-50 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Inspector</p>
              <h2 className="text-2xl font-semibold text-white leading-snug">{product.name}</h2>
              <p className="text-sm text-slate-400 mt-1">{product.source_name} • {product.source_domain}</p>
            </div>
            <button onClick={onClose} className="p-2 rounded-full bg-slate-900/70 border border-slate-800 text-slate-300 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Total price</p>
                <p className="text-3xl font-semibold text-white">{formatPriceNum(breakdown.total, breakdown.currency)}</p>
              </div>
              <div className="text-right text-sm text-slate-400">
                <div>Base {formatPriceNum(breakdown.base, breakdown.currency)}</div>
                <div>Shipping {formatShippingDisplay(breakdown)}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm text-slate-400">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Observed</p>
                <p>{latestObservation}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Stock</p>
                <p>{product.latest_price?.in_stock === true ? 'In stock' : product.latest_price?.in_stock === false ? 'Out of stock' : 'Unknown'}</p>
              </div>
            </div>
          </div>

          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-300">
                <LineChart className="w-4 h-4" />
                <span className="text-sm font-semibold">Price trend</span>
              </div>
              <span className="text-xs text-slate-500">Last {recentValues.length || 0} obs</span>
            </div>
            {isLoading ? (
              <div className="h-20 flex items-center justify-center text-slate-500">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            ) : sparkPath ? (
              <svg viewBox={`0 0 ${sparkWidth} ${sparkHeight}`} className="w-full h-20 text-emerald-400">
                <path d={sparkPath} fill="none" stroke="currentColor" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
              </svg>
            ) : (
              <div className="text-sm text-slate-500">Not enough data yet</div>
            )}
            {latestChange && (
              <div className="text-xs text-slate-400">
                Last change {formatDistanceToNow(new Date(latestChange.changed_at), { addSuffix: true })}
                {latestChange.change_percent !== null && (
                  <span className="ml-1 text-slate-300">
                    ({latestChange.change_percent > 0 ? '+' : ''}{latestChange.change_percent.toFixed(2)}%)
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-4 space-y-4">
            <div className="flex items-center gap-2 text-slate-300">
              <Ship className="w-4 h-4" />
              <span className="text-sm font-semibold">Shipping inputs</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm text-slate-300">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Manual fee</p>
                <p className="text-lg text-white">{shippingFee ? formatPriceNum(shippingFee, breakdown.currency) : '—'}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Scraped shipping</p>
                <p className="text-lg text-white">{scrapedShipping !== null ? formatPriceNum(scrapedShipping, breakdown.currency) : 'Unknown'}</p>
              </div>
            </div>
            <div className="text-xs text-slate-500">
              Shipping display uses stored fee + scraped result. Adjust manual fee to reflect packing or courier surcharges.
            </div>
          </div>

          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-4 space-y-3">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Quick actions</p>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={onOpenProduct}
                className="flex items-center gap-2 px-4 py-2 rounded-2xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-500"
              >
                View detail
              </button>
              <button
                onClick={onOpenShipping}
                className="flex items-center gap-2 px-4 py-2 rounded-2xl border border-slate-700 text-sm text-slate-200 hover:border-slate-500"
              >
                <Settings2 className="w-4 h-4" />
                Edit shipping fee
              </button>
              <a
                href={product.canonical_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-2xl border border-slate-700 text-sm text-slate-200 hover:border-slate-500"
              >
                Visit store
              </a>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

const QUICK_FILTER_TYPES = ['pla', 'petg', 'abs', 'asa', 'tpu', 'nylon']

export default function PriceChangesPage() {
  const navigate = useNavigate()
  const [changeType, setChangeType] = useState<string>('')
  const [category, setCategory] = useState<string>('')
  const [days, setDays] = useState<number>(7)
  const [activeTab, setActiveTab] = useState<'changes' | 'compare'>('changes')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set())
  const [selectedType, setSelectedType] = useState<string>('')
  const [weightFilter, setWeightFilter] = useState<string>('')
  const [expandedVariantDetails, setExpandedVariantDetails] = useState<Set<string>>(new Set())
  const [expandedWeightBuckets, setExpandedWeightBuckets] = useState<Set<string>>(new Set())
  const [inspectorProduct, setInspectorProduct] = useState<ComparisonProduct | null>(null)
  const defaultDays = 7
  const hasActiveFilters =
    changeType !== '' ||
    category !== '' ||
    days !== defaultDays ||
    selectedType !== '' ||
    weightFilter !== ''

  const resetFilters = () => {
    setChangeType('')
    setCategory('')
    setDays(defaultDays)
    setSelectedType('')
    setWeightFilter('')
  }
  
  useEffect(() => {
    if (!inspectorProduct) return
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setInspectorProduct(null)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [inspectorProduct])

  const { data, isLoading, error } = useQuery({
    queryKey: ['products-with-changes', { changeType, category, days }],
    queryFn: () => api.products.withChanges({ 
      change_type: changeType || undefined, 
      category: category || undefined,
      days,
    }),
    refetchInterval: 30000,
  })
  
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: api.sources.list,
    staleTime: 60000,
  })

  const shippingFees = useMemo(() => {
    const map: Record<number, number> = {}
    sourcesData?.items.forEach((source: Source) => {
      if (source.shipping_fee !== null && source.shipping_fee !== undefined && source.shipping_fee !== '') {
        const numeric = Number(source.shipping_fee)
        if (!Number.isNaN(numeric)) {
          map[source.id] = numeric
        }
      }
    })
    return map
  }, [sourcesData])

  const { data: comparisonData, isLoading: comparisonLoading } = useQuery({
    queryKey: ['cross-source-comparison', { category }],
    queryFn: () => api.products.crossSourceComparison({ 
      category: category || undefined,
      limit: 50,
    }),
    enabled: activeTab === 'compare',
    refetchInterval: 60000,
  })

  const { data: inspectorHistory, isLoading: inspectorHistoryLoading } = useQuery<ProductHistoryResponse>({
    queryKey: ['product-history', inspectorProduct?.id],
    queryFn: () => api.products.history(inspectorProduct!.id),
    enabled: !!inspectorProduct,
    staleTime: 60000,
  })

  const openInspector = (product: ComparisonProduct) => {
    setInspectorProduct(product)
  }

  const closeInspector = () => setInspectorProduct(null)
  
  const toggleGroup = (key: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }
  
  const toggleType = (type: string) => {
    setExpandedTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) {
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }
  
  const toggleVariantDetails = (variantKey: string) => {
    setExpandedVariantDetails(prev => {
      const next = new Set(prev)
      if (next.has(variantKey)) {
        next.delete(variantKey)
      } else {
        next.add(variantKey)
      }
      return next
    })
  }

  const toggleWeightBucket = (bucketKey: string) => {
    setExpandedWeightBuckets(prev => {
      const next = new Set(prev)
      if (next.has(bucketKey)) {
        next.delete(bucketKey)
      } else {
        next.add(bucketKey)
      }
      return next
    })
  }

  if (isLoading && activeTab === 'changes') {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }
  
  if (error && activeTab === 'changes') {
    return (
      <div className="bg-red-900/50 text-red-300 p-4 rounded-lg">
        Failed to load price changes: {(error as Error).message}
      </div>
    )
  }
  
  const products = data?.items || []
  const comparisonGroups = comparisonData?.groups || []
  
  return (
    <div className="space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 shadow-2xl shadow-slate-950/40 relative overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-1/2 opacity-40 pointer-events-none" style={{ background: 'radial-gradient(circle at 30% 20%, rgba(59,130,246,0.25), transparent 55%)' }} />
        <div className="relative z-10">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500 mb-2">Insights</p>
          <h1 className="text-3xl font-semibold text-white">Price Intelligence</h1>
          <p className="text-slate-300 mt-2">
            {activeTab === 'changes' 
              ? `${data?.total || 0} products with price changes in the last ${days} days`
              : `${comparisonData?.total_groups || 0} products available from multiple sources`
            }
          </p>
        </div>
      </div>
      
      {/* Tab Navigation */}
      <div className="flex gap-3">
        <button
          onClick={() => setActiveTab('changes')}
          className={`flex items-center gap-2 px-4 py-2 rounded-2xl text-sm font-semibold tracking-wide transition-all ${
            activeTab === 'changes'
              ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white shadow-lg shadow-sky-900/40'
              : 'bg-slate-900/80 text-slate-400 border border-slate-800 hover:text-white'
          }`}
        >
          <TrendingDown className="w-4 h-4" />
          Price Changes
        </button>
        <button
          onClick={() => setActiveTab('compare')}
          className={`flex items-center gap-2 px-4 py-2 rounded-2xl text-sm font-semibold tracking-wide transition-all ${
            activeTab === 'compare'
              ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white shadow-lg shadow-purple-900/40'
              : 'bg-slate-900/80 text-slate-400 border border-slate-800 hover:text-white'
          }`}
        >
          <ArrowRightLeft className="w-4 h-4" />
          Compare Prices
        </button>
      </div>
      
      <div className="bg-slate-900/70 rounded-3xl border border-slate-800 p-5 sticky top-4 z-20 backdrop-blur supports-[backdrop-filter]:bg-slate-900/60">
        <div className="flex flex-wrap gap-4 items-center text-sm text-slate-300">
          <div className="flex items-center gap-2 text-slate-400">
            <div className="h-8 w-8 rounded-2xl bg-slate-800 flex items-center justify-center">
              <Filter className="w-4 h-4" />
            </div>
            {activeTab === 'changes' && (
              <select
                value={changeType}
                onChange={(e) => setChangeType(e.target.value)}
                className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-white"
              >
                <option value="">All Changes</option>
                <option value="price_decrease">Price Drops</option>
                <option value="price_increase">Price Increases</option>
              </select>
            )}
          </div>
          
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-white"
          >
            <option value="">All Categories</option>
            <option value="filament">Filament</option>
            <option value="resin">Resin</option>
          </select>
          
          {activeTab === 'changes' && (
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-white"
            >
              <option value={1}>Last 24 hours</option>
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
          )}
          
          {activeTab === 'compare' && comparisonData?.by_type && (
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-white"
            >
              <option value="">All Types</option>
              {comparisonData.by_type.map((t: TypeSummary) => (
                <option key={t.type} value={t.type}>{t.type} ({t.product_count})</option>
              ))}
            </select>
          )}

          {activeTab === 'compare' && (
            <select
              value={weightFilter}
              onChange={(e) => setWeightFilter(e.target.value)}
              className="px-4 py-2 rounded-xl bg-slate-800 border border-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-white"
            >
              {WEIGHT_FILTER_OPTIONS.map((option) => (
                <option key={option.value || 'all'} value={option.value}>{option.label}</option>
              ))}
            </select>
          )}

          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="ml-auto px-4 py-2 rounded-2xl text-xs font-semibold uppercase tracking-wide border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500"
            >
              Reset filters
            </button>
          )}
        </div>
      </div>
      
      {activeTab === 'compare' && (
        <div className="flex flex-wrap gap-3">
          {QUICK_FILTER_TYPES.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(prev => prev === type ? '' : type)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide border transition-all ${
                selectedType.toLowerCase() === type
                  ? 'bg-blue-600/80 text-white border-blue-500'
                  : 'text-slate-400 border-slate-700 hover:text-white hover:border-slate-500'
              }`}
            >
              {type.toUpperCase()}
            </button>
          ))}
        </div>
      )}
      
      {/* Price Changes Tab */}
      {activeTab === 'changes' && (
        <>
          {products.length === 0 ? (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
              <Package className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No price changes found</p>
              <p className="text-sm text-gray-500 mt-1">
                Try adjusting the filters or time range
              </p>
            </div>
          ) : (
            <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-900 border-b border-gray-700">
                  <tr>
                    <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Product</th>
                    <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Category</th>
                    <th className="text-left px-4 py-3 text-sm font-medium text-gray-300">Change</th>
                    <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Current Price</th>
                    <th className="text-right px-4 py-3 text-sm font-medium text-gray-300">Changed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {products.map((product: Product) => (
                    <tr key={product.id} className="hover:bg-gray-700/50">
                      <td className="px-4 py-3">
                        <Link 
                          to={`/products/${product.id}`}
                          className="flex items-center gap-3 group"
                        >
                          <div className="w-12 h-12 bg-gray-900 rounded-lg flex-shrink-0 overflow-hidden">
                            {product.image_url ? (
                              <img
                                src={product.image_url}
                                alt={product.name}
                                className="w-full h-full object-contain"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none'
                                }}
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <Package className="w-6 h-6 text-gray-700" />
                              </div>
                            )}
                          </div>
                          <div>
                            <div className="font-medium text-gray-100 group-hover:text-blue-400 line-clamp-1">
                              {product.name}
                            </div>
                            {product.brand && (
                              <div className="text-sm text-gray-500">{product.brand}</div>
                            )}
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <CategoryBadge category={product.category} />
                      </td>
                      <td className="px-4 py-3">
                        <ChangeTypeBadge 
                          type={product.latest_change_type} 
                          percent={product.latest_change_percent} 
                        />
                      </td>
                      <td className="px-4 py-3 text-right">
                        {product.latest_price ? (
                          <span className="font-medium text-gray-100">
                            {formatPrice(product.latest_price.price_amount, product.latest_price.currency)}
                          </span>
                        ) : (
                          <span className="text-gray-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-sm text-gray-400">
                        {product.latest_change_at
                          ? formatDistanceToNow(new Date(product.latest_change_at), { addSuffix: true })
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      
      {/* Compare Prices Tab */}
      {activeTab === 'compare' && (
        <>
          {comparisonLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
          ) : comparisonGroups.length === 0 ? (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
              <ArrowRightLeft className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No products found across multiple sources</p>
              <p className="text-sm text-gray-500 mt-1">
                Products need to be available from at least 2 different stores to compare
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {comparisonData?.by_type && comparisonData.by_type.length > 0 && (
                <div className="space-y-4">
                  {comparisonData.by_type
                    .filter((typeSummary: TypeSummary) => {
                      if (selectedType && typeSummary.type !== selectedType) return false
                      if (!weightFilter) return true
                      return collectProductsFromType(typeSummary, weightFilter).length > 0
                    })
                    .map((typeSummary: TypeSummary) => {
                      const summaryMeta = getTypeMeta(typeSummary, weightFilter, shippingFees)
                      const cheapestListings = getCheapestBrandListings(typeSummary, weightFilter, shippingFees)
                      const bestBrand = cheapestListings[0]?.brand || '—'
                      const isTypeExpanded = expandedTypes.has(typeSummary.type)
                      const cheapestObservationTimes = cheapestListings
                        .map(({ product }) => (product.latest_price?.observed_at ? new Date(product.latest_price.observed_at).getTime() : null))
                        .filter((time): time is number => time !== null)
                      const cheapestUpdatedAt = cheapestObservationTimes.length ? new Date(Math.max(...cheapestObservationTimes)) : null

                      return (
                        <div key={typeSummary.type} className="bg-slate-900/80 rounded-3xl border border-slate-800 overflow-hidden">
                          <button
                            onClick={() => toggleType(typeSummary.type)}
                            className="w-full px-4 py-4 flex items-center justify-between hover:bg-slate-800/60 transition-colors"
                          >
                            <div className="flex flex-col gap-3 text-left">
                              <div className="flex items-center gap-3">
                                <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
                                  <span className="text-white font-bold text-sm">{typeSummary.type}</span>
                                </div>
                                <div>
                                  <div className="font-semibold text-white text-lg">
                                    {typeSummary.type} {typeSummary.type.toLowerCase().includes('resin') ? '' : 'Material'}
                                  </div>
                                  <p className="text-xs text-slate-400 tracking-wide uppercase">{typeSummary.product_count} listings • {summaryMeta.sourceCount} sources</p>
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <span className="px-2 py-1 rounded-full text-xs bg-slate-800 text-slate-300 border border-slate-700">
                                  Range {formatPriceNum(summaryMeta.minPrice, 'NOK')} - {formatPriceNum(summaryMeta.maxPrice, 'NOK')}
                                </span>
                                {summaryMeta.priceSpread !== null && (
                                  <span className="px-2 py-1 rounded-full text-xs bg-emerald-900/40 text-emerald-200 border border-emerald-800">
                                    Spread {summaryMeta.priceSpread.toFixed(1)}%
                                  </span>
                                )}
                                <span className="px-2 py-1 rounded-full text-xs bg-slate-800 text-slate-400 border border-slate-700 flex items-center gap-1">
                                  <Clock8 className="w-3 h-3" /> Updated {summaryMeta.latestObservation ? formatDistanceToNow(summaryMeta.latestObservation, { addSuffix: true }) : 'recently'}
                                </span>
                                <span className="px-2 py-1 rounded-full text-xs bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
                                  <Tag className="w-3 h-3" /> Best {bestBrand}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-4">
                              {isTypeExpanded ? (
                                <ChevronUp className="w-5 h-5 text-gray-500" />
                              ) : (
                                <ChevronDown className="w-5 h-5 text-gray-500" />
                              )}
                            </div>
                          </button>

                          {isTypeExpanded && (
                            <div className="border-t border-slate-800 p-5 space-y-6">
                              {cheapestListings.length > 0 && (
                                <div className="space-y-4">
                                  <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div>
                                      <div className="text-xs text-slate-500 uppercase tracking-[0.4em]">Cheapest picks</div>
                                      <div className="text-lg font-semibold text-white">Best price per brand</div>
                                    </div>
                                    <div className="text-xs text-slate-500">
                                      Updated {cheapestUpdatedAt ? formatDistanceToNow(cheapestUpdatedAt, { addSuffix: true }) : 'recently'}
                                    </div>
                                  </div>
                                  <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2">
                                    <Sparkles className="w-3 h-3" />
                                    Open lowest offers:
                                    <div className="flex flex-wrap gap-2">
                                      {cheapestListings.map(({ brand, product }) => (
                                        <a
                                          key={`quick-${typeSummary.type}-${brand}`}
                                          href={product.canonical_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 rounded-full text-slate-300 border border-slate-700 hover:text-white"
                                        >
                                          {brand}
                                          <Link2 className="w-3 h-3" />
                                        </a>
                                      ))}
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                                    {cheapestListings.map(({ brand, product, price, currency, breakdown }) => (
                                      <div key={`${typeSummary.type}-${brand}`} className="rounded-2xl border border-emerald-800/40 bg-gradient-to-br from-emerald-900/20 to-slate-900/60 p-4 flex flex-col gap-2">
                                        <div className="flex items-center justify-between">
                                          <span className="text-emerald-300 font-semibold text-sm uppercase tracking-wide">{brand}</span>
                                          <span className="text-emerald-100 font-bold text-lg">{formatPriceNum(price, currency)}</span>
                                        </div>
                                        <div>
                                          <Link to={`/products/${product.id}`} className="text-slate-100 font-medium hover:text-emerald-200 line-clamp-2">
                                            {product.name}
                                          </Link>
                                          <div className="text-xs text-slate-400 flex flex-wrap gap-1">
                                            <span>{product.source_name}</span>
                                            <span>• {product.latest_price?.in_stock ? 'In stock' : 'Stock unknown'}</span>
                                          </div>
                                        </div>
                                        <div className="flex items-center justify-between text-xs text-slate-500">
                                          <span>
                                            <Clock8 className="inline w-3 h-3 mr-1" />
                                            {product.latest_price?.observed_at ? formatDistanceToNow(new Date(product.latest_price.observed_at), { addSuffix: true }) : 'Unknown'}
                                          </span>
                                          <a
                                            href={product.canonical_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 text-emerald-300 hover:text-emerald-100"
                                          >
                                            View <ExternalLink className="w-3 h-3" />
                                          </a>
                                        </div>
                                        <div className="text-xs text-slate-400">
                                          Total {formatPriceNum(breakdown.total, breakdown.currency)} • Base {breakdown.base !== null ? formatPriceNum(breakdown.base, breakdown.currency) : '—'} • Shipping {formatShippingDisplay(breakdown)}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {typeSummary.variants && typeSummary.variants.length > 0 ? (
                                typeSummary.variants.map((variant: VariantSummary) => {
                                  const allProducts = variant.groups.flatMap((g) => g.products)
                                  const filteredProducts = filterProductsByWeight(allProducts, weightFilter)
                                  if (weightFilter && filteredProducts.length === 0) {
                                    return null
                                  }
                                  const weightBuckets = bucketProductsByWeight(filteredProducts)
                                  const visibleBuckets = weightFilter
                                    ? weightBuckets.filter((bucket) => bucket.key === weightFilter)
                                    : weightBuckets
                                  if (!visibleBuckets.length) {
                                    return null
                                  }
                                  const variantMeta = getTypeMeta({ ...typeSummary, groups: variant.groups }, weightFilter, shippingFees)

                                  return (
                                    <div key={variant.variant_key} className="space-y-4">
                                      <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-3 bg-gradient-to-r from-purple-900/20 to-slate-900/50 rounded-2xl border border-purple-900/40">
                                        <div>
                                          <span className="font-semibold text-purple-200 text-lg block">{variant.variant}</span>
                                          <span className="text-sm text-purple-200/70">
                                            {filteredProducts.length} listings • {formatPriceNum(variantMeta.minPrice, 'NOK')} - {formatPriceNum(variantMeta.maxPrice, 'NOK')}
                                          </span>
                                        </div>
                                        <button
                                          onClick={() => toggleVariantDetails(variant.variant_key)}
                                          className="text-xs uppercase tracking-wide text-purple-200/80 border border-purple-400/40 px-3 py-1 rounded-full hover:text-white"
                                        >
                                          {expandedVariantDetails.has(variant.variant_key) ? 'Hide details' : 'View details'}
                                        </button>
                                      </div>

                                      {visibleBuckets.map((bucket) => {
                                        const bucketPrices = bucket.products
                                          .map((product) => getDeliveredPrice(product.latest_price, shippingFees[product.source_id] || 0))
                                          .filter((value): value is number => typeof value === 'number')
                                        const minPrice = bucketPrices.length ? Math.min(...bucketPrices) : null
                                        const maxPrice = bucketPrices.length ? Math.max(...bucketPrices) : null
                                        const brandGroups = buildBrandGroups(bucket.products, shippingFees)
                                        const bucketKey = `${variant.variant_key}-${bucket.key}`
                                        const isBucketExpanded = expandedWeightBuckets.has(bucketKey)

                                        return (
                                          <div key={bucketKey} className="space-y-3">
                                            <button
                                              onClick={() => toggleWeightBucket(bucketKey)}
                                              className="flex w-full flex-wrap items-center justify-between gap-2 px-3 py-2 bg-slate-900/60 border border-slate-800 rounded-2xl text-left"
                                            >
                                              <div>
                                                <span className="font-semibold text-slate-100 text-base block">{formatWeightBucketLabel(bucket)}</span>
                                                <span className="text-xs text-slate-400">{bucket.products.length} listings • {formatPriceNum(minPrice, 'NOK')} - {formatPriceNum(maxPrice, 'NOK')}</span>
                                              </div>
                                              <div className="flex items-center gap-2 text-xs text-slate-400">
                                                <Tag className="w-3 h-3" />
                                                Weight bucket
                                                {isBucketExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                              </div>
                                            </button>

                                            {isBucketExpanded && (
                                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                {brandGroups.map(({ brand, products }) => {
                                                  const lowestProduct = products[0]
                                                  const lowestBreakdown = getPriceBreakdown(lowestProduct?.latest_price, shippingFees[lowestProduct?.source_id || -1] || 0)
                                                  const priceValues = products
                                                    .map((p) => getDeliveredPrice(p.latest_price, shippingFees[p.source_id] || 0))
                                                    .filter((value): value is number => typeof value === 'number')
                                                  const brandMin = priceValues.length ? Math.min(...priceValues) : null
                                                  const brandMax = priceValues.length ? Math.max(...priceValues) : null

                                                  return (
                                                    <div key={`${bucket.key}-${brand}`} className="border border-slate-800 rounded-2xl p-4 bg-slate-900/60 flex flex-col gap-2">
                                                      <div className="flex items-center justify-between">
                                                        <div>
                                                          <span className="font-semibold text-white">{brand}</span>
                                                          <div className="text-xs text-slate-500">{products.length} listings</div>
                                                        </div>
                                                        <div className="text-xs text-slate-400">{formatWeightBucketLabel(bucket)}</div>
                                                      </div>
                                                      <div className="flex items-center justify-between text-sm">
                                                        <div className="text-slate-400">{formatPriceNum(brandMin, 'NOK')} - {formatPriceNum(brandMax, 'NOK')}</div>
                                                        {lowestProduct?.latest_price?.observed_at && (
                                                          <div className="text-slate-500 text-xs">
                                                            {formatDistanceToNow(new Date(lowestProduct.latest_price.observed_at), { addSuffix: true })}
                                                          </div>
                                                        )}
                                                      </div>
                                                      <div className="text-xs text-slate-500 flex items-center gap-1">
                                                        <Sparkles className="w-3 h-3" /> Lowest: {lowestProduct?.source_name}
                                                      </div>
                                                      <Link
                                                        to={`/products/${lowestProduct?.id}`}
                                                        className="text-sm text-blue-300 hover:text-blue-200 line-clamp-2"
                                                      >
                                                        {lowestProduct?.name}
                                                      </Link>
                                                      {lowestBreakdown.total !== null && (
                                                        <div className="text-xs text-slate-500">
                                                          Total {formatPriceNum(lowestBreakdown.total, lowestBreakdown.currency)} • Base {lowestBreakdown.base !== null ? formatPriceNum(lowestBreakdown.base, lowestBreakdown.currency) : '—'} • Shipping {formatShippingDisplay(lowestBreakdown)}
                                                        </div>
                                                      )}
                                                      {expandedVariantDetails.has(variant.variant_key) && (
                                                        <div className="mt-2 border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60">
                                                          <table className="w-full">
                                                            <tbody className="divide-y divide-slate-800/80">
                                                              {products.map((product, idx) => {
                                                                const breakdown = getPriceBreakdown(product.latest_price, shippingFees[product.source_id] || 0)
                                                                return (
                                                                  <tr key={product.id} className={idx === 0 ? 'bg-emerald-900/10' : ''}>
                                                                    <td className="px-3 py-2">
                                                                      <div className="text-sm text-white">{product.source_name}</div>
                                                                      <div className="text-xs text-slate-500">{product.source_domain}</div>
                                                                    </td>
                                                                    <td className="px-3 py-2 text-right">
                                                                      <div className={`font-medium ${idx === 0 ? 'text-emerald-300' : 'text-slate-100'}`}>
                                                                        {formatPriceNum(breakdown.total, breakdown.currency)}
                                                                      </div>
                                                                      <div className="text-xxs text-slate-500">
                                                                        Base {breakdown.base !== null ? formatPriceNum(breakdown.base, breakdown.currency) : '—'} • Ship {formatShippingDisplay(breakdown)}
                                                                      </div>
                                                                      {idx === 0 && products.length > 1 && (
                                                                        <div className="text-xs text-emerald-400">Lowest</div>
                                                                      )}
                                                                    </td>
                                                                    <td className="px-3 py-2 text-right">
                                                                      <a
                                                                        href={product.canonical_url}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="text-slate-500 hover:text-blue-400"
                                                                      >
                                                                        <ExternalLink className="w-4 h-4" />
                                                                      </a>
                                                                    </td>
                                                                  </tr>
                                                                )
                                                              })}
                                                            </tbody>
                                                          </table>
                                                        </div>
                                                      )}
                                                    </div>
                                                  )
                                                })}
                                              </div>
                                            )}
                                          </div>
                                        )
                                      })}
                                    </div>
                                  )
                                })
                              ) : (
                                typeSummary.groups
                                  .filter((group: CrossSourceGroup) => {
                                    if (!weightFilter) return true
                                    return group.products.some((product) => matchesWeightFilter(product, weightFilter))
                                  })
                                  .map((group: CrossSourceGroup) => (
                                    <ComparisonGroup
                                      key={group.key}
                                      group={group}
                                      isExpanded={expandedGroups.has(group.key)}
                                      onToggle={() => toggleGroup(group.key)}
                                      shippingFees={shippingFees}
                                      onInspect={openInspector}
                                    />
                                  ))
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
