import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, case, or_, func, select

from app.core.database import get_db
from app.utils.weight import extract_weight_grams
from app.models import Product, PriceObservation, PriceChange, Source
from app.materials import (
    detect_material, 
    normalize_material_for_grouping, 
    get_material_display_name,
    MATERIALS,
    get_filament_materials,
    get_resin_materials,
)
from app.schemas import (
    ProductResponse,
    ProductListResponse,
    ProductDetailResponse,
    DealProduct,
    PriceObservationResponse,
    PriceChangeResponse,
    PriceHistoryResponse,
)
from app.schemas.product import LatestPriceResponse

router = APIRouter()


def get_latest_price(product: Product) -> Optional[LatestPriceResponse]:
    if product.price_observations:
        latest = max(product.price_observations, key=lambda p: p.observed_at)
        shipping_amount = latest.shipping_amount
        shipping_currency = latest.shipping_currency or latest.currency
        total_amount = latest.total_price_amount
        if total_amount is None and (latest.price_amount is not None or shipping_amount is not None):
            base = latest.price_amount or Decimal("0")
            ship = shipping_amount or Decimal("0")
            total_amount = base + ship
        return LatestPriceResponse(
            price_amount=latest.price_amount,
            currency=latest.currency,
            list_price_amount=latest.list_price_amount,
            shipping_amount=shipping_amount,
            shipping_currency=shipping_currency,
            total_price_amount=total_amount,
            in_stock=latest.in_stock,
            observed_at=latest.observed_at,
        )
    return None


def _delivered_price_expr():
    """Build the delivered-price expression used for filtering latest observations."""
    return case(
        (
            PriceObservation.total_price_amount.isnot(None),
            PriceObservation.total_price_amount,
        ),
        (
            or_(
                PriceObservation.price_amount.isnot(None),
                PriceObservation.shipping_amount.isnot(None),
            ),
            func.coalesce(PriceObservation.price_amount, 0) + func.coalesce(PriceObservation.shipping_amount, 0),
        ),
        else_=None,
    )


