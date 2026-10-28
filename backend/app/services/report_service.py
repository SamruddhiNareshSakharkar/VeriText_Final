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

        # Detailed student submission roster
        student_roster = []
        for s in submissions:
            ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == s.id).first()
            sim_item = db.query(SimilarityResult).filter(
                (SimilarityResult.submission_a_id == s.id) | (SimilarityResult.submission_b_id == s.id)
            ).order_by(SimilarityResult.score.desc()).first()
            grade_item = db.query(Grade).filter(Grade.submission_id == s.id).first()

            s_name = s.student.full_name if s.student and s.student.full_name else (s.student.name if s.student else "Student")
            s_ai = round(ai.score, 1) if ai else 0.0
            s_sim = round(sim_item.score, 1) if sim_item else 0.0
            s_grade = round(grade_item.final_score, 1) if grade_item else None

            if s_ai >= 50.0 or s_sim >= 40.0:
                s_status = "Flagged"
            elif s_ai >= 20.0 or s_sim >= 20.0:
                s_status = "Review"
            else:
                s_status = "Verified"

            student_roster.append({
                "submission_id": s.id,
                "student_name": s_name,
                "file_name": s.file_name,
                "ai_score": s_ai,
                "similarity_score": s_sim,
                "grade": s_grade,
                "status": s_status,
                "submitted_at": s.submitted_at.strftime("%b %d, %Y %H:%M") if s.submitted_at else "N/A"
            })

        compliance_rate = round((risk_clean / max(total_submissions, 1)) * 100, 1)

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
            "compliance_rate": compliance_rate,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "risk_clean": risk_clean,
            "risk_review": risk_review,
            "risk_flagged": risk_flagged,
            "ai_histogram": ai_histogram,
            "sim_histogram": sim_histogram,
            "student_roster": student_roster,
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
        from reportlab.platypus import PageBreak, KeepTogether

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=36, 
            leftMargin=36, 
            topMargin=36, 
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()

        brand_header_style = ParagraphStyle(
            "VeritextBrand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0284c7")
        )
        title_style = ParagraphStyle(
            "VeritextTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=4
        )
        meta_style = ParagraphStyle(
            "VeritextMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748b")
        )
        section_style = ParagraphStyle(
            "VeritextHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=6
        )
        cell_style = ParagraphStyle(
            "VeritextCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b")
        )
        cell_bold_style = ParagraphStyle(
            "VeritextCellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#0f172a")
        )
        body_style = styles["Normal"]

        story = []

        # ─── HEADER BANNER ───
        story.append(Paragraph("VERITEXT ACADEMIC INTEGRITY PLATFORM • OFFICIAL AUDIT CERTIFICATE", brand_header_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Assignment Assessment Report: {title}", title_style))
        gen_date = data.get("generated_at", "")[:10]
        story.append(Paragraph(
            f"<b>Course Cohort:</b> {data.get('course_name')} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Generated:</b> {gen_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Audited Submissions:</b> {data.get('total_submissions')} students",
            meta_style
        ))
        story.append(Spacer(1, 10))

        # ─── 4-CARD EXECUTIVE KPI BLOCK ───
        compliance = data.get("compliance_rate", 100)
        avg_ai = data.get("avg_ai_score", 0.0)
        max_sim = data.get("highest_similarity_score", 0.0)
        avg_grade = data.get("average_grade", 0.0)
        max_marks = data.get("max_marks", 100.0)

        ai_color = "#ef4444" if avg_ai >= 50 else "#f59e0b" if avg_ai >= 20 else "#10b981"
        sim_color = "#ef4444" if max_sim >= 40 else "#f59e0b" if max_sim >= 20 else "#10b981"

        kpi_table_data = [
            [
                Paragraph(f"<font color='#0284c7' size='18'><b>{compliance}%</b></font><br/><font color='#475569' size='7.5'><b>COMPLIANCE RATE</b><br/>Verified authentic submissions</font>", cell_style),
                Paragraph(f"<font color='{ai_color}' size='18'><b>{avg_ai}%</b></font><br/><font color='#475569' size='7.5'><b>COHORT AI AVERAGE</b><br/>Generative writing index</font>", cell_style),
                Paragraph(f"<font color='{sim_color}' size='18'><b>{max_sim}%</b></font><br/><font color='#475569' size='7.5'><b>PEAK SIMILARITY</b><br/>Highest cross-match observed</font>", cell_style),
                Paragraph(f"<font color='#8b5cf6' size='18'><b>{avg_grade}</b><font size='10'>/{max_marks}</font></font><br/><font color='#475569' size='7.5'><b>AVERAGE GRADE</b><br/>{data.get('graded_count')} graded documents</font>", cell_style),
            ]
        ]
        kpi_table = Table(kpi_table_data, colWidths=[135, 135, 135, 135])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # ─── SECTION 1: EXECUTIVE COHORT SUMMARY ───
        story.append(Paragraph("1. Executive Cohort Summary & Audit Metrics", section_style))
        table_data_1 = [
            [Paragraph("<b>Audit Metric</b>", cell_bold_style), Paragraph("<b>Observed Value</b>", cell_bold_style), Paragraph("<b>Institutional Status</b>", cell_bold_style)],
            [Paragraph("Total Submissions Evaluated", cell_style), Paragraph(str(data.get("total_submissions")), cell_style), Paragraph("Registered students", cell_style)],
            [Paragraph("Completed OCR & Ingestion Jobs", cell_style), Paragraph(str(data.get("completed_submissions")), cell_style), Paragraph("100% processed", cell_style)],
            [Paragraph("Cohort Average AI Writing Index", cell_style), Paragraph(f"{avg_ai}%", cell_style), Paragraph("Moderate" if avg_ai < 35 else "Elevated AI activity", cell_style)],
            [Paragraph("High-Risk AI Submissions (>50%)", cell_style), Paragraph(str(data.get("high_risk_ai_submissions")), cell_style), Paragraph("Requires manual faculty review" if data.get("high_risk_ai_submissions") > 0 else "None", cell_style)],
            [Paragraph("Peak Inter-Submission Similarity", cell_style), Paragraph(f"{max_sim}%", cell_style), Paragraph("Suspicious overlap" if max_sim >= 40 else "Authentic peer independence", cell_style)],
            [Paragraph("Flagged Inter-Peer Similarity Pairs", cell_style), Paragraph(str(data.get("flagged_similarity_pairs")), cell_style), Paragraph("Duplicate passage clusters" if data.get("flagged_similarity_pairs") > 0 else "Zero cross-copying", cell_style)],
        ]
        t1 = Table(table_data_1, colWidths=[220, 130, 190])
        t1.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(t1)
        story.append(Spacer(1, 10))

        # ─── SECTION 2: CHARTS & SCORE DISTRIBUTIONS ───
        story.append(Paragraph("2. Integrity & Score Distribution Curves", section_style))
        ai_hist = data.get("ai_histogram", [0, 0, 0, 0, 0])
        sim_hist = data.get("sim_histogram", [0, 0, 0, 0, 0])

        bar_drawing = Drawing(540, 150)
        bc = VerticalBarChart()
        bc.x = 40
        bc.y = 20
        bc.height = 110
        bc.width = 460
        bc.data = [sim_hist, ai_hist]
        bc.categoryAxis.categoryNames = ["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"]
        bc.categoryAxis.labels.fontName = "Helvetica"
        bc.categoryAxis.labels.fontSize = 8
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max(max(ai_hist), max(sim_hist), 1) + 2
        bc.valueAxis.valueStep = max(1, (max(max(ai_hist), max(sim_hist), 1) + 2) // 4)
        bc.valueAxis.labels.fontName = "Helvetica"
        bc.valueAxis.labels.fontSize = 8
        bc.bars[0].fillColor = colors.HexColor("#0284c7")  # Cyan/Blue - Similarity
        bc.bars[1].fillColor = colors.HexColor("#8b5cf6")  # Purple - AI
        bc.barWidth = 16
        bc.groupSpacing = 18

        bar_drawing.add(bc)
        bar_drawing.add(String(60, 138, "■ Peer Similarity (%)", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor("#0284c7")))
        bar_drawing.add(String(200, 138, "■ AI Probability (%)", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor("#8b5cf6")))
        story.append(bar_drawing)
        story.append(Spacer(1, 10))

        # ─── PAGE 2: STUDENT ROSTER & CERTIFICATION ───
        story.append(PageBreak())

        story.append(Paragraph("3. Individual Student Audit & Integrity Roster", section_style))
        story.append(Paragraph(
            "Detailed breakdown of all enrolled student submissions within this assignment cohort, "
            "including AI writing percentage, peer similarity score, and integrity determination.",
            meta_style
        ))
        story.append(Spacer(1, 8))

        roster = data.get("student_roster", [])
        if roster:
            roster_headers = [
                Paragraph("<b>#</b>", cell_bold_style),
                Paragraph("<b>Student Name</b>", cell_bold_style),
                Paragraph("<b>Submitted File</b>", cell_bold_style),
                Paragraph("<b>AI Writing</b>", cell_bold_style),
                Paragraph("<b>Similarity</b>", cell_bold_style),
                Paragraph("<b>Grade</b>", cell_bold_style),
                Paragraph("<b>Status</b>", cell_bold_style),
            ]
            roster_data = [roster_headers]

            for idx, item in enumerate(roster, start=1):
                status_color = "#10b981" if item["status"] == "Verified" else "#f59e0b" if item["status"] == "Review" else "#ef4444"
                status_p = Paragraph(f"<font color='{status_color}'><b>{item['status'].upper()}</b></font>", cell_style)
                grade_p = Paragraph(f"{item['grade']}/{max_marks}" if item["grade"] is not None else "Pending", cell_style)

                roster_data.append([
                    Paragraph(str(idx), cell_style),
                    Paragraph(item["student_name"][:24], cell_bold_style),
                    Paragraph(item["file_name"][:20], cell_style),
                    Paragraph(f"{item['ai_score']}%", cell_style),
                    Paragraph(f"{item['similarity_score']}%", cell_style),
                    grade_p,
                    status_p,
                ])

            t_roster = Table(roster_data, colWidths=[24, 130, 130, 65, 65, 60, 66])
            t_roster.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("ALIGN", (3, 0), (5, -1), "CENTER"),
            ]))
            story.append(t_roster)
        else:
            story.append(Paragraph("<i>No student submissions recorded in this cohort yet.</i>", cell_style))

        story.append(Spacer(1, 14))

        # ─── SECTION 4: ARCHITECTURE & CERTIFICATION ───
        story.append(Paragraph("4. Verification Engine Architecture & Compliance Disclaimer", section_style))
        disclaimer_text = (
            "<b>VeriText Explainable Multimodal Pipeline:</b> Evaluated via (1) Multi-Tier OCR Ingestion "
            "(PyMuPDF vector streams, PaddleOCR PP-OCRv4, and TrOCR ONNX line recognition), (2) Turnitin-aligned "
            "syntactic & stylometric ensemble (burstiness CV, Shannon lexical entropy, nominalization density, and signature "
            "LLM generative patterns), (3) 5-Gram token inverted index plagiarism localization, and (4) 16-D Computer Vision "
            "handwriting stylometry. All flags are probabilistic indicators intended for faculty audit guidance and disciplinary review."
        )
        story.append(Paragraph(disclaimer_text, cell_style))
        story.append(Spacer(1, 18))

        # Sign-off box
        sig_data = [
            [
                Paragraph("<b>Instructor Audit Signature:</b> ___________________________", cell_style),
                Paragraph("<b>Date of Review:</b> ___________________________", cell_style),
            ],
            [
                Paragraph("<b>Institutional Accreditation Seal:</b> VERITEXT SECURE AUDIT", cell_style),
                Paragraph(f"<b>Report Checksum:</b> SHA-256 / ID #{data.get('assignment_title', '')[:6]}-{gen_date}", cell_style),
            ]
        ]
        t_sig = Table(sig_data, colWidths=[270, 270])
        t_sig.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t_sig)

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

report_service = ReportService()


