from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import auth, projects, documents, extraction, products, pricing

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(extraction.router)
app.include_router(products.router)
app.include_router(pricing.router)


@app.on_event("startup")
def on_startup():
    # For local/dev convenience. In staging/production, use Alembic
    # migrations instead of create_all (see backend/README.md).
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    """Used by the ALB target group health check in AWS."""
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} API", "docs": "/docs"}
