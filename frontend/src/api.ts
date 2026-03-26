const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY?.trim()

export interface CrawlRules {
  max_pages: number
  max_depth: number
  same_domain_only: boolean
  url_patterns: string[]
  exclude_patterns: string[]
  respect_robots_txt: boolean
  schedule_start_hour?: string | null
  schedule_end_hour?: string | null
  schedule_timezone?: string | null
  schedule_days?: string[]
}

export interface RetryPolicy {
  max_retries: number
  backoff_seconds: number
  retry_statuses: string[]
}

export interface CrawlDurationStats {
  avg_seconds?: number | null
  p95_seconds?: number | null
  last_seconds?: number | null
}

export interface AlertSettings {
  failure_threshold: number
  stale_hours: number
  notify_webhook: boolean
  notify_email: boolean
}

export interface SelectorOverrides {
  product_name?: string
  price?: string
  currency?: string
  image?: string
  brand?: string
  sku?: string
  in_stock?: string
  product_links?: string
}

export interface ScrapeStats {
  last_1h: number
  last_12h: number
  last_24h: number
}

export interface CrawlRunSummary {
  id: number
  status: string
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  pages_visited: number
  products_found: number
  products_updated: number
  price_changes_detected: number
  errors_count: number
}

export interface Source {
  id: number
  url: string
  domain: string
  name: string | null
  active: boolean
  crawl_rules: CrawlRules
  selector_overrides: SelectorOverrides | null
  shipping_fee: string | null
  robots_txt_allowed: boolean | null
  retry_policy?: RetryPolicy | null
  crawl_duration_stats?: CrawlDurationStats | null
  alert_settings?: AlertSettings | null
  created_at: string
  updated_at: string
  last_scan_at: string | null
  status: string
  status_message: string | null
  failure_streak?: number
  next_retry_at?: string | null
  product_count: number
  scrape_stats: ScrapeStats
  latest_run?: CrawlRunSummary | null
  success_rate_24h?: number | null
}

export interface VPNConfig {
  gluetun_mode: boolean
  account_number_set: boolean
  proxy_configured: boolean
  enabled: boolean
  auto_rotate: boolean
  rotate_interval_minutes: number
  connected: boolean
  current_server: string | null
  current_ip: string | null
}

export interface VPNStatus {
  connected: boolean
  ip: string | null
  country: string | null
  mullvad_exit_ip: boolean
  error: string | null
}

export interface StatsData {
  overview: {
    total_sources: number
    active_sources: number
    scanning_sources: number
    total_products: number
    active_products: number
    running_crawls: number
  }
  products_by_category: Record<string, number>
  activity: {
    runs_24h: number
    runs_7d: number
    total_runs: number
    observations_24h: number
    observations_7d: number
    changes_24h: number
    changes_7d: number
  }
  recent_runs: Array<{
    id: number
    source_id: number
    source_name: string
    started_at: string | null
    finished_at: string | null
    duration_seconds: number | null
    status: string
    pages_visited: number
    products_found: number
    products_updated: number
    price_changes_detected: number
    errors_count: number
    error_messages?: string[] | null
  }>
  sources: Array<{
    id: number
    name: string
    domain: string
    status: string
    product_count: number
    last_scan_at: string | null
    latest_run: {
      pages_visited: number
      products_found: number
      errors_count: number
      status: string | null
    } | null
  }>
}

export interface HealthData {
  worker: {
    status: 'active' | 'idle'
    active_crawls: number
  }
  latest_scan_at: string | null
  migrations: {
    pending: number
    current_revision: string | null
    head_revision: string | null
  }
}

export interface LatestPrice {
  price_amount: string | null
  currency: string | null
  list_price_amount: string | null
  shipping_amount: string | null
  shipping_currency: string | null
  total_price_amount: string | null
  in_stock: boolean | null
  observed_at: string
}

export interface Product {
  id: number
  source_id: number
  canonical_url: string
  name: string
  brand: string | null
  category: string
  product_type: string | null
  variant: string | null
  color: string | null
  size: string | null
  image_url: string | null
  sku: string | null
  gtin: string | null
  active: boolean
  confidence: number
  latest_change_percent: number | null
  latest_change_type: string | null
  latest_change_at: string | null
  created_at: string
  updated_at: string
  last_seen_at: string | null
  latest_price: LatestPrice | null
  price_per_kg: number | null
  source_name?: string | null
  source_domain?: string | null
}

export interface PriceObservation {
  id: number
  product_id: number
  observed_at: string
  price_amount: string | null
  currency: string | null
  list_price_amount: string | null
  in_stock: boolean | null
  stock_quantity: number | null
}

