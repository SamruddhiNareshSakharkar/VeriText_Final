import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import ScoreRing from "../../components/ScoreRing";
import ProcessingTracker from "../../components/ProcessingTracker";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { api, apiRequest } from "../../lib/api";

type Tab = "overview" | "document" | "ocr" | "ai" | "similarity" | "handwriting" | "grading";
type HighlightLayer = "all" | "ai" | "similarity";

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
  const [activeHLId, setActiveHLId] = useState<string | null>(null);
  const [highlightLayer, setHighlightLayer] = useState<HighlightLayer>("all");
  const markRefs = useRef<Record<string, HTMLElement | null>>({});
  const [loading, setLoading] = useState(true);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [flagged, setFlagged] = useState(false);
  const [ocrExpanded, setOcrExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    if (!Number.isFinite(n) || n < 0) return 0;
    return Math.min(100, Math.max(0, n));
  };
  const fmt = (raw: unknown, digits = 1) => asPercent(raw).toFixed(digits);

  const aiScoreVal = ai ? asPercent(ai.score) : 0;
  const simScoreVal = simScore != null ? asPercent(simScore) : 0;
  const hwConfidenceVal = hw ? (hw.confidence <= 1.0 && hw.confidence > 0 ? hw.confidence * 100 : asPercent(hw.confidence)) : 0;

  const docText = ocr?.extracted_text || "No text could be extracted from this document.";
  const detectedSpans: any[] = Array.isArray(ai?.detected_spans) ? ai.detected_spans : [];

  const maxMarks = gradeData?.max_marks || sub.max_marks || 100;

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

