"""Pydantic request/response schemas."""
from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import datetime


# --- Auth ---
class SignupRequest(BaseModel):
    tenant_name: str
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Projects ---
class ProjectCreate(BaseModel):
    name: str
    customer_name: Optional[str] = None
    currency: str = "SAR"
    margin_percent: float = 15.0


class ProjectOut(BaseModel):
    id: str
    name: str
    customer_name: Optional[str]
    status: str
    currency: str
    margin_percent: float
    created_at: datetime

    class Config:
        from_attributes = True


# --- Documents ---
class DocumentOut(BaseModel):
    id: str
    doc_type: str
    filename: str
    uploaded_at: datetime
    processed: bool

    class Config:
        from_attributes = True


# --- Requirements ---
class RequirementOut(BaseModel):
    id: str
    category: Optional[str]
    description: str
    quantity: float
    unit: str
    technical_attributes: dict
    confidence: float
    matched_product_id: Optional[str]
    reviewed: bool

    class Config:
        from_attributes = True


class RequirementUpdate(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    matched_product_id: Optional[str] = None
    reviewed: Optional[bool] = None


# --- Products (catalog) ---
class ProductCreate(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    spec_json: dict = {}
    unit_cost: float = 0.0
    unit_price: float = 0.0
    currency: str = "SAR"
    lead_time_days: int = 30


class ProductOut(ProductCreate):
    id: str

    class Config:
        from_attributes = True


# --- BOQ / Cost / Estimate ---
class BOQItemOut(BaseModel):
    id: str
    item_code: Optional[str]
    description: str
    quantity: float
    unit: str
    unit_cost: float
    unit_price: float
    line_cost: float
    line_price: float
    margin_percent: float
    rule_trace: list

    class Config:
        from_attributes = True


class BOQGenerateResponse(BaseModel):
    items: list[BOQItemOut]
    total_cost: float
    total_price: float
    unmatched_requirements: list[str]


class CostSheetOut(BaseModel):
    project_id: str
    currency: str
    subtotal_cost: float
    subtotal_price: float
    margin_percent: float
    contingency_percent: float
    contingency_amount: float
    grand_total_price: float
    line_items: list[BOQItemOut]