export interface PriceChange {
  id: number
  product_id: number
  changed_at: string
  old_price: string | null
  new_price: string | null
  old_currency: string | null
  new_currency: string | null
  change_type: string
  change_percent: number | null
  note: string | null
}

export interface PriceAlert {
  id: string
  product_id: number
  target_price: string
  currency: string
  active: boolean
  created_at: string
  triggered_at: string | null
}

export interface PriceAlertList {
  items: PriceAlert[]
  total: number
}

export interface DealProduct extends Product {
  source_name: string | null
  old_price: string | null
  new_price: string | null
  pct_drop: number
  detected_at: string
}

export interface SourceImportResult {
  imported: number
  skipped: number
  errors: Array<{
    url: string
    reason: string
  }>
}

export interface CrawlRun {
  id: number
  source_id: number
  started_at: string
  finished_at: string | null
  status: string
  pages_visited: number
  products_found: number
  products_updated: number
  price_changes_detected: number
  errors_count: number
  error_messages: string[] | null
  stats_json: Record<string, unknown> | null
}

export interface CrossSourceProduct {
  id: number
  name: string
  brand: string | null
  category: string
  product_type: string | null
  color: string | null
  size: string | null
  image_url: string | null
  source_id: number
  source_name: string | null
  source_domain: string | null
  canonical_url: string
  latest_price: {
    amount: number | null
    currency: string | null
    shipping_amount: number | null
    shipping_currency: string | null
    total_amount: number | null
    in_stock: boolean | null
    observed_at: string | null
  } | null
  latest_change_percent: number | null
  latest_change_type: string | null
}

export interface CrossSourceGroup {
  key: string
  display_name: string
  match_type: 'gtin' | 'sku' | 'name'
  products: CrossSourceProduct[]
  source_count: number
  min_price: number | null
  max_price: number | null
  price_spread: number | null
}

export interface VariantSummary {
  variant: string
  variant_key: string
  product_count: number
  min_price: number | null
  max_price: number | null
  groups: CrossSourceGroup[]
}

export interface TypeSummary {
  type: string
  type_key: string
  product_count: number
  min_price: number | null
  max_price: number | null
  variants: VariantSummary[]
  groups: CrossSourceGroup[]
}

export interface CrossSourceComparisonResponse {
  groups: CrossSourceGroup[]
  total_groups: number
  by_type: TypeSummary[]
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(ADMIN_API_KEY ? { 'X-API-Key': ADMIN_API_KEY } : {}),
      ...options?.headers,
    },
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  
  if (response.status === 204) {
    return null as T
  }
  
  return response.json()
}

