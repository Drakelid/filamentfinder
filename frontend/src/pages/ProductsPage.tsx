import { useDeferredValue, useMemo, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ChevronLeft,
  ChevronRight,
  Grid3X3,
  Package,
  Rows3,
  Search,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { api, Product } from '../api'
import {
  CategoryBadge,
  MatchBadge,
  ProductEmptyState,
  ProductSkeletonGrid,
  ProductSkeletonList,
  ProductUpdatedAt,
  StockBadge,
  formatNumberCurrency,
  formatPrice,
} from '../components/products/ProductUI'

type ViewMode = 'list' | 'grid'
type SortKey = 'relevance' | 'price-asc' | 'price-desc' | 'kg-asc' | 'kg-desc' | 'updated' | 'name'

const FILAMENT_TYPES = ['pla', 'petg', 'abs', 'tpu', 'asa', 'nylon', 'pc', 'pva', 'hips', 'wood', 'metal', 'carbon']
const RESIN_TYPES = ['standard', 'tough', 'flexible', 'castable', 'dental', 'engineering']

function getPriceValue(product: Product): number | null {
  const amount = product.latest_price?.price_amount
  return amount ? parseFloat(amount) : null
}

function getPricePerKgValue(product: Product): number | null {
  return product.price_per_kg ?? null
}

function compareValues(a: number | null, b: number | null, direction: 'asc' | 'desc') {
  const left = a ?? Number.POSITIVE_INFINITY
  const right = b ?? Number.POSITIVE_INFINITY
  if (left === right) return 0
  const multiplier = direction === 'asc' ? 1 : -1
  return left > right ? multiplier : -multiplier
}

function sortProducts(products: Product[], sortBy: SortKey) {
  const sorted = [...products]
  sorted.sort((a, b) => {
    switch (sortBy) {
      case 'price-asc':
        return compareValues(getPriceValue(a), getPriceValue(b), 'asc')
      case 'price-desc':
        return compareValues(getPriceValue(a), getPriceValue(b), 'desc')
      case 'kg-asc':
        return compareValues(getPricePerKgValue(a), getPricePerKgValue(b), 'asc')
      case 'kg-desc':
        return compareValues(getPricePerKgValue(a), getPricePerKgValue(b), 'desc')
      case 'updated':
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      case 'name':
        return a.name.localeCompare(b.name)
      case 'relevance':
      default:
        return (b.confidence ?? 0) - (a.confidence ?? 0)
    }
  })
  return sorted
}

function hasImage(product: Product) {
  return Boolean(product.image_url && product.image_url.trim())
}

function ProductSearchSuggestion({ product, onPick }: { product: Product; onPick: (value: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onPick(product.name)}
      className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-slate-800/90 transition-colors"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-950/80 text-slate-500">
        <Package className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-slate-100">{product.name}</div>
        <div className="truncate text-xs text-slate-500">{product.brand || product.source_name || product.source_domain}</div>
      </div>
      <div className="text-right">
        <div className="text-sm font-medium text-slate-100">{formatPrice(product.latest_price?.price_amount ?? null, product.latest_price?.currency ?? null)}</div>
        <div className="text-xs text-slate-500">
          {product.latest_price?.in_stock === true ? 'In stock' : product.latest_price?.in_stock === false ? 'Out' : 'Unknown'}
        </div>
      </div>
    </button>
  )
}

function ProductListRow({ product }: { product: Product }) {
  return (
    <Link
      to={`/products/${product.id}`}
      className="group block rounded-2xl border border-slate-800 bg-slate-900/70 p-4 shadow-lg shadow-black/15 transition-all hover:-translate-y-0.5 hover:border-violet-500/30 hover:bg-slate-900"
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2.3fr)_170px_140px_120px_120px_120px_110px] lg:items-center">
        <div className="flex min-w-0 items-start gap-4">
          {hasImage(product) && (
            <div className="h-16 w-16 shrink-0 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/70">
              <img
                src={product.image_url!}
                alt={product.name}
                className="h-full w-full object-contain"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
            </div>
          )}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={product.category} />
              {product.product_type && (
                <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-300">
                  {product.product_type}
                </span>
              )}
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold text-slate-50 group-hover:text-white">{product.name}</h3>
              <p className="truncate text-sm text-slate-400">{product.brand || 'No brand'} {product.source_name ? `· ${product.source_name}` : ''}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 lg:block">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500 lg:mb-1">Price</div>
          <div className="text-right lg:text-left">
            <div className="font-mono text-lg font-semibold text-slate-50">
              {formatPrice(product.latest_price?.price_amount ?? null, product.latest_price?.currency ?? null)}
            </div>
            {product.latest_price?.list_price_amount && product.latest_price.list_price_amount !== product.latest_price.price_amount && (
              <div className="font-mono text-xs text-slate-500 line-through">
                {formatPrice(product.latest_price.list_price_amount, product.latest_price.currency)}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 lg:block">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500 lg:mb-1">Per kg</div>
          <div className="font-mono text-sm text-slate-200">
            {formatNumberCurrency(product.price_per_kg ?? null, product.latest_price?.currency ?? null)}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 lg:block">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500 lg:mb-1">Stock</div>
          <StockBadge inStock={product.latest_price?.in_stock ?? null} />
        </div>

        <div className="flex items-center justify-between gap-3 lg:block">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500 lg:mb-1">Updated</div>
          <div className="text-sm text-slate-300">
            <ProductUpdatedAt updatedAt={product.updated_at} />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 lg:block">
          <div className="text-xs uppercase tracking-[0.22em] text-slate-500 lg:mb-1">Relevance</div>
          <MatchBadge confidence={product.confidence} />
        </div>

        <div className="hidden justify-end lg:flex">
          <div className="rounded-full border border-slate-700 bg-slate-950/60 p-2 text-slate-400 transition-colors group-hover:border-violet-500/30 group-hover:text-violet-300">
            <TrendingUp className="h-4 w-4" />
          </div>
        </div>
      </div>
    </Link>
  )
}

function ProductGridCard({ product }: { product: Product }) {
  const imagePresent = hasImage(product)

  return (
    <Link
      to={`/products/${product.id}`}
      className="group block overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/70 shadow-lg shadow-black/15 transition-all hover:-translate-y-1 hover:border-violet-500/30 hover:bg-slate-900"
    >
      {imagePresent ? (
        <div className="grid gap-0 md:grid-cols-[144px_minmax(0,1fr)]">
          <div className="min-h-40 border-b border-slate-800 bg-slate-950/60 md:min-h-full md:border-b-0 md:border-r">
            <img
              src={product.image_url!}
              alt={product.name}
              className="h-full w-full object-contain p-4"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
              }}
            />
          </div>
          <div className="flex min-w-0 flex-col p-5">
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={product.category} />
              {product.product_type && (
                <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-300">
                  {product.product_type}
                </span>
              )}
            </div>
            <h3 className="mt-3 line-clamp-2 text-lg font-semibold text-slate-50 group-hover:text-white">{product.name}</h3>
            <p className="mt-1 text-sm text-slate-400">{product.brand || 'No brand'}</p>

            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Price</div>
                <div className="mt-1 font-mono text-base font-semibold text-slate-50">
                  {formatPrice(product.latest_price?.price_amount ?? null, product.latest_price?.currency ?? null)}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Stock</div>
                <div className="mt-2">
                  <StockBadge inStock={product.latest_price?.in_stock ?? null} />
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span><ProductUpdatedAt updatedAt={product.updated_at} /></span>
              <MatchBadge confidence={product.confidence} />
            </div>
          </div>
        </div>
      ) : (
        <div className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={product.category} />
            {product.product_type && (
              <span className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-300">
                {product.product_type}
              </span>
            )}
          </div>
          <h3 className="mt-4 line-clamp-2 text-lg font-semibold text-slate-50 group-hover:text-white">{product.name}</h3>
          <p className="mt-1 text-sm text-slate-400">{product.brand || 'No brand'}</p>

          <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Price</div>
              <div className="mt-1 font-mono text-base font-semibold text-slate-50">
                {formatPrice(product.latest_price?.price_amount ?? null, product.latest_price?.currency ?? null)}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
              <div className="text-xs uppercase tracking-[0.22em] text-slate-500">Per kg</div>
              <div className="mt-1 font-mono text-base text-slate-200">
                {formatNumberCurrency(product.price_per_kg ?? null, product.latest_price?.currency ?? null)}
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <StockBadge inStock={product.latest_price?.in_stock ?? null} />
            <MatchBadge confidence={product.confidence} />
          </div>

          <div className="mt-4 text-xs text-slate-500">
            Updated <ProductUpdatedAt updatedAt={product.updated_at} />
          </div>
        </div>
      )}
    </Link>
  )
}

