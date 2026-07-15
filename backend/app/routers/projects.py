from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    project = models.Project(
        tenant_id=user.tenant_id,
        name=payload.name,
        customer_name=payload.customer_name,
        currency=payload.currency,
        margin_percent=payload.margin_percent,
        created_by=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    return db.query(models.Project).filter(models.Project.tenant_id == user.tenant_id).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = db.query(models.Project).filter(
        models.Project.id == project_id, models.Project.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project
