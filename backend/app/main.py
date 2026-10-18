from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.v1.salesmen import router as salesmen_router
from app.api.v1.territories import router as territories_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.reports import router as reports_router
from app.api.v1.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB
    await connect_to_mongo()
    yield
    # Shutdown: Close MongoDB connection
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Project CORE: Coverage, Outlet & Route Excellence - Sales Intelligence Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for Vite React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check probe returning application status."""
    return {"status": "ok", "app": settings.PROJECT_NAME}


# Mount API v1 Routers under /api/v1
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(salesmen_router, prefix="/api/v1/salesmen", tags=["Salesmen"])
app.include_router(territories_router, prefix="/api/v1/territories", tags=["Territories"])
app.include_router(territories_router, prefix="/api/v1", tags=["Territories Cascading Direct"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports & Exports"])
