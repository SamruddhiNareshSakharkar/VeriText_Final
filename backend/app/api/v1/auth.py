import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.core.dependencies import get_current_user
from backend.app.models.entities import User, AuditLog
from backend.app.schemas.schemas import (
    UserCreate, UserLogin, UserOut, Token,
    PasswordResetRequest, PasswordResetConfirm
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    user = User(
        email=user_in.email.lower(),
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        role=user_in.role.lower(),
        department=user_in.department.strip() if user_in.department else None,
        roll_no=user_in.roll_no.strip() if user_in.roll_no else None,
        faculty_id=user_in.faculty_id.strip() if user_in.faculty_id else None,
        designation=user_in.designation.strip() if user_in.designation else None,
        photo_url=user_in.photo_url.strip() if user_in.photo_url else None
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Record audit log
    audit = AuditLog(
        user_id=user.id,
        action="user_registered",
        target_type="user",
        target_id=user.id,
        details_json={
            "email": user.email, 
            "role": user.role, 
            "department": user.department, 
            "roll_no": user.roll_no,
            "faculty_id": user.faculty_id
        }
    )
    db.add(audit)
    db.commit()

    token = create_access_token(user.id)
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))

@router.post("/login", response_model=Token)
def login_user(login_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_in.email.lower()).first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(user.id)
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))

@router.get("/me", response_model=UserOut)
def get_authenticated_user_profile(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)

@router.post("/forgot-password")
def request_password_reset(data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        # Avoid user enumeration while being honest about operation
        return {"message": "If an account matches this email, a password reset token has been registered."}

    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    db.commit()

    return {
        "message": "Password reset token registered successfully.",
        "reset_token": reset_token  # Exposed in response for academic/development testing
    }

@router.post("/reset-password")
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == data.email.lower(),
        User.reset_token == data.reset_token
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unrecognized password reset token."
        )

    if user.reset_token_expires and user.reset_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new one."
        )

    user.password_hash = get_password_hash(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password has been successfully updated. You may now log in."}
