from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.models.entities import (
    Assignment, Submission, AnalysisJob, TeamMember, User, AuditLog,
    OCRResult, AIAnalysis, SimilarityResult, Grade
)
from backend.app.schemas.schemas import SubmissionOut, UserOut
from backend.app.storage.local_storage import storage_service
from backend.app.services.analysis_orchestrator import run_submission_analysis_pipeline

router = APIRouter(tags=["Submissions"])

@router.get("/submissions/me", response_model=List[SubmissionOut])
def get_my_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all submissions made by the current user."""
    submissions = (
        db.query(Submission)
        .filter(Submission.student_id == current_user.id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )
    return [build_enriched_submission_out(s, db) for s in submissions]


@router.post("/assignments/{assignment_id}/submissions", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def submit_assignment_document(
    assignment_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    # Ensure student/user is enrolled in the course team
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == assignment.team_id,
        TeamMember.user_id == current_user.id
    ).first()
    if not is_member and assignment.team_id:
        auto_member = TeamMember(
            team_id=assignment.team_id,
            user_id=current_user.id,
            role=current_user.role if current_user.role in ["student", "teacher"] else "student"
        )
        db.add(auto_member)
        db.commit()

    # Validate file extension
    ext = Path(file.filename).suffix.lstrip(".").lower()
    allowed = [t.strip().lower() for t in assignment.allowed_file_types.split(",")]
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '.{ext}' is not permitted. Allowed formats: {assignment.allowed_file_types}"
        )

    # Read and validate size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes). Please select a valid document."
        )

    if ext == "pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file does not have a valid PDF header format."
        )

    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum upload limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    # Save to storage
    rel_path, abs_path, size_bytes = storage_service.save_file(content, file.filename)

    # Check for existing previous submission by this student for this assignment
    existing_sub = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_user.id
    ).first()

    if existing_sub:
        # Delete old file
        storage_service.delete_file(existing_sub.file_path)
        existing_sub.file_name = file.filename
        existing_sub.file_path = rel_path
        existing_sub.file_size = size_bytes
        existing_sub.mime_type = file.content_type
        existing_sub.status = "queued"
        existing_sub.error_message = None
        db.commit()
        db.refresh(existing_sub)
        submission = existing_sub
    else:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            file_name=file.filename,
            file_path=rel_path,
            file_size=size_bytes,
            mime_type=file.content_type,
            status="queued"
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

    # Ensure AnalysisJob record is present
    job = db.query(AnalysisJob).filter(AnalysisJob.submission_id == submission.id).first()
    if not job:
        job = AnalysisJob(
            submission_id=submission.id,
            status="queued",
            current_step="Queued for analysis"
        )
        db.add(job)
    else:
        job.status = "queued"
        job.current_step = "Queued for analysis"
        job.error_message = None
        job.completed_at = None
    db.commit()

    # Dispatch analysis task asynchronously
    background_tasks.add_task(run_submission_analysis_pipeline, submission.id)

    audit = AuditLog(
        user_id=current_user.id,
        action="submission_uploaded",
        target_type="submission",
        target_id=submission.id,
        details_json={"assignment_id": assignment_id, "file_name": file.filename}
    )
    db.add(audit)
    db.commit()

    return SubmissionOut(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student=UserOut.model_validate(current_user),
        file_name=submission.file_name,
        file_size=submission.file_size,
        mime_type=submission.mime_type,
        status=submission.status,
        error_message=submission.error_message,
        submitted_at=submission.submitted_at
    )

def build_enriched_submission_out(s: Submission, db: Session) -> SubmissionOut:
    ocr = db.query(OCRResult).filter(OCRResult.submission_id == s.id).first()
    ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == s.id).first()
    grade = db.query(Grade).filter(Grade.submission_id == s.id).first()

    # Cross-submission similarity check within the same assignment
    sim_records = db.query(SimilarityResult).filter(
        SimilarityResult.assignment_id == s.assignment_id,
        ((SimilarityResult.submission_a_id == s.id) | (SimilarityResult.submission_b_id == s.id))
    ).all()

    max_sim = max([r.score for r in sim_records], default=0.0) if sim_records else None

    hw_match_flag = None
    ai_match_flag = None

    for r in sim_records:
        other_sub = r.submission_b if r.submission_a_id == s.id else r.submission_a
        other_name = other_sub.student.full_name if (other_sub and other_sub.student) else "Student"

        if (r.handwriting_score or 0.0) >= 70.0 and not hw_match_flag:
            hw_match_flag = f"Same handwriting as {other_name} ({round(r.handwriting_score, 1)}%)"

        if (r.score or 0.0) >= 60.0 and not ai_match_flag:
            ai_match_flag = f"Identical content with {other_name} ({round(r.score, 1)}%)"

    max_marks = s.assignment.max_marks if s.assignment else 100.0
    auto_grade_val = None
    final_grade_val = None
    is_graded_val = False

    if grade:
        final_grade_val = grade.final_score
        is_graded_val = grade.is_override
        if grade.audit_trail_json:
            for item in grade.audit_trail_json:
                if "Automated" in item.get("changed_by_name", ""):
                    auto_grade_val = item.get("new_score")
                    break
        if auto_grade_val is None:
            auto_grade_val = grade.final_score

    assign_title = s.assignment.title if s.assignment else None
    t_name = s.assignment.team.name if (s.assignment and s.assignment.team) else None

    return SubmissionOut(
        id=s.id,
        assignment_id=s.assignment_id,
        student_id=s.student_id,
        student=UserOut.model_validate(s.student) if s.student else None,
        file_name=s.file_name,
        file_size=s.file_size,
        mime_type=s.mime_type,
        status=s.status,
        error_message=s.error_message,
        submitted_at=s.submitted_at,
        ocr_status=ocr.status if ocr else None,
        ocr_word_count=ocr.word_count if ocr else None,
        ai_score=round(ai.score, 1) if ai else None,
        max_similarity=round(max_sim, 1) if max_sim is not None else None,
        handwriting_match_flag=hw_match_flag,
        ai_match_flag=ai_match_flag,
        auto_grade=auto_grade_val,
        final_grade=final_grade_val,
        max_marks=max_marks,
        is_graded=is_graded_val,
        assignment_title=assign_title,
        team_name=t_name
    )

@router.get("/assignments/{assignment_id}/submissions", response_model=List[SubmissionOut])
def list_assignment_submissions(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    query = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    if current_user.role == "student":
        # Privacy enforcement: students see only their own submission
        query = query.filter(Submission.student_id == current_user.id)
    elif current_user.role in ["teacher", "admin"]:
        # Teachers and administrators can view submissions for evaluation
        pass
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    submissions = query.order_by(Submission.submitted_at.desc()).all()
    return [build_enriched_submission_out(s, db) for s in submissions]

@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission_by_id(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Privacy check
    is_owner = submission.student_id == current_user.id
    is_teacher = current_user.role in ["teacher", "admin"]
    if not is_owner and not is_teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return build_enriched_submission_out(submission, db)

@router.get("/submissions/{submission_id}/file")
def download_submission_file(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    is_owner = submission.student_id == current_user.id
    is_teacher = current_user.role in ["teacher", "admin"]
    if not is_owner and not is_teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    abs_path = storage_service.get_absolute_path(submission.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on storage")

    return FileResponse(
        path=str(abs_path),
        filename=submission.file_name,
        media_type=submission.mime_type or "application/octet-stream"
    )