export const api = {
  config: {
    getVpn: () => fetchApi<VPNConfig>('/config/vpn'),
    updateVpn: (data: {
      account_number?: string
      socks_proxy?: string
      enabled: boolean
      auto_rotate: boolean
      rotate_interval_minutes: number
    }) => fetchApi<VPNConfig>('/config/vpn', { method: 'PUT', body: JSON.stringify(data) }),
    testVpn: () => fetchApi<VPNStatus>('/config/vpn/test', { method: 'POST' }),
  },

  stats: {
    get: () => fetchApi<StatsData>('/stats'),
    health: () => fetchApi<HealthData>('/stats/health'),
  },

  sources: {
    list: () => fetchApi<{ items: Source[]; total: number }>('/sources'),
    get: (id: number) => fetchApi<Source>(`/sources/${id}`),
    create: (data: {
      url: string
      name?: string
      crawl_rules?: Partial<CrawlRules>
      selector_overrides?: Partial<SelectorOverrides>
      shipping_fee?: number | null
      retry_policy?: Partial<RetryPolicy>
      alert_settings?: Partial<AlertSettings>
    }) =>
      fetchApi<Source>('/sources', { method: 'POST', body: JSON.stringify(data) }),
    update: (
      id: number,
      data: {
        name?: string
        active?: boolean
        crawl_rules?: Partial<CrawlRules>
        selector_overrides?: Partial<SelectorOverrides>
        shipping_fee?: number | null
        retry_policy?: Partial<RetryPolicy>
        alert_settings?: Partial<AlertSettings>
      },
    ) =>
      fetchApi<Source>(`/sources/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => fetchApi<void>(`/sources/${id}`, { method: 'DELETE' }),
    scan: (id: number) => fetchApi<{ message: string; source_id: number }>(`/sources/${id}/scan`, { method: 'POST' }),
  },
  
  products: {
    list: (params?: { 
      category?: string; 
      product_type?: string;
      min_price?: number;
      max_price?: number;
      brand?: string;
      source_id?: number; 
      active?: boolean; 
      search?: string
      skip?: number
      limit?: number
    }) => {
      const searchParams = new URLSearchParams()
      if (params?.category) searchParams.set('category', params.category)
      if (params?.product_type) searchParams.set('product_type', params.product_type)
      if (params?.min_price !== undefined) searchParams.set('min_price', params.min_price.toString())
      if (params?.max_price !== undefined) searchParams.set('max_price', params.max_price.toString())
      if (params?.brand) searchParams.set('brand', params.brand)
      if (params?.source_id) searchParams.set('source_id', params.source_id.toString())
      if (params?.active !== undefined) searchParams.set('active', params.active.toString())
      if (params?.search) searchParams.set('search', params.search)
      if (params?.skip !== undefined) searchParams.set('skip', params.skip.toString())
      if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString())
      const query = searchParams.toString()
      return fetchApi<{ items: Product[]; total: number }>(`/products${query ? `?${query}` : ''}`)
    },
    withChanges: (params?: { change_type?: string; category?: string; days?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.change_type) searchParams.set('change_type', params.change_type)
      if (params?.category) searchParams.set('category', params.category)
      if (params?.days) searchParams.set('days', params.days.toString())
      const query = searchParams.toString()
      return fetchApi<{ items: Product[]; total: number }>(`/products/with-changes${query ? `?${query}` : ''}`)
    },
    get: (id: number) => fetchApi<Product>(`/products/${id}`),
    history: (id: number) => fetchApi<{ observations: PriceObservation[]; changes: PriceChange[]; total_observations: number; total_changes: number }>(`/products/${id}/history`),
    changes: (id: number, params?: { from?: string; to?: string }) => {
      const searchParams = new URLSearchParams()
      if (params?.from) searchParams.set('from', params.from)
      if (params?.to) searchParams.set('to', params.to)
      const query = searchParams.toString()
      return fetchApi<PriceChange[]>(`/products/${id}/changes${query ? `?${query}` : ''}`)
    },
    crossSourceComparison: (params?: { category?: string; product_type?: string; brand?: string; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.category) searchParams.set('category', params.category)
      if (params?.product_type) searchParams.set('product_type', params.product_type)
      if (params?.brand) searchParams.set('brand', params.brand)
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      const query = searchParams.toString()
      return fetchApi<CrossSourceComparisonResponse>(`/products/compare/cross-source${query ? `?${query}` : ''}`)
    },
  },
  
  runs: {
    list: (params?: { source_id?: number; status?: string }) => {
      const searchParams = new URLSearchParams()
      if (params?.source_id) searchParams.set('source_id', params.source_id.toString())
      if (params?.status) searchParams.set('status', params.status)
      const query = searchParams.toString()
      return fetchApi<{ items: CrawlRun[]; total: number }>(`/runs${query ? `?${query}` : ''}`)
    },
    get: (id: number) => fetchApi<CrawlRun>(`/runs/${id}`),
  },
}

export function createAlert(productId: number, targetPrice: number, currency: string) {
  return fetchApi<PriceAlert>('/alerts', {
    method: 'POST',
    body: JSON.stringify({
      product_id: productId,
      target_price: targetPrice,
      currency,
    }),
  })
}

export function listAlerts(productId: number, active?: boolean) {
  const searchParams = new URLSearchParams()
  searchParams.set('product_id', productId.toString())
  if (active !== undefined) searchParams.set('active', active.toString())
  return fetchApi<PriceAlertList>(`/alerts?${searchParams.toString()}`)
}

export function deleteAlert(id: string) {
  return fetchApi<void>(`/alerts/${id}`, { method: 'DELETE' })
}

export function fetchDeals(params?: { category?: string; min_pct_drop?: number; limit?: number }) {
  const searchParams = new URLSearchParams()
  if (params?.category) searchParams.set('category', params.category)
  if (params?.min_pct_drop !== undefined) searchParams.set('min_pct_drop', params.min_pct_drop.toString())
  if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString())
  const query = searchParams.toString()
  return fetchApi<DealProduct[]>(`/products/deals${query ? `?${query}` : ''}`)
}

export function getSourcesExportUrl() {
  const searchParams = new URLSearchParams()
  if (ADMIN_API_KEY) searchParams.set('api_key', ADMIN_API_KEY)
  const query = searchParams.toString()
  return `${API_BASE}/sources/export${query ? `?${query}` : ''}`
}

export async function importSources(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/sources/import`, {
    method: 'POST',
    headers: {
      ...(ADMIN_API_KEY ? { 'X-API-Key': ADMIN_API_KEY } : {}),
    },
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json() as Promise<SourceImportResult>
}
