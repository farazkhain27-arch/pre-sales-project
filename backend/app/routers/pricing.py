"""BOQ generation, cost sheet roll-up, and proposal/estimate export — all deterministic."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..services.rules_engine import generate_boq, build_cost_sheet
from ..services.proposal_generator import build_estimate_sheet_xlsx, build_proposal_pdf

router = APIRouter(prefix="/projects/{project_id}", tags=["pricing"])


def _get_project(db, project_id, tenant_id):
    project = db.query(models.Project).filter(
        models.Project.id == project_id, models.Project.tenant_id == tenant_id
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/boq/generate", response_model=schemas.BOQGenerateResponse)
def generate_boq_endpoint(project_id: str, db: Session = Depends(get_db),
                           user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    items, unmatched = generate_boq(db, project)
    project.status = models.ProjectStatus.BOQ_GENERATED
    db.commit()
    total_cost = sum(i.line_cost for i in items)
    total_price = sum(i.line_price for i in items)
    return schemas.BOQGenerateResponse(
        items=items, total_cost=round(total_cost, 2), total_price=round(total_price, 2),
        unmatched_requirements=unmatched,
    )


@router.get("/boq", response_model=list[schemas.BOQItemOut])
def get_boq(project_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    return db.query(models.BOQItem).filter(models.BOQItem.project_id == project.id).all()


@router.get("/cost-sheet", response_model=schemas.CostSheetOut)
def get_cost_sheet(project_id: str, contingency_percent: float = 5.0,
                    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    items = db.query(models.BOQItem).filter(models.BOQItem.project_id == project.id).all()
    if not items:
        raise HTTPException(400, "Generate BOQ first")
    project.status = models.ProjectStatus.PRICED
    db.commit()
    return build_cost_sheet(project, items, contingency_percent)


@router.get("/estimate-sheet.xlsx")
def download_estimate_sheet(project_id: str, contingency_percent: float = 5.0,
                             db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    items = db.query(models.BOQItem).filter(models.BOQItem.project_id == project.id).all()
    if not items:
        raise HTTPException(400, "Generate BOQ first")
    cost_sheet = build_cost_sheet(project, items, contingency_percent)
    xlsx_bytes = build_estimate_sheet_xlsx(cost_sheet)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="estimate_sheet_{project.name}.xlsx"'},
    )


@router.get("/proposal.pdf")
def download_proposal(project_id: str, contingency_percent: float = 5.0,
                       db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    project = _get_project(db, project_id, user.tenant_id)
    items = db.query(models.BOQItem).filter(models.BOQItem.project_id == project.id).all()
    if not items:
        raise HTTPException(400, "Generate BOQ first")
    cost_sheet = build_cost_sheet(project, items, contingency_percent)
    pdf_bytes = build_proposal_pdf(project.name, project.customer_name, cost_sheet)
    project.status = models.ProjectStatus.PROPOSAL_READY
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proposal_{project.name}.pdf"'},
    )
