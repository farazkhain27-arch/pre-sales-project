from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..services import s3_service

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


def _get_project(db, project_id, tenant_id):
    project = db.query(models.Project).filter(
        models.Project.id == project_id, models.Project.tenant_id == tenant_id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("", response_model=schemas.DocumentOut)
async def upload_document(
    project_id: str,
    doc_type: models.DocType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    project = _get_project(db, project_id, user.tenant_id)
    content = await file.read()
    path = s3_service.save_upload(content, file.filename, project.id)

    doc = models.Document(
        project_id=project.id,
        doc_type=doc_type,
        filename=file.filename,
        storage_path=path,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    return db.query(models.Document).filter(models.Document.project_id == project.id).all()
