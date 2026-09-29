export type UserRole = "student" | "teacher" | "admin";

export type SubmissionStatus =
  | "draft"
  | "submitted"
  | "processing"
  | "ocr_processing"
  | "ai_analysis"
  | "similarity_check"
  | "handwriting_analysis"
  | "grading"
  | "complete"
  | "error"
  | "flagged";

export type AnalysisStatus = "pending" | "processing" | "complete" | "error";

export interface ProcessingStep {
  id: string;
  label: string;
  status: AnalysisStatus;
  detail?: string;
}

export const PROCESSING_STEPS: ProcessingStep[] = [
  { id: "ocr", label: "OCR Extraction", status: "pending" },
  { id: "ai", label: "AI Content Analysis", status: "pending" },
  { id: "similarity", label: "Similarity Check", status: "pending" },
  { id: "handwriting", label: "Handwriting Analysis", status: "pending" },
  { id: "grading", label: "Grading", status: "pending" },
];
