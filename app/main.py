from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.db import engine, Base
from app.routes import (
    upload_routes,
    case_routes,
    schedule_routes,
    analytics_routes
)
import os
# Run migrations before SQLAlchemy initialization to ensure columns exist
from app.database.migrations import run_db_migrations
run_db_migrations()

# Create all DB tables
import app.models.case_model  # noqa: F401
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Court Case Backlog Prioritization Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Judicial AI Platform API. Frontend runs on Streamlit (Port 8501)."}

# ── Routers ────────────────────────────────────────────────────
app.include_router(upload_routes.router,    prefix=f"{settings.API_V1_STR}/upload",    tags=["Upload"])
app.include_router(case_routes.router,      prefix=f"{settings.API_V1_STR}/cases",     tags=["Cases"])
app.include_router(schedule_routes.router,  prefix=f"{settings.API_V1_STR}/schedule",  tags=["Schedule"])
app.include_router(analytics_routes.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "online", "app": settings.APP_NAME}
