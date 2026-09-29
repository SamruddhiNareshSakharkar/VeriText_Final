import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { Select } from "../../components/Field";
import { api } from "../../lib/api";

interface SubmissionRow {
  id: string;
  student: string;
  assignment: string;
  fileName: string;
  fileSize: number;
  submittedAt: string;
  status: string;
  aiScore?: number | null;
  ocrStatus?: string | null;
  ocrWordCount?: number | null;
  maxSimilarity?: number | null;
  handwritingMatchFlag?: string | null;
  aiMatchFlag?: string | null;
  autoGrade?: number | null;
  finalGrade?: number | null;
  maxMarks?: number | null;
  isGraded?: boolean;
}

const FILTERS = ["all", "flagged", "processing", "complete", "graded"] as const;

export default function Submissions() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialAssignmentId = searchParams.get("assignmentId") || "";

  const [assignments, setAssignments] = useState<any[]>([]);
  const [selectedAssignment, setSelectedAssignment] = useState(initialAssignmentId);
  const [submissions, setSubmissions] = useState<SubmissionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingAll, setProcessingAll] = useState(false);
  const [filter, setFilter] = useState<typeof FILTERS[number]>("all");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAssignmentsList() {
      try {
        const data = await api.assignments.list();
        setAssignments(data || []);
        if (!selectedAssignment && data && data.length > 0) {
          setSelectedAssignment(data[0].id);
        }
      } catch (err: any) {
        setError(err?.message || "Failed to load assignments.");
      }
    }
    loadAssignmentsList();
  }, []);

  useEffect(() => {
    if (selectedAssignment) {
      loadSubmissions(selectedAssignment);
      setSearchParams({ assignmentId: selectedAssignment });
    } else {
      setLoading(false);
    }
  }, [selectedAssignment]);

  async function loadSubmissions(assignmentId: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.assignments.getSubmissions(assignmentId);
      const currentAssignment = assignments.find((a) => a.id === assignmentId);
      const mapped: SubmissionRow[] = (data || []).map((s: any) => ({
        id: s.id,
        student: s.student?.full_name || s.student?.name || "Student",
        assignment: currentAssignment?.title || "Assignment",
        fileName: s.file_name || "Unnamed file",
        fileSize: Number(s.file_size) || 0,
        submittedAt: s.submitted_at ? new Date(s.submitted_at).toLocaleString() : "—",
        status: s.status || "complete",
        aiScore: s.ai_score,
        ocrStatus: s.ocr_status,
        ocrWordCount: s.ocr_word_count,
        maxSimilarity: s.max_similarity,
        handwritingMatchFlag: s.handwriting_match_flag,
        aiMatchFlag: s.ai_match_flag,
        autoGrade: s.auto_grade,
        finalGrade: s.final_grade,
        maxMarks: s.max_marks ?? currentAssignment?.max_marks ?? 100,
        isGraded: s.is_graded,
      }));
      setSubmissions(mapped);
    } catch (err: any) {
      setError(err?.message || "Failed to load submissions.");
    } finally {
      setLoading(false);
    }
  }

  async function handleProcessAll() {
    if (!selectedAssignment) return;
    setProcessingAll(true);
    try {
      await api.assignments.processAll(selectedAssignment);
      await loadSubmissions(selectedAssignment);
    } catch (err: any) {
      alert(err?.message || "Batch analysis failed.");
    } finally {
      setProcessingAll(false);
    }
  }

  const flaggedList = submissions.filter(
    (s) => s.handwritingMatchFlag || s.aiMatchFlag
  );

  const filtered = submissions.filter((s) => {
    let matchFilter = true;
    if (filter === "flagged") {
      matchFilter = Boolean(s.handwritingMatchFlag || s.aiMatchFlag || (s.aiScore && s.aiScore >= 60));
    } else if (filter === "processing") {
      matchFilter = s.status.toLowerCase().includes("processing") || s.status.toLowerCase().includes("queued");
    } else if (filter === "complete") {
      matchFilter = s.status.toLowerCase().includes("complete");
    } else if (filter === "graded") {
      matchFilter = Boolean(s.isGraded || s.finalGrade !== null);
    }

    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      s.student.toLowerCase().includes(q) ||
      (s.fileName || "").toLowerCase().includes(q);
    return matchFilter && matchSearch;
  });

  // #region agent log
  fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId:'C',location:'Submissions.tsx:render',message:'teacher submissions render',data:{loading,hasError:Boolean(error),assignmentCount:assignments.length,submissionCount:submissions.length,flaggedCount:flaggedList.length,filteredCount:filtered.length,selectedAssignment:Boolean(selectedAssignment)},timestamp:Date.now()})}).catch(()=>{});
  // #endregion

  return (
    <div>
      <PageHeader
        title="Submissions"
        subtitle="Review student submissions, integrity scans, OCR transcripts, and auto-grading."
        actions={
          <div className="flex items-center gap-2">
            <Btn
              variant="primary"
              size="sm"
              disabled={processingAll || !selectedAssignment || submissions.length === 0}
              onClick={handleProcessAll}
              icon={
                processingAll ? (
                  <Spinner size={13} color="white" />
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                )
              }
            >
              {processingAll ? "Running OCR & Integrity Scan…" : "Run OCR & Integrity Scan on All"}
            </Btn>

            <Btn
              variant="outline"
              size="sm"
              onClick={() => navigate("/teacher/compare")}
              icon={
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <rect x="1" y="2" width="4" height="8" rx="0.5" stroke="currentColor" strokeWidth="1.3" />
                  <rect x="7" y="2" width="4" height="8" rx="0.5" stroke="currentColor" strokeWidth="1.3" />
                </svg>
              }
            >
              Compare Submissions
            </Btn>
          </div>
        }
      />

      {/* Flagged Alert Banner */}
      {flaggedList.length > 0 && (
        <div
          className="p-4 rounded-xl mb-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm"
          style={{
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-rose-500/20 text-rose-500 font-bold text-sm shrink-0">
              ⚠️
            </div>
            <div>
              <p className="font-semibold text-sm text-rose-500">
                Academic Integrity Alert: {flaggedList.length} Flagged Submission{flaggedList.length > 1 ? "s" : ""}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Submissions in this assignment exhibit overlapping handwriting stylometry cosine similarity (≥70%) or identical AI/text content (≥60%).
              </p>
            </div>
          </div>
          <Btn
            variant="outline"
            size="xs"
            onClick={() => navigate("/teacher/compare")}
          >
            Open Side-by-Side Comparison →
          </Btn>
        </div>
      )}

      {/* Assignment selector & Filter bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-2 max-w-sm w-full">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap">
            Assignment:
          </span>
          <Select
            value={selectedAssignment}
            onChange={(e) => setSelectedAssignment(e.target.value)}
          >
            <option value="">Select assignment…</option>
            {assignments.map((a) => (
              <option key={a.id} value={a.id}>
                {a.title} ({a.submission_count ?? 0})
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search student or file…"
            className="px-3 py-1.5 rounded-lg text-xs"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-1)",
              minWidth: 180,
            }}
          />
          <div className="flex gap-1">
            {FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition-all cursor-pointer"
                style={{
                  background: filter === f ? "var(--color-navy)" : "var(--color-surface)",
                  color: filter === f ? "white" : "var(--color-text-2)",
                  border: `1px solid ${filter === f ? "var(--color-navy)" : "var(--color-border)"}`,
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading submissions…</span>
        </div>
      ) : error ? (
        <div
          className="p-4 rounded-xl mb-6 text-sm flex items-center justify-between"
          style={{
            background: "var(--color-red-bg)",
            border: "1px solid var(--color-red-border)",
            color: "var(--color-red)",
          }}
        >
          <span>{error}</span>
          <Btn variant="ghost" size="xs" onClick={() => selectedAssignment && loadSubmissions(selectedAssignment)}>
            Retry
          </Btn>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M4 4v12a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7l-4-4H5a1 1 0 0 0-1 1z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M11 3v4h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          }
          title={submissions.length === 0 ? "No submissions yet" : "No results"}
          description={
            submissions.length === 0
              ? "Students have not uploaded any submissions for this assignment yet."
              : "No submissions match your search or filter criteria."
          }
        />
      ) : (
        <div
          className="rounded-xl overflow-x-auto shadow-sm"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
        >
          <table className="w-full text-left border-collapse">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Student & File
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  OCR Status
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  AI Score
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Peer Similarity
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Integrity Flags
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs" style={{ color: "var(--color-text-3)" }}>
                  Grade
                </th>
                <th className="px-4 py-3 font-semibold uppercase tracking-wider text-xs text-right" style={{ color: "var(--color-text-3)" }}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const hasFlags = Boolean(s.handwritingMatchFlag || s.aiMatchFlag);
                const aiNum = s.aiScore != null ? Number(s.aiScore) : NaN;
                const aiVal = !isNaN(aiNum) ? aiNum : null;
                const simNum = s.maxSimilarity != null ? Number(s.maxSimilarity) : NaN;
                const simVal = !isNaN(simNum) ? simNum : null;

                return (
                  <tr
                    key={s.id}
                    style={{ borderBottom: "1px solid var(--color-border)" }}
                    className="cursor-pointer transition-colors"
                    onClick={() => navigate(`/teacher/submissions/${s.id}`)}
                    onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                    onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}
                  >
                    {/* Student & File */}
                    <td className="px-4 py-3.5">
                      <p className="font-semibold text-sm" style={{ color: "var(--color-text-1)" }}>
                        {s.student}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-xs text-indigo-400">
                          {s.fileName}
                        </span>
                        <span className="text-xs text-slate-400">
                          • {(s.fileSize / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    </td>

                    {/* OCR Status */}
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col gap-1 items-start">
                        <StatusBadge status={s.ocrStatus || s.status} size="xs" />
                        {s.ocrWordCount !== undefined && s.ocrWordCount !== null && (
                          <span className="font-mono text-xs text-slate-400">
                            {s.ocrWordCount} words
                          </span>
                        )}
                      </div>
                    </td>

                    {/* AI Score */}
                    <td className="px-4 py-3.5">
                      {aiVal !== null ? (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold"
                          style={{
                            background: aiVal >= 60 ? "rgba(239, 68, 68, 0.15)" : aiVal >= 30 ? "rgba(245, 158, 11, 0.15)" : "rgba(34, 197, 94, 0.15)",
                            color: aiVal >= 60 ? "#ef4444" : aiVal >= 30 ? "#f59e0b" : "#22c55e",
                            border: `1px solid ${aiVal >= 60 ? "rgba(239, 68, 68, 0.3)" : aiVal >= 30 ? "rgba(245, 158, 11, 0.3)" : "rgba(34, 197, 94, 0.3)"}`
                          }}
                        >
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: "currentColor" }} />
                          {aiVal.toFixed(1)}% AI
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </td>

                    {/* Peer Similarity */}
                    <td className="px-4 py-3.5">
                      {simVal !== null ? (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold"
                          style={{
                            background: simVal >= 50 ? "rgba(239, 68, 68, 0.15)" : simVal >= 25 ? "rgba(245, 158, 11, 0.15)" : "rgba(148, 163, 184, 0.15)",
                            color: simVal >= 50 ? "#ef4444" : simVal >= 25 ? "#f59e0b" : "#94a3b8",
                            border: `1px solid ${simVal >= 50 ? "rgba(239, 68, 68, 0.3)" : simVal >= 25 ? "rgba(245, 158, 11, 0.3)" : "rgba(148, 163, 184, 0.3)"}`
                          }}
                        >
                          {simVal.toFixed(1)}% Match
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </td>

                    {/* Integrity Flags */}
                    <td className="px-4 py-3.5">
                      {hasFlags ? (
                        <div className="flex flex-col gap-1">
                          {s.handwritingMatchFlag && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
                              ✍️ {s.handwritingMatchFlag}
                            </span>
                          )}
                          {s.aiMatchFlag && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
                              📋 {s.aiMatchFlag}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
                          ✓ Verified clean
                        </span>
                      )}
                    </td>

                    {/* Grade */}
                    <td className="px-4 py-3.5 font-mono text-xs">
                      {s.finalGrade !== null && s.finalGrade !== undefined ? (
                        <div>
                          <span className="font-semibold text-emerald-400">
                            {s.finalGrade} / {s.maxMarks}
                          </span>
                          <span className="text-slate-400 ml-1 text-2xs block">
                            {s.isGraded ? "Graded" : "Auto-calculated"}
                          </span>
                        </div>
                      ) : s.autoGrade !== null && s.autoGrade !== undefined ? (
                        <span className="text-slate-300">
                          Auto: {s.autoGrade} / {s.maxMarks}
                        </span>
                      ) : (
                        <span className="text-slate-500">Ungraded</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="px-4 py-3.5 text-right">
                      <span className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:underline">
                        Inspect & Grade →
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