function locateSpanOffsets(
  fullText: string,
  rawStart?: number | null,
  rawEnd?: number | null,
  snippet?: string | null
): { start: number; end: number } | null {
  if (!fullText) return null;
  const len = fullText.length;
  const text = snippet?.trim() || "";

  // 1. If start and end are already valid bounds
  if (
    rawStart != null &&
    rawEnd != null &&
    rawStart >= 0 &&
    rawEnd > rawStart &&
    rawEnd <= len
  ) {
    if (!text) return { start: rawStart, end: rawEnd };
    const slice = fullText.substring(rawStart, rawEnd).trim();
    if (slice === text || slice.toLowerCase() === text.toLowerCase() || slice.includes(text) || text.includes(slice)) {
      return { start: rawStart, end: rawEnd };
    }
  }

  // 2. If text is provided, find its exact character range in fullText
  if (text.length >= 2) {
    const exactIdx = fullText.indexOf(text);
    if (exactIdx !== -1) {
      return { start: exactIdx, end: exactIdx + text.length };
    }

    const lowerIdx = fullText.toLowerCase().indexOf(text.toLowerCase());
    if (lowerIdx !== -1) {
      return { start: lowerIdx, end: lowerIdx + text.length };
    }

    const prefix = text.slice(0, Math.min(30, text.length));
    if (prefix.length >= 6) {
      const prefixIdx = fullText.toLowerCase().indexOf(prefix.toLowerCase());
      if (prefixIdx !== -1) {
        return { start: prefixIdx, end: Math.min(len, prefixIdx + text.length) };
      }
    }
  }

  // 3. Fallback to raw bounds if within range
  if (rawStart != null && rawEnd != null && rawStart >= 0 && rawEnd > rawStart) {
    return {
      start: Math.min(len, Math.max(0, rawStart)),
      end: Math.min(len, Math.max(rawStart + 1, rawEnd)),
    };
  }

  return null;
}

  const similarityMatches: any[] = Array.isArray(analysisData.similarity_matches) ? analysisData.similarity_matches : [];
  const topMatchedStudentName: string = analysisData.top_matched_student_name || "Peer Student";
  const topMatchedSubmissionId: string | null = analysisData.top_matched_submission_id || null;

  // Build unified list of highlights with verified character offsets
  const unifiedHighlights: any[] = [];

  detectedSpans.forEach((s, idx) => {
    const located = locateSpanOffsets(docText, s.start, s.end, s.text);
    if (located) {
      unifiedHighlights.push({
        id: `ai-${idx}`,
        type: "ai" as const,
        start: located.start,
        end: located.end,
        text: s.text || docText.substring(located.start, located.end),
        confidence: s.confidence ?? 0.85,
        reason: s.reason || "Artificial stylometric characteristics",
      });
    }
  });

  similarityMatches.forEach((s, idx) => {
    const rawStart = s.start_a ?? s.start;
    const rawEnd = s.end_a ?? s.end;
    const located = locateSpanOffsets(docText, rawStart, rawEnd, s.text);
    if (located) {
      unifiedHighlights.push({
        id: `sim-${idx}`,
        type: "similarity" as const,
        start: located.start,
        end: located.end,
        text: s.text || docText.substring(located.start, located.end),
        confidence: 0.95,
        reason: `Passage matches peer submission (${s.length || (located.end - located.start)} chars)`,
        peerName: topMatchedStudentName,
      });
    }
  });

  const activeHighlights =
    highlightLayer === "ai"
      ? unifiedHighlights.filter((h) => h.type === "ai")
      : highlightLayer === "similarity"
      ? unifiedHighlights.filter((h) => h.type === "similarity")
      : unifiedHighlights;

  function scrollToHighlight(hlId: string) {
    setActiveHLId(hlId);
    const el = markRefs.current[hlId];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // High-efficiency non-overlapping interval partition rendering (O(N log N))
  function renderHighlightedDocument(fullText: string, activeList: any[]) {
    if (!fullText) return null;
    if (!activeList || activeList.length === 0) {
      return <span style={{ whiteSpace: "pre-wrap" }}>{fullText}</span>;
    }

    const pointsSet = new Set<number>([0, fullText.length]);
    activeList.forEach((h) => {
      const s = Math.max(0, Math.min(fullText.length, h.start));
      const e = Math.max(0, Math.min(fullText.length, h.end));
      if (s < e) {
        pointsSet.add(s);
        pointsSet.add(e);
      }
    });

    const sortedPoints = Array.from(pointsSet).sort((a, b) => a - b);
    const elements: React.ReactNode[] = [];

    for (let k = 0; k < sortedPoints.length - 1; k++) {
      const pStart = sortedPoints[k];
      const pEnd = sortedPoints[k + 1];
      if (pStart >= pEnd) continue;

      const subText = fullText.substring(pStart, pEnd);
      const matchingHls = activeList.filter((h) => h.start <= pStart && h.end >= pEnd);

      if (matchingHls.length === 0) {
        elements.push(
          <span key={`txt-${pStart}-${pEnd}`} style={{ whiteSpace: "pre-wrap" }}>
            {subText}
          </span>
        );
      } else {
        const hasAi = matchingHls.some((h) => h.type === "ai");
        const hasSim = matchingHls.some((h) => h.type === "similarity");

        let cls = "hl-ai";
        let badgeText = "AI Content";
        if (hasAi && hasSim) {
          cls = "hl-dual";
          badgeText = "AI + Peer Match";
        } else if (hasSim) {
          cls = "hl-sim";
          badgeText = "Peer Match";
        }

        const primaryHl = matchingHls[0];
        const isSelected = activeHLId === primaryHl.id;

        elements.push(
          <mark
            key={`mark-${pStart}-${pEnd}`}
            ref={(el) => {
              markRefs.current[primaryHl.id] = el;
            }}
            onClick={() => setActiveHLId(isSelected ? null : primaryHl.id)}
            className={`${cls}${isSelected ? " hl-ring ring-2 ring-indigo-500 font-semibold" : ""} cursor-pointer transition-all inline`}
            title={`${badgeText}: ${primaryHl.reason}`}
            style={{ whiteSpace: "pre-wrap" }}
          >
            {subText}
          </mark>
        );
      }
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
              onClick={() => window.open(api.submissions.annotatedPdfUrl(id!), "_blank")}
              style={{ background: "rgba(14, 165, 233, 0.12)", color: "#38bdf8", borderColor: "rgba(14, 165, 233, 0.35)" }}
            >
              📑 Highlighted PDF Report
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => window.open(api.submissions.downloadFileUrl(id!), "_blank")}
            >
              Raw File
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
            {/* Highlight controls toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4 p-3 rounded-xl" style={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border)" }}>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 mr-1">Layer:</span>
                <button
                  type="button"
                  onClick={() => setHighlightLayer("all")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    highlightLayer === "all"
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  All Anomalies ({unifiedHighlights.length})
                </button>
                <button
                  type="button"
                  onClick={() => setHighlightLayer("ai")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    highlightLayer === "ai"
                      ? "bg-rose-600 text-white shadow-sm"
                      : "bg-rose-50 text-rose-700 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300"
                  }`}
                >
                  AI Content ({detectedSpans.length})
                </button>
                <button
                  type="button"
                  onClick={() => setHighlightLayer("similarity")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    highlightLayer === "similarity"
                      ? "bg-amber-600 text-white shadow-sm"
                      : "bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300"
                  }`}
                >
                  Peer Matches ({similarityMatches.length})
                </button>
              </div>

              <div className="flex items-center gap-3">
                {activeHLId && (
                  <button
                    onClick={() => setActiveHLId(null)}
                    className="text-xs text-indigo-500 hover:underline cursor-pointer"
                  >
                    Clear selection
                  </button>
                )}
                {topMatchedSubmissionId && (
                  <Btn
                    variant="outline"
                    size="xs"
                    onClick={() => navigate(`/teacher/compare?subA=${id}&subB=${topMatchedSubmissionId}`)}
                  >
                    Compare with {topMatchedStudentName} →
                  </Btn>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Document Text Area */}
              <div
                className="lg:col-span-2 rounded-xl p-5 overflow-y-auto whitespace-pre-wrap font-serif"
                style={{
                  border: "1px solid var(--color-border)",
                  background: "var(--color-surface-2)",
                  minHeight: 380,
                  maxHeight: 560,
                  fontSize: 14.5,
                  lineHeight: 1.9,
                  color: "var(--color-text-1)",
                }}
              >
                {renderHighlightedDocument(docText, activeHighlights)}
              </div>

              {/* Sidebar with Flagged Passages */}
              <div className="space-y-2.5 max-h-[560px] overflow-y-auto pr-1">
                <div className="flex items-center justify-between">
                  <p className="font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                    Flagged Passages ({activeHighlights.length})
                  </p>
                  <span className="text-[11px] text-slate-400">Click to focus</span>
                </div>

                {activeHighlights.length === 0 ? (
                  <div className="p-4 rounded-xl text-center text-xs text-slate-400" style={{ background: "var(--color-canvas)" }}>
                    No integrity anomalies flagged in this layer.
                  </div>
                ) : (
                  activeHighlights.map((h, i) => {
                    const isSelected = activeHLId === h.id;
                    const isAi = h.type === "ai";
                    return (
                      <div
                        key={h.id || i}
                        onClick={() => scrollToHighlight(h.id)}
                        className="rounded-lg p-3 cursor-pointer transition-all"
                        style={{
                          border: `1px solid ${isSelected ? "var(--color-accent)" : "var(--color-border)"}`,
                          background: isSelected ? "var(--color-accent-bg)" : "var(--color-surface)",
                        }}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span
                            className="inline-block rounded-full px-2 py-0.5 font-mono font-medium text-[10px]"
                            style={{
                              background: isAi ? "var(--color-red-bg)" : "var(--color-amber-bg)",
                              color: isAi ? "var(--color-red)" : "var(--color-amber)",
                              border: `1px solid ${isAi ? "var(--color-red-border)" : "var(--color-amber-border)"}`,
                            }}
                          >
                            {isAi
                              ? `AI (${Math.round((h.confidence ?? 0.85) * 100)}%)`
                              : `Peer Match (${h.peerName || "Alex"})`}
                          </span>
                          <span style={{ fontSize: 11, color: "var(--color-text-3)" }}>
                            Passage #{i + 1}
                          </span>
                        </div>
                        <p style={{ fontSize: 12, color: "var(--color-text-2)", lineHeight: 1.5 }}>
                          "{h.text?.slice(0, 95)}..."
                        </p>
                        <p
                          className="text-[11px] mt-1 italic"
                          style={{ color: isAi ? "#f43f5e" : "#d97706" }}
                        >
                          {h.reason}
                        </p>
                      </div>
                    );
                  })
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
            {/* OCR Review Warning Banner */}
            {Boolean(ocr?.needs_review || (ocr?.flagged_lines_count && ocr.flagged_lines_count > 0)) && (
              <div className="flex items-center gap-2.5 p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300 text-xs font-medium">
                <span className="text-base">⚠️</span>
                <span>
                  <strong>Confidence Review Flagged:</strong> {ocr.flagged_lines_count || 1} line(s) contain uncertain or low-confidence characters requiring teacher inspection.
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <p className="font-semibold uppercase tracking-wider mb-2" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                  OCR Pipeline & Document Metadata
                </p>
                <div className="rounded-xl px-4" style={{ border: "1px solid var(--color-border)" }}>
                  <Row label="Document Classification" value={ocr?.doc_type ? ocr.doc_type.replace('_', ' ').toUpperCase() : "STANDARD"} />
                  <Row label="Recognition Confidence" value={ocr?.avg_confidence ? `${Math.round(ocr.avg_confidence * 100)}%` : "—"} />
                  <Row label="Words extracted" value={ocr?.word_count ?? "—"} />
                  <Row label="Review Flags" value={ocr?.flagged_lines_count ? `${ocr.flagged_lines_count} lines flagged` : "None (High confidence)"} />
                  <Row label="Status" value={ocr?.status || "complete"} />
                  <Row label="File processed" value={sub.file_name || "—"} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
                      Reconstructed Document Text
                    </p>
                    {ocr?.extracted_text && (
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                        {ocr.extracted_text.split('\n').filter((l: string) => l.trim().length > 0).length} lines • {ocr.extracted_text.length} chars
                      </span>
                    )}
                  </div>
                  {ocr?.extracted_text && ocr.extracted_text.split('\n').length > 10 && (
                    <button
                      type="button"
                      onClick={() => setOcrExpanded(!ocrExpanded)}
                      className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      {ocrExpanded ? "Collapse View ↑" : "Expand All Lines ↓"}
                    </button>
                  )}
                </div>
                <div
                  className="rounded-xl p-4 font-mono overflow-y-auto whitespace-pre-wrap transition-all duration-200"
                  style={{
                    border: "1px solid var(--color-border)",
                    background: "var(--color-canvas)",
                    fontSize: 12,
                    color: "var(--color-text-2)",
                    lineHeight: 1.7,
                    minHeight: 200,
                    maxHeight: ocrExpanded ? 800 : 340,
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "AI Score", value: ai ? `${aiScoreVal.toFixed(1)}%` : "0%", color: aiScoreVal >= 50 ? "var(--color-red)" : "var(--color-green)" },
                { label: "Confidence", value: ai ? `${asPercent(ai.confidence).toFixed(0)}%` : "—", color: "var(--color-text-1)" },
                { label: "Perplexity", value: ai?.perplexity != null ? Number(ai.perplexity).toFixed(1) : "—", color: "var(--color-text-1)" },
                { label: "Burstiness", value: ai?.burstiness != null ? `${Number(ai.burstiness).toFixed(1)}%` : "—", color: "var(--color-text-1)" },
              ].map(({ label, value, color }) => (
                <div
                  key={label}
                  className="rounded-xl p-5 text-center"
                  style={{ border: "1px solid var(--color-border)", background: "var(--color-canvas)" }}
                >
                  <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 8 }}>{label}</p>
                  <p className="font-semibold font-mono" style={{ fontSize: 24, color }}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            {/* Classification badge */}
            {ai?.analysis_metadata?.classification && (
              <div className="flex items-center gap-3 p-3 rounded-lg" style={{
                background: aiScoreVal >= 65 ? "rgba(239, 68, 68, 0.08)" : aiScoreVal >= 35 ? "rgba(245, 158, 11, 0.08)" : "rgba(34, 197, 94, 0.08)",
                border: `1px solid ${aiScoreVal >= 65 ? "rgba(239, 68, 68, 0.25)" : aiScoreVal >= 35 ? "rgba(245, 158, 11, 0.25)" : "rgba(34, 197, 94, 0.25)"}`,
              }}>
                <span className="text-base">{aiScoreVal >= 65 ? "🤖" : aiScoreVal >= 35 ? "⚠️" : "✅"}</span>
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{
                    color: aiScoreVal >= 65 ? "#ef4444" : aiScoreVal >= 35 ? "#f59e0b" : "#22c55e"
                  }}>
                    {ai.analysis_metadata.classification}
                  </span>
                  {ai.analysis_metadata?.evidence?.length > 0 && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      {ai.analysis_metadata.evidence[0]}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Feature breakdown */}
            {ai?.analysis_metadata?.features && (
              <div>
                <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-2">Stylometric Features</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {[
                    { label: "Sentence Variation", value: ai.analysis_metadata.features.sentence_variation != null ? (ai.analysis_metadata.features.sentence_variation * 100).toFixed(1) + "%" : "—" },
                    { label: "Vocabulary Richness (TTR)", value: ai.analysis_metadata.features.ttr != null ? (ai.analysis_metadata.features.ttr * 100).toFixed(1) + "%" : "—" },
                    { label: "Phrase Markers", value: ai.analysis_metadata.features.keyword_hits != null ? String(ai.analysis_metadata.features.keyword_hits) : "0" },
                    { label: "Entropy", value: ai.analysis_metadata.features.entropy != null ? Number(ai.analysis_metadata.features.entropy).toFixed(2) : "—" },
                  ].map(({ label, value }) => (
                    <div key={label} className="p-2.5 rounded-lg text-center" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
                      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
                      <p className="text-sm font-mono font-medium" style={{ color: "var(--color-text-2)" }}>{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { label: "Peak Peer Similarity", value: simScore != null ? `${simScoreVal.toFixed(1)}%` : "0%" },
                { label: "Cohort Submissions Scanned", value: analysisData.similar_submissions_count ?? 0 },
                { label: "Matching Passages Found", value: similarityMatches.length },
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

            {/* Peer match spotlight */}
            {topMatchedSubmissionId && (
              <div
                className="p-5 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                style={{
                  background: "rgba(245, 158, 11, 0.08)",
                  borderColor: "rgba(245, 158, 11, 0.3)",
                }}
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span>
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-500">
                      Primary Peer Match Detected
                    </span>
                  </div>
                  <h4 className="font-semibold text-base" style={{ color: "var(--color-text-1)" }}>
                    {topMatchedStudentName}
                  </h4>
                  <p className="text-xs text-slate-400 mt-1">
                    Highest cross-submission alignment with {fmt(simScoreVal)}% overlapping stylometric and n-gram shingle content across {similarityMatches.length} passages.
                  </p>
                </div>

                <Btn
                  variant="primary"
                  size="sm"
                  onClick={() => navigate(`/teacher/compare?subA=${id}&subB=${topMatchedSubmissionId}`)}
                >
                  Open Side-by-Side Dual Viewer →
                </Btn>
              </div>
            )}

            {/* Matching Segments Detail */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Identified Matching Excerpts ({similarityMatches.length})
                </p>
                <span className="text-xs font-mono text-slate-400">
                  Algorithm: Inverted Shingle Index + Greedy Extension
                </span>
              </div>

              {similarityMatches.length === 0 ? (
                <Placeholder text="No duplicate or heavily paraphrased excerpts found against any student submissions in this assignment cohort." />
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {similarityMatches.map((seg, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border transition-all"
                      style={{
                        background: "var(--color-surface)",
                        borderColor: "rgba(245, 158, 11, 0.25)",
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/15 text-amber-500 border border-amber-500/25">
                          <span>Match #{idx + 1}</span>
                          <span>•</span>
                          <span className="font-mono">{seg.length} characters</span>
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          Offsets: [{seg.start_a} – {seg.end_a}]
                        </span>
                      </div>
                      <p className="text-sm font-serif italic text-slate-200 mt-2 bg-slate-900/40 p-3 rounded-lg border border-slate-800">
                        "{seg.text}"
                      </p>
                      <p className="text-xs text-amber-500/90 mt-2">
                        Matches corresponding passage in {topMatchedStudentName}'s submission (chars {seg.start_b} – {seg.end_b})
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "handwriting" && (
          <div className="space-y-4">
            {hw ? (
              <>
                {/* Document classification badge */}
                <div className="flex items-center gap-3 p-3 rounded-lg" style={{
                  background: hwConfidenceVal >= 65 ? "rgba(99, 102, 241, 0.08)" : hwConfidenceVal >= 35 ? "rgba(245, 158, 11, 0.08)" : "rgba(107, 114, 128, 0.08)",
                  border: `1px solid ${hwConfidenceVal >= 65 ? "rgba(99, 102, 241, 0.25)" : hwConfidenceVal >= 35 ? "rgba(245, 158, 11, 0.25)" : "rgba(107, 114, 128, 0.25)"}`,
                }}>
                  <span className="text-base">{hwConfidenceVal >= 65 ? "✍️" : hwConfidenceVal >= 35 ? "📝" : "🖨️"}</span>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider" style={{
                      color: hwConfidenceVal >= 65 ? "#6366f1" : hwConfidenceVal >= 35 ? "#f59e0b" : "#6b7280"
                    }}>
                      {hw.metrics?.document_classification === "handwritten"
                        ? "Handwritten Document Detected"
                        : hw.metrics?.document_classification === "mixed"
                        ? "Mixed Content (Handwritten + Printed)"
                        : "Printed / Digital Document"}
                    </span>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {hwConfidenceVal >= 65
                        ? "Computer vision analysis confirms handwritten stroke patterns with high confidence."
                        : hwConfidenceVal >= 35
                        ? "Document appears to contain both handwritten and printed elements."
                        : "Document appears to be digitally generated or printed. Handwriting features are minimal."}
                    </p>
                  </div>
                </div>

                {/* Core metrics */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs text-slate-400 mb-1">Slant Angle</p>
                    <p className="font-mono text-xl font-semibold">{hw.slant_angle}°</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{Math.abs(hw.slant_angle) <= 3 ? "Upright" : hw.slant_angle > 0 ? "Right-leaning" : "Left-leaning"}</p>
                  </div>
                  <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs text-slate-400 mb-1">Stroke Variance</p>
                    <p className="font-mono text-xl font-semibold">{hw.stroke_variance}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{hw.stroke_variance >= 2 ? "High (handwritten)" : hw.stroke_variance >= 0.5 ? "Medium" : "Low (printed)"}</p>
                  </div>
                  <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs text-slate-400 mb-1">Spacing Rhythm</p>
                    <p className="font-mono text-xl font-semibold">{hw.spacing_rhythm} px</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">Line spacing average</p>
                  </div>
                  <div className="p-4 rounded-xl text-center" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                    <p className="text-xs text-slate-400 mb-1">HW Confidence</p>
                    <p className="font-mono text-xl font-semibold" style={{
                      color: hwConfidenceVal >= 65 ? "#6366f1" : hwConfidenceVal >= 35 ? "#f59e0b" : "var(--color-text-3)"
                    }}>{hwConfidenceVal.toFixed(0)}%</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">Handwriting probability</p>
                  </div>
                </div>

                {/* Additional metrics */}
                {hw.metrics && (
                  <div>
                    <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-2">Detailed CV Metrics</p>
                    <div className="rounded-xl px-4" style={{ border: "1px solid var(--color-border)" }}>
                      <Row label="Ink Density" value={hw.metrics.ink_density != null ? `${(hw.metrics.ink_density * 100).toFixed(1)}%` : "—"} />
                      <Row label="Estimated Lines" value={hw.metrics.line_count_estimate ?? "—"} />
                      <Row label="Resolution" value={hw.metrics.resolution ?? "—"} />
                      <Row label="Stroke Mean" value={hw.metrics.stroke_mean != null ? `${hw.metrics.stroke_mean} px` : "—"} />
                      <Row label="Spacing CV" value={hw.metrics.spacing_cv != null ? hw.metrics.spacing_cv.toFixed(3) : "—"} />
                      <Row label="Analysis Method" value={hw.metrics.analysis_technique ?? "Computer vision stylometry"} />
                    </div>
                  </div>
                )}
              </>
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
