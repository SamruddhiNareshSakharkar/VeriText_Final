from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user
from backend.app.models.entities import (
    User, Team, TeamMember, Assignment, Submission, Grade, AIAnalysis
)

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard/stats")
def get_user_dashboard_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    if current_user.role in ["teacher", "admin"]:
        teacher_teams = db.query(Team).filter(Team.owner_id == current_user.id).all()
        team_ids = [t.id for t in teacher_teams]

        assignments = db.query(Assignment).filter(Assignment.team_id.in_(team_ids)).all()
        assignment_ids = [a.id for a in assignments]

        submissions = db.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).all()
        submission_ids = [s.id for s in submissions]

        # Graded submissions
        grades = db.query(Grade).filter(Grade.assignment_id.in_(assignment_ids)).all()
        graded_submission_ids = set(g.submission_id for g in grades)
        pending_reviews = len([s for s in submissions if s.id not in graded_submission_ids and s.status == "completed"])

        # High AI alerts (> 50%)
        high_ai_records = db.query(AIAnalysis).filter(
            AIAnalysis.submission_id.in_(submission_ids),
            AIAnalysis.score >= 50.0
        ).count()

        # Recent 5 submissions
        recent_subs = (
            db.query(Submission)
            .filter(Submission.assignment_id.in_(assignment_ids))
            .order_by(Submission.submitted_at.desc())
            .limit(5)
            .all()
        )

        recent_activity = []
        for s in recent_subs:
            ai_rec = db.query(AIAnalysis).filter(AIAnalysis.submission_id == s.id).first()
            recent_activity.append({
                "submission_id": s.id,
                "assignment_id": s.assignment_id,
                "assignment_title": s.assignment.title if s.assignment else "Assignment",
                "student_name": s.student.full_name if s.student else "Student",
                "submitted_at": s.submitted_at.isoformat(),
                "status": s.status,
                "ai_score": ai_rec.score if ai_rec else None
            })

        return {
            "role": "teacher",
            "total_teams": len(teacher_teams),
            "total_assignments": len(assignments),
            "total_submissions": len(submissions),
            "pending_reviews": pending_reviews,
            "high_ai_flags": high_ai_records,
            "recent_submissions": recent_activity
        }
    else:
        # Student Dashboard
        memberships = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).all()
        team_ids = [m.team_id for m in memberships]

        assignments = db.query(Assignment).filter(Assignment.team_id.in_(team_ids)).all()
        assignment_ids = [a.id for a in assignments]

        submissions = db.query(Submission).filter(Submission.student_id == current_user.id).all()
        submitted_assignment_ids = set(s.assignment_id for s in submissions)

        grades = db.query(Grade).filter(Grade.student_id == current_user.id).all()
        grade_percentages = [(g.final_score / g.max_marks) * 100.0 for g in grades if g.max_marks > 0]
        avg_score = round(sum(grade_percentages) / len(grade_percentages), 1) if grade_percentages else 0.0

        # Pending assignments
        pending_assignments = [
            {
                "id": a.id,
                "title": a.title,
                "course_name": a.team.name if a.team else "Course",
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "max_marks": a.max_marks
            }
            for a in assignments if a.id not in submitted_assignment_ids and a.is_active
        ]

        recent_submissions = [
            {
                "id": s.id,
                "assignment_title": s.assignment.title if s.assignment else "Assignment",
                "submitted_at": s.submitted_at.isoformat(),
                "status": s.status,
                "file_name": s.file_name,
                "grade": next((g.final_score for g in grades if g.submission_id == s.id), None),
                "max_marks": s.assignment.max_marks if s.assignment else 100.0
            }
            for s in submissions[:5]
        ]

        return {
            "role": "student",
            "enrolled_teams": len(team_ids),
            "pending_assignments_count": len(pending_assignments),
            "completed_submissions_count": len(submissions),
            "graded_count": len(grades),
            "average_grade_percentage": avg_score,
            "pending_assignments": pending_assignments[:5],
            "recent_submissions": recent_submissions
        }
