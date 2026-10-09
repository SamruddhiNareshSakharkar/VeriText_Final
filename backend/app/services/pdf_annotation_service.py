import io
import re
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import pymupdf  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Circle, String, Rect

from backend.app.models.entities import Submission, AIAnalysis, OCRResult, SimilarityResult
from backend.app.storage.local_storage import storage_service

logger = logging.getLogger(__name__)

class PDFAnnotationService:
    """
    Generates Turnitin-style annotated PDF reports with highlighted AI-generated
    and plagiarized content directly on the submitted document pages.
    """

    # Turnitin Standard Annotation Colors (RGB normalized 0.0 - 1.0)
    COLOR_AI = (0.22, 0.74, 0.97)          # Cyan / Blue (#38bdf8)
    COLOR_SIMILARITY = (0.98, 0.45, 0.09)  # Orange (#f97316)
    COLOR_DUAL = (0.65, 0.35, 0.95)        # Purple for overlapping

    def create_cover_page(
        self,
        submission: Submission,
        ai_score: float,
        sim_score: float,
        hw_score: Optional[float],
        word_count: int,
        page_count: int
    ) -> bytes:
        """Creates a Turnitin-style Cover Page as a 1-page PDF in bytes."""
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
        title_style = ParagraphStyle(
            "VeriTextTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a")
        )
        subtitle_style = ParagraphStyle(
            "VeriTextSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#64748b")
        )
        section_style = ParagraphStyle(
            "VeriTextSection",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=10,
            spaceAfter=6
        )
        label_style = ParagraphStyle(
            "VeriTextLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569")
        )
        value_style = ParagraphStyle(
            "VeriTextValue",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0f172a")
        )

        elements = []

        # Top Header Bar
        elements.append(Paragraph("VERITEXT INTEGRITY REPORT", title_style))
        elements.append(Paragraph("Turnitin-Aligned AI Writing Assessment & Plagiarism Localization", subtitle_style))
        elements.append(Spacer(1, 15))

        # Overview Score Cards
        ai_color = "#ef4444" if ai_score >= 50 else "#f59e0b" if ai_score >= 20 else "#10b981"
        sim_color = "#ef4444" if sim_score >= 40 else "#f59e0b" if sim_score >= 20 else "#10b981"
        ai_class = "Likely AI-Generated" if ai_score >= 65 else "Possibly AI-Assisted" if ai_score >= 20 else "Likely Human-Written"

        score_table_data = [
            [
                Paragraph(f"<font color='{ai_color}' size='26'><b>{ai_score:.1f}%</b></font><br/><font color='#334155' size='9'><b>AI WRITING DETECTED</b><br/>{ai_class}</font>", value_style),
                Paragraph(f"<font color='{sim_color}' size='26'><b>{sim_score:.1f}%</b></font><br/><font color='#334155' size='9'><b>SIMILARITY INDEX</b><br/>Peer & Source Matching</font>", value_style),
                Paragraph(f"<font color='#0284c7' size='26'><b>{hw_score if hw_score is not None else 0:.1f}%</b></font><br/><font color='#334155' size='9'><b>HANDWRITING MATCH</b><br/>Author Verification</font>", value_style),
            ]
        ]
        score_table = Table(score_table_data, colWidths=[180, 180, 180])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(score_table)
        elements.append(Spacer(1, 15))

        # Submission Details Section
        elements.append(Paragraph("DOCUMENT & SUBMISSION DETAILS", section_style))
        student_name = submission.student.full_name if submission.student else "Student"
        student_email = submission.student.email if submission.student else "N/A"
        assign_title = submission.assignment.title if submission.assignment else "Assignment"
        sub_date = submission.submitted_at.strftime("%b %d, %Y, %I:%M %p") if submission.submitted_at else "Recent"

        details_data = [
            [Paragraph("Document Title", label_style), Paragraph(submission.file_name or "Untitled", value_style),
             Paragraph("Submission ID", label_style), Paragraph(str(submission.id)[:18], value_style)],
            [Paragraph("Student Name", label_style), Paragraph(student_name, value_style),
             Paragraph("Total Pages", label_style), Paragraph(str(page_count), value_style)],
            [Paragraph("Assignment", label_style), Paragraph(assign_title, value_style),
             Paragraph("Total Word Count", label_style), Paragraph(f"{word_count:,} words", value_style)],
            [Paragraph("Submission Date", label_style), Paragraph(sub_date, value_style),
             Paragraph("Student Email", label_style), Paragraph(student_email, value_style)],
        ]
        details_table = Table(details_data, colWidths=[110, 160, 110, 160])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 15))

        # Highlighting Legend
        elements.append(Paragraph("REPORT HIGHLIGHTING LEGEND", section_style))
        legend_data = [
            [
                Paragraph("<font color='#0284c7'><b>■ CYAN HIGHLIGHT</b></font>", label_style),
                Paragraph("Likely AI-generated or AI-assisted sentences. Exactly matches the reported AI %.", value_style)
            ],
            [
                Paragraph("<font color='#ea580c'><b>■ ORANGE HIGHLIGHT</b></font>", label_style),
                Paragraph("Plagiarized or verbatim text matching peer submissions or reference sources.", value_style)
            ],
            [
                Paragraph("<font color='#6b21a8'><b>■ PURPLE HIGHLIGHT</b></font>", label_style),
                Paragraph("Compound overlap containing both AI generative phrasing and peer match.", value_style)
            ]
        ]
        legend_table = Table(legend_data, colWidths=[150, 390])
        legend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(legend_table)
        elements.append(Spacer(1, 15))

        # Advisory Disclaimer
        disclaimer_text = (
            "<b>Disclaimer:</b> VeriText AI Writing & Plagiarism Assessment is designed to assist educators in evaluating "
            "academic originality. The highlighted passages indicate text characteristics consistent with large language models "
            "and external sources. Results should be reviewed in conjunction with institutional academic integrity policies."
        )
        elements.append(Paragraph(disclaimer_text, subtitle_style))

        doc.build(elements)
        return buffer.getvalue()

    def generate_annotated_pdf(self, submission_id: str, db: Session) -> Optional[bytes]:
        """
        Generates the complete annotated PDF for a submission:
        - Turnitin Cover Page (Page 1)
        - Original Document Pages with 1:1 cyan/orange highlight annotations.
        """
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            return None

        abs_path = storage_service.get_absolute_path(submission.file_path)
        if not abs_path.exists():
            return None

        ai = db.query(AIAnalysis).filter(AIAnalysis.submission_id == submission_id).first()
        ocr = db.query(OCRResult).filter(OCRResult.submission_id == submission_id).first()
        
        # Cross similarity
        sims = db.query(SimilarityResult).filter(
            SimilarityResult.assignment_id == submission.assignment_id,
            ((SimilarityResult.submission_a_id == submission_id) | (SimilarityResult.submission_b_id == submission_id))
        ).all()
        top_sim = max(sims, key=lambda s: s.score, default=None)
        sim_score = top_sim.score if top_sim else 0.0
        hw_score = top_sim.handwriting_score if top_sim else None

        ai_score = ai.score if ai else 0.0
        ai_spans = ai.detected_spans_json if ai else []
        sim_segments = top_sim.matching_segments_json if (top_sim and top_sim.matching_segments_json) else []

        doc_pdf = None
        suffix = abs_path.suffix.lower()

        try:
            if suffix == ".pdf":
                doc_pdf = pymupdf.open(str(abs_path))
            elif suffix in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
                # Convert image to 1-page PDF
                doc_pdf = pymupdf.open()
                img_doc = pymupdf.open(str(abs_path))
                pdf_bytes = img_doc.convert_to_pdf()
                img_pdf = pymupdf.open("pdf", pdf_bytes)
                doc_pdf.insert_pdf(img_pdf)
                img_doc.close()
                img_pdf.close()
            else:
                # Text or other format -> Create simple PDF
                text = ocr.extracted_text if ocr else ""
                doc_pdf = pymupdf.open()
                page = doc_pdf.new_page(width=612, height=792)
                page.insert_text((40, 50), text[:3000], fontsize=10)

            total_pages = len(doc_pdf)
            word_count = ocr.word_count if ocr else len((ocr.extracted_text or "").split())

            # -------------------------------------------------------------
            # STEP 1: EMBED HIGHLIGHT ANNOTATIONS ACROSS DOCUMENT PAGES
            # -------------------------------------------------------------
            # Pre-extract page texts for fast O(1) matching
            page_text_cache = []
            for p in doc_pdf:
                page_text_cache.append((p, (p.get_text("text") or "").lower()))

            # Highlight AI-generated spans (Cyan #38bdf8)
            for span in ai_spans:
                s_text = span.get("text", "").strip()
                if not s_text or len(s_text) < 10:
                    continue

                words = [w for w in s_text.split() if w]
                chunks = []
                chunk_size = 5
                for i in range(0, len(words), max(1, chunk_size - 1)):
                    chunk = " ".join(words[i:i + chunk_size])
                    if len(chunk) >= 12:
                        chunks.append(chunk)

                for chunk in chunks:
                    chunk_lower = chunk.lower()
                    probe = chunk_lower[:12]
                    for page, p_text in page_text_cache:
                        if probe in p_text or chunk_lower in p_text:
                            rects = page.search_for(chunk)
                            for r in rects:
                                annot = page.add_highlight_annot(r)
                                annot.set_colors(stroke=self.COLOR_AI)
                                annot.set_info(
                                    title="AI Content",
                                    content=f"Turnitin AI Match ({span.get('confidence', 0.85)*100:.0f}% confidence): {span.get('reason', 'Generative syntax')}"
                                )
                                annot.update()

            # Highlight Similarity / Plagiarism segments (Orange #f97316)
            for seg in sim_segments:
                seg_text = seg.get("text", "").strip()
                if not seg_text or len(seg_text) < 10:
                    continue

                words = [w for w in seg_text.split() if w]
                chunks = []
                chunk_size = 5
                for i in range(0, len(words), max(1, chunk_size - 1)):
                    chunk = " ".join(words[i:i + chunk_size])
                    if len(chunk) >= 12:
                        chunks.append(chunk)

                for chunk in chunks:
                    chunk_lower = chunk.lower()
                    probe = chunk_lower[:12]
                    for page, p_text in page_text_cache:
                        if probe in p_text or chunk_lower in p_text:
                            rects = page.search_for(chunk)
                            for r in rects:
                                annot = page.add_highlight_annot(r)
                                annot.set_colors(stroke=self.COLOR_SIMILARITY)
                                annot.set_info(
                                    title="Plagiarism Match",
                                    content=f"Identical text passage with peer source ({len(seg_text)} characters)."
                                )
                                annot.update()

            # Handle Scanned / Handwritten line boxes from OCRResult.pages_json
            if ocr and ocr.pages_json:
                for page_info in ocr.pages_json:
                    p_num = page_info.get("page_number", 1) - 1
                    if 0 <= p_num < len(doc_pdf):
                        page = doc_pdf[p_num]
                        lines = page_info.get("lines", [])
                        for l in lines:
                            l_text = l.get("authoritative_text") or l.get("text") or ""
                            l_box = l.get("line_bbox")
                            if not l_box or len(l_box) != 4 or not l_text:
                                continue
                            
                            # Check if line text overlaps with AI spans
                            is_line_ai = any(s.get("text", "") in l_text or l_text in s.get("text", "") for s in ai_spans if len(s.get("text", "")) > 15)
                            is_line_sim = any(s.get("text", "") in l_text or l_text in s.get("text", "") for s in sim_segments if len(s.get("text", "")) > 15)

                            if is_line_ai or is_line_sim:
                                rect = pymupdf.Rect(l_box[0], l_box[1], l_box[2], l_box[3])
                                annot = page.add_rect_annot(rect)
                                if is_line_ai and is_line_sim:
                                    annot.set_colors(stroke=self.COLOR_DUAL, fill=self.COLOR_DUAL)
                                elif is_line_ai:
                                    annot.set_colors(stroke=self.COLOR_AI, fill=self.COLOR_AI)
                                else:
                                    annot.set_colors(stroke=self.COLOR_SIMILARITY, fill=self.COLOR_SIMILARITY)
                                annot.set_opacity(0.35)
                                annot.update()

            # -------------------------------------------------------------
            # STEP 2: BUILD TURNITIN-STYLE COVER PAGE & COMBINE
            # -------------------------------------------------------------
            cover_bytes = self.create_cover_page(
                submission=submission,
                ai_score=ai_score,
                sim_score=sim_score,
                hw_score=hw_score,
                word_count=word_count,
                page_count=total_pages
            )

            cover_pdf = pymupdf.open("pdf", cover_bytes)
            final_pdf = pymupdf.open()
            
            # Page 1: Cover Page
            final_pdf.insert_pdf(cover_pdf)
            # Pages 2+: Document with embedded highlights
            final_pdf.insert_pdf(doc_pdf)

            output_bytes = final_pdf.tobytes()

            cover_pdf.close()
            doc_pdf.close()
            final_pdf.close()

            return output_bytes

        except Exception as e:
            logger.error(f"Failed to generate annotated PDF for {submission_id}: {e}", exc_info=True)
            if doc_pdf:
                doc_pdf.close()
            return None

pdf_annotation_service = PDFAnnotationService()
