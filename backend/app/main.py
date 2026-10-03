import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["OMP_NUM_THREADS"] = "4"

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from backend.app.core.config import settings
from backend.app.database.session import engine, Base
# Import all models to ensure declarative metadata is registered
from backend.app.models.entities import *
from backend.app.api.v1 import (
    auth, teams, assignments, submissions, analysis, grading, reports, dashboard, audit
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veritext")

# Create tables if not existing
Base.metadata.create_all(bind=engine)

# Migration check for new columns in SQLite
try:
    with engine.connect() as conn:
        from sqlalchemy import text
        for col_def in [
            "ALTER TABLE similarity_results ADD COLUMN handwriting_score FLOAT DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN department VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN roll_no VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN faculty_id VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN designation VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN photo_url TEXT",
        ]:
            try:
                conn.execute(text(col_def))
                conn.commit()
            except Exception:
                pass  # Column already exists
except Exception:
    pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="VERITEXT: Academic Collaboration, Assignment Integrity, OCR/Handwriting Analysis, and Grading Platform"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits standard local Vite development ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing request: {request.url} - {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact the academic administrator."}
    )

# Include API v1 routers
api_prefix = settings.API_V1_STR
app.include_router(auth.router, prefix=api_prefix)
app.include_router(teams.router, prefix=api_prefix)
app.include_router(assignments.router, prefix=api_prefix)
app.include_router(submissions.router, prefix=api_prefix)
app.include_router(analysis.router, prefix=api_prefix)
app.include_router(grading.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Check for built frontend
frontend_dist = Path(__file__).resolve().parent.parent.parent / "New_frontend" / "dist"

@app.on_event("startup")
def seed_demo_accounts():
    from backend.app.database.session import SessionLocal
    from backend.app.core.security import get_password_hash
    from backend.app.models.entities import User
    db = SessionLocal()
    try:
        demo_accounts = [
            ("t.chen@uni.edu", "password123", "Prof. T. Chen", "teacher", "Computer Engineering", None, "FAC-COMP-01", "Associate Professor", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"),
            ("prof.smith@veritext.edu", "Password123!", "Prof. Smith", "teacher", "Information Technology", None, "FAC-IT-04", "Professor & HOD", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80"),
            ("student@uni.edu", "password123", "Alex Rivera", "student", "Computer Engineering", "24102A0074", None, None, "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80"),
            ("alex.rivera@veritext.edu", "StudentPassword456!", "Alex Rivera", "student", "Computer Engineering", "24102A0074", None, None, "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80"),
        ]
        for email, pwd, name, role, dept, roll, fac_id, desig, photo in demo_accounts:
            existing = db.query(User).filter(User.email == email).first()
            if not existing:
                db.add(User(
                    email=email,
                    password_hash=get_password_hash(pwd),
                    full_name=name,
                    role=role,
                    department=dept,
                    roll_no=roll,
                    faculty_id=fac_id,
                    designation=desig,
                    photo_url=photo
                ))
            else:
                existing.password_hash = get_password_hash(pwd)
                if not existing.department:
                    existing.department = dept
                if not existing.roll_no and roll:
                    existing.roll_no = roll
                if not existing.faculty_id and fac_id:
                    existing.faculty_id = fac_id
                if not existing.designation and desig:
                    existing.designation = desig
                if not existing.photo_url and photo:
                    existing.photo_url = photo
        
        # Also enrich any registered student accounts missing department/roll_no
        students = db.query(User).filter(User.role == "student", User.department == None).all()
        for s in students:
            s.department = "Computer Engineering"
            if not s.roll_no:
                s.roll_no = "24102A0074"
        db.commit()
    except Exception as e:
        logger.warning(f"Demo account seeding skipped or error: {e}")
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Mount frontend assets and provide SPA fallback via middleware
# (A catch-all @app.get route would shadow the API routers, so we use
#  a Starlette middleware that only fires for non-API GET requests.)
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response as StarletteResponse

    class SPAFallbackMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            # Only serve index.html for GET requests that:
            # 1. Are NOT API routes (/api/...)
            # 2. Are NOT the health endpoint
            # 3. Are NOT static assets
            # 4. Returned 404 (i.e. no FastAPI route matched)
            if (
                request.method == "GET"
                and response.status_code == 404
                and not request.url.path.startswith("/api")
                and not request.url.path.startswith("/assets")
                and request.url.path != "/health"
            ):
                index_path = frontend_dist / "index.html"
                if index_path.is_file():
                    return FileResponse(index_path)
            return response

    app.add_middleware(SPAFallbackMiddleware)
else:
    @app.get("/")
    def root_status():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "description": "Academic Collaboration & Assignment Integrity Engine"
        }
