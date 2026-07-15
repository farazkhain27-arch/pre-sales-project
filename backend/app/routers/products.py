"""Product / datasheet catalog — feeds the rules engine's requirement matching."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=schemas.ProductOut)
def create_product(payload: schemas.ProductCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    product = models.Product(tenant_id=user.tenant_id, **payload.dict())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[schemas.ProductOut])
def list_products(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Product).filter(models.Product.tenant_id == user.tenant_id).all()


@router.delete("/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    product = db.query(models.Product).filter(
        models.Product.id == product_id, models.Product.tenant_id == user.tenant_id
    ).first()
    if not product:
        raise HTTPException(404, "Product not found")
    db.delete(product)
    db.commit()
    return {"ok": True}
