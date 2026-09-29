from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user, get_current_teacher
from backend.app.models.entities import Assignment, Report, User, AuditLog
from backend.app.schemas.schemas import ReportCreate, ReportOut
from backend.app.services.report_service import report_service
from backend.app.storage.local_storage import storage_service

router = APIRouter(tags=["Reports"])

@router.post("/assignments/{assignment_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_assignment_report(
    assignment_id: str,
    data: ReportCreate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    report_record = report_service.generate_assignment_report(
        assignment_id=assignment_id,
        teacher_id=current_user.id,
        report_type=data.report_type,
        title=data.title,
        db=db
    )

    audit = AuditLog(
        user_id=current_user.id,
        action="report_generated",
        target_type="report",
        target_id=report_record.id,
        details_json={"assignment_id": assignment_id, "title": report_record.title}
    )
    db.add(audit)
    db.commit()

    return ReportOut(
        id=report_record.id,
        assignment_id=report_record.assignment_id,
        teacher_id=report_record.teacher_id,
        report_type=report_record.report_type,
        title=report_record.title,
        summary_data=report_record.summary_json or {},
        file_url=f"/api/v1/reports/{report_record.id}/download",
        created_at=report_record.created_at
    )

@router.get("/assignments/{assignment_id}/reports", response_model=List[ReportOut])
def get_assignment_report_history(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    reports = db.query(Report).filter(Report.assignment_id == assignment_id).order_by(Report.created_at.desc()).all()
    return [
        ReportOut(
            id=r.id,
            assignment_id=r.assignment_id,
            teacher_id=r.teacher_id,
            report_type=r.report_type,
            title=r.title,
            summary_data=r.summary_json or {},
            file_url=f"/api/v1/reports/{r.id}/download",
            created_at=r.created_at
        )
        for r in reports
    ]

@router.get("/reports/{report_id}/download")
def download_generated_report_pdf(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if not report.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF file not available")

    abs_path = storage_service.get_absolute_path(report.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF file missing from storage")

    return FileResponse(
        path=str(abs_path),
        filename=f"{report.title.replace(' ', '_')}.pdf",
        media_type="application/pdf"
    )
