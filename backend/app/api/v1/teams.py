import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user, get_current_teacher
from backend.app.models.entities import Team, TeamMember, User, AuditLog
from backend.app.schemas.schemas import (
    TeamCreate, TeamUpdate, TeamOut, TeamJoinRequest, TeamMemberOut, UserOut
)

router = APIRouter(prefix="/teams", tags=["Teams"])

def generate_join_code() -> str:
    # 6-character clean alphanumeric code prefixed with VTX-
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    random_str = "".join(secrets.choice(chars) for _ in range(6))
    return f"VTX-{random_str}"

@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    team_in: TeamCreate,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    # Ensure unique join code
    for _ in range(5):
        code = generate_join_code()
        if not db.query(Team).filter(Team.join_code == code).first():
            break

    team = Team(
        name=team_in.name.strip(),
        description=team_in.description.strip() if team_in.description else None,
        course_code=team_in.course_code.strip() if team_in.course_code else None,
        join_code=code,
        owner_id=current_user.id
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    # Automatically add creator as a member too
    membership = TeamMember(team_id=team.id, user_id=current_user.id)
    db.add(membership)

    audit = AuditLog(
        user_id=current_user.id,
        action="team_created",
        target_type="team",
        target_id=team.id,
        details_json={"name": team.name, "join_code": team.join_code}
    )
    db.add(audit)
    db.commit()

    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        course_code=team.course_code,
        join_code=team.join_code,
        owner_id=team.owner_id,
        owner=UserOut.model_validate(current_user),
        member_count=1,
        assignment_count=0,
        created_at=team.created_at
    )

@router.get("", response_model=List[TeamOut])
def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role in ["teacher", "admin"]:
        teams = db.query(Team).filter(Team.owner_id == current_user.id).order_by(Team.created_at.desc()).all()
    else:
        # Student: fetch teams joined via TeamMember
        team_ids = db.query(TeamMember.team_id).filter(TeamMember.user_id == current_user.id).all()
        ids = [t[0] for t in team_ids]
        teams = db.query(Team).filter(Team.id.in_(ids)).order_by(Team.created_at.desc()).all()

    result = []
    for t in teams:
        m_count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        a_count = len(t.assignments)
        result.append(TeamOut(
            id=t.id,
            name=t.name,
            description=t.description,
            course_code=t.course_code,
            join_code=t.join_code,
            owner_id=t.owner_id,
            owner=UserOut.model_validate(t.owner) if t.owner else None,
            member_count=m_count,
            assignment_count=a_count,
            created_at=t.created_at
        ))
    return result

@router.get("/{team_id}", response_model=TeamOut)
def get_team_detail(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team / Course not found")

    # Access check: user must be owner or member
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    if team.owner_id != current_user.id and not is_member and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this team")

    m_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    a_count = len(team.assignments)

    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        course_code=team.course_code,
        join_code=team.join_code,
        owner_id=team.owner_id,
        owner=UserOut.model_validate(team.owner) if team.owner else None,
        member_count=m_count,
        assignment_count=a_count,
        created_at=team.created_at
    )

@router.post("/join", response_model=TeamOut)
def join_team_by_code(
    data: TeamJoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clean_code = data.join_code.strip().upper()
    team = db.query(Team).filter(Team.join_code == clean_code).first()
    if not team and not clean_code.startswith("VTX-"):
        team = db.query(Team).filter(Team.join_code == f"VTX-{clean_code}").first()
    if not team:
        # Also try matching case-insensitive or without hyphen
        without_hyphen = clean_code.replace("-", "").replace(" ", "")
        team = db.query(Team).filter(
            (Team.join_code.ilike(f"%{clean_code}%")) |
            (Team.join_code.ilike(f"VTX-{without_hyphen}"))
        ).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid join code '{data.join_code}'. No active course matches this code."
        )

    # Check if already joined
    existing_membership = db.query(TeamMember).filter(
        TeamMember.team_id == team.id,
        TeamMember.user_id == current_user.id
    ).first()

    if not existing_membership:
        membership = TeamMember(team_id=team.id, user_id=current_user.id)
        db.add(membership)

        audit = AuditLog(
            user_id=current_user.id,
            action="team_joined",
            target_type="team",
            target_id=team.id,
            details_json={"join_code": clean_code, "team_name": team.name}
        )
        db.add(audit)
        db.commit()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already an enrolled member of this team."
        )

    m_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        course_code=team.course_code,
        join_code=team.join_code,
        owner_id=team.owner_id,
        owner=UserOut.model_validate(team.owner) if team.owner else None,
        member_count=m_count,
        assignment_count=len(team.assignments),
        created_at=team.created_at
    )

@router.get("/{team_id}/members", response_model=List[TeamMemberOut])
def get_team_members(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    return [
        TeamMemberOut(
            id=m.id,
            user_id=m.user_id,
            user=UserOut.model_validate(m.user),
            joined_at=m.joined_at
        )
        for m in members if m.user
    ]
