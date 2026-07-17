"""
SQLAlchemy models.

Multi-tenant SaaS: every business object hangs off tenant_id so one
deployment can serve multiple customer organizations with row-level isolation.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, Enum, JSON
)
from sqlalchemy.orm import relationship
from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class DocType(str, enum.Enum):
    RFP = "RFP"
    BOQ = "BOQ"
    COST_SHEET = "COST_SHEET"
    ESTIMATE_SHEET = "ESTIMATE_SHEET"
    DATASHEET = "DATASHEET"
    CUSTOMER_REQUIREMENTS = "CUSTOMER_REQUIREMENTS"


class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    EXTRACTING = "EXTRACTING"
    REQUIREMENTS_READY = "REQUIREMENTS_READY"
    BOQ_GENERATED = "BOQ_GENERATED"
    PRICED = "PRICED"
    PROPOSAL_READY = "PROPOSAL_READY"


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    plan = Column(String, default="trial")           # trial | pro | enterprise
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="tenant")
    projects = relationship("Project", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default="sales_engineer")   # admin | sales_engineer | viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Project(Base):
    """One customer opportunity / bid."""
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    customer_name = Column(String)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
    currency = Column(String, default="SAR")
    margin_percent = Column(Float, default=15.0)      # default markup used by pricing engine
    created_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="projects")
    documents = relationship("Document", back_populates="project")
    requirements = relationship("ExtractedRequirement", back_populates="project")
    boq_items = relationship("BOQItem", back_populates="project")


class Document(Base):
    """Uploaded file: RFP, BOQ, Cost Sheet, Estimate Sheet, Datasheet, Customer Requirements."""
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    doc_type = Column(Enum(DocType), nullable=False)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)     # s3://... or local path
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)

    project = relationship("Project", back_populates="documents")


class Product(Base):
    """Tenant's product / datasheet catalog used for requirement matching + pricing."""
    __tablename__ = "products"
    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    sku = Column(String, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)                          # e.g. "DWDM", "Router", "ONT"
    spec_json = Column(JSON, default=dict)              # structured datasheet attributes
    unit_cost = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    currency = Column(String, default="SAR")
    lead_time_days = Column(Integer, default=30)

    tenant = relationship("Tenant", back_populates="products")


class ExtractedRequirement(Base):
    """
    Structured requirement extracted from RFP / Customer Requirements docs
    by the LLM extraction agent. Confidence + source_snippet kept for
    human-in-the-loop review (LLM never auto-decides quantities/pricing).
    """
    __tablename__ = "extracted_requirements"
    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    category = Column(String)
    description = Column(Text, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, default="unit")
    technical_attributes = Column(JSON, default=dict)
    confidence = Column(Float, default=0.0)
    source_snippet = Column(Text)
    matched_product_id = Column(String, ForeignKey("products.id"), nullable=True)
    reviewed = Column(Boolean, default=False)           # human approval flag

    project = relationship("Project", back_populates="requirements")


class BOQItem(Base):
    """
    Bill of Quantities line item. Produced by the deterministic matching +
    pricing rules engine — NOT by the LLM — so every number is auditable.
    """
    __tablename__ = "boq_items"
    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    requirement_id = Column(String, ForeignKey("extracted_requirements.id"), nullable=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=True)
    item_code = Column(String)
    description = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, default="unit")
    unit_cost = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    line_cost = Column(Float, default=0.0)
    line_price = Column(Float, default=0.0)
    margin_percent = Column(Float, default=0.0)
    rule_trace = Column(JSON, default=list)             # human-readable list of rules applied

    project = relationship("Project", back_populates="boq_items")


class PolicyDocument(Base):
    """
    Company internal policy document (discount policy, technical standards,
    approval thresholds, compliance clauses, etc.) — tenant-wide, not tied
    to a single project/bid. Uploaded once, referenced across every project.
    """
    __tablename__ = "policy_documents"
    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    ingested = Column(Boolean, default=False)           # chunked + embedded yet?
    chunk_count = Column(Integer, default=0)

    tenant = relationship("Tenant")


class PolicyChunk(Base):
    """
    A chunk of a policy document with its embedding vector, used for
    semantic retrieval (RAG). The embedding is stored as a plain JSON
    float array — fine at this scale; swap for pgvector + ANN index if
    the policy library grows past a few thousand chunks.
    """
    __tablename__ = "policy_chunks"
    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    document_id = Column(String, ForeignKey("policy_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=False)             # list[float]

    document = relationship("PolicyDocument")