export default function ProductsPage() {
  const [category, setCategory] = useState<string>('')
  const [productType, setProductType] = useState<string>('')
  const [brand, setBrand] = useState<string>('')
  const [minPrice, setMinPrice] = useState<string>('')
  const [maxPrice, setMaxPrice] = useState<string>('')
  const [stockOnly, setStockOnly] = useState(false)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [sortBy, setSortBy] = useState<SortKey>('relevance')
  const PAGE_SIZE = 24
  const [page, setPage] = useState(1)

  const deferredSearch = useDeferredValue(searchInput.trim())

  const { data, isLoading, error } = useQuery({
    queryKey: ['products', { category, productType, brand, minPrice, maxPrice, search, page }],
    queryFn: () => api.products.list({
      category: category || undefined,
      product_type: productType || undefined,
      brand: brand || undefined,
      min_price: minPrice ? parseFloat(minPrice) : undefined,
      max_price: maxPrice ? parseFloat(maxPrice) : undefined,
      search: search || undefined,
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    staleTime: 60_000,
  })

  const searchSuggestions = useQuery({
    queryKey: ['products-suggestions', deferredSearch, category, productType],
    queryFn: () => api.products.list({
      category: category || undefined,
      product_type: productType || undefined,
      search: deferredSearch || undefined,
      limit: 5,
    }),
    enabled: deferredSearch.length >= 2,
    staleTime: 60_000,
  })

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    setSearch(searchInput.trim())
    setPage(1)
  }

  const clearFilters = () => {
    setCategory('')
    setProductType('')
    setBrand('')
    setMinPrice('')
    setMaxPrice('')
    setStockOnly(false)
    setSearch('')
    setSearchInput('')
    setPage(1)
    setSortBy('relevance')
  }

  const products = data?.items ?? []
  const productTypes = useMemo(() => {
    const source = products.length > 0 ? products : []
    const typePool = category === 'resin' ? RESIN_TYPES : category === 'filament' ? FILAMENT_TYPES : []
    if (typePool.length) return typePool
    return Array.from(new Set(source.map((product) => product.product_type).filter((value): value is string => Boolean(value)))).slice(0, 12)
  }, [category, products])
  const brandOptions = useMemo(
    () =>
      Array.from(
        new Set(products.map((product) => product.brand?.trim()).filter((value): value is string => Boolean(value))),
      ).slice(0, 6),
    [products],
  )
  const priceSliderMax = useMemo(() => {
    const values = products
      .map((product) => getPriceValue(product))
      .filter((value): value is number => value !== null)
    return Math.max(1000, ...(values.length ? values : [1000]))
  }, [products])
  const currentPriceCap = maxPrice ? parseFloat(maxPrice) : priceSliderMax

  const filteredProducts = useMemo(() => {
    const filtered = products.filter((product) => !stockOnly || product.latest_price?.in_stock === true)
    return sortProducts(filtered, sortBy)
  }, [products, sortBy, stockOnly])

  const hasActiveFilters = Boolean(category || productType || brand || minPrice || maxPrice || search || stockOnly)

  const activeCount = [category, productType, brand, minPrice || maxPrice, search, stockOnly ? 'stock' : '']
    .filter(Boolean).length

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <div className="h-8 w-48 rounded bg-slate-800 animate-pulse" />
          <div className="h-4 w-64 rounded bg-slate-800 animate-pulse" />
        </div>
        {viewMode === 'list' ? <ProductSkeletonList /> : <ProductSkeletonGrid />}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-800 bg-rose-950/40 p-4 text-rose-200">
        Failed to load products: {(error as Error).message}
      </div>
    )
  }

  const emptyState = filteredProducts.length === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Catalog</p>
          <h1 className="text-3xl font-semibold text-slate-50">Products</h1>
          <p className="text-sm text-slate-400">{data?.total || 0} products tracked</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
              viewMode === 'list'
                ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-slate-600'
            }`}
          >
            <Rows3 className="h-4 w-4" />
            List
          </button>
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
              viewMode === 'grid'
                ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-slate-600'
            }`}
          >
            <Grid3X3 className="h-4 w-4" />
            Grid
          </button>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg shadow-black/20">
        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={handleSearch} className="relative min-w-[280px] flex-1">
            <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.currentTarget.value)}
              placeholder="Search products, brands, materials..."
              className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 py-3 pl-10 pr-4 text-slate-100 placeholder:text-slate-500 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
            />

            {deferredSearch.length >= 2 && searchSuggestions.data?.items?.length ? (
              <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-20 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/95 shadow-2xl shadow-black/40">
                {searchSuggestions.data.items.map((product) => (
                  <ProductSearchSuggestion
                    key={product.id}
                    product={product}
                    onPick={(value) => {
                      setSearchInput(value)
                      setSearch(value)
                      setPage(1)
                    }}
                  />
                ))}
              </div>
            ) : null}
          </form>

          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center gap-2 rounded-xl border px-3 py-3 text-sm transition-colors ${
              showFilters || hasActiveFilters
                ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                : 'border-slate-700 bg-slate-900/70 text-slate-300 hover:border-slate-600'
            }`}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[11px] font-medium text-violet-100">
                {activeCount}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => window.open('/api/products/export', '_blank')}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-3 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-800"
          >
            Export CSV
          </button>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-sm text-slate-400 hover:text-slate-200"
            >
              Clear all
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Quick filters</span>
          <button
            type="button"
            onClick={() => { setCategory(''); setPage(1) }}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${!category ? 'border-violet-500/40 bg-violet-500/10 text-violet-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'}`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => { setCategory('filament'); setPage(1) }}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${category === 'filament' ? 'border-violet-500/40 bg-violet-500/10 text-violet-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'}`}
          >
            Filament
          </button>
          <button
            type="button"
            onClick={() => { setCategory('resin'); setPage(1) }}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${category === 'resin' ? 'border-amber-500/40 bg-amber-500/10 text-amber-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'}`}
          >
            Resin
          </button>

          <button
            type="button"
            onClick={() => setStockOnly((current) => !current)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${stockOnly ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'}`}
          >
            In stock only
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {productTypes.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => {
                  setProductType(type === productType ? '' : type)
                setPage(1)
              }}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] transition-colors ${
                productType === type
                  ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                  : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'
              }`}
            >
              {type}
            </button>
          ))}
          {brandOptions.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setBrand(item === brand ? '' : item)
                setPage(1)
              }}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                brand === item
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-100'
                  : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:border-slate-600'
              }`}
            >
              {item}
            </button>
          ))}
        </div>

        {showFilters && (
          <div className="mt-4 grid gap-4 border-t border-slate-800 pt-4 md:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs uppercase tracking-[0.24em] text-slate-500">Category</label>
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.currentTarget.value)
                  setProductType('')
                  setBrand('')
                  setPage(1)
                }}
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2.5 text-slate-100 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              >
                <option value="">All Categories</option>
                <option value="filament">Filament</option>
                <option value="resin">Resin</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs uppercase tracking-[0.24em] text-slate-500">Material Type</label>
              <select
                value={productType}
                onChange={(e) => {
                  setProductType(e.currentTarget.value)
                  setPage(1)
                }}
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2.5 text-slate-100 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              >
                <option value="">All types</option>
                {productTypes.map((type) => (
                  <option key={type} value={type}>
                    {type.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs uppercase tracking-[0.24em] text-slate-500">Min price</label>
              <input
                type="number"
                value={minPrice}
                onChange={(e) => {
                  setMinPrice(e.currentTarget.value)
                  setPage(1)
                }}
                placeholder="0"
                min="0"
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2.5 text-slate-100 placeholder:text-slate-500 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              />
            </div>
          <div>
            <label className="mb-1 block text-xs uppercase tracking-[0.24em] text-slate-500">Max price</label>
            <input
              type="number"
              value={maxPrice}
                onChange={(e) => {
                  setMaxPrice(e.currentTarget.value)
                  setPage(1)
                }}
                placeholder="No limit"
                min="0"
                className="w-full rounded-2xl border border-slate-700 bg-slate-950/60 px-3 py-2.5 text-slate-100 placeholder:text-slate-500 focus:border-violet-500/50 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
              />
            </div>
            <div className="md:col-span-2 lg:col-span-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <label className="block text-xs uppercase tracking-[0.24em] text-slate-500">Price cap slider</label>
                <span className="font-mono text-sm text-slate-200">{formatNumberCurrency(currentPriceCap, products[0]?.latest_price?.currency ?? 'USD')}</span>
              </div>
              <input
                type="range"
                min="0"
                max={priceSliderMax}
                value={currentPriceCap}
                onChange={(e) => {
                  setMaxPrice(String(e.currentTarget.value))
                  setPage(1)
                }}
                className="w-full accent-violet-500"
              />
              <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                <span>0</span>
                <span>{formatNumberCurrency(priceSliderMax, products[0]?.latest_price?.currency ?? 'USD')}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {emptyState ? (
        <ProductEmptyState
          title="No products matched your filters"
          description="Try widening the price range, clearing the brand chip, or switching back to all categories."
          action={
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-2 rounded-xl bg-violet-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-400"
            >
              <Sparkles className="h-4 w-4" />
              Clear filters
            </button>
          }
        />
      ) : viewMode === 'list' ? (
        <div className="space-y-3">
          <div className="hidden rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-xs uppercase tracking-[0.24em] text-slate-500 lg:grid lg:grid-cols-[minmax(0,2.3fr)_170px_140px_120px_120px_120px_110px]">
            <div>Product</div>
            <div>Price</div>
            <div>Per kg</div>
            <div>Stock</div>
            <div>Updated</div>
            <div>Relevance</div>
            <div />
          </div>
          {filteredProducts.map((product) => (
            <ProductListRow key={product.id} product={product} />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filteredProducts.map((product) => (
            <ProductGridCard key={product.id} product={product} />
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-400">
            Page {page} of {Math.ceil(data.total / PAGE_SIZE)}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page === 1}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
              Prev
            </button>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(Math.ceil(data.total / PAGE_SIZE), current + 1))}
              disabled={page >= Math.ceil(data.total / PAGE_SIZE)}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
