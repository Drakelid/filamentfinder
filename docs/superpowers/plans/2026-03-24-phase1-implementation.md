# FilamentFinder Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add price-per-kg normalization, product list pagination, reduced polling intervals, and CSV export to FilamentFinder.

**Architecture:** Backend utility computes weight from product text fields; `price_per_kg` is a computed field on `ProductResponse` (no DB migration). Pagination wires up existing `skip`/`limit` backend params to new frontend controls. CSV export streams from a new `GET /api/products/export` endpoint registered before `/{product_id}`. Refetch tuning is three targeted frontend edits.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (joinedload), Pydantic v2, pytest; React 18, TypeScript, React Query v5, Tailwind CSS, lucide-react.

---

## File Map

| File | Role |
|---|---|
| `backend/app/utils/__init__.py` | New — makes `utils` a Python package |
| `backend/app/utils/weight.py` | New — `extract_weight_grams` weight parsing utility |
| `backend/tests/test_weight.py` | New — unit tests for weight extraction |
| `backend/app/schemas/product.py` | Edit — add `price_per_kg` field to `ProductResponse` |
| `backend/app/api/endpoints/products.py` | Edit — import utility; compute `price_per_kg` in list/get; add `/export` before `/{product_id}` |
| `frontend/src/api.ts` | Edit — add `price_per_kg` to `Product` interface; add `skip`/`limit` to `products.list` |
| `frontend/src/pages/ProductsPage.tsx` | Edit — pagination controls; `price_per_kg` on cards; export button; remove `refetchInterval` |
| `frontend/src/pages/StatsPage.tsx` | Edit — adaptive `refetchInterval` using React Query v5 syntax |
| `frontend/src/pages/ProductDetailPage.tsx` | Edit — `price_per_kg` display in Current Price panel |
| `frontend/src/pages/PriceChangesPage.tsx` | Edit — add `/kg` column to comparison table using existing `parseWeightFromText` |

---

## Task 1: Weight Extraction Utility (TDD)

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/weight.py`
- Create: `backend/tests/test_weight.py`

- [ ] **Step 1: Create the utils package**

Create `backend/app/utils/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_weight.py`:

```python
import pytest
from app.utils.weight import extract_weight_grams


# --- kg patterns ---
def test_kg_integer():
    assert extract_weight_grams("Bambu PLA 1kg spool") == 1000.0

def test_kg_decimal():
    assert extract_weight_grams("Filament 2.3 kg") == 2300.0

def test_kg_no_space():
    assert extract_weight_grams("Polymaker PLA 1kg") == 1000.0


# --- g patterns ---
def test_grams_integer():
    assert extract_weight_grams("Sample spool 500g") == 500.0

def test_grams_with_space():
    assert extract_weight_grams("Mini spool 250 g") == 250.0

def test_grams_not_diameter():
    # 1.75mm should NOT be interpreted as 1.75g
    assert extract_weight_grams("PLA 1.75mm filament") is None

def test_grams_small_number_with_mm():
    # 3mm diameter filament — should not match as weight
    assert extract_weight_grams("ABS 3mm spool") is None


# --- lbs patterns ---
def test_lbs():
    result = extract_weight_grams("1 lb spool")
    assert result is not None
    assert abs(result - 453.592) < 1.0

def test_lb_singular():
    result = extract_weight_grams("2lb roll")
    assert result is not None
    assert abs(result - 907.18) < 1.0


# --- guard cases ---
def test_empty_string():
    assert extract_weight_grams("") is None

def test_no_weight():
    assert extract_weight_grams("PLA Matte Black") is None

def test_below_minimum():
    # 30g is noise — ignore
    assert extract_weight_grams("Sample 30g") is None

def test_above_maximum():
    # 25000g implausible spool
    assert extract_weight_grams("Industrial 25000g") is None

def test_combined_fields():
    # Simulates concatenated name + variant + size
    assert extract_weight_grams("Bambu PLA  1kg") == 1000.0

def test_case_insensitive():
    assert extract_weight_grams("PETG 1KG BLACK") == 1000.0
