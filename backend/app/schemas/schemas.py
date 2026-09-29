from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# --- AUTH & USER SCHEMAS ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    department: Optional[str] = None
    roll_no: Optional[str] = None
    faculty_id: Optional[str] = None
    designation: Optional[str] = None
    photo_url: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(min_length=6)
    role: str = Field(default="student", pattern="^(student|teacher|admin)$")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(UserBase):
    id: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    email: EmailStr
    reset_token: str
    new_password: str = Field(min_length=6)


# --- TEAM SCHEMAS ---
class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    course_code: Optional[str] = None

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    course_code: Optional[str] = None

class TeamMemberOut(BaseModel):
    id: str
    user_id: str
    user: UserOut
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TeamOut(TeamBase):
    id: str
    join_code: str
    owner_id: str
    owner: Optional[UserOut] = None
    member_count: int = 0
    assignment_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TeamJoinRequest(BaseModel):
    join_code: str = Field(min_length=4, max_length=32)


# --- ASSIGNMENT SCHEMAS ---
class AssignmentBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_marks: float = Field(default=100.0, ge=1.0)
    allowed_file_types: str = Field(default="pdf,txt,docx,png,jpg")

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    max_marks: Optional[float] = None
    allowed_file_types: Optional[str] = None
    is_active: Optional[bool] = None

class AssignmentOut(AssignmentBase):
    id: str
    team_id: str
    is_active: bool
    submission_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- SUBMISSION SCHEMAS ---
class SubmissionOut(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student: Optional[UserOut] = None
    file_name: str
    file_size: int
    mime_type: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    submitted_at: datetime
    # Enriched analytical & grading metrics for side-by-side view
    ai_score: Optional[float] = None
    ocr_status: Optional[str] = None
    ocr_word_count: Optional[int] = None
    max_similarity: Optional[float] = None
    handwriting_match_flag: Optional[str] = None
    ai_match_flag: Optional[str] = None
    auto_grade: Optional[float] = None
    final_grade: Optional[float] = None
    max_marks: Optional[float] = None
    is_graded: Optional[bool] = None
    assignment_title: Optional[str] = None
    team_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- ANALYSIS SCHEMAS ---
class DetectedSpan(BaseModel):
    start: int
    end: int
    text: str
    confidence: float
    reason: str

class AIAnalysisOut(BaseModel):
    id: str
    submission_id: str
    score: float
    confidence: float
    perplexity: Optional[float] = None
    burstiness: Optional[float] = None
    entropy: Optional[float] = None
    detected_spans: List[DetectedSpan] = []
    analysis_metadata: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class OCRPage(BaseModel):
    page_number: int
    text: str
    line_count: int

class OCRResultOut(BaseModel):
    id: str
    submission_id: str
    extracted_text: str
    pages: List[OCRPage] = []
    word_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MatchingSegment(BaseModel):
    start_a: int
    end_a: int
    start_b: int
    end_b: int
    text: str
    length: int

class SimilarityResultOut(BaseModel):
    id: str
    assignment_id: str
    submission_a_id: str
    submission_b_id: str
    score: float
    handwriting_score: Optional[float] = 0.0
    matching_segments: List[MatchingSegment] = []
    algorithm: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class HandwritingAnalysisOut(BaseModel):
    id: str
    submission_id: str
    slant_angle: float
    stroke_variance: float
    spacing_rhythm: float
    aspect_ratio: float
    feature_vector: List[float] = []
    metrics: Dict[str, Any] = {}
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FullAnalysisOut(BaseModel):
    submission: SubmissionOut
    job_status: str
    current_step: str
    ai_analysis: Optional[AIAnalysisOut] = None
    ocr_result: Optional[OCRResultOut] = None
    handwriting_analysis: Optional[HandwritingAnalysisOut] = None
    max_similarity_score: Optional[float] = None
    similar_submissions_count: int = 0


# --- TWO-SUBMISSION COMPARISON SCHEMAS ---
class TwoSubmissionCompareRequest(BaseModel):
    submission_a_id: str
    submission_b_id: str

class TwoSubmissionCompareOut(BaseModel):
    submission_a: Optional[SubmissionOut] = None
    submission_b: Optional[SubmissionOut] = None
    ocr_text_a: str
    ocr_text_b: str
    similarity_score: float
    algorithm: str
    matching_segments: List[MatchingSegment] = []
    ai_analysis_a: Optional[AIAnalysisOut] = None
    ai_analysis_b: Optional[AIAnalysisOut] = None
    handwriting_a: Optional[HandwritingAnalysisOut] = None
    handwriting_b: Optional[HandwritingAnalysisOut] = None
    handwriting_similarity_score: Optional[float] = None


# --- GRADING SCHEMAS ---
class CriteriaItem(BaseModel):
    name: str
    weight: float
    description: Optional[str] = None

class RuleItem(BaseModel):
    rule_type: str  # e.g., 'ai_threshold', 'similarity_threshold', 'manual_review'
    threshold: float
    penalty_marks: float = 0.0
    action: str = "deduct"  # 'deduct', 'flag', 'zero'

class GradingConfigCreate(BaseModel):
    criteria: List[CriteriaItem] = []
    rules: List[RuleItem] = []

class GradingConfigOut(BaseModel):
    id: str
    assignment_id: str
    criteria: List[CriteriaItem] = []
    rules: List[RuleItem] = []
    created_at: datetime
    updated_at: datetime

class GradeUpdate(BaseModel):
    final_score: float
    criteria_scores: Dict[str, float] = {}
    feedback: Optional[str] = None
    reason: Optional[str] = "Manual grade assignment/adjustment"

class GradeAuditItem(BaseModel):
    previous_score: Optional[float]
    new_score: float
    changed_by_name: str
    reason: str
    timestamp: str

class GradeOut(BaseModel):
    id: str
    submission_id: str
    assignment_id: str
    student_id: str
    student: Optional[UserOut] = None
    grader_id: Optional[str] = None
    final_score: float
    max_marks: float
    criteria_scores: Dict[str, float] = {}
    feedback: Optional[str] = None
    is_override: bool
    audit_trail: List[GradeAuditItem] = []
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- REPORT SCHEMAS ---
class ReportCreate(BaseModel):
    report_type: str = "comprehensive"  # 'comprehensive', 'integrity_summary', 'grading_breakdown'
    title: Optional[str] = None

class ReportOut(BaseModel):
    id: str
    assignment_id: str
    teacher_id: str
    report_type: str
    title: str
    summary_data: Dict[str, Any]
    file_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- AUDIT SCHEMAS ---
class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    target_type: str
    target_id: str
    details: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
