import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, status
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.core.dependencies import get_current_user, get_current_teacher
from backend.app.models.entities import (
    Submission, AnalysisJob, AIAnalysis, OCRResult,
    SimilarityResult, HandwritingAnalysis, Assignment, Grade, User
)
from backend.app.schemas.schemas import (
    FullAnalysisOut, SubmissionOut, AIAnalysisOut, OCRResultOut,
    HandwritingAnalysisOut, TwoSubmissionCompareRequest, TwoSubmissionCompareOut,
    UserOut, MatchingSegment, OCRPage, DetectedSpan
)
from backend.app.services.analysis_orchestrator import (
    run_submission_analysis_pipeline, run_batch_assignment_analysis
)
from backend.app.ml.ocr_engine import ocr_engine
from backend.app.ml.ai_detector import ai_detector
from backend.app.ml.similarity_engine import similarity_engine
from backend.app.ml.handwriting_engine import handwriting_engine
from backend.app.storage.local_storage import storage_service

router = APIRouter(tags=["Analysis Engine"])

@router.get("/submissions/{submission_id}/analysis", response_model=FullAnalysisOut)
def get_submission_analysis(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # Authorization
    is_owner = submission.student_id == current_user.id
    is_teacher = current_user.role in ["teacher", "admin"]
    if not is_owner and not is_teacher:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    job = db.query(AnalysisJob).filter(AnalysisJob.submission_id == submission_id).first()
    ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == submission_id).first()
    ocr = db.query(OCRResult).filter(OCRResult.submission_id == submission_id).first()
    hw = db.query(HandwritingAnalysis).filter(HandwritingAnalysis.submission_id == submission_id).first()

    # Query similarity records involving this submission
    sim_query = db.query(SimilarityResult).filter(
        (SimilarityResult.submission_a_id == submission_id) |
        (SimilarityResult.submission_b_id == submission_id)
    ).all()

    top_sim = max(sim_query, key=lambda s: s.score, default=None)
    max_sim = top_sim.score if top_sim else 0.0

    similarity_matches = []
    top_matched_sub_id = None
    top_matched_name = None

    if top_sim and top_sim.matching_segments_json:
        is_a = (top_sim.submission_a_id == submission_id)
        peer_sub_id = top_sim.submission_b_id if is_a else top_sim.submission_a_id
        top_matched_sub_id = peer_sub_id
        peer_sub = db.query(Submission).filter(Submission.id == peer_sub_id).first()
        if peer_sub and peer_sub.student:
            top_matched_name = peer_sub.student.full_name or peer_sub.student.name or peer_sub.file_name
        elif peer_sub:
            top_matched_name = peer_sub.file_name

        raw_segs = top_sim.matching_segments_json or []
        for seg in raw_segs:
            if is_a:
                similarity_matches.append(MatchingSegment(
                    start_a=seg.get("start_a", 0),
                    end_a=seg.get("end_a", 0),
                    start_b=seg.get("start_b", 0),
                    end_b=seg.get("end_b", 0),
                    text=seg.get("text", ""),
                    length=seg.get("length", 0)
                ))
            else:
                similarity_matches.append(MatchingSegment(
                    start_a=seg.get("start_b", 0),
                    end_a=seg.get("end_b", 0),
                    start_b=seg.get("start_a", 0),
                    end_b=seg.get("end_a", 0),
                    text=seg.get("text", ""),
                    length=seg.get("length", 0)
                ))

    ai_out = None
    if ai:
        ai_out = AIAnalysisOut(
            id=ai.id,
            submission_id=ai.submission_id,
            score=ai.score,
            confidence=ai.confidence,
            perplexity=ai.perplexity,
            burstiness=ai.burstiness,
            entropy=ai.entropy,
            detected_spans=ai.detected_spans_json or [],
            analysis_metadata=ai.analysis_metadata_json or {},
            created_at=ai.created_at
        )

    ocr_out = None
    if ocr:
        ocr_out = OCRResultOut(
            id=ocr.id,
            submission_id=ocr.submission_id,
            extracted_text=ocr.extracted_text,
            pages=ocr.pages_json or [],
            word_count=ocr.word_count,
            status=ocr.status,
            created_at=ocr.created_at
        )

    hw_out = None
    if hw:
        hw_out = HandwritingAnalysisOut(
            id=hw.id,
            submission_id=hw.submission_id,
            slant_angle=hw.slant_angle,
            stroke_variance=hw.stroke_variance,
            spacing_rhythm=hw.spacing_rhythm,
            aspect_ratio=hw.aspect_ratio,
            feature_vector=hw.feature_vector_json or [],
            metrics=hw.metrics_json or {},
            confidence=hw.confidence,
            created_at=hw.created_at
        )

    return FullAnalysisOut(
        submission=SubmissionOut(
            id=submission.id,
            assignment_id=submission.assignment_id,
            student_id=submission.student_id,
            student=UserOut.model_validate(submission.student) if submission.student else None,
            file_name=submission.file_name,
            file_size=submission.file_size,
            mime_type=submission.mime_type,
            status=submission.status,
            error_message=submission.error_message,
            submitted_at=submission.submitted_at,
            assignment_title=submission.assignment.title if submission.assignment else None,
            team_name=submission.assignment.team.name if (submission.assignment and submission.assignment.team) else None
        ),
        job_status=job.status if job else "queued",
        current_step=job.current_step if job else "Initializing",
        ai_analysis=ai_out,
        ocr_result=ocr_out,
        handwriting_analysis=hw_out,
        max_similarity_score=round(max_sim, 1),
        similar_submissions_count=len(sim_query),
        similarity_matches=similarity_matches,
        top_matched_submission_id=top_matched_sub_id,
        top_matched_student_name=top_matched_name
    )

