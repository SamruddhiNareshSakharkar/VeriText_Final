import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import ScoreRing from "../../components/ScoreRing";
import ProcessingTracker from "../../components/ProcessingTracker";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { api, apiRequest } from "../../lib/api";

type Tab = "overview" | "document" | "ocr" | "ai" | "similarity" | "handwriting" | "grading";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "document", label: "Document" },
  { id: "ocr", label: "OCR" },
  { id: "ai", label: "AI Analysis" },
  { id: "similarity", label: "Similarity" },
  { id: "handwriting", label: "Handwriting" },
  { id: "grading", label: "Editable Grading" },
];

type StepStatus = "pending" | "processing" | "complete" | "error" | "skipped";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2.5" style={{ borderBottom: "1px solid var(--color-border)" }}>
      <span style={{ fontSize: 12.5, color: "var(--color-text-3)", flexShrink: 0, width: 140 }}>{label}</span>
      <span style={{ fontSize: 12.5, color: "var(--color-text-1)", textAlign: "right" }}>{value}</span>
    </div>
  );
}

function Placeholder({ text }: { text: string }) {
  return (
    <div
      className="rounded-xl py-12 flex items-center justify-center text-center px-6"
      style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)", color: "var(--color-text-4)", fontSize: 13 }}
    >
      {text}
    </div>
  );
}