```

- [ ] **Step 3: Run tests — verify they all fail**

```bash
cd backend && python -m pytest tests/test_weight.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `app.utils.weight` doesn't exist yet.

- [ ] **Step 4: Implement `extract_weight_grams`**

Create `backend/app/utils/weight.py`:

```python
import re
from typing import Optional

# (number)(optional space)(unit) patterns, evaluated in priority order.
# The 'g' pattern has a negative lookahead to reject filament diameters like "1.75mm".
_PATTERNS = [
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*kg\b', re.IGNORECASE), 1000.0),
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*lbs?\b', re.IGNORECASE), 453.592),
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*g\b(?!\s*\d*\s*mm)', re.IGNORECASE), 1.0),
]

_MIN_GRAMS = 50.0
_MAX_GRAMS = 20000.0


def extract_weight_grams(text: str) -> Optional[float]:
    """
    Parse the first weight value found in `text` and return it in grams.

    Returns None if no weight is found, or if the result is outside
    the plausible spool range (50g – 20,000g).
    """
    if not text:
        return None

    lowered = text.lower()

    for pattern, multiplier in _PATTERNS:
        match = pattern.search(lowered)
        if match:
            raw = match.group(1).replace(',', '.')
            try:
                value = float(raw)
            except ValueError:
                continue
            grams = value * multiplier
            if _MIN_GRAMS <= grams <= _MAX_GRAMS:
                return grams

    return None
```

- [ ] **Step 5: Run tests — verify they all pass**

```bash
cd backend && python -m pytest tests/test_weight.py -v
```
Expected: all 15 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/utils/__init__.py backend/app/utils/weight.py backend/tests/test_weight.py
git commit -m "feat: add extract_weight_grams utility with unit tests"
```

---

## Task 2: `price_per_kg` in Backend Schema and Products Endpoints

**Files:**
- Modify: `backend/app/schemas/product.py`
- Modify: `backend/app/api/endpoints/products.py`

- [ ] **Step 1: Add `price_per_kg` to `ProductResponse`**

In `backend/app/schemas/product.py`, add one field to `ProductResponse` after `latest_price`:

```python
# Before:
    latest_price: Optional[LatestPriceResponse] = None

    class Config:
        from_attributes = True

# After:
    latest_price: Optional[LatestPriceResponse] = None
    price_per_kg: Optional[float] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Add the import in `products.py`**

In `backend/app/api/endpoints/products.py`, add the import after the existing imports (around line 10, after `from app.core.database import get_db`):

```python
from app.utils.weight import extract_weight_grams
```

- [ ] **Step 3: Compute `price_per_kg` in `list_products`**

In `list_products` (around line 127–151), the loop currently builds each `item` and then calls `items.append(item)`. Add the `price_per_kg` computation between those two lines:

```python
    # Existing code:
    for p in products:
        item = ProductResponse(
            id=p.id,
            # ... all existing fields ...
            latest_price=get_latest_price(p),
        )
        # ADD THIS BLOCK:
        price_per_kg = None
        if p.category == 'filament':
            weight_g = extract_weight_grams(
                f"{p.name} {p.variant or ''} {p.size or ''}"
            )
            lp = get_latest_price(p)
            if weight_g is not None and lp is not None and lp.price_amount is not None:
                price_per_kg = float(lp.price_amount) / (weight_g / 1000)
        item.price_per_kg = price_per_kg
        # END ADDED BLOCK
        items.append(item)
```

- [ ] **Step 4: Compute `price_per_kg` in `get_product`**

In `get_product` (around line 261–284), extend the `ProductDetailResponse(...)` constructor call to include `price_per_kg`. Add it as a kwarg after `latest_price=get_latest_price(product)`:

First compute it before the return:
```python
    # Before the return statement, add:
    _price_per_kg = None
    if product.category == 'filament':
        _weight_g = extract_weight_grams(
            f"{product.name} {product.variant or ''} {product.size or ''}"
        )
        _lp = get_latest_price(product)
        if _weight_g is not None and _lp is not None and _lp.price_amount is not None:
            _price_per_kg = float(_lp.price_amount) / (_weight_g / 1000)

    return ProductDetailResponse(
        # ... all existing fields ...
        latest_price=get_latest_price(product),
        source_name=product.source.name if product.source else None,
        source_domain=product.source.domain if product.source else "",
        canonical_product_id=product.canonical_product_id,
        price_per_kg=_price_per_kg,   # ADD THIS
    )
```

