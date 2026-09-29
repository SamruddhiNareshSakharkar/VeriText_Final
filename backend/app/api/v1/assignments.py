from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user, get_current_teacher
from backend.app.models.entities import Team, TeamMember, Assignment, Submission, User, AuditLog
from backend.app.schemas.schemas import (
    AssignmentCreate, AssignmentUpdate, AssignmentOut
)

router = APIRouter(tags=["Assignments"])

@router.post("/teams/{team_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    team_id: str,
    data: AssignmentCreate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course / Team not found")

    if team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create assignments in courses you instruct."
        )

    assignment = Assignment(
        team_id=team_id,
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        due_date=data.due_date,
        max_marks=data.max_marks,
        allowed_file_types=data.allowed_file_types.strip().lower()
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    audit = AuditLog(
        user_id=current_user.id,
        action="assignment_created",
        target_type="assignment",
        target_id=assignment.id,
        details_json={"title": assignment.title, "team_id": team_id}
    )
    db.add(audit)
    db.commit()

    return AssignmentOut(
        id=assignment.id,
        team_id=assignment.team_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        max_marks=assignment.max_marks,
        allowed_file_types=assignment.allowed_file_types,
        is_active=assignment.is_active,
        submission_count=0,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at
    )

@router.get("/teams/{team_id}/assignments", response_model=List[AssignmentOut])
def list_team_assignments(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    assignments = db.query(Assignment).filter(Assignment.team_id == team_id).order_by(Assignment.created_at.desc()).all()
    results = []
    for a in assignments:
        sub_count = db.query(Submission).filter(Submission.assignment_id == a.id).count()
        results.append(AssignmentOut(
            id=a.id,
            team_id=a.team_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            max_marks=a.max_marks,
            allowed_file_types=a.allowed_file_types,
            is_active=a.is_active,
            submission_count=sub_count,
            created_at=a.created_at,
            updated_at=a.updated_at
        ))
    return results

@router.get("/assignments", response_model=List[AssignmentOut])
def list_user_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "admin":
        assignments = db.query(Assignment).order_by(Assignment.created_at.desc()).all()
    elif current_user.role == "teacher":
        teacher_teams = db.query(Team.id).filter(Team.owner_id == current_user.id).all()
        team_ids = [t[0] for t in teacher_teams]
        member_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).all()
        team_ids.extend([t[0] for t in member_teams])
        if team_ids:
            assignments = db.query(Assignment).filter(Assignment.team_id.in_(team_ids)).order_by(Assignment.created_at.desc()).all()
        else:
            assignments = []
        if not assignments:
            # Provide system assignments so teachers can review and compare submissions
            assignments = db.query(Assignment).order_by(Assignment.created_at.desc()).all()
    else:
        member_teams = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).all()
        team_ids = [t[0] for t in member_teams]
        sub_assign_ids = [s[0] for s in db.query(Submission.assignment_id).filter(Submission.student_id == current_user.id).all()]
        assignments = db.query(Assignment).filter(
            (Assignment.team_id.in_(team_ids)) | (Assignment.id.in_(sub_assign_ids))
        ).order_by(Assignment.created_at.desc()).all()
    results = []
    for a in assignments:
        sub_count = db.query(Submission).filter(Submission.assignment_id == a.id).count()
        results.append(AssignmentOut(
            id=a.id,
            team_id=a.team_id,
            title=a.title,
            description=a.description,
            due_date=a.due_date,
            max_marks=a.max_marks,
            allowed_file_types=a.allowed_file_types,
            is_active=a.is_active,
            submission_count=sub_count,
            created_at=a.created_at,
            updated_at=a.updated_at
        ))
    return results

@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment_detail(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    sub_count = db.query(Submission).filter(Submission.assignment_id == assignment.id).count()
    return AssignmentOut(
        id=assignment.id,
        team_id=assignment.team_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        max_marks=assignment.max_marks,
        allowed_file_types=assignment.allowed_file_types,
        is_active=assignment.is_active,
        submission_count=sub_count,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at
    )

@router.put("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: str,
    data: AssignmentUpdate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    if data.title is not None:
        assignment.title = data.title.strip()
    if data.description is not None:
        assignment.description = data.description.strip()
    if data.due_date is not None:
        assignment.due_date = data.due_date
    if data.max_marks is not None:
        assignment.max_marks = data.max_marks
    if data.allowed_file_types is not None:
        assignment.allowed_file_types = data.allowed_file_types.strip().lower()
    if data.is_active is not None:
        assignment.is_active = data.is_active

    db.commit()
    db.refresh(assignment)

    audit = AuditLog(
        user_id=current_user.id,
        action="assignment_updated",
        target_type="assignment",
        target_id=assignment.id,
        details_json={"title": assignment.title}
    )
    db.add(audit)
    db.commit()

    sub_count = db.query(Submission).filter(Submission.assignment_id == assignment.id).count()
    return AssignmentOut(
        id=assignment.id,
        team_id=assignment.team_id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        max_marks=assignment.max_marks,
        allowed_file_types=assignment.allowed_file_types,
        is_active=assignment.is_active,
        submission_count=sub_count,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at
    )
