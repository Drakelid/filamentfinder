import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, Filter, Loader2, Package, Download, ChevronLeft, ChevronRight } from 'lucide-react'
import { api, Product } from '../api'
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

function StockBadge({ inStock }: { inStock: boolean | null }) {
  if (inStock === null) return null
  
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
      inStock ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
    }`}>
      {inStock ? 'In Stock' : 'Out of Stock'}
    </span>
  )
}

const FILAMENT_TYPES = ['pla', 'petg', 'abs', 'tpu', 'asa', 'nylon', 'pc', 'pva', 'hips', 'wood', 'metal', 'carbon']
const RESIN_TYPES = ['standard', 'tough', 'flexible', 'castable', 'dental', 'engineering']

export default function ProductsPage() {
  const [category, setCategory] = useState<string>('')
  const [productType, setProductType] = useState<string>('')
  const [minPrice, setMinPrice] = useState<string>('')
  const [maxPrice, setMaxPrice] = useState<string>('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const PAGE_SIZE = 24
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['products', { category, productType, minPrice, maxPrice, search, page }],
    queryFn: () => api.products.list({
      category: category || undefined,
      product_type: productType || undefined,
      min_price: minPrice ? parseFloat(minPrice) : undefined,
      max_price: maxPrice ? parseFloat(maxPrice) : undefined,
      search: search || undefined,
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    staleTime: 60_000,
  })
  
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
  }
  
  const clearFilters = () => {
    setCategory('')
    setProductType('')
    setMinPrice('')
    setMaxPrice('')
    setSearch('')
    setSearchInput('')
    setPage(1)
  }
  
  const hasActiveFilters = category || productType || minPrice || maxPrice || search
  const productTypes = category === 'resin' ? RESIN_TYPES : FILAMENT_TYPES
  
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
        Failed to load products: {(error as Error).message}
      </div>
    )
  }
  
  const products = data?.items || []
  
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Products</h1>
          <p className="text-gray-400 mt-1">
            {data?.total || 0} products tracked
          </p>
        </div>
      </div>
      
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-center">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search products..."
                className="w-full pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
              />
            </div>
          </form>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
              showFilters || hasActiveFilters
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Filter className="w-5 h-5" />
            Filters
            {hasActiveFilters && (
              <span className="bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {[category, productType, minPrice || maxPrice, search].filter(Boolean).length}
              </span>
            )}
          </button>
          
          <button
            onClick={() => window.open('/api/products/export', '_blank')}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600 transition-colors"
          >
            <Download className="w-5 h-5" />
            Export CSV
          </button>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-gray-400 hover:text-gray-200 text-sm"
            >
              Clear all
            </button>
          )}
        </div>
        
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-700 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value)
                  setProductType('')
                  setPage(1)
                }}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
              >
                <option value="">All Categories</option>
                <option value="filament">Filament</option>
                <option value="resin">Resin</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Material Type</label>
              <select
                value={productType}
                onChange={(e) => { setProductType(e.target.value); setPage(1) }}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100"
              >
                <option value="">All Types</option>
                {productTypes.map(type => (
                  <option key={type} value={type}>{type.toUpperCase()}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Min Price</label>
              <input
                type="number"
                value={minPrice}
                onChange={(e) => { setMinPrice(e.target.value); setPage(1) }}
                placeholder="0"
                min="0"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Max Price</label>
              <input
                type="number"
                value={maxPrice}
                onChange={(e) => { setMaxPrice(e.target.value); setPage(1) }}
                placeholder="No limit"
                min="0"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-100 placeholder-gray-500"
              />
            </div>
          </div>
        )}
      </div>
      
      {products.length === 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
          <Package className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No products found</p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-blue-400 hover:text-blue-300 font-medium mt-2"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {products.map((product: Product) => (
            <Link
              key={product.id}
              to={`/products/${product.id}`}
              className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden hover:border-gray-600 transition-colors"
            >
              <div className="aspect-video bg-gray-900 relative">
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
                    <Package className="w-12 h-12 text-gray-700" />
                  </div>
                )}
                <div className="absolute top-2 left-2">
                  <CategoryBadge category={product.category} />
                </div>
              </div>
              
              <div className="p-4">
                <h3 className="font-medium text-gray-100 line-clamp-2 mb-1">
                  {product.name}
                </h3>
                
                {product.brand && (
                  <p className="text-sm text-gray-400 mb-2">{product.brand}</p>
                )}
                
                <div className="flex items-center justify-between">
                  <div>
                    {product.latest_price ? (
                      <>
                        <div className="text-lg font-bold text-gray-100">
                          {formatPrice(product.latest_price.price_amount, product.latest_price.currency)}
                        </div>
                        {product.latest_price.list_price_amount && 
                         product.latest_price.list_price_amount !== product.latest_price.price_amount && (
                          <div className="text-sm text-gray-500 line-through">
                            {formatPrice(product.latest_price.list_price_amount, product.latest_price.currency)}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-gray-500">No price</div>
                    )}
                  </div>
                  
                  {product.latest_price && (
                    <StockBadge inStock={product.latest_price.in_stock} />
                  )}
                </div>

                {product.price_per_kg != null && (
                  <div className="text-xs text-gray-400 mt-1">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: product.latest_price?.currency || 'USD' }).format(product.price_per_kg)}/kg
                  </div>
                )}

                <div className="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between text-xs text-gray-500">
                  <span>
                    Updated {formatDistanceToNow(new Date(product.updated_at), { addSuffix: true })}
                  </span>
                  <span className="flex items-center gap-1">
                    {Math.round(product.confidence * 100)}% match
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-gray-400">
            Page {page} of {Math.ceil(data.total / PAGE_SIZE)}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 px-3 py-2 rounded-lg border border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(Math.ceil(data.total / PAGE_SIZE), p + 1))}
              disabled={page >= Math.ceil(data.total / PAGE_SIZE)}
              className="flex items-center gap-1 px-3 py-2 rounded-lg border border-gray-600 bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