- [ ] **Step 5: Write a quick smoke test**

Start the backend locally (or run existing tests) to confirm no import errors:

```bash
cd backend && python -c "from app.api.endpoints.products import router; print('OK')"
```
Expected: prints `OK` with no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/product.py backend/app/api/endpoints/products.py
git commit -m "feat: compute price_per_kg on product responses"
```

---

## Task 3: CSV Export Endpoint

**Files:**
- Modify: `backend/app/api/endpoints/products.py`

- [ ] **Step 1: Add required imports at the top of `products.py`**

Add these imports after the existing ones (around line 1–10):

```python
import csv
import io
from fastapi.responses import StreamingResponse
```

- [ ] **Step 2: Add the export endpoint**

The `/export` route must be registered **before** `@router.get("/{product_id}")` (currently around line 250). A good location is right after the `/materials` endpoint (currently ends around line 247) and before line 250. Add:

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
    """Export matching products as a CSV file."""
    query = db.query(Product).options(
        joinedload(Product.price_observations),
        joinedload(Product.source),
    )

    if category:
        query = query.filter(Product.category == category.lower())
    if product_type:
        query = query.filter(Product.product_type == product_type.lower())
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if source_id:
        query = query.filter(Product.source_id == source_id)

    if min_price is not None or max_price is not None:
        latest_prices = db.query(
            PriceObservation.product_id,
            func.max(PriceObservation.observed_at).label('max_observed')
        ).group_by(PriceObservation.product_id).subquery()

        price_filter_query = db.query(PriceObservation.product_id).join(
            latest_prices,
            (PriceObservation.product_id == latest_prices.c.product_id) &
            (PriceObservation.observed_at == latest_prices.c.max_observed)
        )
        delivered_price = _delivered_price_expr()
        if min_price is not None:
            price_filter_query = price_filter_query.filter(delivered_price >= min_price)
        if max_price is not None:
            price_filter_query = price_filter_query.filter(delivered_price <= max_price)
        product_ids = [r[0] for r in price_filter_query.all()]
        query = query.filter(Product.id.in_(product_ids))

    products = query.order_by(desc(Product.updated_at)).limit(10_000).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            'id', 'name', 'brand', 'category', 'product_type', 'size',
            'price', 'currency', 'list_price', 'shipping', 'delivered_price',
            'price_per_kg', 'in_stock', 'source_name', 'source_domain',
            'url', 'last_seen_at',
        ])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()

        for p in products:
            lp = get_latest_price(p)
            ppkg = None
            if p.category == 'filament':
                wg = extract_weight_grams(
                    f"{p.name} {p.variant or ''} {p.size or ''}"
                )
                if wg is not None and lp is not None and lp.price_amount is not None:
                    ppkg = round(float(lp.price_amount) / (wg / 1000), 2)

            writer.writerow([
                p.id,
                p.name,
                p.brand or '',
                p.category,
                p.product_type or '',
                p.size or '',
                str(lp.price_amount) if lp and lp.price_amount is not None else '',
                lp.currency or '' if lp else '',
                str(lp.list_price_amount) if lp and lp.list_price_amount is not None else '',
                str(lp.shipping_amount) if lp and lp.shipping_amount is not None else '',
                str(lp.total_price_amount) if lp and lp.total_price_amount is not None else '',
                str(ppkg) if ppkg is not None else '',
                str(lp.in_stock) if lp and lp.in_stock is not None else '',
                p.source.name if p.source else '',
                p.source.domain if p.source else '',
                p.canonical_url,
                p.last_seen_at.isoformat() if p.last_seen_at else '',
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="filamentfinder-export.csv"'},
    )
```

- [ ] **Step 3: Write a test for the export endpoint**

