import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from backend.app.database.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="student")  # 'student', 'teacher', 'admin'
    department = Column(String(100), nullable=True)  # Computer Engineering, IT, ECS, EXTC, Biomedical
    roll_no = Column(String(50), nullable=True)  # For students (e.g. 24102A0074)
    faculty_id = Column(String(50), nullable=True)  # For teachers (e.g. FAC-COMP-01)
    designation = Column(String(100), nullable=True)  # For teachers (e.g. Assistant Professor)
    photo_url = Column(Text, nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    owned_teams = relationship("Team", back_populates="owner", cascade="all, delete-orphan")
    memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan")
    grades = relationship("Grade", back_populates="student", foreign_keys="Grade.student_id")
    audit_logs = relationship("AuditLog", back_populates="user")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    course_code = Column(String(50), nullable=True)
    join_code = Column(String(32), unique=True, index=True, nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    owner = relationship("User", back_populates="owned_teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=utc_now, nullable=False)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    max_marks = Column(Float, default=100.0, nullable=False)
    allowed_file_types = Column(String(255), default="pdf,txt,docx,png,jpg", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    team = relationship("Team", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")
    grading_config = relationship("GradingConfig", back_populates="assignment", uselist=False, cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    mime_type = Column(String(100), nullable=True)
    status = Column(String(50), default="uploaded", nullable=False)  # uploaded, queued, processing, completed, failed
    error_message = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=utc_now, nullable=False)

    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User", back_populates="submissions")
    analysis_job = relationship("AnalysisJob", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    ai_analysis = relationship("AIAnalysis", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    ocr_result = relationship("OCRResult", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    handwriting_analysis = relationship("HandwritingAnalysis", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    grade = relationship("Grade", back_populates="submission", uselist=False, cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, unique=True)
    status = Column(String(50), default="queued", nullable=False)  # queued, processing_ocr, processing_ai, processing_similarity, processing_handwriting, completed, failed
    current_step = Column(String(100), default="Initializing analysis", nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    submission = relationship("Submission", back_populates="analysis_job")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, unique=True)
    score = Column(Float, default=0.0, nullable=False)  # 0.0 - 100.0 percentage
    confidence = Column(Float, default=0.0, nullable=False)  # 0.0 - 1.0
    perplexity = Column(Float, default=0.0, nullable=True)
    burstiness = Column(Float, default=0.0, nullable=True)
    entropy = Column(Float, default=0.0, nullable=True)
    detected_spans_json = Column(JSON, default=list, nullable=False)  # list of {start, end, text, confidence, reason}
    analysis_metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    submission = relationship("Submission", back_populates="ai_analysis")


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, unique=True)
    extracted_text = Column(Text, nullable=False, default="")
    pages_json = Column(JSON, default=list, nullable=False)  # list of {page_number, text, line_count}
    word_count = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    submission = relationship("Submission", back_populates="ocr_result")


class SimilarityResult(Base):
    __tablename__ = "similarity_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False)
    submission_a_id = Column(String(36), ForeignKey("submissions.id"), nullable=False)
    submission_b_id = Column(String(36), ForeignKey("submissions.id"), nullable=False)
    score = Column(Float, default=0.0, nullable=False)  # 0.0 - 100.0 percentage
    handwriting_score = Column(Float, default=0.0, nullable=True)  # 0.0 - 100.0 percentage
    matching_segments_json = Column(JSON, default=list, nullable=False)  # list of {start_a, end_a, start_b, end_b, text, length}
    algorithm = Column(String(100), default="hybrid_tfidf_shingling", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    submission_a = relationship("Submission", foreign_keys=[submission_a_id])
    submission_b = relationship("Submission", foreign_keys=[submission_b_id])


class HandwritingAnalysis(Base):
    __tablename__ = "handwriting_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, unique=True)
    slant_angle = Column(Float, default=0.0, nullable=False)
    stroke_variance = Column(Float, default=0.0, nullable=False)
    spacing_rhythm = Column(Float, default=0.0, nullable=False)
    aspect_ratio = Column(Float, default=0.0, nullable=False)
    feature_vector_json = Column(JSON, default=list, nullable=False)
    metrics_json = Column(JSON, default=dict, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    submission = relationship("Submission", back_populates="handwriting_analysis")


class GradingConfig(Base):
    __tablename__ = "grading_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False, unique=True)
    criteria_json = Column(JSON, default=list, nullable=False)  # list of {name, weight, description}
    rules_json = Column(JSON, default=list, nullable=False)  # list of {rule_type, threshold, penalty, action}
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    assignment = relationship("Assignment", back_populates="grading_config")


class Grade(Base):
    __tablename__ = "grades"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, unique=True)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    grader_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    final_score = Column(Float, default=0.0, nullable=False)
    max_marks = Column(Float, default=100.0, nullable=False)
    criteria_scores_json = Column(JSON, default=dict, nullable=False)  # {criteria_name: score}
    feedback = Column(Text, nullable=True)
    is_override = Column(Boolean, default=False, nullable=False)
    audit_trail_json = Column(JSON, default=list, nullable=False)  # list of {previous_score, new_score, changed_by, reason, timestamp}
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    submission = relationship("Submission", back_populates="grade")
    student = relationship("User", foreign_keys=[student_id], back_populates="grades")
    grader = relationship("User", foreign_keys=[grader_id])


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    report_type = Column(String(50), default="comprehensive", nullable=False)
    title = Column(String(255), nullable=False)
    summary_json = Column(JSON, default=dict, nullable=False)
    file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    assignment = relationship("Assignment", back_populates="reports")
    teacher = relationship("User", foreign_keys=[teacher_id])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(100), nullable=False)
    target_id = Column(String(36), nullable=False)
    details_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="audit_logs")
