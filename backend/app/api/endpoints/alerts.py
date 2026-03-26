from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import PriceAlert, Product
from app.schemas.price_alert import PriceAlertCreate, PriceAlertList, PriceAlertRead

router = APIRouter()


@router.post("", response_model=PriceAlertRead, status_code=201)
def create_alert(alert_in: PriceAlertCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == alert_in.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    alert = PriceAlert(
        product_id=alert_in.product_id,
        target_price=alert_in.target_price,
        currency=alert_in.currency.upper(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=PriceAlertList)
def list_alerts(
    product_id: int | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(PriceAlert)
    if product_id is not None:
        query = query.filter(PriceAlert.product_id == product_id)
    if active is not None:
        query = query.filter(PriceAlert.active == active)

    total = query.count()
    items = query.order_by(PriceAlert.created_at.desc()).all()
    return PriceAlertList(items=items, total=total)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: UUID, db: Session = Depends(get_db)):
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.delete(alert)
    db.commit()
    return None
