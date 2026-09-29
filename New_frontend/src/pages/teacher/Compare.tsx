import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import Spinner from "../../components/Spinner";
import Btn from "../../components/Btn";
import { api } from "../../lib/api";

type HLType = "ai" | "sim" | "match";
type FilterMode = "all" | HLType;

interface Highlight {
  start: number;
  end: number;
  type: HLType;
  pairIdx?: number;
  note: string;
}

interface Doc {
  studentLabel: string;
  submittedAt: string;
  wordCount: number;
  text: string;
  highlights: Highlight[];
}

interface RenderedDocProps {
  doc: Doc;
  active: number | null;
  onActivate: (i: number | null) => void;
  filter: FilterMode;
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

function RenderedDocument({ doc, active, onActivate, filter, scrollRef }: RenderedDocProps) {
  const spanRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    if (active != null && spanRefs.current[active]) {
      spanRefs.current[active]?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [active]);

  const visHL = doc.highlights.filter((h) => filter === "all" || h.type === filter);

  // Interval Partitioning: O(N log N) strictly monotonic text segmentation without duplicates or cursor scrambles
  const renderDocumentContent = () => {
    if (!doc.text) {
      return <p className="text-slate-500 italic">No text content available.</p>;
    }

    if (visHL.length === 0) {
      return <span>{doc.text}</span>;
    }

    // Collect all unique boundary points
    const pointsSet = new Set<number>([0, doc.text.length]);
    visHL.forEach((h) => {
      const s = Math.max(0, Math.min(doc.text.length, h.start));
      const e = Math.max(0, Math.min(doc.text.length, h.end));
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

      const subText = doc.text.substring(pStart, pEnd);
      // Find all highlights in doc.highlights that cover this interval
      const matchingHls = doc.highlights
        .map((h, originalIdx) => ({ h, originalIdx }))
        .filter(({ h }) => (filter === "all" || h.type === filter) && h.start <= pStart && h.end >= pEnd);

      if (matchingHls.length === 0) {
        elements.push(<span key={`txt-${pStart}-${pEnd}`}>{subText}</span>);
      } else {
        const primary = matchingHls[0];
        const origIdx = primary.originalIdx;
        const isActive = active === origIdx;

        let cls = primary.h.type === "ai" ? "hl-ai" : primary.h.type === "sim" ? "hl-sim" : "hl-match";
        const hasAi = matchingHls.some((m) => m.h.type === "ai");
        const hasMatch = matchingHls.some((m) => m.h.type === "match" || m.h.type === "sim");
        if (hasAi && hasMatch) {
          cls = "hl-dual";
        }

        elements.push(
          <mark
            key={`mark-${pStart}-${pEnd}`}
            ref={(el) => {
              if (el) spanRefs.current[origIdx] = el;
            }}
            className={`${cls}${isActive ? " hl-ring" : ""} cursor-pointer transition-all inline`}
            onClick={() => onActivate(isActive ? null : origIdx)}
            title={primary.h.note}
          >
            {subText}
          </mark>
        );
      }
    }

    return elements;
  };

  return (
    <div
      ref={scrollRef}
      className="flex-1 min-w-0 flex flex-col rounded-xl overflow-hidden shadow-sm"
      style={{ border: "1px solid var(--color-border)", background: "var(--color-surface)" }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-2.5"
        style={{ borderBottom: "1px solid var(--color-border)", background: "var(--color-surface-2)" }}
      >
        <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--color-accent)", flexShrink: 0 }} />
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate" style={{ fontSize: 13, color: "var(--color-text-1)" }}>
            {doc.studentLabel}
          </p>
          <p style={{ fontSize: 11, color: "var(--color-text-4)" }}>{doc.submittedAt}</p>
        </div>
        <div className="flex items-center gap-2">
          {doc.wordCount > 0 && (
            <span className="font-mono text-xs text-slate-400">
              {doc.wordCount} words
            </span>
          )}
          <span className="font-mono text-xs text-slate-500">
            {visHL.length} flags
          </span>
        </div>
      </div>

      {/* Body */}
      <div
        className="flex-1 overflow-y-auto p-5 font-serif"
        style={{ fontSize: 14, lineHeight: 1.9, color: "var(--color-text-1)" }}
      >
        {renderDocumentContent()}
      </div>
    </div>
  );
}

export default function Compare() {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<"database" | "upload">("database");

  // Database Mode State
  const [assignments, setAssignments] = useState<any[]>([]);
  const [selectedAssignment, setSelectedAssignment] = useState("");
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [leftSubId, setLeftSubId] = useState("");
  const [rightSubId, setRightSubId] = useState("");

  // Upload Mode State
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Comparison Results State
  const [compareResult, setCompareResult] = useState<any>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [activeLeft, setActiveLeft] = useState<number | null>(null);
  const [activeRight, setActiveRight] = useState<number | null>(null);
  const [detail, setDetail] = useState<string | null>(null);

  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  // Load assignments on mount
  useEffect(() => {
    async function init() {
      try {
        const list = await api.assignments.list();
        setAssignments(list || []);
        if (list && list.length > 0) {
          const firstId = list[0].id;
          setSelectedAssignment(firstId);
        }
      } catch (e) {
        console.error("Failed to load assignments", e);
      }
    }
    init();
  }, []);

  // Load submissions when assignment changes
  useEffect(() => {
    if (!selectedAssignment) return;
    async function loadSubs() {
      try {
        const subs = await api.assignments.getSubmissions(selectedAssignment);
        setSubmissions(subs || []);

        const qA = searchParams.get("subA");
        const qB = searchParams.get("subB");

        if (qA && subs.some((s: any) => s.id === qA)) {
          setLeftSubId(qA);
        } else if (subs.length > 0) {
          setLeftSubId(subs[0].id);
        }

        if (qB && subs.some((s: any) => s.id === qB)) {
          setRightSubId(qB);
        } else if (subs.length > 1) {
          setRightSubId(subs[1].id);
        } else if (subs.length > 0) {
          setRightSubId(subs[0].id);
        }
      } catch (e) {
        console.error("Failed to load submissions", e);
      }
    }
    loadSubs();
  }, [selectedAssignment, searchParams]);

  // Run DB compare when both selected
  useEffect(() => {
    if (mode !== "database" || !leftSubId || !rightSubId) return;
    if (leftSubId === rightSubId) return;

    async function executeCompare() {
      setLoadingCompare(true);
      setActiveLeft(null);
      setActiveRight(null);
      setDetail(null);
      try {
        const data = await api.comparison.compare(leftSubId, rightSubId);
        setCompareResult(data);
      } catch (e) {
        console.error("Comparison failed", e);
      } finally {
        setLoadingCompare(false);
      }
    }
    executeCompare();
  }, [mode, leftSubId, rightSubId]);

  // Execute Upload Compare
  async function handleUploadCompare() {
    if (!fileA || !fileB) return;
    setUploading(true);
    setLoadingCompare(true);
    setActiveLeft(null);
    setActiveRight(null);
    setDetail(null);
    try {
      const data = await api.comparison.uploadCompare(fileA, fileB);
      setCompareResult(data);
    } catch (err: any) {
      alert(err?.message || "File upload comparison failed.");
    } finally {
      setUploading(false);
      setLoadingCompare(false);
    }
  }

  // Build Docs from Compare Result
  let docLeft: Doc = {
    studentLabel: "Select a Left Submission",
    submittedAt: "—",
    wordCount: 0,
    text: "Select submissions or upload documents above to run side-by-side analysis.",
    highlights: [],
  };

  let docRight: Doc = {
    studentLabel: "Select a Right Submission",
    submittedAt: "—",
    wordCount: 0,
    text: "Extracted document text and matching passages will appear here.",
    highlights: [],
  };

  if (compareResult) {
    const textA = compareResult.ocr_text_a || "";
    const textB = compareResult.ocr_text_b || "";
    const segs: any[] = compareResult.matching_segments || [];
    const aiA: any[] = compareResult.ai_analysis_a?.detected_spans || [];
    const aiB: any[] = compareResult.ai_analysis_b?.detected_spans || [];

    const hlLeft: Highlight[] = [];
    const hlRight: Highlight[] = [];

    // Matched text segments
    segs.forEach((seg, idx) => {
      hlLeft.push({
        start: seg.start_a,
        end: seg.end_a,
        type: "match",
        pairIdx: idx,
        note: `Exact matching excerpt with Right document (${seg.length} chars).`,
      });
      hlRight.push({
        start: seg.start_b,
        end: seg.end_b,
        type: "match",
        pairIdx: idx,
        note: `Exact matching excerpt with Left document (${seg.length} chars).`,
      });
    });

    // AI spans Left
    aiA.forEach((span) => {
      hlLeft.push({
        start: span.start,
        end: span.end,
        type: "ai",
        note: `AI-generated content (${Math.round(span.confidence * 100)}% confidence): ${span.reason || "Artificial stylometry"}`,
      });
    });

    // AI spans Right
    aiB.forEach((span) => {
      hlRight.push({
        start: span.start,
        end: span.end,
        type: "ai",
        note: `AI-generated content (${Math.round(span.confidence * 100)}% confidence): ${span.reason || "Artificial stylometry"}`,
      });
    });

    docLeft = {
      studentLabel:
        compareResult.submission_a?.student?.full_name ||
        compareResult.submission_a?.file_name ||
        "Document A",
      submittedAt: compareResult.submission_a?.submitted_at
        ? new Date(compareResult.submission_a.submitted_at).toLocaleDateString()
        : "Direct Upload",
      wordCount: textA.split(/\s+/).filter(Boolean).length,
      text: textA,
      highlights: hlLeft,
    };

    docRight = {
      studentLabel:
        compareResult.submission_b?.student?.full_name ||
        compareResult.submission_b?.file_name ||
        "Document B",
      submittedAt: compareResult.submission_b?.submitted_at
        ? new Date(compareResult.submission_b.submitted_at).toLocaleDateString()
        : "Direct Upload",
      wordCount: textB.split(/\s+/).filter(Boolean).length,
      text: textB,
      highlights: hlRight,
    };
  }

  function handleActivateLeft(i: number | null) {
    setActiveLeft(i);
    if (i != null && docLeft.highlights[i]) {
      const hl = docLeft.highlights[i];
      setDetail(hl.note);
      if (hl.pairIdx !== undefined) {
        const rIdx = docRight.highlights.findIndex((h) => h.pairIdx === hl.pairIdx);
        if (rIdx !== -1) setActiveRight(rIdx);
      }
    } else {
      setDetail(null);
      setActiveRight(null);
    }
  }

  function handleActivateRight(i: number | null) {
    setActiveRight(i);
    if (i != null && docRight.highlights[i]) {
      const hl = docRight.highlights[i];
      setDetail(hl.note);
      if (hl.pairIdx !== undefined) {
        const lIdx = docLeft.highlights.findIndex((h) => h.pairIdx === hl.pairIdx);
        if (lIdx !== -1) setActiveLeft(lIdx);
      }
    } else {
      setDetail(null);
      setActiveLeft(null);
    }
  }

  const LEGEND: { type: HLType; cls: string; label: string }[] = [
    { type: "ai", cls: "hl-ai", label: "AI Content" },
    { type: "match", cls: "hl-match", label: "Matching Text" },
  ];

  const hwScore = compareResult?.handwriting_similarity_score ?? null;
  const simScore = compareResult?.similarity_score ?? null;

  return (
    <div className="flex flex-col min-h-[calc(100vh-120px)]">
      <PageHeader
        title="Document Comparison"
        subtitle="Side-by-side text synchronization, AI passages, and handwriting stylometry comparison."
        actions={
          <div className="flex items-center gap-1 bg-slate-800/60 p-1 rounded-lg border border-slate-700">
            <button
              onClick={() => setMode("database")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                mode === "database" ? "bg-indigo-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
              }`}
            >
              Assignment Submissions
            </button>
            <button
              onClick={() => setMode("upload")}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                mode === "upload" ? "bg-indigo-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
              }`}
            >
              Upload Any Two Files
            </button>
          </div>
        }
      />

      {/* Mode 1: Database Selectors */}
      {mode === "database" ? (
        <div
          className="rounded-xl p-4 mb-3 grid grid-cols-1 md:grid-cols-3 gap-4 items-end shadow-sm"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
        >
          <div>
            <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Assignment</p>
            <select
              value={selectedAssignment}
              onChange={(e) => setSelectedAssignment(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-xs"
              style={{
                background: "var(--color-canvas)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-1)",
              }}
            >
              {assignments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title} ({a.submission_count ?? 0} subs)
                </option>
              ))}
            </select>
          </div>

          <div>
            <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Document 1 (Left)</p>
            <select
              value={leftSubId}
              onChange={(e) => setLeftSubId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-xs"
              style={{
                background: "var(--color-canvas)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-1)",
              }}
            >
              <option value="">Select submission…</option>
              {submissions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.student?.full_name || "Student"} — {s.file_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Document 2 (Right)</p>
            <select
              value={rightSubId}
              onChange={(e) => setRightSubId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-xs"
              style={{
                background: "var(--color-canvas)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-1)",
              }}
            >
              <option value="">Select submission…</option>
              {submissions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.student?.full_name || "Student"} — {s.file_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : (
        /* Mode 2: Direct File Upload */
        <div
          className="rounded-xl p-4 mb-3 grid grid-cols-1 md:grid-cols-3 gap-4 items-end shadow-sm"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
        >
          <div>
            <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-1.5">First Document (PDF, Image, Text)</p>
            <input
              type="file"
              onChange={(e) => setFileA(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
          </div>

          <div>
            <p className="font-semibold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Second Document (PDF, Image, Text)</p>
            <input
              type="file"
              onChange={(e) => setFileB(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
          </div>

          <div>
            <Btn
              variant="primary"
              size="sm"
              disabled={!fileA || !fileB || uploading}
              onClick={handleUploadCompare}
              icon={uploading ? <Spinner size={14} color="white" /> : undefined}
            >
              {uploading ? "Analyzing Documents…" : "Compare Uploaded Files"}
            </Btn>
          </div>
        </div>
      )}

      {/* Metrics & Stylometry Banner */}
      {compareResult && (
        <div
          className="rounded-xl p-4 mb-3 flex flex-wrap items-center justify-between gap-4"
          style={{
            background: "var(--color-surface)",
            border: `1px solid ${(hwScore && hwScore >= 70) || (simScore && simScore >= 60) ? "rgba(239, 68, 68, 0.4)" : "var(--color-border)"}`,
          }}
        >
          <div className="flex items-center gap-6">
            <div>
              <span className="text-2xs uppercase tracking-wider text-slate-400 font-semibold block">Text Similarity</span>
              <span
                className="font-mono text-xl font-bold"
                style={{ color: simScore >= 50 ? "#ef4444" : simScore >= 25 ? "#f59e0b" : "#22c55e" }}
              >
                {simScore !== null ? `${simScore.toFixed(1)}%` : "0%"}
              </span>
            </div>

            {hwScore !== null && (
              <div>
                <span className="text-2xs uppercase tracking-wider text-slate-400 font-semibold block">Handwriting Match</span>
                <span
                  className="font-mono text-xl font-bold"
                  style={{ color: hwScore >= 70 ? "#ef4444" : hwScore >= 40 ? "#f59e0b" : "#22c55e" }}
                >
                  {hwScore.toFixed(1)}%
                </span>
              </div>
            )}

            {compareResult.handwriting_a && compareResult.handwriting_b && (
              <div className="hidden lg:flex items-center gap-4 text-xs font-mono text-slate-400 border-l border-slate-700 pl-4">
                <div>
                  <span className="text-slate-500 block text-2xs uppercase">Slant Angle</span>
                  {compareResult.handwriting_a.slant_angle}° vs {compareResult.handwriting_b.slant_angle}°
                </div>
                <div>
                  <span className="text-slate-500 block text-2xs uppercase">Stroke Variance</span>
                  {compareResult.handwriting_a.stroke_variance} vs {compareResult.handwriting_b.stroke_variance}
                </div>
              </div>
            )}
          </div>

          <div>
            {(hwScore && hwScore >= 70) || (simScore && simScore >= 60) ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                ⚠️ Academic Integrity Alert: Suspicious Author Similarity
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                ✓ No Critical Author Match
              </span>
            )}
          </div>
        </div>
      )}

      {compareResult && (!compareResult.matching_segments || compareResult.matching_segments.length === 0) && (
        <div
          className="mb-3 px-4 py-2.5 rounded-xl text-xs flex items-center justify-between"
          style={{
            background: "rgba(59, 130, 246, 0.08)",
            border: "1px solid rgba(59, 130, 246, 0.25)",
            color: "var(--color-text-2)",
          }}
        >
          <div className="flex items-center gap-2">
            <span className="text-base">ℹ️</span>
            <span>
              <strong>Low text similarity ({Number(compareResult.similarity_score || 0).toFixed(1)}%):</strong> No duplicate text passages found between these two documents. (To inspect plagiarism, choose two submissions for the same assignment in the dropdowns above).
            </span>
          </div>
        </div>
      )}

      {/* Filter & Legend Strip */}
      <div className="flex items-center justify-between gap-4 mb-3">
        <div className="flex items-center gap-3">
          {LEGEND.map((l) => (
            <div key={l.type} className="flex items-center gap-1.5">
              <mark className={l.cls} style={{ padding: "1px 6px", fontSize: 11, borderRadius: 3, cursor: "default" }}>
                {l.label}
              </mark>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {(activeLeft != null || activeRight != null) && (
            <button
              onClick={() => {
                setActiveLeft(null);
                setActiveRight(null);
                setDetail(null);
              }}
              className="text-xs text-indigo-400 hover:underline cursor-pointer"
            >
              Clear highlight selection
            </button>
          )}

          <div className="flex gap-1">
            {(["all", "ai", "match"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setFilter(m)}
                className="px-2.5 py-1 rounded-md text-xs font-medium capitalize cursor-pointer transition-all"
                style={{
                  background: filter === m ? "var(--color-navy)" : "var(--color-canvas)",
                  color: filter === m ? "white" : "var(--color-text-2)",
                  border: `1px solid ${filter === m ? "var(--color-navy)" : "var(--color-border)"}`,
                }}
              >
                {m === "match" ? "Matching text" : m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Side-by-side Document Panels */}
      {loadingCompare ? (
        <div className="flex-1 min-h-[360px] flex flex-col items-center justify-center gap-3 bg-slate-900/30 rounded-xl border border-slate-800">
          <Spinner size={28} color="var(--color-accent)" />
          <span className="text-xs text-slate-400">Synchronizing and aligning documents…</span>
        </div>
      ) : (
        <div className="flex flex-col md:flex-row gap-4 flex-1 min-h-[420px] mb-3">
          <RenderedDocument
            doc={docLeft}
            active={activeLeft}
            onActivate={handleActivateLeft}
            filter={filter}
            scrollRef={leftRef}
          />
          <RenderedDocument
            doc={docRight}
            active={activeRight}
            onActivate={handleActivateRight}
            filter={filter}
            scrollRef={rightRef}
          />
        </div>
      )}

      {/* Detail Inspector Bar */}
      <div
        className="rounded-xl px-4 py-3 flex items-start gap-3 transition-all"
        style={{
          background: detail ? "var(--color-blue-bg)" : "var(--color-canvas)",
          border: `1px solid ${detail ? "var(--color-blue-border)" : "var(--color-border)"}`,
          minHeight: 48,
        }}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="flex-shrink-0 mt-0.5">
          <circle cx="7" cy="7" r="5.5" stroke="var(--color-blue)" strokeWidth="1.3" />
          <path d="M7 6.5V10M7 4.5v.5" stroke="var(--color-blue)" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
        <p style={{ fontSize: 13, color: detail ? "var(--color-blue)" : "var(--color-text-4)", lineHeight: 1.5 }}>
          {detail ?? "Click any highlighted passage or match to inspect cross-document alignment details."}
        </p>
      </div>
    </div>
  );
}
