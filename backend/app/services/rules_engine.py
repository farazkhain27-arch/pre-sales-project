"""
Deterministic requirement-matching + pricing rules engine.

Zero LLM involvement here by design — every BOQ line, cost, and margin is
produced by explicit, auditable rules so a sales-ops reviewer (or an
auditor) can see exactly why a number is what it is. `rule_trace` on each
BOQItem records which rules fired.
"""
from difflib import SequenceMatcher
from typing import List, Optional
from sqlalchemy.orm import Session

from .. import models


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_requirement_to_product(
    requirement: models.ExtractedRequirement, catalog: List[models.Product]
) -> tuple[Optional[models.Product], float, list]:
    """
    Rule 1: category match boosts score.
    Rule 2: text similarity between requirement description and product name.
    Rule 3: technical attribute overlap (e.g. bandwidth, protocol) boosts score.
    Best-scoring product above threshold 0.35 wins; otherwise unmatched.
    """
    best_product, best_score, trace = None, 0.0, []

    for product in catalog:
        score = 0.0
        local_trace = []

        if requirement.category and product.category and \
           requirement.category.lower() == product.category.lower():
            score += 0.3
            local_trace.append(f"category match '{product.category}' (+0.30)")

        sim = _text_similarity(requirement.description, product.name)
        score += sim * 0.5
        local_trace.append(f"description similarity {sim:.2f} (+{sim*0.5:.2f})")

        req_attrs = requirement.technical_attributes or {}
        prod_attrs = product.spec_json or {}
        overlap = 0
        for k, v in req_attrs.items():
            if k in prod_attrs and str(prod_attrs[k]).lower() == str(v).lower():
                overlap += 1
        if req_attrs:
            attr_score = 0.2 * (overlap / max(len(req_attrs), 1))
            score += attr_score
            if overlap:
                local_trace.append(f"{overlap} matching technical attribute(s) (+{attr_score:.2f})")

        if score > best_score:
            best_product, best_score, trace = product, score, local_trace

    if best_score < 0.35:
        return None, best_score, ["no product scored above match threshold 0.35"]

    return best_product, best_score, trace


def generate_boq(db: Session, project: models.Project) -> tuple[list[models.BOQItem], list[str]]:
    """
    Builds BOQ line items from every reviewed (human-approved) requirement.
    Requirements with no confident product match are returned separately so
    a sales engineer can manually source/price them.
    """
    catalog = db.query(models.Product).filter(
        models.Product.tenant_id == project.tenant_id
    ).all()

    requirements = db.query(models.ExtractedRequirement).filter(
        models.ExtractedRequirement.project_id == project.id
    ).all()

    # clear previous BOQ for this project (regeneration is idempotent)
    db.query(models.BOQItem).filter(models.BOQItem.project_id == project.id).delete()

    boq_items, unmatched = [], []

    for req in requirements:
        product, score, trace = match_requirement_to_product(req, catalog)
        if product is None:
            unmatched.append(req.description)
            continue

        req.matched_product_id = product.id
        line_cost = product.unit_cost * req.quantity
        margin = project.margin_percent
        unit_price = product.unit_cost * (1 + margin / 100) if product.unit_price == 0 else product.unit_price
        line_price = unit_price * req.quantity

        item = models.BOQItem(
            project_id=project.id,
            requirement_id=req.id,
            product_id=product.id,
            item_code=product.sku,
            description=product.name,
            quantity=req.quantity,
            unit=req.unit,
            unit_cost=product.unit_cost,
            unit_price=unit_price,
            line_cost=line_cost,
            line_price=line_price,
            margin_percent=margin,
            rule_trace=trace + [f"match score {score:.2f}", f"margin {margin}% applied"],
        )
        db.add(item)
        boq_items.append(item)

    db.commit()
    for item in boq_items:
        db.refresh(item)

    return boq_items, unmatched


def build_cost_sheet(project: models.Project, boq_items: list[models.BOQItem], contingency_percent: float = 5.0) -> dict:
    """Deterministic roll-up: subtotal -> contingency -> grand total."""
    subtotal_cost = sum(i.line_cost for i in boq_items)
    subtotal_price = sum(i.line_price for i in boq_items)
    contingency_amount = subtotal_price * (contingency_percent / 100)
    grand_total = subtotal_price + contingency_amount

    return {
        "project_id": project.id,
        "currency": project.currency,
        "subtotal_cost": round(subtotal_cost, 2),
        "subtotal_price": round(subtotal_price, 2),
        "margin_percent": project.margin_percent,
        "contingency_percent": contingency_percent,
        "contingency_amount": round(contingency_amount, 2),
        "grand_total_price": round(grand_total, 2),
        "line_items": boq_items,
    }
