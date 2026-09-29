import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

from backend.app.models.entities import Assignment, Submission, AIAnalysis, SimilarityResult, Grade, Report
from backend.app.storage.local_storage import storage_service

class ReportService:
    def generate_assignment_report(
        self, 
        assignment_id: str, 
        teacher_id: str, 
        report_type: str = "comprehensive", 
        title: str = None,
        db: Session = None
    ) -> Report:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment:
            raise ValueError("Assignment not found")

        submissions = db.query(Submission).filter(Submission.id.in_(
            db.query(Submission.id).filter(Submission.assignment_id == assignment_id)
        )).all()

        total_submissions = len(submissions)
        completed_submissions = len([s for s in submissions if s.status == "completed"])

        # Collect AI analysis metrics
        ai_scores = []
        high_risk_ai_count = 0
        for s in submissions:
            ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == s.id).first()
            if ai:
                ai_scores.append(ai.score)
                if ai.score >= 50.0:
                    high_risk_ai_count += 1

        avg_ai_score = round(sum(ai_scores) / len(ai_scores), 1) if ai_scores else 0.0

        # Collect similarity metrics
        sim_results = db.query(SimilarityResult).filter(SimilarityResult.assignment_id == assignment_id).all()
        sim_scores = [s.score for s in sim_results]
        max_sim_score = max(sim_scores, default=0.0)
        high_similarity_pairs = len([s for s in sim_results if s.score >= 40.0])

        # Collect grades
        grades = db.query(Grade).filter(Grade.assignment_id == assignment_id).all()
        grade_scores = [g.final_score for g in grades]
        avg_grade = round(sum(grade_scores) / len(grade_scores), 1) if grade_scores else 0.0
        max_grade = max(grade_scores, default=0.0)
        min_grade = min(grade_scores, default=0.0)

        # Risk breakdown counts
        risk_clean = len([s for s in ai_scores if s < 25])
        risk_review = len([s for s in ai_scores if 25 <= s < 50])
        risk_flagged = len([s for s in ai_scores if s >= 50])

        # Score band histogram (AI scores)
        ai_histogram = [0, 0, 0, 0, 0]  # 0-20, 21-40, 41-60, 61-80, 81-100
        for score in ai_scores:
            idx = min(int(score / 20), 4)
            ai_histogram[idx] += 1

        # Score band histogram (Similarity scores)
        sim_histogram = [0, 0, 0, 0, 0]
        for score in sim_scores:
            idx = min(int(score / 20), 4)
            sim_histogram[idx] += 1

        summary_data = {
            "assignment_title": assignment.title,
            "course_name": assignment.team.name if assignment.team else "N/A",
            "due_date": assignment.due_date.isoformat() if assignment.due_date else "None",
            "max_marks": assignment.max_marks,
            "total_submissions": total_submissions,
            "completed_submissions": completed_submissions,
            "avg_ai_score": avg_ai_score,
            "high_risk_ai_submissions": high_risk_ai_count,
            "highest_similarity_score": max_sim_score,
            "flagged_similarity_pairs": high_similarity_pairs,
            "graded_count": len(grades),
            "average_grade": avg_grade,
            "highest_grade": max_grade,
            "lowest_grade": min_grade,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "risk_clean": risk_clean,
            "risk_review": risk_review,
            "risk_flagged": risk_flagged,
            "ai_histogram": ai_histogram,
            "sim_histogram": sim_histogram,
        }

        # Generate real PDF document
        pdf_filename = f"report_{assignment_id[:8]}_{int(datetime.now().timestamp())}.pdf"
        pdf_bytes = self._build_pdf_report(assignment.title, summary_data)
        rel_path, abs_path = storage_service.save_report(pdf_bytes, pdf_filename)

        report_record = Report(
            assignment_id=assignment_id,
            teacher_id=teacher_id,
            report_type=report_type,
            title=title or f"Integrity & Grading Report: {assignment.title}",
            summary_json=summary_data,
            file_path=rel_path
        )
        db.add(report_record)
        db.commit()
        db.refresh(report_record)

        return report_record

    def _build_pdf_report(self, title: str, data: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=40, 
            leftMargin=40, 
            topMargin=40, 
            bottomMargin=40
        )
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "VeritextTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=12
        )
        subtitle_style = ParagraphStyle(
            "VeritextSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=20
        )
        heading_style = ParagraphStyle(
            "VeritextHeading",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#312E81"),
            spaceBefore=14,
            spaceAfter=8
        )
        body_style = styles["Normal"]

        story = []
        story.append(Paragraph("VERITEXT ACADEMIC INTEGRITY & ASSESSMENT REPORT", subtitle_style))
        story.append(Paragraph(f"Assignment: {title}", title_style))
        story.append(Paragraph(f"Course: {data.get('course_name')} | Generated: {data.get('generated_at')[:10]}", subtitle_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph("1. Executive Summary", heading_style))
        table_data_1 = [
            ["Metric", "Value", "Status / Flag"],
            ["Total Submissions Received", str(data.get("total_submissions")), "Registered cohort"],
            ["Completed Analysis Jobs", str(data.get("completed_submissions")), "Active documents"],
            ["Cohort Average AI Stylometry Score", f"{data.get('avg_ai_score')}%", "Moderate" if data.get('avg_ai_score') < 40 else "Elevated"],
            ["Submissions with Elevated AI Likelihood (>50%)", str(data.get("high_risk_ai_submissions")), "Requires review"],
            ["Peak Inter-Submission Similarity", f"{data.get('highest_similarity_score')}%", "Normal" if data.get('highest_similarity_score') < 35 else "Cross-match flagged"],
        ]
        t1 = Table(table_data_1, colWidths=[200, 120, 180])
        t1.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(t1)
        story.append(Spacer(1, 15))

        story.append(Paragraph("2. Assessment & Grading Distribution", heading_style))
        table_data_2 = [
            ["Grading Metric", "Score"],
            ["Graded Submissions Count", str(data.get("graded_count"))],
            ["Average Cohort Grade", f"{data.get('average_grade')} / {data.get('max_marks')}"],
            ["Highest Grade", f"{data.get('highest_grade')} / {data.get('max_marks')}"],
            ["Lowest Grade", f"{data.get('lowest_grade')} / {data.get('max_marks')}"],
        ]
        t2 = Table(table_data_2, colWidths=[280, 220])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312E81")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(t2)
        story.append(Spacer(1, 20))

        # ── 3. Visual Charts ──────────────────────────────────────────────
        story.append(Paragraph("3. AI & Similarity Score Distribution", heading_style))
        story.append(Paragraph(
            "Bar chart showing the number of submissions falling into each score band "
            "for both AI-generated content probability and peer similarity metrics.",
            body_style
        ))
        story.append(Spacer(1, 8))

        # Build dual-series bar chart
        ai_hist = data.get("ai_histogram", [0, 0, 0, 0, 0])
        sim_hist = data.get("sim_histogram", [0, 0, 0, 0, 0])

        bar_drawing = Drawing(500, 200)
        bc = VerticalBarChart()
        bc.x = 60
        bc.y = 30
        bc.height = 140
        bc.width = 400
        bc.data = [sim_hist, ai_hist]
        bc.categoryAxis.categoryNames = ["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"]
        bc.categoryAxis.labels.fontName = "Helvetica"
        bc.categoryAxis.labels.fontSize = 8
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max(max(ai_hist), max(sim_hist), 1) + 2
        bc.valueAxis.valueStep = max(1, (max(max(ai_hist), max(sim_hist), 1) + 2) // 5)
        bc.valueAxis.labels.fontName = "Helvetica"
        bc.valueAxis.labels.fontSize = 8
        bc.bars[0].fillColor = colors.HexColor("#3B82F6")  # Blue - Similarity
        bc.bars[1].fillColor = colors.HexColor("#8B5CF6")  # Purple - AI
        bc.barWidth = 12
        bc.groupSpacing = 15

        # Legend labels
        bar_drawing.add(bc)
        bar_drawing.add(String(80, 185, "■ Peer Similarity", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#3B82F6")))
        bar_drawing.add(String(200, 185, "■ AI Probability", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#8B5CF6")))
        story.append(bar_drawing)
        story.append(Spacer(1, 15))

        # ── 4. Risk Breakdown Pie Chart ───────────────────────────────────
        story.append(Paragraph("4. Cohort Risk Breakdown", heading_style))
        story.append(Paragraph(
            "Pie chart showing the proportion of submissions classified as Clean (<25% AI score), "
            "Moderate Review (25–50%), and High Risk (>50%).",
            body_style
        ))
        story.append(Spacer(1, 8))

        risk_clean = data.get("risk_clean", 0)
        risk_review = data.get("risk_review", 0)
        risk_flagged = data.get("risk_flagged", 0)
        total_risk = risk_clean + risk_review + risk_flagged

        pie_drawing = Drawing(500, 200)

        if total_risk > 0:
            pie = Pie()
            pie.x = 120
            pie.y = 20
            pie.width = 150
            pie.height = 150
            pie.data = [risk_clean, risk_review, risk_flagged]
            pie.labels = [
                f"Clean ({risk_clean})",
                f"Review ({risk_review})",
                f"Flagged ({risk_flagged})",
            ]
            pie.slices[0].fillColor = colors.HexColor("#10B981")  # Green
            pie.slices[1].fillColor = colors.HexColor("#F59E0B")  # Amber
            pie.slices[2].fillColor = colors.HexColor("#EF4444")  # Red
            pie.slices.fontName = "Helvetica"
            pie.slices.fontSize = 8
            pie.slices.strokeWidth = 0.5
            pie.slices.strokeColor = colors.white
            pie_drawing.add(pie)

            # Legend text
            pie_drawing.add(String(310, 150, f"● Clean / Verified (<25%): {risk_clean}", fontName="Helvetica", fontSize=9, fillColor=colors.HexColor("#10B981")))
            pie_drawing.add(String(310, 130, f"● Moderate Review (25–50%): {risk_review}", fontName="Helvetica", fontSize=9, fillColor=colors.HexColor("#F59E0B")))
            pie_drawing.add(String(310, 110, f"● High Risk Flag (>50%): {risk_flagged}", fontName="Helvetica", fontSize=9, fillColor=colors.HexColor("#EF4444")))

            if total_risk > 0:
                compliance_pct = round((risk_clean / total_risk) * 100, 1)
                pie_drawing.add(String(310, 80, f"Compliance Rate: {compliance_pct}%", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#1E293B")))
        else:
            pie_drawing.add(String(150, 100, "No submission data available for risk chart.", fontName="Helvetica", fontSize=10, fillColor=colors.HexColor("#94A3B8")))

        story.append(pie_drawing)
        story.append(Spacer(1, 20))

        story.append(Paragraph("Certification Notice", heading_style))
        notice_text = (
            "This report was compiled deterministically from database records, stylometric n-gram entropy "
            "evaluations, cross-document shingling algorithms, and instructor audit trails by the VERITEXT "
            "Academic Engine. All analytical flags represent probabilistic indicators intended to guide "
            "academic review, not sole determinations of student misconduct."
        )
        story.append(Paragraph(notice_text, body_style))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

report_service = ReportService()

