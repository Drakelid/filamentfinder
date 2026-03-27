import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, case, or_, func

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
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum products to return"),
    db: Session = Depends(get_db),
):
    query = db.query(Product).options(joinedload(Product.price_observations))
    
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
    products = query.order_by(desc(Product.updated_at)).offset(skip).limit(limit).all()
    
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
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
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
    from sqlalchemy import func, and_
    import re
    
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
    
    def normalize_product_name(name: str) -> str:
        """Normalize product name for matching."""
        name = name.lower().strip()
        # Remove common suffixes/prefixes
        name = re.sub(r'\s*-\s*', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        # Remove store-specific text
        name = re.sub(r'3d[- ]?print(ing)?[- ]?filament', '', name)
        name = re.sub(r'filament\s*$', '', name)
        return name.strip()
    
    def extract_product_key(product: Product) -> tuple:
        """
        Extract a unique key for matching products across sources.
        Only matches products that are truly identical (same brand, product line, material, weight, color).
        Priority: GTIN > SKU/Model > exact product match
        """
        name_lower = product.name.lower()
        
        # Filter out non-consumable products (printer parts, accessories, etc.)
        # These should not appear in filament/resin price comparisons
        exclude_patterns = [
            r"\b(nozzle|hotend|extruder|heater|thermistor|sensor)\b",
            r"(plate|buildplate|build plate|print bed|heated bed|flexplate|flex plate|pei plate|glass plate)",
            r"\b(tensioner|belt|pulley|bearing|motor|stepper)\b",
            r"\b(panel|cover|enclosure|door|lid|frame)\b",
            r"\b(cable|wire|connector|adapter|power supply|psu)\b",
            r"\b(screen|display|lcd|touchscreen)\b",
            r"\b(fan|cooling|duct|shroud)\b",
            r"\b(tube|ptfe|bowden|coupler|fitting)\b",
            r"\b(scraper|spatula|tool|wrench|allen)\b",
            r"\b(tape|glue|adhesive|hairspray)\b",
            r"\b(silicone|sock|insulation)\b",
            r"\b(spring|magnet|clip|clamp)\b",
            r"\b(upgrade|kit|mod|replacement|spare)\b",
            r"\b(3d printer|printer|fdm printer|sla printer|resin printer)\b",
            r"\b(wash|cure|station|cleaning)\b",
            r"\b(tank|vat|fep|film)\b",
            r"\b(leveling|calibration|probe)\b",
            r"\b(spool\s*holder|filament\s*holder|dry\s*box|dryer)\b",
            r"\b(bed\s*adhesive|print\s*surface)\b",
            r"\b(radiostyrt|rc\s*(car|boat|plane|drone)|drone|helicopter|aircraft|propeller)\b",
            r"\b(serv[o|e]|receiver|transmitter|gimbal)\b",
            r"\b(battery|batteri|lipo|mah|charger)\b",
            r"\b(gear|gears|shock|shocks|tire|tires|wheel|wheels|axle|axles|suspension|suspensions|rim|rims)\b",
            r"\b(tilbeh[oø]r|tilbehor|accessor(?:y|ies))\b",
            r"\b(trykplade|trykplate|plade|platta|byggplate|byggplade)\b",
            r"\b(build\s*sheet|plate\s*film|surface\s*sheet)\b",
            r"\b(traxxas|trx-?\d{3,4}|1\/10\s*(scale)?|rc\s*wheels?)\b",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, name_lower):
                return ('none', None)

        # Additional exclusion using canonical URL keywords (useful when name is generic)
        canonical_lower = (product.canonical_url or "").lower()
        url_exclusion_keywords = [
            'radiostyrt', 'rc/', '/rc-', 'rc-bil', 'rc-car', 'traxxas', '/servo', '/propeller', '/helicopter', '/drone'
        ]
        if any(keyword in canonical_lower for keyword in url_exclusion_keywords):
            return ('none', None)

        # Require material detection to ensure only filament/resin consumables are matched
        material_from_name = detect_material(product.name, None)
        material_key = material_from_name or detect_material(product.name, product.product_type)
        material_info = MATERIALS.get(material_key) if material_key else None
        if not material_info:
            return ('none', None)
        material_category = material_info.get('category')
        if material_category not in {'filament', 'resin'}:
            return ('none', None)

        # If detection only came from metadata (product_type), ensure name hints at consumable material
        if not material_from_name:
            material_keywords = [
                'filament', 'resin', 'pla', 'petg', 'abs', 'asa', 'tpu', 'tpe', 'nylon',
                'pa6', 'pa12', 'pctg', 'pc', 'peek', 'pekk', 'pei', 'hips', 'pva',
                'carbon fiber', 'cf', 'glass fiber', 'gf'
            ]
            if not any(keyword in name_lower for keyword in material_keywords):
                return ('none', None)

        # 1. Try GTIN (EAN/UPC) - most reliable, exact match
        if product.gtin and len(product.gtin) >= 8:
            return ('gtin', product.gtin)
        
        # Normalize unicode characters
        name_lower = name_lower.replace('ã', 'a').replace('â', 'a').replace('å', 'a')
        name_lower = name_lower.replace('ø', 'o').replace('æ', 'ae')
        
        # 2. Try to extract manufacturer SKU/model number for exact matching
        # Look for patterns like "PA02052", "CA04059", "3301010461"
        sku_patterns = [
            r'\b([A-Z]{2}\d{5,})\b',  # PA02052, CA04059
            r'\b(\d{10,13})\b',  # Long numeric codes (potential GTIN without proper field)
            r'\((\d{10})\)',  # Codes in parentheses like (3301010461)
        ]
        for pattern in sku_patterns:
            sku_match = re.search(pattern, product.name, re.IGNORECASE)
            if sku_match:
                sku_code = sku_match.group(1).upper()
                # Validate it's not just a weight like "1000g"
                if not re.match(r'^\d+[GKM]?$', sku_code):
                    return ('sku', sku_code)
        
        brand = (product.brand or "").lower().strip()
        
        # 3. Extract brand from name if not set
        known_brands = {
            # Multi-word brands (longer strings matched first)
            'clas ohlson by flashforge': 'flashforge',
            'clas ohlson': 'clasohlson',
            'bambu lab': 'bambulab',
            'devil design': 'devildesign',
            'amazon basics': 'amazonbasics',
            'add north': 'addnorth',
            'add:north': 'addnorth',
            'lay filaments': 'layfilaments',
            'prima creator': 'primacreator',
            'siraya tech': 'siraya',
            'the filament': 'thefilament',
            '3d xtech': '3dxtech',
            'raise 3d': 'raise3d',
            'creality 3d': 'creality',
            'creality3d': 'creality',
            'copymaster 3d': 'copymaster',
            'copymaster3d': 'copymaster',
            'innofil 3d': 'innofil3d',
            'innofil3d': 'innofil3d',
            'xyz printing': 'xyzprinting',
            'filament pm': 'filamentpm',
            'c-tech': 'ctech',
            'poly filament': 'polymaker',
            # Polymaker product lines -> polymaker
            'polyterra': 'polymaker',
            'polylite': 'polymaker',
            'polysonic': 'polymaker',
            'polycast': 'polymaker',
            'panchroma': 'polymaker',
            'polymax': 'polymaker',
            'polysmooth': 'polymaker',
            'polywood': 'polymaker',
            'polymide': 'polymaker',
            'polyflex': 'polymaker',
            'polymaker': 'polymaker',
            # Single word brands - common
            'bambulab': 'bambulab',
            'bambu': 'bambulab',
            'prusament': 'prusament',
            'prusa': 'prusa',
            'esun': 'esun',
            'sunlu': 'sunlu',
            'overture': 'overture',
            'hatchbox': 'hatchbox',
            'eryone': 'eryone',
            'creality': 'creality',
            'elegoo': 'elegoo',
            'anycubic': 'anycubic',
            'flashforge': 'flashforge',
            'fiberlogy': 'fiberlogy',
            'colorfabb': 'colorfabb',
            'formfutura': 'formfutura',
            'fillamentum': 'fillamentum',
            'extrudr': 'extrudr',
            '3djake': '3djake',
            'spectrum': 'spectrum',
            'spektrum': 'spectrum',
            'rosa3d': 'rosa3d',
            'polyalkemi': 'polyalkemi',
            'jayo': 'jayo',
            'kingroon': 'kingroon',
            'qidi': 'qidi',
            'siraya': 'siraya',
            'phrozen': 'phrozen',
            'monocure': 'monocure',
            'liqcreate': 'liqcreate',
            'inland': 'inland',
            'geeetech': 'geeetech',
            'tianse': 'tianse',
            'ziro': 'ziro',
            'matterhackers': 'matterhackers',
            'protopasta': 'protopasta',
            'maertz': 'maertz',
            'real': 'real',
            'verbatim': 'verbatim',
            'basf': 'basf',
            'ultimaker': 'ultimaker',
            'ultimaker': 'ultimaker',
            'zortrax': 'zortrax',
            # Lay filaments variants
            'laybrick': 'layfilaments',
            'laywood': 'layfilaments',
            'laywoo': 'layfilaments',
            # PrimaCreator variants
            'primacreator': 'primacreator',
            'primaselect': 'primacreator',
            'easyprint': 'primacreator',
            # Additional brands from database
            'gembird': 'gembird',
            'renkforce': 'renkforce',
            'copymaster': 'copymaster',
            'ordrett': 'ordrett',
            'panda': 'panda',
            'makerbot': 'makerbot',
            'radius': 'radius',
            'kruzzel': 'kruzzel',
            'azurefilm': 'azurefilm',
            'nobufil': 'nobufil',
            'r3d': 'r3d',
            'recreus': 'recreus',
            'formlabs': 'formlabs',
            'cctree': 'cctree',
            # 3DXTech variants
            '3dxtech': '3dxtech',
            'carbonx': '3dxtech',
            '3dxstat': '3dxtech',
            # More brands from product analysis
            'addnorth': 'addnorth',
            '3dnet': '3dnet',
            'raise3d': 'raise3d',
            'devildesign': 'devildesign',
            'devil': 'devildesign',
            'smartfil': 'smartfil',
            'xyzprinting': 'xyzprinting',
            'filamentpm': 'filamentpm',
            'ctech': 'ctech',
            # Additional brand variations
            'ultimaker': 'ultimaker',
            'ulti maker': 'ultimaker',
            'easyprint': 'primacreator',
            'easy print': 'primacreator',
            'cr-pla': 'creality',
            'cr-petg': 'creality',
            'cr-abs': 'creality',
            'ender': 'creality',
            'cctree': 'cctree',
            'cc tree': 'cctree',
            # Norwegian/European brands
            'polyalkemi': 'polyalkemi',
            # More common brands
            'tinmorry': 'tinmorry',
            'reprapper': 'reprapper',
            'gst3d': 'gst3d',
            'yousu': 'yousu',
            'amolen': 'amolen',
            'ttyt3d': 'ttyt3d',
            'mika3d': 'mika3d',
            'duramic': 'duramic',
            'stronghero3d': 'stronghero3d',
            'iwecolor': 'iwecolor',
            'novamaker': 'novamaker',
            'tecbears': 'tecbears',
            'voxelab': 'voxelab',
            'longer': 'longer',
            'sovol': 'sovol',
            'artillery': 'artillery',
            'tronxy': 'tronxy',
            'wanhao': 'wanhao',
            'monoprice': 'monoprice',
            'dremel': 'dremel',
            'snapmaker': 'snapmaker',
            'flashforge': 'flashforge',
            'intamsys': 'intamsys',
            'markforged': 'markforged',
            'stratasys': 'stratasys',
            '3dsystems': '3dsystems',
            'formlabs': 'formlabs',
            'peopoly': 'peopoly',
            'wham bam': 'whambam',
            'whambam': 'whambam',
            'buildtak': 'buildtak',
            'magigoo': 'magigoo',
            'dimafix': 'dimafix',
        }
        
        # Sort by length descending to match longer brand names first
        sorted_brands = sorted(known_brands.items(), key=lambda x: len(x[0]), reverse=True)
        
        if not brand:
            for b_name, b_key in sorted_brands:
                if b_name in name_lower:
                    brand = b_key
                    break
        else:
            # Normalize existing brand from database
            brand_lower = brand.lower().replace(' ', '')
            # First try exact match on normalized brand
            for b_name, b_key in sorted_brands:
                b_normalized = b_name.replace(' ', '')
                if b_normalized == brand_lower or b_name in brand_lower:
                    brand = b_key
                    break
            else:
                # If no match found, use the original brand (normalized)
                brand = re.sub(r'[^a-z0-9]', '', brand_lower)
        
        # If still no brand, try to extract from name
        if not brand:
            for b_name, b_key in sorted_brands:
                if b_name in name_lower:
                    brand = b_key
                    break
        
        # Must have a brand to match
        if not brand:
            return ('none', None)
        
        # 4. Extract material type using the centralized material registry
        detected_material = detect_material(product.name, product.product_type)
        if not detected_material:
            return ('none', None)
        
        # Use lowercase for key consistency
        material = detected_material.lower()
        
        # 5. Extract weight - normalize to grams
        weight = ""
        # Try multiple weight patterns - order matters, more specific first
        weight_patterns = [
            # Explicit kg patterns
            (r'(\d+(?:[.,]\d+)?)\s*kg\b', 'kg'),           # 1kg, 1.75kg, 0.75kg
            (r'(\d+(?:[.,]\d+)?)\s*kilo\b', 'kg'),         # 1 kilo
            # Explicit gram patterns
            (r'(\d+(?:[.,]\d+)?)\s*g\b', 'g'),             # 1000g, 500g
            (r'(\d+)\s*(?:gram|grams)\b', 'g'),            # 1000 grams
            # Patterns with separators
            (r'-\s*(\d+(?:[.,]\d+)?)\s*kg\b', 'kg'),       # - 1kg (with dash)
            (r'-\s*(\d+)\s*g\b', 'g'),                     # - 1000g
            (r'x\s*(\d+)\s*g\b', 'g'),                     # x 1000g
            (r'/\s*(\d+)\s*g\b', 'g'),                     # / 1000g
            (r'\((\d+)\s*g\)', 'g'),                       # (1000g)
            (r'\((\d+(?:[.,]\d+)?)\s*kg\)', 'kg'),         # (1kg)
            # Common spool sizes without explicit unit (assume grams if 3-4 digits)
            (r'\b(1000|750|500|250|2000|3000|2300)\b', 'g'),  # Common spool sizes
            # Weight in parentheses at end
            (r'\((\d{3,4})\s*g?\)$', 'g'),                 # (1000) or (1000g) at end
        ]
        for pattern, unit in weight_patterns:
            weight_match = re.search(pattern, name_lower)
            if weight_match:
                num = float(weight_match.group(1).replace(',', '.'))
                if unit == 'kg':
                    num = int(num * 1000)
                else:
                    num = int(num)
                # Validate reasonable weight (50g to 10kg)
                if 50 <= num <= 10000:
                    weight = f"{num}g"
                    break
        
        # Weight is preferred but not strictly required if we have other strong identifiers
        
        # 6. Extract product line/series - important for distinguishing variants
        product_lines = []
        line_patterns = [
            # Polymaker lines
            ('polylite', r'\bpolylite\b'),
            ('polyterra', r'\bpolyterra\b'),
            ('polymax', r'\bpolymax\b'),
            ('polywood', r'\bpolywood\b'),
            ('polysmooth', r'\bpolysmooth\b'),
            ('polyflex', r'\bpolyflex\b'),
            ('polycast', r'\bpolycast\b'),
            ('polymide', r'\bpolymide\b'),
            ('panchroma', r'\bpanchroma\b'),
            # Bambu Lab lines
            ('basic', r'\bbasic\b'),
            ('matte', r'\bmatte\b'),
            ('silk', r'\bsilk\b'),
            ('sparkle', r'\bsparkle\b'),
            ('metal', r'\bmetal\b'),
            ('marble', r'\bmarble\b'),
            ('wood', r'\bwood\b'),
            ('aero', r'\baero\b'),
            ('gradient', r'\bgradient\b'),
            # Speed variants
            ('hf', r'\bhf\b'),
            ('hs', r'\bhs\b'),
            ('highspeed', r'\bhigh[\s-]?speed\b'),
            ('hyper', r'\bhyper\b'),
            # Quality variants
            ('pro', r'\bpro\b'),
            ('plus', r'\bplus\b'),
            ('premium', r'\bpremium\b'),
            ('lite', r'\blite\b'),
            # Special variants
            ('refill', r'\brefill\b'),
            ('translucent', r'\btranslucent\b'),
            ('transparent', r'\btransparent\b'),
            ('glow', r'\bglow\b'),
            ('glitter', r'\bglitter\b'),
            ('rainbow', r'\brainbow\b'),
            ('multicolor', r'\bmulti[\s-]?colou?r\b'),
        ]
        for line_name, pattern in line_patterns:
            if re.search(pattern, name_lower):
                product_lines.append(line_name)
        
        # Sort and join for consistent key
        product_line = '_'.join(sorted(product_lines)) if product_lines else ""
        
        # 7. Extract color
        colors = {
            'black': [r'\bblack\b', r'\bsvart\b', r'\bsort\b', r'\bnero\b', r'\bschwarz\b', r'\bjuodas\b', r'\bczarny\b', r'\bdeep\s*black\b'],
            'white': [r'\bwhite\b', r'\bhvit\b', r'\bhvitt\b', r'\bbianco\b', r'\bweiss\b', r'\bbaltas\b', r'\bbialy\b', r'\bpure\s*white\b'],
            'red': [r'\bred\b', r'\brød\b', r'\brod\b', r'\brosso\b', r'\brot\b', r'\braudonas\b', r'\bczerwony\b'],
            'blue': [r'\bblue\b', r'\bblå\b', r'\bbla\b', r'\bblu\b', r'\bblau\b', r'\bmelynas\b', r'\bniebieski\b'],
            'green': [r'\bgreen\b', r'\bgrønn\b', r'\bgronn\b', r'\bverde\b', r'\bgrün\b', r'\bzalias\b', r'\bzielony\b', r'\bemerald\b'],
            'yellow': [r'\byellow\b', r'\bgul\b', r'\bgiallo\b', r'\bgelb\b', r'\bgeltonas\b', r'\bzolty\b'],
            'orange': [r'\borange\b', r'\boransje\b', r'\barancione\b', r'\boranžinis\b', r'\bpomaranczowy\b'],
            'purple': [r'\bpurple\b', r'\blilla\b', r'\bviola\b', r'\bvioletine\b', r'\bfioletowy\b', r'\bviolet\b'],
            'pink': [r'\bpink\b', r'\brosa\b', r'\brozine\b', r'\brozowy\b'],
            'grey': [r'\bgrey\b', r'\bgray\b', r'\bgrå\b', r'\bgra\b', r'\bgrigio\b', r'\bgrau\b', r'\bpilkas\b', r'\bszary\b', r'\bdark\s*grey\b', r'\bmørkegrå\b'],
            'brown': [r'\bbrown\b', r'\bbrun\b', r'\bmarrone\b', r'\bbraun\b', r'\brudas\b', r'\bbrazowy\b'],
            'clear': [r'\bclear\b', r'\btransparent\b', r'\bgjennomsiktig\b', r'\bskaidrus\b', r'\bprzezroczysty\b'],
            'natural': [r'\bnatural\b', r'\bnatur\b', r'\bnaturale\b', r'\bnaturalus\b', r'\bnaturalny\b', r'\bnatūralus\b'],
            'silver': [r'\bsilver\b', r'\bsølv\b', r'\bargento\b', r'\bsilber\b', r'\bsidabrinis\b', r'\bsrebrny\b'],
            'gold': [r'\bgold\b', r'\bgull\b', r'\boro\b', r'\bauksinis\b', r'\bzloty\b', r'\bgolden\b'],
            'jade': [r'\bjade\b', r'\bjadeit\b'],
            'ivory': [r'\bivory\b', r'\belfenbein\b'],
            'beige': [r'\bbeige\b', r'\bbež\b'],
            'olive': [r'\bolive\b', r'\bolivgrun\b'],
            'navy': [r'\bnavy\b', r'\bmarine\b'],
            'cyan': [r'\bcyan\b', r'\btürkis\b'],
            'magenta': [r'\bmagenta\b', r'\bfuchsia\b'],
            'teal': [r'\bteal\b', r'\bpetrol\b'],
            'coral': [r'\bcoral\b', r'\bkoralle\b'],
            'charcoal': [r'\bcharcoal\b', r'\banthrazit\b'],
            'cream': [r'\bcream\b', r'\bcreme\b'],
            'burgundy': [r'\bburgundy\b', r'\bweinrot\b'],
            'lime': [r'\blime\b', r'\blimette\b'],
            'mint': [r'\bmint\b', r'\bminze\b'],
            'peach': [r'\bpeach\b', r'\bpfirsich\b'],
            'lavender': [r'\blavender\b', r'\blavendel\b'],
            'turquoise': [r'\bturquoise\b', r'\btürkis\b'],
            'copper': [r'\bcopper\b', r'\bkupfer\b'],
            'bronze': [r'\bbronze\b'],
            'army': [r'\barmy\b'],
            'sand': [r'\bsand\b'],
            'sky': [r'\bsky\b'],
            'ocean': [r'\bocean\b'],
            'forest': [r'\bforest\b'],
            'midnight': [r'\bmidnight\b'],
            'melon': [r'\bmelon\b'],
            'multicolor': [r'\bmulti[\s-]?colou?r\b', r'\bflerfarve\b', r'\bflerfarget\b'],
            'pumpkin': [r'\bpumpkin\b'],
            'cappuccino': [r'\bcappuccino\b'],
        }
        color = ""
        for color_key, patterns in colors.items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    color = color_key
                    break
            if color:
                break
        
        # Also check product.color field
        if not color and product.color:
            color_lower = product.color.lower()
            for color_key, patterns in colors.items():
                for pattern in patterns:
                    if re.search(pattern, color_lower):
                        color = color_key
                        break
                if color:
                    break
        
        # Create matching key - be flexible with what we require
        # Minimum requirement: brand + material
        # Better matches include: weight, color, product_line
        key_parts = [brand, material]
        
        # Add optional components if available
        if product_line:
            key_parts.append(product_line)
        
        # Normalize weight to standard sizes for better matching
        normalized_weight = ""
        if weight:
            weight_num = int(weight.replace('g', ''))
            # Normalize to common spool sizes with wider ranges
            if 200 <= weight_num <= 400:
                normalized_weight = '250g'
            elif 400 < weight_num <= 650:
                normalized_weight = '500g'
            elif 650 < weight_num <= 900:
                normalized_weight = '750g'
            elif 900 < weight_num <= 1200:
                normalized_weight = '1000g'
            elif 1700 <= weight_num <= 2500:
                normalized_weight = '2000g'
            elif 2500 < weight_num <= 3500:
                normalized_weight = '3000g'
            else:
                normalized_weight = weight  # Keep original if not standard
        
        # Build key with weight if available
        if normalized_weight:
            key_parts.append(normalized_weight)
        
        if color:
            key_parts.append(color)
        else:
            key_parts.append('anycolor')
        
        key = '_'.join(p for p in key_parts if p)
        return ('name', key)
    
    # Group products by their keys
    gtin_groups = {}  # GTIN-based groups (highest confidence)
    sku_groups = {}   # SKU-based groups (high confidence)
    name_groups = {}  # Name-based groups (with weight)
    name_groups_noweight = {}  # Name-based groups (without weight, fallback)
    
    for product in products:
        key_type, key_value = extract_product_key(product)
        
        if key_type == 'none' or not key_value:
            continue
        
        latest_price = None
        if product.price_observations:
            latest = max(product.price_observations, key=lambda p: p.observed_at)
            amount = float(latest.price_amount) if latest.price_amount is not None else None
            shipping_amount = float(latest.shipping_amount) if latest.shipping_amount is not None else None
            total_amount = float(latest.total_price_amount) if latest.total_price_amount is not None else None
            if total_amount is None and (amount is not None or shipping_amount is not None):
                total_amount = (amount or 0) + (shipping_amount or 0)
            latest_price = {
                "amount": amount,
                "currency": latest.currency,
                "shipping_amount": shipping_amount,
                "shipping_currency": latest.shipping_currency or latest.currency,
                "total_amount": total_amount,
                "in_stock": latest.in_stock,
                "observed_at": latest.observed_at.isoformat() if latest.observed_at else None,
            }
        
        product_data = {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "product_type": product.product_type,
            "color": product.color,
            "size": product.size,
            "image_url": product.image_url,
            "source_id": product.source_id,
            "source_name": product.source.name if product.source else None,
            "source_domain": product.source.domain if product.source else None,
            "canonical_url": product.canonical_url,
            "latest_price": latest_price,
            "latest_change_percent": product.latest_change_percent,
            "latest_change_type": product.latest_change_type,
            "gtin": product.gtin,
            "sku": product.sku,
        }
        
        if key_type == 'gtin':
            if key_value not in gtin_groups:
                gtin_groups[key_value] = []
            gtin_groups[key_value].append(product_data)
        elif key_type == 'sku':
            if key_value not in sku_groups:
                sku_groups[key_value] = []
            sku_groups[key_value].append(product_data)
        else:
            if key_value not in name_groups:
                name_groups[key_value] = []
            name_groups[key_value].append(product_data)
            
            # Also add to no-weight fallback group for broader matching
            # Extract key without weight component for fallback matching
            key_parts = key_value.split('_')
            # Remove weight-like parts (e.g., "1000g", "500g")
            noweight_parts = [p for p in key_parts if not re.match(r'^\d+g$', p)]
            noweight_key = '_'.join(noweight_parts)
            if noweight_key != key_value:  # Only if different
                if noweight_key not in name_groups_noweight:
                    name_groups_noweight[noweight_key] = []
                name_groups_noweight[noweight_key].append(product_data)
            
            # Also create a key without color for even broader matching
            # This helps match products where color names differ across sources
            nocolor_parts = [p for p in key_parts if not re.match(r'^\d+g$', p) and p != 'anycolor']
            # Remove common color names
            color_names = {'black', 'white', 'red', 'blue', 'green', 'yellow', 'orange', 'purple', 
                          'pink', 'grey', 'gray', 'brown', 'clear', 'natural', 'silver', 'gold',
                          'transparent', 'navy', 'cyan', 'magenta', 'teal', 'beige', 'ivory'}
            nocolor_parts = [p for p in nocolor_parts if p not in color_names]
            nocolor_key = '_'.join(nocolor_parts)
            if nocolor_key and nocolor_key != key_value and nocolor_key != noweight_key:
                if nocolor_key not in name_groups_noweight:
                    name_groups_noweight[nocolor_key] = []
                name_groups_noweight[nocolor_key].append(product_data)
    
    def create_group_result(key: str, prods: list, match_type: str) -> dict:
        """Create a group result dict."""
        # Only include groups with products from different sources
        source_ids = set(p["source_id"] for p in prods)
        if len(source_ids) < 2:
            return None
        
        def delivered_price(product_dict: dict) -> Optional[float]:
            latest = product_dict.get("latest_price")
            if not latest:
                return None
            return latest.get("total_amount") or latest.get("amount")

        sorted_prods = sorted(
            prods,
            key=lambda p: delivered_price(p) if delivered_price(p) is not None else float('inf')
        )

        prices = [delivered_price(p) for p in prods if delivered_price(p) is not None]
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        
        price_spread = None
        if min_price and max_price and min_price > 0:
            price_spread = round(((max_price - min_price) / min_price) * 100, 1)
        
        # Create display name using detected material variant (not brand)
        first = sorted_prods[0]
        detected = detect_material(first.get("name", ""), first.get("product_type"))
        material_display = get_material_display_name(detected) if detected else (first['product_type'] or '')
        # Include brand and color for context
        brand_part = first['brand'] or ''
        color_part = first['color'] or ''
        display_name = f"{brand_part} {material_display} {color_part}".strip()
        if not display_name:
            display_name = first['name'][:50]
        
        return {
            "key": key,
            "display_name": display_name,
            "match_type": match_type,
            "products": sorted_prods,
            "source_count": len(source_ids),
            "min_price": min_price,
            "max_price": max_price,
            "price_spread": price_spread,
        }
    
    # Build results - GTIN matches first (most reliable), then SKU, then name matches
    results = []
    
    for key, prods in gtin_groups.items():
        group = create_group_result(key, prods, "gtin")
        if group:
            results.append(group)
    
    for key, prods in sku_groups.items():
        group = create_group_result(key, prods, "sku")
        if group:
            results.append(group)
    
    for key, prods in name_groups.items():
        group = create_group_result(key, prods, "name")
        if group:
            results.append(group)
    
    # Add fallback matches (without weight) for products not already matched
    matched_product_ids = set()
    for group in results:
        for p in group["products"]:
            matched_product_ids.add(p["id"])
    
    for key, prods in name_groups_noweight.items():
        # Filter out products already in a match
        unmatched = [p for p in prods if p["id"] not in matched_product_ids]
        if len(unmatched) >= 2:
            group = create_group_result(key, unmatched, "name_fallback")
            if group:
                results.append(group)
                # Mark these as matched
                for p in group["products"]:
                    matched_product_ids.add(p["id"])
    
    # Sort by price spread (biggest differences first)
    results.sort(key=lambda g: (g["price_spread"] or 0, g["source_count"]), reverse=True)
    
    # Group results by material type using the centralized material registry
    # First level: base material (PLA, PETG, etc.)
    # Second level: specific variant (PLA+, Tough PLA, Silk, etc.)
    type_groups = {}
    for group in results:
        # Detect material from first product using the registry
        first_product = group["products"][0]
        detected = detect_material(first_product.get("name", ""), first_product.get("product_type"))
        
        # Get base material for top-level grouping (e.g., PLA-CF -> PLA)
        base_material = normalize_material_for_grouping(detected)
        # Keep the specific variant for sub-grouping (e.g., PLA+, PLA-CF, Silk)
        specific_variant = detected if detected else base_material
        
        if base_material not in type_groups:
            type_groups[base_material] = {}
        if specific_variant not in type_groups[base_material]:
            type_groups[base_material][specific_variant] = []
        type_groups[base_material][specific_variant].append(group)
    
    # Create type summary with stats, including variant sub-groups
    type_summaries = []
    for material_key, variant_groups in type_groups.items():
        all_prices = []
        total_product_count = 0
        
        # Build variant summaries
        variant_summaries = []
        for variant_key, groups in variant_groups.items():
            variant_prices = []
            for g in groups:
                if g["min_price"]:
                    variant_prices.append(g["min_price"])
                    all_prices.append(g["min_price"])
                if g["max_price"]:
                    variant_prices.append(g["max_price"])
                    all_prices.append(g["max_price"])
            
            variant_display = get_material_display_name(variant_key)
            total_product_count += len(groups)
            
            variant_summaries.append({
                "variant": variant_display,
                "variant_key": variant_key,
                "product_count": len(groups),
                "min_price": min(variant_prices) if variant_prices else None,
                "max_price": max(variant_prices) if variant_prices else None,
                "groups": groups[:limit],
            })
        
        # Sort variants by product count
        variant_summaries.sort(key=lambda v: v["product_count"], reverse=True)
        
        # Get proper display name from registry
        display_name = get_material_display_name(material_key)
        
        # Flatten groups for backward compatibility (all groups under this material)
        all_groups = []
        for v in variant_summaries:
            all_groups.extend(v["groups"])
        
        type_summaries.append({
            "type": display_name,
            "type_key": material_key,
            "product_count": total_product_count,
            "min_price": min(all_prices) if all_prices else None,
            "max_price": max(all_prices) if all_prices else None,
            "variants": variant_summaries,
            "groups": all_groups[:limit],  # Backward compatibility
        })
    
    # Sort type summaries by product count
    type_summaries.sort(key=lambda t: t["product_count"], reverse=True)
    
    return {
        "groups": results[:limit],
        "total_groups": len(results),
        "by_type": type_summaries,
    }
