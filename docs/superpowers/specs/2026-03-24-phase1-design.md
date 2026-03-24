# FilamentFinder Phase 1 — Design Spec

**Date:** 2026-03-24
**Status:** Approved
**Scope:** 4 focused improvements — no new DB migrations, no new infrastructure

---

## Background

FilamentFinder already has a solid foundation: product discovery, price tracking, crawl history, Shopify/Magento/JSON-LD/WooCommerce parsers, cross-source price comparison, and per-source shipping fees.

Note: The WooCommerce parser (`worker/parsers/woocommerce.py`, priority=85) was found to already be fully implemented during spec review. It is excluded from Phase 1 scope.

Phase 1 adds 4 improvements that ship without new DB tables or background services.

**Out of scope for Phase 1:** price alerts/watchlist, charting, deduplication UI, low-confidence review queue (Phase 2 and 3).

---

## Feature 1: Price-per-kg Normalization

### Problem
Filament is sold in 500g, 1kg, and 2.3kg spools. Comparing prices across spool sizes is the core use case, but no normalized per-kg price is currently shown.

### Design

**New utility — `backend/app/utils/weight.py`:**

```python
def extract_weight_grams(text: str) -> Optional[float]
```

- Input: concatenated `name + ' ' + (variant or '') + ' ' + (size or '')`, lowercased
- Regex patterns in priority order:
  1. `(\d+(?:\.\d+)?)\s*kg` → value × 1000
  2. `(\d+(?:\.\d+)?)\s*g\b` → value as-is; guard: skip if the number is < 10 AND the match is immediately followed by `mm` (filament diameter, not weight)
  3. `(\d+(?:\.\d+)?)\s*lbs?` → value × 453.592
- Returns `None` if: no match found, result < 50 (noise), result > 20000 (implausible spool)
- `backend/app/utils/__init__.py` — new empty file to make `utils` a package

**`price_per_kg` added to `ProductResponse` schema (`backend/app/schemas/product.py`):**
```python
price_per_kg: Optional[float] = None
```

**Computed in `backend/app/api/endpoints/products.py`** inside the `list_products` loop, after `get_latest_price(p)` is called:

Add the import at the top of the file:
```python
from app.utils.weight import extract_weight_grams
```

Computation (must guard all nullable fields):
```python
price_per_kg = None
if p.category == 'filament':
    weight_g = extract_weight_grams(f"{p.name} {p.variant or ''} {p.size or ''}")
    latest = get_latest_price(p)
    if weight_g is not None and latest is not None and latest.price_amount is not None:
        price_per_kg = float(latest.price_amount) / (weight_g / 1000)
item.price_per_kg = price_per_kg
```

Same null-guarded computation applied in `get_product` (single product endpoint) and the export endpoint.

**Frontend — `frontend/src/api.ts`:**
Add `price_per_kg: number | null` to the `Product` interface.

**Frontend display:**
- `ProductsPage` cards: below the main price, show `"NOK X/kg"` in `text-xs text-gray-500` when `price_per_kg` is non-null
- `ProductDetailPage` header: show price-per-kg next to the main price
- `PriceChangesPage` comparison table: add a `/kg` column to the material-grouped view

---

## Feature 2: Pagination

### Problem
`ProductsPage` fetches up to 100 products with no UI controls. As tracked products grow, this is slow to render.

### Design

**Backend:** no changes. `GET /api/products` already accepts `skip` (default 0) and `limit` (default 100, max 500).

**`frontend/src/api.ts` — `products.list` function:**
Add `skip` and `limit` to the params object and forward them to `URLSearchParams`:
```typescript
list: (params?: {
  category?: string;
  product_type?: string;
  min_price?: number;
  max_price?: number;
  brand?: string;
  source_id?: number;
  active?: boolean;
  search?: string;
  skip?: number;      // NEW
  limit?: number;     // NEW
}) => { ... }
```
Inside the function body, add:
```typescript
if (params?.skip !== undefined) searchParams.set('skip', params.skip.toString())
if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString())
```

**`frontend/src/pages/ProductsPage.tsx` state:**
- Add `const PAGE_SIZE = 24`
- Add `const [page, setPage] = useState(1)`
- Update query call: `skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE`
- In `clearFilters`: also call `setPage(1)`
- In each filter's `onChange` handler: call `setPage(1)`

**Pagination controls** (inline, below the product grid):
- Show only when `(data?.total ?? 0) > PAGE_SIZE`
- `totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE)`
- Previous button: disabled when `page === 1`, calls `setPage(p => p - 1)`
- Label: `"Page {page} of {totalPages}"`
- Next button: disabled when `page === totalPages`, calls `setPage(p => p + 1)`

