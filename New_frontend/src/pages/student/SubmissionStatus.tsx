import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import ProcessingTracker from "../../components/ProcessingTracker";
import ScoreRing from "../../components/ScoreRing";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

type StepStatus = "pending" | "processing" | "complete" | "error" | "skipped";

interface Step { id: string; label: string; status: StepStatus; detail?: string }

export default function SubmissionStatus() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [grade, setGrade] = useState<any>(null);
  const [assignment, setAssignment] = useState<any>(null);

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      let subData: any = null;
      let analysisData: any = null;

      // 1. Check if id is a submission ID directly
      try {
        analysisData = await api.submissions.getAnalysis(id!);
        subData = analysisData?.submission;
      } catch {
        // Not a submission ID or direct lookup failed — maybe it's an assignment ID
      }

      // 2. If subData not resolved yet, check student's submissions
      if (!subData) {
        const mySubs = await api.submissions.mySubmissions().catch(() => []);
        // Match either submission.id == id or submission.assignment_id == id
        subData = mySubs.find((s: any) => s.id === id || s.assignment_id === id);

        if (subData) {
          try {
            analysisData = await api.submissions.getAnalysis(subData.id);
          } catch {
            // Analysis might still be in queue
          }
        }
      }

      // 3. If no submission found, try loading the assignment info to offer submission
      if (!subData) {
        try {
          const assignData = await api.assignments.get(id!);
          setAssignment(assignData);
        } catch {
          // Both lookups failed
        }
      }

      if (subData) {
        setSubmission(subData);
        setAnalysis(analysisData);
        // Try fetching grade if available
        try {
          const g = await api.grading.getGrade(subData.id);
          setGrade(g);
        } catch {
          // Grade not available yet
        }
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load submission information.");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size={28} color="var(--color-accent)" />
        <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading submission status…</span>
      </div>
    );
  }

  // If no submission exists for this assignment yet
  if (!submission && assignment) {
    return (
      <div>
        <PageHeader
          title={`Submission Status: ${assignment.title}`}
          breadcrumbs={[{ label: "Assignments", href: "/student/assignments" }, { label: "Status" }]}
          subtitle="You have not submitted work for this assignment yet."
        />
        <div className="max-w-md p-6 rounded-xl text-center mx-auto mt-8"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <p className="font-semibold text-base mb-2" style={{ color: "var(--color-text-1)" }}>
            No Submission Found
          </p>
          <p className="text-sm mb-6" style={{ color: "var(--color-text-3)" }}>
            You haven't uploaded your document for "{assignment.title}". Submit your work to initiate academic integrity and handwriting analysis.
          </p>
          <Btn variant="primary" size="md" onClick={() => navigate(`/student/submit/${assignment.id}`)}>
            Submit Work Now →
          </Btn>
        </div>
      </div>
    );
  }

  if (error && !submission) {
    return (
      <div className="p-6 rounded-xl max-w-lg mx-auto text-center mt-10"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
        <p className="font-semibold text-red-500 mb-2">Could Not Find Submission</p>
        <p className="text-sm text-slate-400 mb-4">{error}</p>
        <Btn variant="primary" size="sm" onClick={() => navigate("/student/assignments")}>
          Back to Assignments
        </Btn>
      </div>
    );
  }

  if (!submission && !assignment) {
    return (
      <div className="p-6 rounded-xl max-w-lg mx-auto text-center mt-10"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
        <p className="font-semibold text-red-500 mb-2">No Submission Found</p>
        <p className="text-sm text-slate-400 mb-4">
          {error || "Could not find a submission or active assignment for this ID."}
        </p>
        <Btn variant="primary" size="sm" onClick={() => navigate("/student/assignments")}>
          Back to Assignments
        </Btn>
      </div>
    );
  }

  const sub = submission || {};
  const ocr = analysis?.ocr_result;
  const ai = analysis?.ai_analysis;
  const hw = analysis?.handwriting_analysis;
  const simScore = analysis?.max_similarity_score ?? sub.max_similarity ?? null;

  const normPct = (raw: unknown): number | null => {
    if (raw == null) return null;
    const n = Number(raw);
    if (!Number.isFinite(n) || n < 0) return 0;
    return Math.min(100, Math.max(0, n));
  };

  const aiScoreVal = ai ? normPct(ai.score) : sub.ai_score != null ? normPct(sub.ai_score) : null;
  const simScoreVal = simScore != null ? normPct(simScore) : null;
  const hwConfidenceVal = hw && hw.confidence > 0 ? (hw.confidence <= 1.0 ? hw.confidence * 100 : normPct(hw.confidence)) : null;

  const isCompleted = sub.status === "completed" || Boolean(analysis);
  // #region agent log
  fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId:'B',location:'SubmissionStatus.tsx:render',message:'student status render',data:{hasSubmission:Boolean(submission),hasAnalysis:Boolean(analysis),hasGrade:Boolean(grade),status:sub.status||null,aiScoreType:typeof aiScoreVal,aiScoreVal,simScoreVal,hwConfidenceVal,fileSizeType:typeof sub.file_size},timestamp:Date.now()})}).catch(()=>{});
  // #endregion

  const steps: Step[] = [
    {
      id: "ocr",
      label: "OCR Text Extraction",
      status: ocr ? "complete" : isCompleted ? "complete" : "processing",
      detail: ocr?.word_count ? `${ocr.word_count} words extracted` : "Text structure processed",
    },
    {
      id: "ai",
      label: "AI Content Analysis",
      status: ai ? "complete" : isCompleted ? "complete" : "processing",
      detail: aiScoreVal != null ? `AI Probability: ${Math.round(aiScoreVal)}%` : "Scanning stylometric entropy",
    },
    {
      id: "similarity",
      label: "Similarity Check",
      status: simScoreVal != null ? "complete" : isCompleted ? "complete" : "pending",
      detail: simScoreVal != null ? `Cross-match: ${Math.round(simScoreVal)}%` : "Comparing peer submissions",
    },
    {
      id: "handwriting",
      label: "Handwriting Analysis",
      status: hw && hw.confidence > 0 ? "complete" : "skipped",
      detail: hw && hw.confidence > 0
        ? `Slant: ${hw.slant_angle}° • Variance: ${hw.stroke_variance}`
        : "Not applicable — digital document format",
    },
    {
      id: "grading",
      label: "Evaluation & Grade",
      status: grade ? "complete" : "pending",
      detail: grade ? `Grade: ${grade.final_score}/${grade.max_marks}` : "Awaiting instructor review",
    },
  ];

  const allDone = steps.every((s) => s.status === "complete" || s.status === "skipped");

  return (
    <div>
      <PageHeader
        title={`Submission: ${sub.file_name || "Document"}`}
        breadcrumbs={[
          { label: "Assignments", href: "/student/assignments" },
          { label: sub.assignment_title || "Status" },
        ]}
        subtitle="Processing pipeline and integrity analysis status for your submission."
        actions={
          <div className="flex items-center gap-2">
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => window.open(api.submissions.annotatedPdfUrl(sub.id), "_blank")}
              style={{ background: "rgba(14, 165, 233, 0.12)", color: "#38bdf8", borderColor: "rgba(14, 165, 233, 0.35)" }}
            >
              📑 Highlighted PDF Report
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => window.open(api.submissions.downloadFileUrl(sub.id), "_blank")}
            >
              Raw File
            </Btn>
            <Btn
              variant="primary"
              size="sm"
              onClick={() => navigate("/student/results")}
            >
              My Results →
            </Btn>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 max-w-4xl">
        {/* Left — pipeline */}
        <div className="lg:col-span-2">
          <div className="rounded-xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            {/* File info */}
            <div className="flex items-center gap-3 mb-6 pb-5" style={{ borderBottom: "1px solid var(--color-border)" }}>
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <rect x="3" y="2" width="12" height="14" rx="1.5" stroke="var(--color-text-3)" strokeWidth="1.4" />
                  <path d="M6 7h6M6 10h4" stroke="var(--color-text-3)" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="font-medium truncate" style={{ fontSize: 14, color: "var(--color-text-1)" }}>
                  {sub.file_name || "Document"}
                </p>
                <p style={{ fontSize: 12, color: "var(--color-text-4)" }}>
                  {sub.file_size ? `${(sub.file_size / 1024).toFixed(1)} KB • ` : ""}
                  Submitted {sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : "Recently"}
                </p>
              </div>
              <div className="ml-auto">
                <StatusBadge status={sub.status || (allDone ? "complete" : "processing")} />
              </div>
            </div>

            <ProcessingTracker steps={steps} />

            {allDone && (
              <div className="mt-5 pt-5" style={{ borderTop: "1px solid var(--color-border)" }}>
                <div className="rounded-lg p-3 mb-4" style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}>
                  <p className="font-semibold" style={{ fontSize: 13, color: "var(--color-green)" }}>Processing complete</p>
                  <p style={{ fontSize: 12, color: "var(--color-green)", opacity: 0.85, marginTop: 2 }}>
                    Your submission has been analysed for optical character structure, AI content, and cross-peer integrity.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Btn variant="primary" size="sm" onClick={() => navigate("/student/results")}>
                    View full results →
                  </Btn>
                  <Btn variant="secondary" size="sm" onClick={() => navigate("/student/assignments")}>
                    Back to assignments
                  </Btn>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right — scores */}
        <div className="space-y-4">
          <div className="rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <p className="font-semibold mb-4" style={{ fontSize: 13, color: "var(--color-text-1)" }}>Analysis Scores</p>
            <div className="flex flex-col gap-5">
              <ScoreRing value={aiScoreVal != null ? Math.round(aiScoreVal) : null} label="AI Content" size={64} />
              <ScoreRing value={simScoreVal != null ? Math.round(simScoreVal) : null} label="Similarity" size={64} />
              <ScoreRing value={hwConfidenceVal != null ? Math.round(hwConfidenceVal) : null} label="Handwriting" size={64} />
            </div>
            {grade && (
              <div className="mt-5 pt-4 text-center border-t border-slate-700/50">
                <span className="text-xs uppercase tracking-wider text-slate-400 block mb-1">Final Grade</span>
                <span className="font-mono text-2xl font-bold text-emerald-400">
                  {grade.final_score} / {grade.max_marks}
                </span>
              </div>
            )}
            <p style={{ fontSize: 11, color: "var(--color-text-4)", marginTop: 14, lineHeight: 1.5 }}>
              Scores populate automatically from the optical and stylometric engines.
            </p>
          </div>

          <div className="rounded-xl p-4" style={{ background: "var(--color-amber-bg)", border: "1px solid var(--color-amber-border)" }}>
            <p className="font-semibold mb-1" style={{ fontSize: 12.5, color: "var(--color-amber)" }}>Score Interpretation</p>
            <div className="space-y-1" style={{ fontSize: 12, color: "var(--color-amber)", opacity: 0.85 }}>
              <p>🟢 Below 40% — low concern</p>
              <p>🟡 40–70% — moderate review</p>
              <p>🔴 Above 70% — flagged for review</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