Create `backend/tests/test_export.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


def test_export_returns_csv_headers():
    """Export endpoint must return text/csv with Content-Disposition."""
    with patch("app.api.endpoints.products.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.options.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_get_db.return_value = mock_db

        response = client.get("/api/products/export")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert "filamentfinder-export.csv" in response.headers["content-disposition"]


def test_export_contains_header_row():
    """CSV output must include the header row."""
    with patch("app.api.endpoints.products.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.options.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_get_db.return_value = mock_db

        response = client.get("/api/products/export")

    content = response.text
    assert "id,name,brand" in content
    assert "price_per_kg" in content
    assert "source_name" in content
```

Note: if the TestClient approach doesn't work cleanly with the DB dependency injection, simplify to just testing the `/export` path returns a non-404 by running the app against a real test database. The key assertions are the response headers and CSV structure.

- [ ] **Step 4: Run smoke test**

```bash
cd backend && python -c "
from app.api.endpoints.products import router
routes = [r.path for r in router.routes]
export_idx = routes.index('/export')
product_id_idx = routes.index('/{product_id}')
assert export_idx < product_id_idx, f'/export ({export_idx}) must come before /{{product_id}} ({product_id_idx})'
print('Route order OK:', routes)
"
```
Expected: prints `Route order OK:` with `/export` appearing before `/{product_id}`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/endpoints/products.py backend/tests/test_export.py
git commit -m "feat: add GET /api/products/export CSV streaming endpoint"
```

---

## Task 4: Frontend Type Updates (`api.ts`)

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add `price_per_kg` to the `Product` interface**

In `frontend/src/api.ts`, find the `Product` interface (around line 183). Add `price_per_kg` after `latest_price`:

```typescript
// Before:
  latest_price: LatestPrice | null
  source_name?: string
  source_domain?: string
}