---

## Feature 3: Refetch Interval Tuning

### Problem
`ProductsPage` polls the backend every 3 seconds — aggressive for data that changes only during crawl runs.

### Design

Three targeted frontend-only changes:

**`frontend/src/pages/ProductsPage.tsx`** — products query:
```typescript
// Before:
refetchInterval: 3000,

// After:
staleTime: 60_000,
// (remove refetchInterval entirely)
```

**`frontend/src/pages/StatsPage.tsx`** — stats query (React Query v5 syntax):
```typescript
// Before:
refetchInterval: 5000,

// After:
refetchInterval: (query) =>
  (query.state.data as StatsData | undefined)?.overview?.running_crawls > 0
    ? 5000
    : 60_000,
```

The `stats-health` query (`refetchInterval: 15000`) is left unchanged.

Note: The functional form of `refetchInterval` in React Query v5 receives a `Query` object, not the data directly. The data is accessed via `query.state.data`.

---

## Feature 4: CSV Export

### Problem
No way to export product data for spreadsheet analysis.

### Design

**Backend — `backend/app/api/endpoints/products.py`:**

New endpoint `GET /api/products/export`. This route **must be registered before** `@router.get("/{product_id}")` to avoid FastAPI interpreting "export" as a product ID integer.

```python
@router.get("/export")
def export_products(
    category: Optional[str] = None,
    product_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    source_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
```

- Reuses the same filter logic as `list_products` (extract to a shared `_build_product_query` helper or inline the same filters)
- Hard cap: `limit(10_000)`
- Eagerly loads both `price_observations` and `source` via `joinedload`:
  ```python
  query = db.query(Product).options(
      joinedload(Product.price_observations),
      joinedload(Product.source),
  )
  ```
  `source.name` and `source.domain` are then accessed as `product.source.name` and `product.source.domain` (not via `ProductResponse`, which doesn't include them)
- Returns `StreamingResponse(generate_csv(...), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="filamentfinder-export.csv"'})`
- The generator function uses `csv.writer` writing to a `StringIO` per row (or yields lines directly)

**CSV columns:**
`id, name, brand, category, product_type, size, price, currency, list_price, shipping, delivered_price, price_per_kg, in_stock, source_name, source_domain, url, last_seen_at`

`source_name` is populated from the joined `Source.name` (not from `ProductResponse`, which doesn't include it). The export endpoint queries `Source` directly rather than relying on the response schema.

**Frontend — `frontend/src/pages/ProductsPage.tsx`:**

Add a download button in the toolbar row (next to the Filters button):
```tsx
import { Download } from 'lucide-react'
```

On click: build a query string from the current active filter state (same params as the list query minus `skip`/`limit`) and call `window.open('/api/products/export?' + queryString, '_blank')`. The browser handles the file download natively.

**`frontend/src/api.ts`:** No new function needed — the export is a direct browser navigation, not a fetch call.

---

## File Change Summary

| File | Change |
|---|---|
| `backend/app/utils/__init__.py` | New (empty package init) |
| `backend/app/utils/weight.py` | New — `extract_weight_grams` utility |
| `backend/app/schemas/product.py` | Edit — add `price_per_kg: Optional[float] = None` to `ProductResponse` |
| `backend/app/api/endpoints/products.py` | Edit — compute `price_per_kg` in list/get loops; add `/export` endpoint before `/{product_id}` |
| `frontend/src/api.ts` | Edit — add `price_per_kg` to `Product` interface; add `skip`/`limit` to `products.list` params |
| `frontend/src/pages/ProductsPage.tsx` | Edit — pagination state + controls; `price_per_kg` display; export button; remove `refetchInterval` |
| `frontend/src/pages/StatsPage.tsx` | Edit — adaptive `refetchInterval` using React Query v5 `query.state.data` syntax |
| `frontend/src/pages/ProductDetailPage.tsx` | Edit — `price_per_kg` display |
| `frontend/src/pages/PriceChangesPage.tsx` | Edit — `/kg` column in comparison table |

**No DB migrations. No new npm packages. No Docker changes.**

---

## Testing Notes

- `extract_weight_grams`: unit tests for kg, g, lbs patterns; guard cases (diameter `1.75mm`, values < 50g, values > 20000g, empty string)
- `price_per_kg`: verify it is `None` for resin products and `None` when weight cannot be parsed
- CSV export: test that `Content-Type: text/csv` and `Content-Disposition` headers are set; test that `source_name` column is populated (not empty); test that filter params narrow the result set
- Pagination: verify `skip`/`limit` are forwarded in `api.ts`; verify page resets to 1 on filter change