@router.post("/submissions/{submission_id}/reanalyze")
def trigger_submission_reanalysis(
    submission_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")



    submission.status = "queued"
    job = db.query(AnalysisJob).filter(AnalysisJob.submission_id == submission_id).first()
    if job:
        job.status = "queued"
        job.current_step = "Re-analysis queued"
        job.error_message = None
        job.completed_at = None
    db.commit()

    background_tasks.add_task(run_submission_analysis_pipeline, submission_id)
    return {"message": "Re-analysis queued successfully", "status": "queued"}

@router.post("/comparison", response_model=TwoSubmissionCompareOut)
def compare_two_submissions(
    data: TwoSubmissionCompareRequest,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    sub_a = db.query(Submission).filter(Submission.id == data.submission_a_id).first()
    sub_b = db.query(Submission).filter(Submission.id == data.submission_b_id).first()

    if not sub_a or not sub_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both submissions not found")

    # Verify teacher ownership
    if sub_a.assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    ocr_a = db.query(OCRResult).filter(OCRResult.submission_id == sub_a.id).first()
    ocr_b = db.query(OCRResult).filter(OCRResult.submission_id == sub_b.id).first()

    text_a = ocr_a.extracted_text if ocr_a else ""
    text_b = ocr_b.extracted_text if ocr_b else ""

    sim_result = similarity_engine.compare_documents(text_a, text_b)

    ai_a = db.query(AIAnalysis).filter(AIAnalysis.submission_id == sub_a.id).first()
    ai_b = db.query(AIAnalysis).filter(AIAnalysis.submission_id == sub_b.id).first()

    spans_a = ai_a.detected_spans_json if (ai_a and ai_a.detected_spans_json) else []
    if not spans_a and text_a and len(text_a.strip()) > 30:
        live_ai_a = ai_detector.analyze_text(text_a)
        spans_a = live_ai_a.get("detected_spans", [])

    spans_b = ai_b.detected_spans_json if (ai_b and ai_b.detected_spans_json) else []
    if not spans_b and text_b and len(text_b.strip()) > 30:
        live_ai_b = ai_detector.analyze_text(text_b)
        spans_b = live_ai_b.get("detected_spans", [])

    hw_a = db.query(HandwritingAnalysis).filter(HandwritingAnalysis.submission_id == sub_a.id).first()
    hw_b = db.query(HandwritingAnalysis).filter(HandwritingAnalysis.submission_id == sub_b.id).first()

    hw_score = None
    if hw_a and hw_b and hw_a.feature_vector_json and hw_b.feature_vector_json:
        hw_score = handwriting_engine.compare_handwriting(hw_a.feature_vector_json, hw_b.feature_vector_json)

    return TwoSubmissionCompareOut(
        submission_a=SubmissionOut.model_validate(sub_a),
        submission_b=SubmissionOut.model_validate(sub_b),
        ocr_text_a=text_a,
        ocr_text_b=text_b,
        similarity_score=sim_result["score"],
        algorithm=sim_result["algorithm"],
        matching_segments=[MatchingSegment(**m) for m in sim_result["matching_segments"]],
        ai_analysis_a=AIAnalysisOut(
            id=ai_a.id if ai_a else str(uuid.uuid4()),
            submission_id=sub_a.id,
            score=ai_a.score if ai_a else 0.0,
            confidence=ai_a.confidence if ai_a else 0.0,
            perplexity=ai_a.perplexity if ai_a else None,
            burstiness=ai_a.burstiness if ai_a else None,
            entropy=ai_a.entropy if ai_a else None,
            detected_spans=spans_a,
            analysis_metadata=ai_a.analysis_metadata_json if ai_a else {},
            created_at=ai_a.created_at if ai_a else datetime.now(timezone.utc)
        ),
        ai_analysis_b=AIAnalysisOut(
            id=ai_b.id if ai_b else str(uuid.uuid4()),
            submission_id=sub_b.id,
            score=ai_b.score if ai_b else 0.0,
            confidence=ai_b.confidence if ai_b else 0.0,
            perplexity=ai_b.perplexity if ai_b else None,
            burstiness=ai_b.burstiness if ai_b else None,
            entropy=ai_b.entropy if ai_b else None,
            detected_spans=spans_b,
            analysis_metadata=ai_b.analysis_metadata_json if ai_b else {},
            created_at=ai_b.created_at if ai_b else datetime.now(timezone.utc)
        ),
        handwriting_a=HandwritingAnalysisOut(
            id=hw_a.id,
            submission_id=hw_a.submission_id,
            slant_angle=hw_a.slant_angle,
            stroke_variance=hw_a.stroke_variance,
            spacing_rhythm=hw_a.spacing_rhythm,
            aspect_ratio=hw_a.aspect_ratio,
            feature_vector=hw_a.feature_vector_json or [],
            metrics=hw_a.metrics_json or {},
            confidence=hw_a.confidence,
            created_at=hw_a.created_at
        ) if hw_a else None,
        handwriting_b=HandwritingAnalysisOut(
            id=hw_b.id,
            submission_id=hw_b.submission_id,
            slant_angle=hw_b.slant_angle,
            stroke_variance=hw_b.stroke_variance,
            spacing_rhythm=hw_b.spacing_rhythm,
            aspect_ratio=hw_b.aspect_ratio,
            feature_vector=hw_b.feature_vector_json or [],
            metrics=hw_b.metrics_json or {},
            confidence=hw_b.confidence,
            created_at=hw_b.created_at
        ) if hw_b else None,
        handwriting_similarity_score=hw_score
    )

@router.get("/assignments/{assignment_id}/cohort-analytics")
def get_cohort_analytics(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
    if not submissions:
        return {
            "has_data": False,
            "total_submissions": 0,
            "message": "No submissions yet for this assignment."
        }

    # Aggregate AI score brackets
    ai_records = db.query(AIAnalysis).filter(
        AIAnalysis.submission_id.in_([s.id for s in submissions])
    ).all()

    brackets = {"0-20% (Low)": 0, "21-50% (Moderate)": 0, "51-80% (High)": 0, "81-100% (Critical)": 0}
    ai_scores_list = []
    for r in ai_records:
        ai_scores_list.append(r.score)
        if r.score <= 20:
            brackets["0-20% (Low)"] += 1
        elif r.score <= 50:
            brackets["21-50% (Moderate)"] += 1
        elif r.score <= 80:
            brackets["51-80% (High)"] += 1
        else:
            brackets["81-100% (Critical)"] += 1

    # Similarity and handwriting pairs
    sim_pairs = db.query(SimilarityResult).filter(SimilarityResult.assignment_id == assignment_id).all()
    flagged_pairs = []
    flagged_handwriting_pairs = []
    for p in sim_pairs:
        name_a = p.submission_a.student.full_name if p.submission_a and p.submission_a.student else "Student A"
        name_b = p.submission_b.student.full_name if p.submission_b and p.submission_b.student else "Student B"
        if p.score >= 25.0:
            flagged_pairs.append({
                "id": p.id,
                "submission_a_id": p.submission_a_id,
                "student_a_name": name_a,
                "submission_b_id": p.submission_b_id,
                "student_b_name": name_b,
                "score": p.score,
                "matched_segments_count": len(p.matching_segments_json or [])
            })
        if (p.handwriting_score or 0.0) >= 70.0:
            flagged_handwriting_pairs.append({
                "id": p.id,
                "submission_a_id": p.submission_a_id,
                "student_a_name": name_a,
                "submission_b_id": p.submission_b_id,
                "student_b_name": name_b,
                "handwriting_score": p.handwriting_score,
                "flag": "Matching Handwriting Detected"
            })

    # Grades distribution
    grades = db.query(Grade).filter(Grade.assignment_id == assignment_id).all()
    grade_scores = [g.final_score for g in grades]

    return {
        "has_data": True,
        "total_submissions": len(submissions),
        "completed_count": len([s for s in submissions if s.status == "completed"]),
        "ai_distribution": [{"bracket": k, "count": v} for k, v in brackets.items()],
        "average_ai_score": round(sum(ai_scores_list) / len(ai_scores_list), 1) if ai_scores_list else 0.0,
        "flagged_similarity_pairs": flagged_pairs,
        "flagged_handwriting_pairs": flagged_handwriting_pairs,
        "graded_count": len(grades),
        "average_grade": round(sum(grade_scores) / len(grade_scores), 1) if grade_scores else 0.0,
        "max_marks": assignment.max_marks
    }


@router.post("/assignments/{assignment_id}/process-all")
def process_all_assignment_submissions(
    assignment_id: str,
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """
    Triggers batch OCR, AI detection, cross-comparison (text + handwriting),
    and auto-grading evaluation for all submissions under an assignment.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.team.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = run_batch_assignment_analysis(assignment_id)
    return result


@router.post("/comparison/upload-compare", response_model=TwoSubmissionCompareOut)
async def upload_and_compare_documents(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    current_user: User = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    """
    Uploads two documents directly on the fly, runs OCR, AI stylometry detection,
    document similarity, and handwriting feature matching, returning a side-by-side comparison.
    """
    content_a = await file_a.read()
    content_b = await file_b.read()

    rel_a, abs_a, size_a = storage_service.save_file(content_a, file_a.filename)
    rel_b, abs_b, size_b = storage_service.save_file(content_b, file_b.filename)

    # 1. OCR / Text Extraction (offloaded to thread to avoid event loop conflicts)
    ocr_a = await asyncio.to_thread(ocr_engine.process_document, str(abs_a))
    ocr_b = await asyncio.to_thread(ocr_engine.process_document, str(abs_b))
    text_a = ocr_a.get("extracted_text", "")
    text_b = ocr_b.get("extracted_text", "")

    # Safety Fallback: If OCR returned empty but raw content is decodeable text (code/txt/markdown)
    if not text_a.strip() and content_a:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                decoded = content_a.decode(enc).strip()
                if decoded and len(decoded.split()) > 0:
                    text_a = decoded
                    ocr_a["word_count"] = len(decoded.split())
                    break
            except Exception:
                pass

    if not text_b.strip() and content_b:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                decoded = content_b.decode(enc).strip()
                if decoded and len(decoded.split()) > 0:
                    text_b = decoded
                    ocr_b["word_count"] = len(decoded.split())
                    break
            except Exception:
                pass

    # 2. AI Content Detection
    ai_a = await asyncio.to_thread(ai_detector.analyze_text, text_a)
    ai_b = await asyncio.to_thread(ai_detector.analyze_text, text_b)

    # 3. Text Similarity
    sim_result = await asyncio.to_thread(similarity_engine.compare_documents, text_a, text_b)

    # 4. Handwriting CV Analysis
    hw_a = await asyncio.to_thread(handwriting_engine.analyze_document, str(abs_a))
    hw_b = await asyncio.to_thread(handwriting_engine.analyze_document, str(abs_b))
    hw_sim = handwriting_engine.compare_handwriting(
        hw_a.get("feature_vector", []), hw_b.get("feature_vector", [])
    )

    now = datetime.now(timezone.utc)

    sub_out_a = SubmissionOut(
        id=str(uuid.uuid4()),
        assignment_id="",
        student_id="",
        file_name=file_a.filename or "Document 1",
        file_size=size_a,
        mime_type=file_a.content_type or "application/octet-stream",
        status="completed",
        submitted_at=now,
        ocr_status="completed",
        ocr_word_count=ocr_a.get("word_count", 0),
        ai_score=ai_a.get("score", 0.0)
    )

    sub_out_b = SubmissionOut(
        id=str(uuid.uuid4()),
        assignment_id="",
        student_id="",
        file_name=file_b.filename or "Document 2",
        file_size=size_b,
        mime_type=file_b.content_type or "application/octet-stream",
        status="completed",
        submitted_at=now,
        ocr_status="completed",
        ocr_word_count=ocr_b.get("word_count", 0),
        ai_score=ai_b.get("score", 0.0)
    )

    return TwoSubmissionCompareOut(
        submission_a=sub_out_a,
        submission_b=sub_out_b,
        ocr_text_a=text_a,
        ocr_text_b=text_b,
        similarity_score=sim_result["score"],
        algorithm=sim_result["algorithm"],
        matching_segments=[MatchingSegment(**m) for m in sim_result["matching_segments"]],
        ai_analysis_a=AIAnalysisOut(
            id=str(uuid.uuid4()),
            submission_id=sub_out_a.id,
            score=ai_a["score"],
            confidence=ai_a["confidence"],
            perplexity=ai_a.get("perplexity"),
            burstiness=ai_a.get("burstiness"),
            entropy=ai_a.get("entropy"),
            detected_spans=[DetectedSpan(**s) for s in ai_a.get("detected_spans", [])],
            analysis_metadata=ai_a.get("analysis_metadata", {}),
            created_at=now
        ),
        ai_analysis_b=AIAnalysisOut(
            id=str(uuid.uuid4()),
            submission_id=sub_out_b.id,
            score=ai_b["score"],
            confidence=ai_b["confidence"],
            perplexity=ai_b.get("perplexity"),
            burstiness=ai_b.get("burstiness"),
            entropy=ai_b.get("entropy"),
            detected_spans=[DetectedSpan(**s) for s in ai_b.get("detected_spans", [])],
            analysis_metadata=ai_b.get("analysis_metadata", {}),
            created_at=now
        ),
        handwriting_a=HandwritingAnalysisOut(
            id=str(uuid.uuid4()),
            submission_id=sub_out_a.id,
            slant_angle=hw_a.get("slant_angle", 0.0),
            stroke_variance=hw_a.get("stroke_variance", 0.0),
            spacing_rhythm=hw_a.get("spacing_rhythm", 0.0),
            aspect_ratio=hw_a.get("aspect_ratio", 0.0),
            feature_vector=hw_a.get("feature_vector", []),
            metrics=hw_a.get("metrics", {}),
            confidence=hw_a.get("confidence", 0.0),
            created_at=now
        ),
        handwriting_b=HandwritingAnalysisOut(
            id=str(uuid.uuid4()),
            submission_id=sub_out_b.id,
            slant_angle=hw_b.get("slant_angle", 0.0),
            stroke_variance=hw_b.get("stroke_variance", 0.0),
            spacing_rhythm=hw_b.get("spacing_rhythm", 0.0),
            aspect_ratio=hw_b.get("aspect_ratio", 0.0),
            feature_vector=hw_b.get("feature_vector", []),
            metrics=hw_b.get("metrics", {}),
            confidence=hw_b.get("confidence", 0.0),
            created_at=now
        ),
        handwriting_similarity_score=hw_sim
    )