@router.get("", response_model=ProductListResponse)
def list_products(
    category: Optional[str] = Query(None, description="Filter by category: filament or resin"),
    product_type: Optional[str] = Query(None, description="Filter by product type: pla, petg, abs, tpu, etc."),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    brand: Optional[str] = Query(None, description="Filter by brand name"),
    source_id: Optional[int] = None,
    active: Optional[bool] = None,
    search: Optional[str] = None,
    sort: Optional[str] = Query(None, description="Sort by updated, name, price_asc, or price_desc"),
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum products to return"),
    db: Session = Depends(get_db),
):
    query = db.query(Product).options(joinedload(Product.price_observations))
    latest_delivered_price = (
        select(_delivered_price_expr())
        .where(PriceObservation.product_id == Product.id)
        .order_by(PriceObservation.observed_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    
    if category:
        query = query.filter(Product.category == category.lower())
    if product_type:
        query = query.filter(Product.product_type == product_type.lower())
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    if source_id:
        query = query.filter(Product.source_id == source_id)
    if active is not None:
        query = query.filter(Product.active == active)
    if search:
        query = query.filter(
            Product.search_vector.op("@@")(func.plainto_tsquery("english", search))
        )
    
    # Price filtering requires a subquery on price_observations
    if min_price is not None or max_price is not None:
        # Get products with latest price in range
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
        
        product_ids_with_price = [r[0] for r in price_filter_query.all()]
        query = query.filter(Product.id.in_(product_ids_with_price))
    
    total = query.count()

    if sort == "price_asc":
        query = query.order_by(latest_delivered_price.asc().nullslast(), desc(Product.updated_at))
    elif sort == "price_desc":
        query = query.order_by(latest_delivered_price.desc().nullslast(), desc(Product.updated_at))
    elif sort == "name":
        query = query.order_by(Product.name.asc(), desc(Product.updated_at))
    elif sort == "relevance":
        query = query.order_by(desc(Product.confidence), desc(Product.updated_at))
    else:
        query = query.order_by(desc(Product.updated_at))

    products = query.offset(skip).limit(limit).all()
    
    items = []
    for p in products:
        item = ProductResponse(
            id=p.id,
            source_id=p.source_id,
            canonical_url=p.canonical_url,
            name=p.name,
            brand=p.brand,
            category=p.category,
            product_type=p.product_type,
            variant=p.variant,
            color=p.color,
            size=p.size,
            image_url=p.image_url,
            sku=p.sku,
            gtin=p.gtin,
            active=p.active,
            confidence=p.confidence,
            created_at=p.created_at,
            updated_at=p.updated_at,
            last_seen_at=p.last_seen_at,
            latest_price=get_latest_price(p),
        )
        price_per_kg = None
        if p.category == 'filament':
            weight_g = extract_weight_grams(f"{p.name} {p.variant or ''} {p.size or ''}")
            lp = get_latest_price(p)
            if weight_g is not None and lp is not None and lp.price_amount is not None:
                price_per_kg = float(lp.price_amount) / (weight_g / 1000)
        item.price_per_kg = price_per_kg
        items.append(item)

    return ProductListResponse(items=items, total=total)


@router.get("/deals", response_model=list[DealProduct])
def list_deals(
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None, description="Filter by category: filament or resin"),
    min_pct_drop: float = Query(5.0, ge=0),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    pct_drop_expr = ((PriceChange.old_price - PriceChange.new_price) / PriceChange.old_price * 100).label("pct_drop")

    query = (
        db.query(Product, PriceChange, pct_drop_expr)
        .join(PriceChange, PriceChange.product_id == Product.id)
        .options(joinedload(Product.price_observations), joinedload(Product.source))
        .filter(PriceChange.changed_at >= cutoff)
        .filter(PriceChange.old_price.isnot(None), PriceChange.new_price.isnot(None))
        .filter(PriceChange.old_price > 0)
        .filter(PriceChange.old_price < 100000)
        .filter(PriceChange.new_price < 100000)
        .filter(PriceChange.change_type.in_(["decrease", "price_decrease"]))
        .filter(PriceChange.new_price < PriceChange.old_price)
        .filter(pct_drop_expr >= min_pct_drop)
        .filter(pct_drop_expr <= 95)
    )

    if category:
        query = query.filter(Product.category == category.lower())

    results = query.order_by(desc(pct_drop_expr), desc(PriceChange.changed_at)).limit(limit).all()
    items = []
    for product, change, pct_drop in results:
        price_per_kg = None
        if product.category == "filament":
            weight_g = extract_weight_grams(f"{product.name} {product.variant or ''} {product.size or ''}")
            latest_price = get_latest_price(product)
            if weight_g is not None and latest_price is not None and latest_price.price_amount is not None:
                price_per_kg = float(latest_price.price_amount) / (weight_g / 1000)

        items.append(
            DealProduct(
                id=product.id,
                source_id=product.source_id,
                canonical_url=product.canonical_url,
                name=product.name,
                brand=product.brand,
                category=product.category,
                product_type=product.product_type,
                variant=product.variant,
                color=product.color,
                size=product.size,
                image_url=product.image_url,
                sku=product.sku,
                gtin=product.gtin,
                active=product.active,
                confidence=product.confidence,
                latest_change_percent=product.latest_change_percent,
                latest_change_type=product.latest_change_type,
                latest_change_at=product.latest_change_at,
                created_at=product.created_at,
                updated_at=product.updated_at,
                last_seen_at=product.last_seen_at,
                latest_price=get_latest_price(product),
                price_per_kg=price_per_kg,
                source_name=product.source.name if product.source else None,
                old_price=change.old_price,
                new_price=change.new_price,
                pct_drop=float(pct_drop),
                detected_at=change.changed_at,
            )
        )

    return items


@router.get("/with-changes", response_model=ProductListResponse)
def list_products_with_changes(
    change_type: Optional[str] = Query(None, description="Filter by change type: price_increase, price_decrease"),
    category: Optional[str] = Query(None, description="Filter by category: filament or resin"),
    days: int = Query(7, description="Number of days to look back for changes"),
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum products to return"),
    db: Session = Depends(get_db),
):
    """Get products that have had price changes in the specified time period."""
    from datetime import timedelta
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = (
        db.query(Product)
        .options(joinedload(Product.price_observations))
        .filter(Product.latest_change_at != None)
        .filter(Product.latest_change_at >= cutoff_date)
    )
    
    if change_type:
        query = query.filter(Product.latest_change_type == change_type)
    if category:
        query = query.filter(Product.category == category.lower())
    
    total = query.count()
    products = query.order_by(desc(Product.latest_change_at)).offset(skip).limit(limit).all()
    
    items = []
    for p in products:
        item = ProductResponse(
            id=p.id,
            source_id=p.source_id,
            canonical_url=p.canonical_url,
            name=p.name,
            brand=p.brand,
            category=p.category,
            product_type=p.product_type,
            variant=p.variant,
            color=p.color,
            size=p.size,
            image_url=p.image_url,
            sku=p.sku,
            gtin=p.gtin,
            active=p.active,
            confidence=p.confidence,
            latest_change_percent=p.latest_change_percent,
            latest_change_type=p.latest_change_type,
            latest_change_at=p.latest_change_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
            last_seen_at=p.last_seen_at,
            latest_price=get_latest_price(p),
        )
        items.append(item)
    
    return ProductListResponse(items=items, total=total)


@router.get("/materials")
async def get_materials(
    category: Optional[str] = Query(None, description="Filter by category: filament or resin"),
):
    """
    Get the material registry with all supported material types.
    """
    if category == "filament":
        material_keys = get_filament_materials()
    elif category == "resin":
        material_keys = get_resin_materials()
    else:
        material_keys = list(MATERIALS.keys())
    
    materials = []
    for key in material_keys:
        info = MATERIALS[key]
        materials.append({
            "key": key,
            "display_name": info.get("display_name", key),
            "category": info.get("category"),
            "description": info.get("description"),
            "parent": info.get("parent"),
            "variants": info.get("variants", []),
        })
    
    # Sort by category then display name
    materials.sort(key=lambda m: (m["category"], m["display_name"]))
    
    return {
        "materials": materials,
        "total": len(materials),
    }


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
                wg = extract_weight_grams(f"{p.name} {p.variant or ''} {p.size or ''}")
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


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(joinedload(Product.price_observations), joinedload(Product.source))
        .filter(Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    _price_per_kg = None
    if product.category == 'filament':
        _weight_g = extract_weight_grams(f"{product.name} {product.variant or ''} {product.size or ''}")
        _lp = get_latest_price(product)
        if _weight_g is not None and _lp is not None and _lp.price_amount is not None:
            _price_per_kg = float(_lp.price_amount) / (_weight_g / 1000)

    return ProductDetailResponse(
        id=product.id,
        source_id=product.source_id,
        canonical_url=product.canonical_url,
        name=product.name,
        brand=product.brand,
        category=product.category,
        product_type=product.product_type,
        variant=product.variant,
        color=product.color,
        size=product.size,
        image_url=product.image_url,
        sku=product.sku,
        gtin=product.gtin,
        active=product.active,
        confidence=product.confidence,
        created_at=product.created_at,
        updated_at=product.updated_at,
        last_seen_at=product.last_seen_at,
        latest_price=get_latest_price(product),
        source_name=product.source.name if product.source else None,
        source_domain=product.source.domain if product.source else "",
        canonical_product_id=product.canonical_product_id,
        price_per_kg=_price_per_kg,
    )


@router.get("/{product_id}/history", response_model=PriceHistoryResponse)
def get_product_history(
    product_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    obs_query = db.query(PriceObservation).filter(PriceObservation.product_id == product_id)
    if from_date:
        obs_query = obs_query.filter(PriceObservation.observed_at >= from_date)
    if to_date:
        obs_query = obs_query.filter(PriceObservation.observed_at <= to_date)
    
    observations = obs_query.order_by(desc(PriceObservation.observed_at)).all()
    
    changes_query = db.query(PriceChange).filter(PriceChange.product_id == product_id)
    if from_date:
        changes_query = changes_query.filter(PriceChange.changed_at >= from_date)
    if to_date:
        changes_query = changes_query.filter(PriceChange.changed_at <= to_date)
    
    changes = changes_query.order_by(desc(PriceChange.changed_at)).all()
    
    return PriceHistoryResponse(
        observations=[PriceObservationResponse.model_validate(o) for o in observations],
        changes=[PriceChangeResponse.model_validate(c) for c in changes],
        total_observations=len(observations),
        total_changes=len(changes),
    )


@router.get("/{product_id}/changes", response_model=list[PriceChangeResponse])
def get_product_changes(
    product_id: int,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum price changes to return"),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    query = db.query(PriceChange).filter(PriceChange.product_id == product_id)
    if from_date:
        query = query.filter(PriceChange.changed_at >= from_date)
    if to_date:
        query = query.filter(PriceChange.changed_at <= to_date)
    
    changes = query.order_by(desc(PriceChange.changed_at)).offset(skip).limit(limit).all()
    
    return [PriceChangeResponse.model_validate(c) for c in changes]


@router.get("/compare/cross-source")
def get_cross_source_comparison(
    category: Optional[str] = Query(None, description="Filter by category: filament or resin"),
    product_type: Optional[str] = Query(None, description="Filter by product type: pla, petg, abs, etc."),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    limit: int = Query(50, ge=1, le=200, description="Max number of product groups to return"),
    db: Session = Depends(get_db),
):
    """
    Get products grouped by exact match across different sources for price comparison.
    Uses GTIN, SKU, and normalized product names to find the same product at different stores.
    """
    from app.services.cross_source import compare_products
    
    # Get all active products with their latest prices
    query = (
        db.query(Product)
        .options(joinedload(Product.price_observations), joinedload(Product.source))
        .filter(Product.active == True)
    )
    
    if category:
        query = query.filter(Product.category == category.lower())
    if product_type:
        query = query.filter(Product.product_type == product_type.lower())
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    
    products = query.all()
    return compare_products(products, limit=limit)

