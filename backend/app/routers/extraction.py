"""
Triggers the LangGraph extraction agent against uploaded RFP / Customer
Requirements documents and persists structured, human-reviewable requirements.
"""
import io
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pypdf import PdfReader

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..services import s3_service
from ..services.extraction_agent import run_extraction

router = APIRouter(prefix="/projects/{project_id}", tags=["extraction"])


def _get_project(db, project_id, tenant_id):
    project = db.query(models.Project).filter(
        models.Project.id == project_id, models.Project.tenant_id == tenant_id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _extract_text(storage_path: str, filename: str) -> str:
    raw = s3_service.read_file(storage_path)
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return raw.decode("utf-8", errors="ignore")


@router.post("/extract", response_model=list[schemas.RequirementOut])
def extract_requirements(project_id: str, db: Session = Depends(get_db),
                          user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    project.status = models.ProjectStatus.EXTRACTING
    db.commit()

    source_docs = db.query(models.Document).filter(
        models.Document.project_id == project.id,
        models.Document.doc_type.in_([
            models.DocType.RFP, models.DocType.CUSTOMER_REQUIREMENTS
        ]),
    ).all()
    if not source_docs:
        raise HTTPException(400, "Upload an RFP or Customer Requirements document first")

    created = []
    for doc in source_docs:
        text = _extract_text(doc.storage_path, doc.filename)
        results = run_extraction(text, doc.doc_type.value)
        for r in results:
            req = models.ExtractedRequirement(
                project_id=project.id,
                category=r.get("category"),
                description=r["description"],
                quantity=r.get("quantity", 1),
                unit=r.get("unit", "unit"),
                technical_attributes=r.get("technical_attributes", {}),
                confidence=r.get("confidence", 0.5),
                source_snippet=r.get("source_snippet", ""),
            )
            db.add(req)
            created.append(req)
        doc.processed = True

    project.status = models.ProjectStatus.REQUIREMENTS_READY
    db.commit()
    for r in created:
        db.refresh(r)
    return created


@router.get("/requirements", response_model=list[schemas.RequirementOut])
def list_requirements(project_id: str, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    return db.query(models.ExtractedRequirement).filter(
        models.ExtractedRequirement.project_id == project.id
    ).all()


@router.patch("/requirements/{requirement_id}", response_model=schemas.RequirementOut)
def update_requirement(project_id: str, requirement_id: str, payload: schemas.RequirementUpdate,
                        db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    req = db.query(models.ExtractedRequirement).filter(
        models.ExtractedRequirement.id == requirement_id,
        models.ExtractedRequirement.project_id == project.id,
    ).first()
    if not req:
        raise HTTPException(404, "Requirement not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(req, field, value)
    db.commit()
    db.refresh(req)
    return req