// After:
  latest_price: LatestPrice | null
  price_per_kg: number | null
  source_name?: string
  source_domain?: string
}
```

- [ ] **Step 2: Add `skip` and `limit` to `products.list`**

In the `products.list` function (around line 381), extend the params type and the URLSearchParams construction:

Params type — add two new optional fields:
```typescript
// Before:
    search?: string
  }) => {

// After:
    search?: string
    skip?: number
    limit?: number
  }) => {
```

URLSearchParams body — add two new conditions after the existing `search` param line:
```typescript
      if (params?.search) searchParams.set('search', params.search)
      // ADD:
      if (params?.skip !== undefined) searchParams.set('skip', params.skip.toString())
      if (params?.limit !== undefined) searchParams.set('limit', params.limit.toString())
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add price_per_kg and pagination params to api.ts Product type"
```

---

## Task 5: `ProductsPage` — Pagination, Price/kg, Export Button, Refetch Tuning

**Files:**
- Modify: `frontend/src/pages/ProductsPage.tsx`

This task has multiple changes to the same file. Apply them in order.

- [ ] **Step 1: Add `Download` to lucide imports**

Find the existing lucide-react import line (line 3):
```typescript
// Before:
import { Search, Filter, Loader2, Package } from 'lucide-react'

// After:
import { Search, Filter, Loader2, Package, Download, ChevronLeft, ChevronRight } from 'lucide-react'
```

- [ ] **Step 2: Add `PAGE_SIZE` constant and `page` state**

Find the state declarations (around line 49–55). Add below the existing `useState` calls:

```typescript
// After the existing useState declarations, add:
const PAGE_SIZE = 24
const [page, setPage] = useState(1)
```

- [ ] **Step 3: Remove `refetchInterval`, add `staleTime`**

Find `refetchInterval: 3000` in the `useQuery` call (around line 66). Replace:

```typescript
// Before:
    refetchInterval: 3000,

// After:
    staleTime: 60_000,
```

- [ ] **Step 4: Wire pagination into the query**

In the `queryFn` call, add `skip` and `limit` to the params:

```typescript
// Before:
    queryFn: () => api.products.list({
      category: category || undefined,
      product_type: productType || undefined,
      min_price: minPrice ? parseFloat(minPrice) : undefined,
      max_price: maxPrice ? parseFloat(maxPrice) : undefined,
      search: search || undefined
    }),

// After:
    queryFn: () => api.products.list({
      category: category || undefined,
      product_type: productType || undefined,
      min_price: minPrice ? parseFloat(minPrice) : undefined,
      max_price: maxPrice ? parseFloat(maxPrice) : undefined,
      search: search || undefined,
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
```

Also add `page` to the `queryKey` array:
```typescript
// Before:
    queryKey: ['products', { category, productType, minPrice, maxPrice, search }],

// After:
    queryKey: ['products', { category, productType, minPrice, maxPrice, search, page }],
```

- [ ] **Step 5: Reset page on filter changes**

In `clearFilters` (around line 74), add `setPage(1)`:
```typescript
  const clearFilters = () => {
    setCategory('')
    setProductType('')
    setMinPrice('')
    setMaxPrice('')
    setSearch('')
    setSearchInput('')
    setPage(1)   // ADD
  }
```

In each filter `onChange` handler inside the filter panel (the `<select>` for Category, the `<select>` for Material Type, and the `<input>` for Min/Max Price), add `setPage(1)`. For example:

```typescript
// Category select — Before:
onChange={(e) => {
  setCategory(e.target.value)
  setProductType('')
}}

// After:
onChange={(e) => {
  setCategory(e.target.value)
  setProductType('')
  setPage(1)
}}
```

Do the same for Material Type select (`setPage(1)` after `setProductType(e.target.value)`), Min Price input (`setPage(1)` after `setMinPrice(e.target.value)`), and Max Price input (`setPage(1)` after `setMaxPrice(e.target.value)`).

- [ ] **Step 6: Add export button to the toolbar**

Find the toolbar row (around line 115–155). Add the export button after the existing Filters button:

```tsx
// After the closing </button> of the Filters button, add:
<button
  onClick={() => {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (productType) params.set('product_type', productType)
    if (minPrice) params.set('min_price', minPrice)
    if (maxPrice) params.set('max_price', maxPrice)
    if (search) params.set('search', search)
    window.open(`/api/products/export${params.toString() ? '?' + params.toString() : ''}`, '_blank')
  }}
  className="flex items-center gap-2 px-3 py-2 rounded-lg border bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600 transition-colors"
  title="Export to CSV"
>
  <Download className="w-5 h-5" />
  Export
</button>
```

- [ ] **Step 7: Show `price_per_kg` on product cards**

Inside the product card's price section (around line 267–282, in the `<div className="text-lg font-bold text-gray-100">` block), add the per-kg line after the main price display:

```tsx
// After the list_price strikethrough block, add:
{product.price_per_kg && product.latest_price?.currency && (
  <div className="text-xs text-gray-500 mt-0.5">
    {new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: product.latest_price.currency,
      maximumFractionDigits: 0,
    }).format(product.price_per_kg)}/kg
  </div>
)}
```

- [ ] **Step 8: Add pagination controls below the product grid**

After the closing `</div>` of the product grid (after the `products.map(...)` block, around line 301), add:

```tsx
{(data?.total ?? 0) > PAGE_SIZE && (() => {
  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE)
  return (
    <div className="flex items-center justify-center gap-4 mt-6">
      <button
        onClick={() => setPage(p => p - 1)}
        disabled={page === 1}
        className="flex items-center gap-1 px-3 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Previous
      </button>
      <span className="text-sm text-gray-400">
        Page {page} of {totalPages}
      </span>
      <button
        onClick={() => setPage(p => p + 1)}
        disabled={page === totalPages}
        className="flex items-center gap-1 px-3 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Next
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  )
})()}
```

- [ ] **Step 9: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/ProductsPage.tsx
git commit -m "feat: add pagination, price/kg display, export button, and fix refetch interval on ProductsPage"
```

---

## Task 6: `StatsPage` Refetch Tuning

**Files:**
- Modify: `frontend/src/pages/StatsPage.tsx`

- [ ] **Step 1: Update the stats query refetchInterval**

In `StatsPage.tsx` (around line 260–263), find the stats `useQuery` call:

```typescript
// Before:
  const { data, isLoading, error } = useQuery<StatsData>({
    queryKey: ['stats'],
    queryFn: api.stats.get,
    refetchInterval: 5000,
  })

// After:
  const { data, isLoading, error } = useQuery<StatsData>({
    queryKey: ['stats'],
    queryFn: api.stats.get,
    refetchInterval: (query) =>
      (query.state.data as StatsData | undefined)?.overview?.running_crawls > 0
        ? 5000
        : 60_000,
  })
```

Leave the `stats-health` query (around line 265–268) unchanged.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/StatsPage.tsx
git commit -m "perf: adaptive refetch on StatsPage — poll fast only when crawls are running"
```

---

## Task 7: `ProductDetailPage` Price/kg Display

**Files:**
- Modify: `frontend/src/pages/ProductDetailPage.tsx`

- [ ] **Step 1: Add `price_per_kg` below the main price**

In `ProductDetailPage.tsx`, find the "Current Price" panel (around line 204–243). Inside the `{product.latest_price ? (` block, add the per-kg line after the main price `<div>` (around line 210):

```tsx
// After:
<div className="text-3xl font-bold text-gray-100">
  {formatPrice(product.latest_price.price_amount, product.latest_price.currency)}
</div>

// Add:
{product.price_per_kg && product.latest_price.currency && (
  <div className="text-sm text-gray-400 mt-1">
    {new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: product.latest_price.currency,
      maximumFractionDigits: 0,
    }).format(product.price_per_kg)}/kg
  </div>
)}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProductDetailPage.tsx
git commit -m "feat: show price per kg on ProductDetailPage"
```

---

## Task 8: `PriceChangesPage` /kg Column

**Files:**
- Modify: `frontend/src/pages/PriceChangesPage.tsx`

`PriceChangesPage` already has `parseWeightFromText` and `getDeliveredPrice` helper functions (around lines 94–152). The `/kg` column uses these — no backend change needed.

- [ ] **Step 1: Add a `getPricePerKg` helper**

`PriceChangesPage` already has all the weight/price helpers needed. Add this helper after `getDeliveredPrice` (around line 152):

```typescript
function getPricePerKg(
  product: ComparisonProduct,
  extraFee = 0
): number | null {
  const delivered = getDeliveredPrice(product.latest_price, extraFee)
  if (delivered === null) return null
  const weight = getProductWeight(product)
  if (!weight) return null
  return delivered / (weight.grams / 1000)
}
```

- [ ] **Step 2: Find the product comparison rows and add the `/kg` column**

Search `PriceChangesPage.tsx` for where individual `ComparisonProduct` items are rendered in a table or list (look for `product.latest_price`, `source_name`, or the price columns). This is typically inside a map over `group.products` or `crossSourceGroup.products`.

In each row that shows a price, add a new cell after the delivered price cell:

```tsx
<td className="px-3 py-2 text-right text-xs text-gray-400 whitespace-nowrap">
  {getPricePerKg(product, shippingFee) !== null
    ? `${new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 0,
      }).format(getPricePerKg(product, shippingFee)!)} /kg`
    : '—'}
</td>
```

Also add the corresponding column header cell `<th className="px-3 py-2 text-right text-xs text-gray-400">/kg</th>` in the table header row.

Note: `PriceChangesPage` is a large file (~800+ lines). Use your editor's search for `group.products.map` or `ComparisonProduct` renders to find the right location. There may be multiple product-row rendering sites (grouped by type, by variant); add the `/kg` column consistently to each.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/PriceChangesPage.tsx
git commit -m "feat: add price-per-kg column to PriceChangesPage comparison table"
```

---

## Final Verification

- [ ] **Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: all tests pass including `test_weight.py`.

- [ ] **Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Manual smoke test checklist**
  - [ ] `/products` page loads, shows 24 products, Previous/Next pagination works
  - [ ] Product cards show price/kg for filament products with known spool sizes
  - [ ] Clicking Export downloads a `.csv` file with correct columns including `source_name`
  - [ ] `/products/{id}` detail page shows price/kg below the main price for filament
  - [ ] `/price-changes` comparison table has a `/kg` column
  - [ ] `/stats` page stops polling every 5s when no crawls are running (verify in browser Network tab — requests should be ~60s apart when `running_crawls == 0`)
