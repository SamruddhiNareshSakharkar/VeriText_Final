import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.database.session import SessionLocal
from backend.app.models.entities import (
    Submission, AnalysisJob, OCRResult, AIAnalysis, 
    SimilarityResult, HandwritingAnalysis, GradingConfig, Grade, AuditLog
)
from backend.app.ml.ocr_engine import ocr_engine
from backend.app.ml.ai_detector import ai_detector
from backend.app.ml.similarity_engine import similarity_engine
from backend.app.ml.handwriting_engine import handwriting_engine
from backend.app.storage.local_storage import storage_service

logger = logging.getLogger(__name__)

def run_submission_analysis_pipeline(submission_id: str):
    """
    Complete backend analysis orchestrator executed synchronously or as a background task.
    Updates database state persistently at each step.
    """
    db: Session = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            logger.error(f"Submission {submission_id} not found for analysis.")
            return

        job = db.query(AnalysisJob).filter(AnalysisJob.submission_id == submission_id).first()
        if not job:
            job = AnalysisJob(
                submission_id=submission_id,
                status="processing_ocr",
                current_step="Starting document ingestion"
            )
            db.add(job)
            db.commit()
            db.refresh(job)

        abs_file_path = storage_service.get_absolute_path(submission.file_path)

        # -------------------------------------------------------------
        # STEP 1: OCR & DOCUMENT EXTRACTION
        # -------------------------------------------------------------
        job.status = "processing_ocr"
        job.current_step = "Extracting document content and text structures"
        submission.status = "processing"
        db.commit()

        ocr_data = ocr_engine.process_document(str(abs_file_path))
        extracted_text = ocr_data.get("extracted_text", "")

        existing_ocr = db.query(OCRResult).filter(OCRResult.submission_id == submission_id).first()
        if existing_ocr:
            existing_ocr.extracted_text = extracted_text
            existing_ocr.pages_json = ocr_data.get("pages", [])
            existing_ocr.word_count = ocr_data.get("word_count", 0)
            existing_ocr.status = ocr_data.get("status", "completed")
        else:
            ocr_record = OCRResult(
                submission_id=submission_id,
                extracted_text=extracted_text,
                pages_json=ocr_data.get("pages", []),
                word_count=ocr_data.get("word_count", 0),
                status=ocr_data.get("status", "completed")
            )
            db.add(ocr_record)
        db.commit()

        if ocr_data.get("status") == "failed" and not extracted_text:
            err = ocr_data.get("error", "No readable text could be extracted from document.")
            job.status = "failed"
            job.current_step = "Document extraction failed"
            job.error_message = err
            submission.status = "failed"
            submission.error_message = err
            db.commit()
            logger.warning(f"Submission {submission_id} failed document extraction: {err}")
            return

        # -------------------------------------------------------------
        # STEP 2: AI CONTENT DETECTION
        # -------------------------------------------------------------
        job.status = "processing_ai"
        job.current_step = "Evaluating stylometric entropy, perplexity, and AI probability"
        db.commit()

        ai_data = ai_detector.analyze_text(extracted_text)

        existing_ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == submission_id).first()
        if existing_ai:
            existing_ai.score = ai_data["score"]
            existing_ai.confidence = ai_data["confidence"]
            existing_ai.perplexity = ai_data["perplexity"]
            existing_ai.burstiness = ai_data["burstiness"]
            existing_ai.entropy = ai_data["entropy"]
            existing_ai.detected_spans_json = ai_data["detected_spans"]
            existing_ai.analysis_metadata_json = ai_data["analysis_metadata"]
        else:
            ai_record = AIAnalysis(
                submission_id=submission_id,
                score=ai_data["score"],
                confidence=ai_data["confidence"],
                perplexity=ai_data["perplexity"],
                burstiness=ai_data["burstiness"],
                entropy=ai_data["entropy"],
                detected_spans_json=ai_data["detected_spans"],
                analysis_metadata_json=ai_data["analysis_metadata"]
            )
            db.add(ai_record)
        db.commit()

        # -------------------------------------------------------------
        # STEP 3: CROSS-SUBMISSION SIMILARITY MATCHING
        # -------------------------------------------------------------
        job.status = "processing_similarity"
        job.current_step = "Analyzing cross-submission content similarity against peer submissions"
        db.commit()

        other_submissions = (
            db.query(Submission)
            .filter(
                Submission.assignment_id == submission.assignment_id,
                Submission.id != submission_id
            )
            .all()
        )

        for other_sub in other_submissions:
            other_ocr = db.query(OCRResult).filter(OCRResult.submission_id == other_sub.id).first()
            if not other_ocr or not other_ocr.extracted_text:
                continue

            sim_data = similarity_engine.compare_documents(extracted_text, other_ocr.extracted_text)

            # Check if pair record already exists
            existing_sim = (
                db.query(SimilarityResult)
                .filter(
                    SimilarityResult.assignment_id == submission.assignment_id,
                    ((SimilarityResult.submission_a_id == submission_id) & (SimilarityResult.submission_b_id == other_sub.id)) |
                    ((SimilarityResult.submission_a_id == other_sub.id) & (SimilarityResult.submission_b_id == submission_id))
                )
                .first()
            )

            if existing_sim:
                existing_sim.score = sim_data["score"]
                existing_sim.matching_segments_json = sim_data["matching_segments"]
                existing_sim.algorithm = sim_data["algorithm"]
            else:
                sim_record = SimilarityResult(
                    assignment_id=submission.assignment_id,
                    submission_a_id=submission_id,
                    submission_b_id=other_sub.id,
                    score=sim_data["score"],
                    matching_segments_json=sim_data["matching_segments"],
                    algorithm=sim_data["algorithm"]
                )
                db.add(sim_record)
        db.commit()

        # -------------------------------------------------------------
        # STEP 4: HANDWRITING COMPUTER VISION ANALYSIS & PAIR MATCHING
        # -------------------------------------------------------------
        job.status = "processing_handwriting"
        job.current_step = "Extracting handwriting stroke and slant geometric characteristics"
        db.commit()

        hw_data = handwriting_engine.analyze_document(str(abs_file_path))
        hw_feature_vec = hw_data.get("feature_vector", [])

        existing_hw = db.query(HandwritingAnalysis).filter(HandwritingAnalysis.submission_id == submission_id).first()
        if existing_hw:
            existing_hw.slant_angle = hw_data["slant_angle"]
            existing_hw.stroke_variance = hw_data["stroke_variance"]
            existing_hw.spacing_rhythm = hw_data["spacing_rhythm"]
            existing_hw.aspect_ratio = hw_data["aspect_ratio"]
            existing_hw.feature_vector_json = hw_feature_vec
            existing_hw.metrics_json = hw_data["metrics"]
            existing_hw.confidence = hw_data["confidence"]
        else:
            hw_record = HandwritingAnalysis(
                submission_id=submission_id,
                slant_angle=hw_data["slant_angle"],
                stroke_variance=hw_data["stroke_variance"],
                spacing_rhythm=hw_data["spacing_rhythm"],
                aspect_ratio=hw_data["aspect_ratio"],
                feature_vector_json=hw_feature_vec,
                metrics_json=hw_data["metrics"],
                confidence=hw_data["confidence"]
            )
            db.add(hw_record)
        db.commit()

        # Update pairwise handwriting similarity across peer submissions
        for other_sub in other_submissions:
            other_hw = db.query(HandwritingAnalysis).filter(HandwritingAnalysis.submission_id == other_sub.id).first()
            if not other_hw or not other_hw.feature_vector_json or not hw_feature_vec:
                continue

            hw_sim = handwriting_engine.compare_handwriting(hw_feature_vec, other_hw.feature_vector_json)

            sim_record = (
                db.query(SimilarityResult)
                .filter(
                    SimilarityResult.assignment_id == submission.assignment_id,
                    ((SimilarityResult.submission_a_id == submission_id) & (SimilarityResult.submission_b_id == other_sub.id)) |
                    ((SimilarityResult.submission_a_id == other_sub.id) & (SimilarityResult.submission_b_id == submission_id))
                )
                .first()
            )

            if sim_record:
                sim_record.handwriting_score = hw_sim
            else:
                sim_record = SimilarityResult(
                    assignment_id=submission.assignment_id,
                    submission_a_id=submission_id,
                    submission_b_id=other_sub.id,
                    score=0.0,
                    handwriting_score=hw_sim,
                    matching_segments_json=[],
                    algorithm="handwriting_stylometry"
                )
                db.add(sim_record)
        db.commit()

        # -------------------------------------------------------------
        # STEP 5: AUTOMATED GRADING EVALUATION
        # -------------------------------------------------------------
        max_marks = submission.assignment.max_marks if submission.assignment else 100.0
        grading_cfg = db.query(GradingConfig).filter(GradingConfig.assignment_id == submission.assignment_id).first()
        rule_audit = []
        calculated_score = max_marks

        # Check for highest similarity with peer submissions
        peer_sims = db.query(SimilarityResult).filter(
            SimilarityResult.assignment_id == submission.assignment_id,
            ((SimilarityResult.submission_a_id == submission_id) | (SimilarityResult.submission_b_id == submission_id))
        ).all()
        max_peer_sim = max([s.score for s in peer_sims], default=0.0)
        max_hw_sim = max([s.handwriting_score or 0.0 for s in peer_sims], default=0.0)

        if grading_cfg and grading_cfg.rules_json:
            for rule in grading_cfg.rules_json:
                rtype = rule.get("rule_type")
                threshold = float(rule.get("threshold", 0.0))
                penalty = float(rule.get("penalty_marks", 0.0))

                if rtype == "ai_threshold" and ai_data["score"] >= threshold:
                    deduction = min(calculated_score, penalty)
                    calculated_score -= deduction
                    rule_audit.append(f"AI Content Score ({ai_data['score']}%) exceeded threshold ({threshold}%): -{penalty} marks")
                elif rtype == "similarity_threshold" and max_peer_sim >= threshold:
                    deduction = min(calculated_score, penalty)
                    calculated_score -= deduction
                    rule_audit.append(f"Content Similarity ({max_peer_sim}%) exceeded threshold ({threshold}%): -{penalty} marks")
        else:
            # Baseline auto-grading calculation
            if ai_data["score"] > 30.0:
                ai_deduction = round(min(max_marks * 0.45, (ai_data["score"] - 30.0) * 0.6), 1)
                calculated_score -= ai_deduction
                rule_audit.append(f"Automated AI deduction: {ai_data['score']}% artificial stylometry (-{ai_deduction} marks)")

            if max_peer_sim > 30.0:
                sim_deduction = round(min(max_marks * 0.45, (max_peer_sim - 30.0) * 0.7), 1)
                calculated_score -= sim_deduction
                rule_audit.append(f"Automated similarity deduction: {max_peer_sim}% matching text with peer submission (-{sim_deduction} marks)")

            if max_hw_sim >= 75.0:
                rule_audit.append(f"Academic integrity alert: identical handwriting match ({max_hw_sim}%) flagged for teacher review")

        calculated_score = round(max(0.0, min(max_marks, calculated_score)), 1)

        # Update or create grade record
        existing_grade = db.query(Grade).filter(Grade.submission_id == submission_id).first()
        if not existing_grade:
            grade_record = Grade(
                submission_id=submission_id,
                assignment_id=submission.assignment_id,
                student_id=submission.student_id,
                final_score=calculated_score,
                max_marks=max_marks,
                criteria_scores_json={},
                feedback="Auto-graded based on document completeness, AI stylometry analysis, and peer similarity checks.",
                is_override=False,
                audit_trail_json=[{
                    "previous_score": None,
                    "new_score": calculated_score,
                    "changed_by_name": "Automated Grading Engine",
                    "reason": "; ".join(rule_audit) if rule_audit else "Baseline auto-grade generation",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }]
            )
            db.add(grade_record)
            db.commit()
        elif not existing_grade.is_override:
            # Update auto-calculated grade if teacher hasn't overridden
             previous_score = existing_grade.final_score
             existing_grade.final_score = calculated_score
             trail = existing_grade.audit_trail_json or []
             trail.append({
                "previous_score": previous_score,
                "new_score": calculated_score,
                "changed_by_name": "Automated Grading Engine",
                "reason": "; ".join(rule_audit) if rule_audit else "Updated auto-grade calculation",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
             existing_grade.audit_trail_json = trail
             db.commit()

        # -------------------------------------------------------------
        # COMPLETION
        # -------------------------------------------------------------
        job.status = "completed"
        job.current_step = "All integrity and document analyses completed successfully"
        job.completed_at = datetime.now(timezone.utc)
        submission.status = "completed"
        db.commit()

    except Exception as e:
        logger.exception(f"Error during submission {submission_id} analysis: {e}")
        db.rollback()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.submission_id == submission_id).first()
            if job:
                job.status = "failed"
                job.current_step = "Analysis encountered an unrecoverable failure"
                job.error_message = str(e)
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if submission:
                submission.status = "failed"
                submission.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def run_batch_assignment_analysis(assignment_id: str):
    """
    Executes full batch analysis across all submissions for a specified assignment:
    1. Runs OCR, AI stylometry, and Handwriting extraction on each submission.
    2. Performs N x N pairwise cross-matching for content similarity and handwriting similarity.
    3. Evaluates and applies automated grading for all submissions.
    """
    db: Session = SessionLocal()
    try:
        submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
        submission_ids = [s.id for s in submissions]
        db.close()

        # Run pipeline for each submission
        for sub_id in submission_ids:
            run_submission_analysis_pipeline(sub_id)

        # Query updated state to find flagged pairs
        db = SessionLocal()
        sim_pairs = db.query(SimilarityResult).filter(SimilarityResult.assignment_id == assignment_id).all()
        
        flagged_handwriting = []
        flagged_ai_content = []

        for p in sim_pairs:
            hw_score = p.handwriting_score or 0.0
            text_score = p.score or 0.0

            sub_a = p.submission_a
            sub_b = p.submission_b
            name_a = sub_a.student.full_name if sub_a and sub_a.student else "Student A"
            name_b = sub_b.student.full_name if sub_b and sub_b.student else "Student B"

            if hw_score >= 70.0:
                flagged_handwriting.append({
                    "id": p.id,
                    "submission_a_id": p.submission_a_id,
                    "submission_b_id": p.submission_b_id,
                    "student_a_name": name_a,
                    "student_b_name": name_b,
                    "handwriting_score": hw_score,
                    "flag": "Matching Handwriting Detected"
                })

            if text_score >= 60.0:
                flagged_ai_content.append({
                    "id": p.id,
                    "submission_a_id": p.submission_a_id,
                    "submission_b_id": p.submission_b_id,
                    "student_a_name": name_a,
                    "student_b_name": name_b,
                    "similarity_score": text_score,
                    "flag": "High Content / AI Match Detected"
                })

        return {
            "assignment_id": assignment_id,
            "total_processed": len(submission_ids),
            "flagged_handwriting_count": len(flagged_handwriting),
            "flagged_content_count": len(flagged_ai_content),
            "flagged_handwriting_pairs": flagged_handwriting,
            "flagged_content_pairs": flagged_ai_content
        }
    except Exception as e:
        logger.exception(f"Error in batch assignment analysis for {assignment_id}: {e}")
        return {"error": str(e)}
    finally:
        try:
            db.close()
        except Exception:
            pass