export default function SubmissionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [activeHL, setActiveHL] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [flagged, setFlagged] = useState(false);

  // Editable Grading State
  const [gradeData, setGradeData] = useState<any>(null);
  const [gradeScore, setGradeScore] = useState<number>(100);
  const [gradeFeedback, setGradeFeedback] = useState<string>("");
  const [gradeReason, setGradeReason] = useState<string>("");
  const [savingGrade, setSavingGrade] = useState(false);
  const [gradeSaveSuccess, setGradeSaveSuccess] = useState(false);

  useEffect(() => {
    if (id) {
      loadAnalysis(id);
      loadGrade(id);
    }
  }, [id]);

  async function loadAnalysis(submissionId: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.submissions.getAnalysis(submissionId);
      setAnalysisData(data);
    } catch (err: any) {
      // #region agent log
      fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId:'D',location:'SubmissionDetail.tsx:loadAnalysis',message:'analysis fetch failed',data:{msg:String(err?.message||err),status:err?.status||null,id:submissionId},timestamp:Date.now()})}).catch(()=>{});
      // #endregion
      setError(err?.message || "Failed to load submission analysis.");
    } finally {
      setLoading(false);
    }
  }

  async function loadGrade(submissionId: string) {
    try {
      const g = await api.grading.getGrade(submissionId);
      if (g) {
        setGradeData(g);
        setGradeScore(g.final_score ?? 100);
        setGradeFeedback(g.feedback || "");
      }
    } catch {
      // Grade might not exist yet
    }
  }

  async function handleSaveGrade(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!id) return;
    setSavingGrade(true);
    setGradeSaveSuccess(false);
    try {
      const updated = await api.grading.submitGrade(id, {
        final_score: Number(gradeScore),
        feedback: gradeFeedback,
        reason: gradeReason || "Instructor grade evaluation",
        criteria_scores: gradeData?.criteria_scores || {},
      });
      setGradeData(updated);
      setGradeSaveSuccess(true);
      setGradeReason("");
      setTimeout(() => setGradeSaveSuccess(false), 3500);
    } catch (err: any) {
      alert(err?.message || "Failed to save grade.");
    } finally {
      setSavingGrade(false);
    }
  }

  async function handleReanalyze() {
    if (!id) return;
    setReanalyzing(true);
    try {
      await apiRequest(`/submissions/${id}/reanalyze`, { method: "POST" });
      setTimeout(() => {
        loadAnalysis(id);
        loadGrade(id);
      }, 1500);
    } catch (err: any) {
      alert(err?.message || "Re-analysis request failed.");
    } finally {
      setReanalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size={28} color="var(--color-accent)" />
        <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading submission integrity profile…</span>
      </div>
    );
  }

  if (error || !analysisData) {
    return (
      <div className="p-6 rounded-xl max-w-lg mx-auto text-center" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
        <p className="font-semibold text-red-500 mb-2">Failed to load submission</p>
        <p className="text-sm text-slate-400 mb-4">{error || "Submission record not found."}</p>
        <Btn variant="primary" size="sm" onClick={() => id && loadAnalysis(id)}>Retry</Btn>
      </div>
    );
  }

  const sub = analysisData.submission || {};
  const ai = analysisData.ai_analysis;
  const ocr = analysisData.ocr_result;
  const hw = analysisData.handwriting_analysis;
  const simScore = analysisData.max_similarity_score ?? null;

  const asPercent = (raw: unknown): number => {
    const n = Number(raw);
    if (!Number.isFinite(n)) return 0;
    return n <= 1 && n > 0 ? n * 100 : n;
  };
  const fmt = (raw: unknown, digits = 1) => asPercent(raw).toFixed(digits);

  const aiScoreVal = ai ? asPercent(ai.score) : 0;
  const simScoreVal = simScore != null ? asPercent(simScore) : 0;
  const hwConfidenceVal = hw ? asPercent(hw.confidence) : 0;

  const docText = ocr?.extracted_text || "No text could be extracted from this document.";
  const detectedSpans: any[] = Array.isArray(ai?.detected_spans) ? ai.detected_spans : [];

  const maxMarks = gradeData?.max_marks || sub.max_marks || 100;
  // #region agent log
  fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId:'B',location:'SubmissionDetail.tsx:render',message:'teacher detail render',data:{hasAi:Boolean(ai),hasOcr:Boolean(ocr),hasHw:Boolean(hw),aiScoreType:typeof (ai&&ai.score),aiScoreVal,simScoreVal,hwConfidenceVal,spanIsArray:Array.isArray(ai?.detected_spans),spanLen:detectedSpans.length,status:sub.status||null},timestamp:Date.now()})}).catch(()=>{});
  // #endregion

  const pipelineSteps = [
    {
      id: "ocr",
      label: "OCR Extraction",
      status: (ocr?.status === "completed" || ocr?.extracted_text ? "complete" : sub.status === "processing" ? "processing" : "complete") as StepStatus,
      detail: ocr?.extracted_text ? `${ocr.word_count || 0} words extracted` : "Digital / Scanned document processed",
    },
    {
      id: "ai",
      label: "AI Content Analysis",
      status: (ai ? "complete" : sub.status === "processing" ? "processing" : "pending") as StepStatus,
      detail: ai ? `AI Probability: ${fmt(aiScoreVal)}% • Perplexity: ${Number(ai.perplexity ?? 0).toFixed(1)}` : "Awaiting scan",
    },
    {
      id: "similarity",
      label: "Similarity Check",
      status: (simScore != null ? "complete" : "pending") as StepStatus,
      detail: simScore != null ? `Peak match: ${fmt(simScoreVal)}%` : "Cross-comparison pending",
    },
    {
      id: "handwriting",
      label: "Handwriting CV",
      status: (hw ? "complete" : "complete") as StepStatus,
      detail: hw ? `Slant: ${hw.slant_angle}° • Variance: ${hw.stroke_variance}` : "Computer vision evaluated",
    },
    {
      id: "grading",
      label: "Auto & Instructor Grading",
      status: (gradeData ? "complete" : "pending") as StepStatus,
      detail: gradeData ? `Score: ${gradeData.final_score}/${maxMarks}` : "Auto-grade generated",
    },
  ];

  // Render text with highlight marks
  function renderHighlightedText(fullText: string, spans: any[]) {
    if (!spans || spans.length === 0) return fullText;

    const sortedSpans = [...spans]
      .filter((s) => s && (s.start !== undefined || s.text))
      .sort((a, b) => (a.start || 0) - (b.start || 0));
    const elements = [];
    let lastIndex = 0;

    sortedSpans.forEach((span, i) => {
      const rawStart = span.start ?? 0;
      const rawEnd = span.end ?? (rawStart + (span.text?.length || 0));
      if (rawEnd <= lastIndex) return;

      const start = Math.max(rawStart, lastIndex);
      const end = Math.min(rawEnd, fullText.length);

      if (start > lastIndex) {
        elements.push(fullText.substring(lastIndex, start));
      }
      const isSelected = activeHL === i;
      const confVal = Math.round((span.confidence ?? 0.85) * (span.confidence <= 1 ? 100 : 1));
      elements.push(
        <mark
          key={i}
          onClick={() => setActiveHL(isSelected ? null : i)}
          className={`cursor-pointer transition-all ${isSelected ? "ring-2 ring-rose-500 font-semibold" : ""}`}
          style={{
            background: "rgba(239, 68, 68, 0.25)",
            color: "#fca5a5",
            padding: "2px 4px",
            borderRadius: "3px",
          }}
          title={`AI Passage: ${confVal}% confidence`}
        >
          {fullText.substring(start, end) || span.text}
        </mark>
      );
      lastIndex = Math.max(lastIndex, end);
    });

    if (lastIndex < fullText.length) {
      elements.push(fullText.substring(lastIndex));
    }

    return elements;
  }

  return (
    <div>
      <PageHeader
        title={`Submission: ${sub.file_name || "Document"}`}
        breadcrumbs={[{ label: "Submissions", href: "/teacher/submissions" }, { label: "Review" }]}
        actions={
          <div className="flex items-center gap-2">
            <Btn
              variant="secondary"
              size="sm"
              loading={reanalyzing}
              onClick={handleReanalyze}
            >
              Re-analyze
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => window.open(`/api/v1/submissions/${id}/file`, "_blank")}
            >
              Download File
            </Btn>
            <Btn
              variant="danger"
              size="sm"
              onClick={() => setFlagged(!flagged)}
              style={flagged ? { background: "var(--color-red-bg)", borderColor: "var(--color-red)", color: "var(--color-red)" } : {}}
            >
              {flagged ? "Flagged ⚑" : "Flag"}
            </Btn>
            <Btn variant="primary" size="sm" onClick={() => setTab("grading")}>
              Grade Submission →
            </Btn>
          </div>
        }
      />

      {/* Flagged Warning Banner */}
      {(sub.handwriting_match_flag || sub.ai_match_flag || aiScoreVal >= 70 || simScoreVal >= 60) && (
        <div
          className="p-4 rounded-xl mb-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3"
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.35)",
          }}
        >
          <div className="flex items-center gap-3">
            <span className="text-xl">⚠️</span>
            <div>
              <p className="font-semibold text-sm text-rose-500">
                Academic Integrity Warning
              </p>
              <p className="text-xs text-slate-300 mt-0.5">
                {sub.handwriting_match_flag && <span>{sub.handwriting_match_flag}. </span>}
                {sub.ai_match_flag && <span>{sub.ai_match_flag}. </span>}
                {aiScoreVal >= 70 && <span>High artificial stylometry ({fmt(aiScoreVal)}%). </span>}
                {simScoreVal >= 60 && <span>High cross-document similarity ({fmt(simScoreVal)}%).</span>}
              </p>
            </div>
          </div>
          <Btn
            variant="outline"
            size="xs"
            onClick={() => navigate("/teacher/compare")}
          >
            Compare in Dual Viewer →
          </Btn>
        </div>
      )}

      {/* Meta strip */}
      <div
        className="rounded-xl px-5 py-4 mb-4 flex flex-wrap items-center gap-5"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
      >
        {[
          { label: "Student", value: sub.student?.full_name || sub.student?.name || "Student" },
          { label: "File name", value: sub.file_name },
          { label: "File size", value: `${((sub.file_size || 0) / 1024).toFixed(1)} KB` },
          { label: "Submitted", value: sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : "—" },
          { label: "Format", value: sub.mime_type || "Document" },
        ].map(({ label, value }) => (
          <div key={label}>
            <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 2 }}>{label}</p>
            <p className="font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{value}</p>
          </div>
        ))}

        <div className="ml-auto flex items-center gap-4">
          <ScoreRing value={ai ? Math.round(aiScoreVal) : null} label="AI" size={52} />
          <ScoreRing value={simScore != null ? Math.round(simScoreVal) : null} label="Similarity" size={52} />
          <ScoreRing value={hw ? Math.round(hwConfidenceVal) : null} label="Handwriting" size={52} />
          <StatusBadge status={flagged ? "flagged" : sub.status || "complete"} />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto" style={{ borderBottom: "2px solid var(--color-border)", marginBottom: -2 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="px-4 py-2.5 font-medium whitespace-nowrap transition-colors"
            style={{
              fontSize: 13.5,
              color: tab === t.id ? "var(--color-accent)" : "var(--color-text-3)",
              background: "none",
              border: "none",
              borderBottom: tab === t.id ? `2px solid var(--color-accent)` : "2px solid transparent",
              cursor: "pointer",
              marginBottom: -2,
              fontFamily: "inherit",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div
        className="rounded-b-xl rounded-tr-xl mt-0 p-5"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderTop: "none" }}
      >
        {tab === "overview" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-5">
              <div>
                <p className="font-semibold uppercase tracking-wider mb-3" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                  Submission Information
                </p>
                <div className="rounded-xl px-4" style={{ border: "1px solid var(--color-border)" }}>
                  <Row label="Student ID" value={sub.student_id || "—"} />
                  <Row label="Student Name" value={sub.student?.full_name || sub.student?.name || "—"} />
                  <Row label="Email" value={sub.student?.email || "—"} />
                  <Row label="File name" value={sub.file_name || "—"} />
                  <Row label="File size" value={`${((sub.file_size || 0) / 1024).toFixed(1)} KB`} />
                  <Row label="Word count" value={ocr?.word_count ? `${ocr.word_count} words` : "—"} />
                  <Row label="Submission time" value={sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : "—"} />
                </div>
              </div>

              <div>
                <p className="font-semibold uppercase tracking-wider mb-3" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                  Integrity & Grading Overview
                </p>
                <div className="rounded-xl px-4" style={{ border: "1px solid var(--color-border)" }}>
                  <Row
                    label="AI Content Probability"
                    value={ai ? <span className="font-mono font-semibold" style={{ color: aiScoreVal > 40 ? "var(--color-red)" : "var(--color-green)" }}>{aiScoreVal.toFixed(1)}%</span> : "—"}
                  />
                  <Row
                    label="Peer Similarity"
                    value={simScore != null ? <span className="font-mono font-semibold" style={{ color: simScoreVal > 40 ? "var(--color-red)" : "var(--color-green)" }}>{simScoreVal.toFixed(1)}%</span> : "—"}
                  />
                  <Row
                    label="Handwriting Stylometry"
                    value={hw ? `${hwConfidenceVal.toFixed(0)}% confidence (${hw.slant_angle}° slant)` : "Not applicable (Digital document)"}
                  />
                  <Row
                    label="Assigned Grade"
                    value={
                      gradeData ? (
                        <span className="font-mono font-semibold text-emerald-400">
                          {gradeData.final_score} / {maxMarks} {gradeData.is_override ? "(Manual Review)" : "(Auto-graded)"}
                        </span>
                      ) : (
                        "Pending review"
                      )
                    }
                  />
                </div>
              </div>
            </div>

            <div>
              <p className="font-semibold uppercase tracking-wider mb-3" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                Processing Pipeline
              </p>
              <ProcessingTracker steps={pipelineSteps} />
            </div>
          </div>
        )}

        {tab === "document" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                  Highlighted passages indicate AI-generated content
                </span>
              </div>
              {activeHL != null && (
                <button
                  onClick={() => setActiveHL(null)}
                  className="text-xs text-indigo-400 hover:underline cursor-pointer"
                >
                  Clear highlighted selection
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div
                className="lg:col-span-2 rounded-xl p-5 overflow-y-auto whitespace-pre-wrap font-serif"
                style={{
                  border: "1px solid var(--color-border)",
                  background: "var(--color-surface-2)",
                  minHeight: 360,
                  maxHeight: 520,
                  fontSize: 14.5,
                  lineHeight: 1.9,
                  color: "var(--color-text-1)",
                }}
              >
                {renderHighlightedText(docText, detectedSpans)}
              </div>

              <div className="space-y-2.5">
                <p className="font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Detected Regions ({detectedSpans.length})
                </p>
                {detectedSpans.length === 0 ? (
                  <div className="p-4 rounded-xl text-center text-xs text-slate-400" style={{ background: "var(--color-canvas)" }}>
                    No AI or integrity anomalies detected.
                  </div>
                ) : (
                  detectedSpans.map((h, i) => (
                    <div
                      key={i}
                      onClick={() => setActiveHL(activeHL === i ? null : i)}
                      className="rounded-lg p-3 cursor-pointer transition-all"
                      style={{
                        border: `1px solid ${activeHL === i ? "var(--color-accent)" : "var(--color-border)"}`,
                        background: activeHL === i ? "var(--color-accent-bg)" : "var(--color-surface)",
                      }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className="inline-block rounded-full px-2 py-0.5 font-mono font-medium text-[10px]"
                          style={{
                            background: "var(--color-red-bg)",
                            color: "var(--color-red)",
                            border: "1px solid var(--color-red-border)",
                          }}
                        >
                          AI ({Math.round((h.confidence ?? 0.85) * (h.confidence <= 1 ? 100 : 1))}%)
                        </span>
                        <span style={{ fontSize: 11, color: "var(--color-text-3)" }}>Passage #{i + 1}</span>
                      </div>
                      <p style={{ fontSize: 12, color: "var(--color-text-2)", lineHeight: 1.5 }}>
                        "{h.text?.slice(0, 100)}..."
                      </p>
                      <p className="text-[11px] text-rose-400 mt-1 italic">
                        {h.reason || "High artificial stylometric predictability"}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {tab === "ocr" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg" style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}>
              <StatusBadge status="complete" />
              <span style={{ fontSize: 13, color: "var(--color-green)" }}>
                OCR Text Extraction Engine Completed
              </span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <p className="font-semibold uppercase tracking-wider mb-2" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                  OCR Metadata
                </p>
                <div className="rounded-xl px-4" style={{ border: "1px solid var(--color-border)" }}>
                  <Row label="Words extracted" value={ocr?.word_count ?? "—"} />
                  <Row label="Status" value={ocr?.status || "complete"} />
                  <Row label="File processed" value={sub.file_name || "—"} />
                </div>
              </div>
              <div>
                <p className="font-semibold uppercase tracking-wider mb-2" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                  Extracted Text
                </p>
                <div
                  className="rounded-xl p-4 font-mono overflow-y-auto whitespace-pre-wrap"
                  style={{
                    border: "1px solid var(--color-border)",
                    background: "var(--color-canvas)",
                    fontSize: 12,
                    color: "var(--color-text-2)",
                    lineHeight: 1.7,
                    minHeight: 200,
                    maxHeight: 340,
                  }}
                >
                  {ocr?.extracted_text || "No text extracted."}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "ai" && (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "AI Score", value: ai ? `${aiScoreVal.toFixed(1)}%` : "0%" },
                { label: "Confidence", value: ai ? `${(ai.confidence * 100).toFixed(0)}%` : "—" },
                { label: "Perplexity", value: ai?.perplexity != null ? ai.perplexity.toFixed(1) : "—" },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-xl p-5 text-center"
                  style={{ border: "1px solid var(--color-border)", background: "var(--color-canvas)" }}
                >
                  <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 8 }}>{label}</p>
                  <p className="font-semibold font-mono" style={{ fontSize: 26, color: "var(--color-text-1)" }}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            {detectedSpans.length > 0 ? (
              <div className="space-y-3">
                <p className="font-semibold text-xs uppercase tracking-wider text-slate-400">
                  Flagged Excerpts ({detectedSpans.length})
                </p>
                {detectedSpans.map((span, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border"
                    style={{ background: "var(--color-surface)", borderColor: "var(--color-red-border)" }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-rose-500">
                        Passage #{idx + 1} — Confidence {Math.round((span.confidence ?? 0.85) * (span.confidence <= 1 ? 100 : 1))}%
                      </span>
                      <span className="text-xs text-slate-400">{span.reason || "High artificial burstiness"}</span>
                    </div>
                    <p className="text-sm font-serif italic text-slate-200">"{span.text}"</p>
                  </div>
                ))}
              </div>
            ) : (
              <Placeholder text="No passages flagged as artificial by the AI content detection model." />
            )}
          </div>
        )}

        {tab === "similarity" && (
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Similarity Score", value: simScore != null ? `${simScoreVal.toFixed(1)}%` : "0%" },
                { label: "Matched Submissions", value: analysisData.similar_submissions_count ?? 0 },
                { label: "Algorithm", value: "MinHash / TF-IDF Shingling" },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-xl p-5 text-center"
                  style={{ border: "1px solid var(--color-border)", background: "var(--color-canvas)" }}
                >
                  <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 8 }}>{label}</p>
                  <p className="font-semibold font-mono" style={{ fontSize: 26, color: "var(--color-text-1)" }}>
                    {value}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex justify-center pt-2">
              <Btn variant="outline" size="sm" onClick={() => navigate("/teacher/compare")}>
                Open Side-by-Side Document Comparison
              </Btn>
            </div>
          </div>
        )}

        {tab === "handwriting" && (
          <div className="space-y-4">
            {hw ? (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                  <p className="text-xs text-slate-400 mb-1">Slant Angle</p>
                  <p className="font-mono text-xl font-semibold">{hw.slant_angle}°</p>
                </div>
                <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                  <p className="text-xs text-slate-400 mb-1">Stroke Variance</p>
                  <p className="font-mono text-xl font-semibold">{hw.stroke_variance}</p>
                </div>
                <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                  <p className="text-xs text-slate-400 mb-1">Spacing Rhythm</p>
                  <p className="font-mono text-xl font-semibold">{hw.spacing_rhythm} px</p>
                </div>
                <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                  <p className="text-xs text-slate-400 mb-1">Confidence</p>
                  <p className="font-mono text-xl font-semibold">{hwConfidenceVal.toFixed(0)}%</p>
                </div>
              </div>
            ) : (
              <Placeholder text="Handwriting analysis is active for scanned images and physical assignment uploads." />
            )}
          </div>
        )}

        {tab === "grading" && (
          <div className="space-y-6 max-w-3xl">
            {/* Auto-Grade Summary */}
            <div
              className="p-5 rounded-xl border flex items-center justify-between"
              style={{ background: "var(--color-surface-2)", borderColor: "var(--color-border)" }}
            >
              <div>
                <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold block">
                  Automated Grade Baseline
                </span>
                <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                  {gradeData?.final_score ?? sub.auto_grade ?? maxMarks} / {maxMarks}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {gradeData?.is_override
                    ? "Instructor has adjusted the grade with custom assessment."
                    : "Automatically evaluated by AI stylometry and peer similarity rules."}
                </p>
              </div>

              <div className="text-right font-mono text-xs text-slate-400">
                <p>AI Penalty: {aiScoreVal > 30 ? `-${Math.min(45, (aiScoreVal - 30) * 0.6).toFixed(1)}` : "0"} marks</p>
                <p>Similarity Penalty: {simScoreVal > 30 ? `-${Math.min(45, (simScoreVal - 30) * 0.7).toFixed(1)}` : "0"} marks</p>
              </div>
            </div>

            {/* Editable Grading Form */}
            <form onSubmit={handleSaveGrade} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Final Score (out of {maxMarks})
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={maxMarks}
                    step={0.5}
                    value={gradeScore}
                    onChange={(e) => setGradeScore(Number(e.target.value))}
                    required
                    className="w-full px-3 py-2 rounded-lg text-sm font-mono"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text-1)",
                    }}
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Adjustment Reason (Audit trail)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Verified legitimate citations, manually curved"
                    value={gradeReason}
                    onChange={(e) => setGradeReason(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text-1)",
                    }}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Instructor Feedback & Guidance
                </label>
                <textarea
                  rows={4}
                  placeholder="Provide structured feedback for the student regarding document integrity, thesis structure, and style..."
                  value={gradeFeedback}
                  onChange={(e) => setGradeFeedback(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-1)",
                  }}
                />
              </div>

              <div className="flex items-center gap-3 pt-2">
                <Btn
                  variant="primary"
                  size="sm"
                  disabled={savingGrade}
                  onClick={handleSaveGrade}
                  icon={savingGrade ? <Spinner size={14} color="white" /> : undefined}
                >
                  {savingGrade ? "Saving Grade…" : "Save & Publish Grade"}
                </Btn>

                {gradeSaveSuccess && (
                  <span className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                    ✓ Grade and audit trail saved successfully!
                  </span>
                )}
              </div>
            </form>

            {/* Audit Trail */}
            {gradeData?.audit_trail && gradeData.audit_trail.length > 0 && (
              <div className="mt-6 pt-5 border-t border-slate-700/50">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                  Grading Audit Trail & Change History
                </p>
                <div className="space-y-2">
                  {gradeData.audit_trail.map((item: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg flex items-center justify-between text-xs"
                      style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
                    >
                      <div>
                        <span className="font-semibold text-slate-200">{item.changed_by_name}</span>: {item.reason}
                      </div>
                      <div className="font-mono text-slate-400">
                        {item.new_score} / {maxMarks} • {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
