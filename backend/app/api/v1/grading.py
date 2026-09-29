from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user, get_current_teacher
from backend.app.models.entities import (
    Assignment, Submission, GradingConfig, Grade, User, AuditLog
)
from backend.app.schemas.schemas import (
    GradingConfigCreate, GradingConfigOut, GradeUpdate, GradeOut, UserOut
)

router = APIRouter(tags=["Grading"])

@router.get("/grades/me", response_model=List[GradeOut])
def get_my_grades(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all grades for the current student."""
    grades = (
        db.query(Grade)
        .filter(Grade.student_id == current_user.id)
        .order_by(Grade.updated_at.desc())
        .all()
    )
    return [
        GradeOut(
            id=g.id,
            submission_id=g.submission_id,
            assignment_id=g.assignment_id,
            student_id=g.student_id,
            student=UserOut.model_validate(g.student) if g.student else None,
            grader_id=g.grader_id,
            final_score=g.final_score,
            max_marks=g.max_marks,
            criteria_scores=g.criteria_scores_json or {},
            feedback=g.feedback,
            is_override=g.is_override,
            audit_trail=g.audit_trail_json or [],
            updated_at=g.updated_at
        )
        for g in grades
    ]


@router.get("/assignments/{assignment_id}/grading-config", response_model=Optional[GradingConfigOut])
def get_assignment_grading_config(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    config = db.query(GradingConfig).filter(GradingConfig.assignment_id == assignment_id).first()
    if not config:
        return None

    return GradingConfigOut(
        id=config.id,
        assignment_id=config.assignment_id,
        criteria=config.criteria_json or [],
        rules=config.rules_json or [],
        created_at=config.created_at,
        updated_at=config.updated_at
    )

@router.post("/assignments/{assignment_id}/grading-config", response_model=GradingConfigOut)
def save_assignment_grading_config(
    assignment_id: str,
    data: GradingConfigCreate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Validate criteria weight
    if data.criteria:
        total_weight = sum(c.weight for c in data.criteria)
        if abs(total_weight - 100.0) > 0.5 and abs(total_weight - assignment.max_marks) > 0.5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Criteria weights must sum to 100% or to the assignment maximum marks ({assignment.max_marks}). Current sum: {total_weight}"
            )

    config = db.query(GradingConfig).filter(GradingConfig.assignment_id == assignment_id).first()
    criteria_dicts = [c.model_dump() for c in data.criteria]
    rules_dicts = [r.model_dump() for r in data.rules]

    if config:
        config.criteria_json = criteria_dicts
        config.rules_json = rules_dicts
        config.updated_at = datetime.now(timezone.utc)
    else:
        config = GradingConfig(
            assignment_id=assignment_id,
            criteria_json=criteria_dicts,
            rules_json=rules_dicts
        )
        db.add(config)

    audit = AuditLog(
        user_id=current_user.id,
        action="grading_config_updated",
        target_type="grading_config",
        target_id=assignment_id,
        details_json={"criteria_count": len(criteria_dicts), "rules_count": len(rules_dicts)}
    )
    db.add(audit)
    db.commit()
    db.refresh(config)

    return GradingConfigOut(
        id=config.id,
        assignment_id=config.assignment_id,
        criteria=config.criteria_json,
        rules=config.rules_json,
        created_at=config.created_at,
        updated_at=config.updated_at
    )

@router.get("/submissions/{submission_id}/grade", response_model=Optional[GradeOut])
def get_submission_grade(
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

    grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
    if not grade:
        return None

    return GradeOut(
        id=grade.id,
        submission_id=grade.submission_id,
        assignment_id=grade.assignment_id,
        student_id=grade.student_id,
        student=UserOut.model_validate(grade.student) if grade.student else None,
        grader_id=grade.grader_id,
        final_score=grade.final_score,
        max_marks=grade.max_marks,
        criteria_scores=grade.criteria_scores_json or {},
        feedback=grade.feedback,
        is_override=grade.is_override,
        audit_trail=grade.audit_trail_json or [],
        updated_at=grade.updated_at
    )

@router.post("/submissions/{submission_id}/grade", response_model=GradeOut)
@router.put("/submissions/{submission_id}/grade", response_model=GradeOut)
def record_submission_grade(
    submission_id: str,
    data: GradeUpdate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")



    max_marks = submission.assignment.max_marks
    if data.final_score < 0 or data.final_score > max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Final score must be between 0 and {max_marks}"
        )

    grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
    previous_score = grade.final_score if grade else None

    # Audit log entry for grade preservation
    audit_entry = {
        "previous_score": previous_score,
        "new_score": data.final_score,
        "changed_by_name": current_user.full_name,
        "reason": data.reason or "Manual grading assessment",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if grade:
        current_trail = grade.audit_trail_json or []
        current_trail.append(audit_entry)
        grade.final_score = data.final_score
        grade.criteria_scores_json = data.criteria_scores
        grade.feedback = data.feedback
        grade.grader_id = current_user.id
        grade.is_override = True
        grade.audit_trail_json = current_trail
        grade.updated_at = datetime.now(timezone.utc)
    else:
        grade = Grade(
            submission_id=submission_id,
            assignment_id=submission.assignment_id,
            student_id=submission.student_id,
            grader_id=current_user.id,
            final_score=data.final_score,
            max_marks=max_marks,
            criteria_scores_json=data.criteria_scores,
            feedback=data.feedback,
            is_override=True,
            audit_trail_json=[audit_entry]
        )
        db.add(grade)

    audit = AuditLog(
        user_id=current_user.id,
        action="grade_modified",
        target_type="grade",
        target_id=submission_id,
        details_json={
            "previous_score": previous_score,
            "new_score": data.final_score,
            "student_id": submission.student_id
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(grade)

    return GradeOut(
        id=grade.id,
        submission_id=grade.submission_id,
        assignment_id=grade.assignment_id,
        student_id=grade.student_id,
        student=UserOut.model_validate(grade.student) if grade.student else None,
        grader_id=grade.grader_id,
        final_score=grade.final_score,
        max_marks=grade.max_marks,
        criteria_scores=grade.criteria_scores_json or {},
        feedback=grade.feedback,
        is_override=grade.is_override,
        audit_trail=grade.audit_trail_json or [],
        updated_at=grade.updated_at
    )
