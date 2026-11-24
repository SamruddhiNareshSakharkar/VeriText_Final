import io
import re
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
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

    @staticmethod
    def _line_matches_spans(line_text: str, spans: List[Dict[str, Any]], min_overlap_words: int = 3) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Determines if a handwritten OCR line text matches or overlaps with flagged AI/plagiarism spans.
        Uses substring check, 3-gram token matching, and proportional word overlap for robust matching.
        """
        if not line_text or len(line_text.strip()) < 4 or not spans:
            return False, None

        line_clean = re.sub(r'[^\w\s]', ' ', line_text.lower()).strip()
        line_words = [w for w in line_clean.split() if len(w) >= 2]
        if not line_words:
            return False, None

        for span in spans:
            s_text = span.get("text", "")
            if not s_text or len(s_text.strip()) < 8:
                continue
            s_clean = re.sub(r'[^\w\s]', ' ', s_text.lower()).strip()

            # 1. Direct substring inclusion
            if line_clean in s_clean or s_clean in line_clean:
                return True, span

            s_words = [w for w in s_clean.split() if len(w) >= 2]
            if len(line_words) >= min_overlap_words and len(s_words) >= min_overlap_words:
                # 2. Consecutive word n-gram matching
                line_ngrams = {" ".join(line_words[i:i + min_overlap_words]) for i in range(len(line_words) - min_overlap_words + 1)}
                span_ngrams = {" ".join(s_words[i:i + min_overlap_words]) for i in range(len(s_words) - min_overlap_words + 1)}
                if line_ngrams & span_ngrams:
                    return True, span

                # 3. Proportional word overlap check
                shared = set(line_words) & set(s_words)
                if len(shared) >= 3 and (len(shared) / len(line_words)) >= 0.40:
                    return True, span

        return False, None

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
            word_count = (ocr.word_count if ocr.word_count is not None else len((ocr.extracted_text or "").split())) if ocr else 0

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

            # -------------------------------------------------------------
            # STEP 1B: EMBED HIGHLIGHTS ON HANDWRITTEN & SCANNED PAGES
            # (Matches OCR line bounding boxes & scales to PDF points)
            # -------------------------------------------------------------
            if ocr and ocr.pages_json:
                for page_info in ocr.pages_json:
                    p_num = page_info.get("page_number", 1) - 1
                    if 0 <= p_num < len(doc_pdf):
                        page = doc_pdf[p_num]
                        lines = page_info.get("lines", [])
                        if not lines:
                            continue

                        # Determine coordinate scaling from OCR image space to PDF points
                        pw, ph = page.rect.width, page.rect.height
                        valid_boxes = [l.get("bbox") or l.get("line_bbox") for l in lines if (l.get("bbox") or l.get("line_bbox"))]
                        max_bx = max((b[2] for b in valid_boxes if len(b) == 4), default=pw)
                        max_by = max((b[3] for b in valid_boxes if len(b) == 4), default=ph)

                        scale_x = (pw / max_bx) if max_bx > pw * 1.15 else 1.0
                        scale_y = (ph / max_by) if max_by > ph * 1.15 else 1.0

                        total_page_lines = max(len(lines), 1)

                        for idx, l in enumerate(lines, start=1):
                            l_text = l.get("authoritative_text") or l.get("text") or l.get("raw_text") or ""
                            if not l_text.strip():
                                continue

                            # Check for AI writing or peer similarity matches
                            is_line_ai, ai_match = self._line_matches_spans(l_text, ai_spans)
                            is_line_sim, sim_match = self._line_matches_spans(l_text, sim_segments)

                            if not is_line_ai and not is_line_sim:
                                continue

                            # Resolve line bounding box
                            l_box = l.get("bbox") or l.get("line_bbox")
                            if l_box and len(l_box) == 4:
                                x1 = max(0, min(pw, l_box[0] * scale_x))
                                y1 = max(0, min(ph, l_box[1] * scale_y))
                                x2 = max(0, min(pw, l_box[2] * scale_x))
                                y2 = max(0, min(ph, l_box[3] * scale_y))
                                rect = pymupdf.Rect(x1, y1, x2, y2)
                            else:
                                # Vertical band fallback if explicit bbox not present
                                line_h = ph / total_page_lines
                                y1 = (idx - 1) * line_h
                                y2 = idx * line_h
                                rect = pymupdf.Rect(30, y1, pw - 30, y2)

                            annot = page.add_rect_annot(rect)
                            if is_line_ai and is_line_sim:
                                annot.set_colors(stroke=self.COLOR_DUAL, fill=self.COLOR_DUAL)
                                annot.set_info(
                                    title="AI & Similarity Match",
                                    content=f"Compound overlap (AI syntax & peer match): '{l_text[:70]}...'"
                                )
                            elif is_line_ai:
                                conf_pct = (ai_match.get("confidence", 0.90) * 100) if ai_match else 90
                                annot.set_colors(stroke=self.COLOR_AI, fill=self.COLOR_AI)
                                annot.set_info(
                                    title="AI Writing Detected",
                                    content=f"AI Syntax ({conf_pct:.0f}% confidence): {ai_match.get('reason', 'Generative syntax') if ai_match else 'Generative cadence'}"
                                )
                            else:
                                annot.set_colors(stroke=self.COLOR_SIMILARITY, fill=self.COLOR_SIMILARITY)
                                annot.set_info(
                                    title="Plagiarism Match",
                                    content=f"Peer match in handwriting: '{l_text[:70]}...'"
                                )
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
