import { useState, useEffect, useMemo, useRef } from "react";
import Btn from "../../components/Btn";
import PageHeader from "../../components/PageHeader";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

type ReportType = "comprehensive" | "integrity_summary" | "grading_breakdown";
type GenState = "idle" | "generating" | "done" | "error";
type ActiveTab = "analytics" | "leaderboard" | "timeline" | "archives";

async function downloadReport(reportId: string, title: string) {
  const token = localStorage.getItem("veritext_token");
  const res = await fetch(`/api/v1/reports/${reportId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error("Download failed. Please try again.");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/\s+/g, "_")}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ─── Animated Radial Gauge ─── */
function RadialGauge({
  value,
  label,
  color,
  glowColor,
  icon,
  size = 130,
  suffix = "%",
  subtext,
}: {
  value: number;
  label: string;
  color: string;
  glowColor: string;
  icon: string;
  size?: number;
  suffix?: string;
  subtext?: string;
}) {
  const [animVal, setAnimVal] = useState(0);
  const r = (size - 14) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (animVal / 100) * circ;

  useEffect(() => {
    const timer = setTimeout(() => setAnimVal(Math.min(100, Math.max(0, value))), 100);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className="flex flex-col items-center gap-2 group">
      <div style={{ width: size, height: size, position: "relative" }}>
        {/* Glow background */}
        <div
          className="absolute inset-0 rounded-full opacity-30 blur-xl transition-opacity duration-700 group-hover:opacity-50"
          style={{ background: glowColor }}
        />
        <svg width={size} height={size} className="relative z-10">
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-border)"
            strokeWidth="10"
            opacity="0.4"
          />
          {/* Active arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{
              transition: "stroke-dashoffset 1.2s cubic-bezier(0.22, 1, 0.36, 1)",
              filter: `drop-shadow(0 0 8px ${glowColor})`,
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center z-20">
          <span className="text-lg mb-0.5">{icon}</span>
          <span
            className="font-mono font-bold"
            style={{ fontSize: size > 110 ? 22 : 16, color: "var(--color-text-1)" }}
          >
            {Math.round(animVal)}{suffix}
          </span>
        </div>
      </div>
      <p className="font-semibold text-xs text-center" style={{ color: "var(--color-text-2)" }}>
        {label}
      </p>
      {subtext && (
        <p className="text-[10px] text-center font-mono" style={{ color: "var(--color-text-4)" }}>
          {subtext}
        </p>
      )}
    </div>
  );
}

/* ─── Scatter Plot (Similarity vs AI) ─── */
function ScatterPlot({ submissions }: { submissions: any[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<any>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const W = 600, H = 320;
  const pad = { top: 30, right: 30, bottom: 50, left: 55 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;

  const points = useMemo(
    () =>
      submissions.map((s) => ({
        id: s.id,
        name: s.student?.full_name || s.student?.name || "Student",
        sim: Number(s.max_similarity || s.similarity_score || 0),
        ai: Number(s.ai_score || 0),
        grade: s.grade_score ?? null,
      })),
    [submissions]
  );

  function getColor(sim: number, ai: number) {
    const max = Math.max(sim, ai);
    if (max > 50) return "#ef4444";
    if (max >= 25) return "#f59e0b";
    return "#10b981";
  }

  return (
    <div className="relative w-full overflow-hidden">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-auto"
        style={{ maxHeight: 340 }}
      >
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={`grid-${v}`}>
            <line
              x1={pad.left}
              y1={pad.top + ph - (v / 100) * ph}
              x2={pad.left + pw}
              y2={pad.top + ph - (v / 100) * ph}
              stroke="var(--color-border)"
              strokeWidth="0.5"
              strokeDasharray="4 4"
            />
            <text
              x={pad.left - 8}
              y={pad.top + ph - (v / 100) * ph + 4}
              textAnchor="end"
              fontSize="10"
              fill="var(--color-text-4)"
              fontFamily="var(--font-mono)"
            >
              {v}%
            </text>
            <line
              x1={pad.left + (v / 100) * pw}
              y1={pad.top}
              x2={pad.left + (v / 100) * pw}
              y2={pad.top + ph}
              stroke="var(--color-border)"
              strokeWidth="0.5"
              strokeDasharray="4 4"
            />
            <text
              x={pad.left + (v / 100) * pw}
              y={H - pad.bottom + 18}
              textAnchor="middle"
              fontSize="10"
              fill="var(--color-text-4)"
              fontFamily="var(--font-mono)"
            >
              {v}%
            </text>
          </g>
        ))}

        {/* Danger zone rectangle */}
        <rect
          x={pad.left + (50 / 100) * pw}
          y={pad.top}
          width={(50 / 100) * pw}
          height={(50 / 100) * ph}
          fill="rgba(239, 68, 68, 0.06)"
          rx="4"
        />
        <text
          x={pad.left + (75 / 100) * pw}
          y={pad.top + 16}
          textAnchor="middle"
          fontSize="9"
          fill="rgba(239, 68, 68, 0.4)"
          fontFamily="var(--font-sans)"
          fontWeight="600"
        >
          ⚠ HIGH RISK ZONE
        </text>

        {/* Axis labels */}
        <text
          x={pad.left + pw / 2}
          y={H - 6}
          textAnchor="middle"
          fontSize="11"
          fill="var(--color-text-3)"
          fontFamily="var(--font-sans)"
          fontWeight="600"
        >
          Peer Similarity Score →
        </text>
        <text
          x={14}
          y={pad.top + ph / 2}
          textAnchor="middle"
          fontSize="11"
          fill="var(--color-text-3)"
          fontFamily="var(--font-sans)"
          fontWeight="600"
          transform={`rotate(-90, 14, ${pad.top + ph / 2})`}
        >
          AI Probability →
        </text>

        {/* Data points */}
        {points.map((p, i) => {
          const cx = pad.left + (p.sim / 100) * pw;
          const cy = pad.top + ph - (p.ai / 100) * ph;
          return (
            <g key={p.id || i}>
              <circle
                cx={cx}
                cy={cy}
                r={hovered?.id === p.id ? 8 : 5.5}
                fill={getColor(p.sim, p.ai)}
                opacity={hovered && hovered.id !== p.id ? 0.3 : 0.85}
                stroke="white"
                strokeWidth="1.5"
                style={{
                  transition: "all 0.25s ease",
                  cursor: "pointer",
                  filter: hovered?.id === p.id ? `drop-shadow(0 0 6px ${getColor(p.sim, p.ai)})` : "none",
                }}
                onMouseEnter={(e) => {
                  setHovered(p);
                  const svg = svgRef.current;
                  if (svg) {
                    const rect = svg.getBoundingClientRect();
                    const scaleX = rect.width / W;
                    const scaleY = rect.height / H;
                    setTooltipPos({ x: cx * scaleX, y: cy * scaleY });
                  }
                }}
                onMouseLeave={() => setHovered(null)}
              />
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hovered && (
        <div
          className="absolute z-50 pointer-events-none animate-fade-in"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 10,
            transform: "translateY(-100%)",
          }}
        >
          <div
            className="rounded-xl px-3.5 py-2.5 shadow-lg text-xs"
            style={{
              background: "var(--color-navy)",
              color: "white",
              border: "1px solid var(--color-navy-border)",
              minWidth: 160,
            }}
          >
            <p className="font-semibold text-[11px] mb-1">{hovered.name}</p>
            <div className="flex items-center gap-3 font-mono text-[10.5px]">
              <span>
                SIM: <span style={{ color: "#60a5fa" }}>{hovered.sim}%</span>
              </span>
              <span>
                AI: <span style={{ color: "#c084fc" }}>{hovered.ai}%</span>
              </span>
            </div>
            {hovered.grade != null && (
              <p className="mt-1 text-[10px] opacity-70">Grade: {hovered.grade}/100</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Expandable Student Card ─── */
function StudentDetailCard({ sub, rank }: { sub: any; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const sim = Number(sub.max_similarity || sub.similarity_score || 0);
  const ai = Number(sub.ai_score || 0);
  const maxScore = Math.max(sim, ai);
  const riskColor =
    maxScore > 50 ? "var(--color-red)" : maxScore >= 25 ? "var(--color-amber)" : "var(--color-green)";
  const riskBg =
    maxScore > 50 ? "var(--color-red-bg)" : maxScore >= 25 ? "var(--color-amber-bg)" : "var(--color-green-bg)";
  const riskLabel = maxScore > 50 ? "High Risk" : maxScore >= 25 ? "Review" : "Clean";

  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-300 card-hover"
      style={{
        background: "var(--color-surface)",
        border: `1px solid ${expanded ? riskColor : "var(--color-border)"}`,
        boxShadow: expanded ? `0 0 0 1px ${riskColor}20, 0 4px 16px ${riskColor}10` : "none",
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3.5 flex items-center gap-3 cursor-pointer text-left"
      >
        {/* Rank badge */}
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center font-mono font-bold text-xs shrink-0"
          style={{
            background: rank <= 3 ? "var(--color-navy)" : "var(--color-canvas)",
            color: rank <= 3 ? "white" : "var(--color-text-3)",
            border: rank > 3 ? "1px solid var(--color-border)" : "none",
          }}
        >
          #{rank}
        </div>

        {/* Name */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-xs truncate" style={{ color: "var(--color-text-1)" }}>
            {sub.student?.full_name || sub.student?.name || "Student"}
          </p>
          <p className="text-[10.5px] font-mono truncate" style={{ color: "var(--color-text-4)" }}>
            {sub.student?.email || sub.id?.slice(0, 12)}
          </p>
        </div>

        {/* Score pills */}
        <div className="flex items-center gap-2 shrink-0">
          <span
            className="px-2 py-0.5 rounded-md font-mono text-[10.5px] font-bold"
            style={{
              background: sim > 50 ? "var(--color-red-bg)" : "var(--color-blue-bg)",
              color: sim > 50 ? "var(--color-red)" : "var(--color-blue)",
            }}
          >
            SIM {sim}%
          </span>
          <span
            className="px-2 py-0.5 rounded-md font-mono text-[10.5px] font-bold"
            style={{
              background: ai > 50 ? "var(--color-red-bg)" : "var(--color-violet-bg)",
              color: ai > 50 ? "var(--color-red)" : "var(--color-violet)",
            }}
          >
            AI {ai}%
          </span>
        </div>

        {/* Risk badge */}
        <span
          className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider shrink-0"
          style={{ background: riskBg, color: riskColor }}
        >
          {riskLabel}
        </span>

        {/* Chevron */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--color-text-4)"
          strokeWidth="2"
          className="shrink-0 transition-transform duration-300"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0)" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div
          className="px-4 pb-4 pt-2 animate-fade-in"
          style={{ borderTop: "1px solid var(--color-border)" }}
        >
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
            <div className="rounded-lg p-2.5" style={{ background: "var(--color-canvas)" }}>
              <p className="text-[9.5px] uppercase font-bold tracking-wider" style={{ color: "var(--color-text-4)" }}>
                Similarity Score
              </p>
              <p className="font-mono font-bold text-sm mt-0.5" style={{ color: sim > 50 ? "var(--color-red)" : "var(--color-text-1)" }}>
                {sim}%
              </p>
            </div>
            <div className="rounded-lg p-2.5" style={{ background: "var(--color-canvas)" }}>
              <p className="text-[9.5px] uppercase font-bold tracking-wider" style={{ color: "var(--color-text-4)" }}>
                AI Probability
              </p>
              <p className="font-mono font-bold text-sm mt-0.5" style={{ color: ai > 50 ? "var(--color-red)" : "var(--color-text-1)" }}>
                {ai}%
              </p>
            </div>
            <div className="rounded-lg p-2.5" style={{ background: "var(--color-canvas)" }}>
              <p className="text-[9.5px] uppercase font-bold tracking-wider" style={{ color: "var(--color-text-4)" }}>
                Handwriting
              </p>
              <p className="font-mono font-bold text-sm mt-0.5" style={{ color: "var(--color-text-1)" }}>
                {sub.handwriting_score != null ? `${sub.handwriting_score}%` : "N/A"}
              </p>
            </div>
            <div className="rounded-lg p-2.5" style={{ background: "var(--color-canvas)" }}>
              <p className="text-[9.5px] uppercase font-bold tracking-wider" style={{ color: "var(--color-text-4)" }}>
                Grade
              </p>
              <p className="font-mono font-bold text-sm mt-0.5" style={{ color: "var(--color-text-1)" }}>
                {sub.grade_score != null ? `${sub.grade_score}/100` : "Pending"}
              </p>
            </div>
          </div>

          {/* OCR & AI extracted details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {sub.ocr_preview && (
              <div className="rounded-lg p-3" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                <p className="text-[10px] uppercase font-bold tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: "var(--color-blue)" }}>
                  <span>📝</span> OCR Extract Preview
                </p>
                <p className="text-[11px] leading-relaxed line-clamp-4 font-mono" style={{ color: "var(--color-text-2)" }}>
                  {sub.ocr_preview}
                </p>
              </div>
            )}
            {sub.ai_flags && sub.ai_flags.length > 0 && (
              <div className="rounded-lg p-3" style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)" }}>
                <p className="text-[10px] uppercase font-bold tracking-wider mb-1.5 flex items-center gap-1.5" style={{ color: "var(--color-red)" }}>
                  <span>🤖</span> AI Detection Flags
                </p>
                <ul className="space-y-1">
                  {sub.ai_flags.map((flag: string, i: number) => (
                    <li key={i} className="text-[11px]" style={{ color: "var(--color-red)" }}>
                      • {flag}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="mt-3 flex items-center justify-end gap-2">
            <a
              href={`/teacher/submissions/${sub.id}`}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
              style={{
                background: "var(--color-accent-bg)",
                color: "var(--color-accent)",
                border: "1px solid var(--color-accent-ring)",
              }}
            >
              Full Inspection →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Submission Timeline Heatmap ─── */
function SubmissionTimeline({ submissions }: { submissions: any[] }) {
  const hourBuckets = useMemo(() => {
    const buckets = new Array(24).fill(0);
    submissions.forEach((s) => {
      if (s.created_at || s.submitted_at) {
        const d = new Date(s.created_at || s.submitted_at);
        buckets[d.getHours()]++;
      }
    });
    return buckets;
  }, [submissions]);

  const dayBuckets = useMemo(() => {
    const map: Record<string, number> = {};
    submissions.forEach((s) => {
      if (s.created_at || s.submitted_at) {
        const d = new Date(s.created_at || s.submitted_at);
        const key = d.toISOString().split("T")[0];
        map[key] = (map[key] || 0) + 1;
      }
    });
    return map;
  }, [submissions]);

  const maxHour = Math.max(1, ...hourBuckets);
  const dayEntries = Object.entries(dayBuckets).sort((a, b) => a[0].localeCompare(b[0]));
  const maxDay = Math.max(1, ...Object.values(dayBuckets));

  return (
    <div className="space-y-6">
      {/* Hourly Distribution */}
      <div>
        <h4 className="font-bold text-xs mb-3 flex items-center gap-2" style={{ color: "var(--color-text-2)" }}>
          <span>🕐</span> Submission Hour Distribution (24h)
        </h4>
        <div className="flex items-end gap-1 h-28 px-1">
          {hourBuckets.map((count, h) => {
            const pct = count / maxHour;
            const isLate = h >= 22 || h <= 5;
            return (
              <div
                key={h}
                className="flex-1 flex flex-col items-center justify-end group"
                title={`${h}:00 — ${count} submission${count !== 1 ? "s" : ""}`}
              >
                <div
                  className="w-full rounded-t-sm transition-all duration-500 group-hover:brightness-110"
                  style={{
                    height: `${Math.max(4, pct * 100)}%`,
                    background: isLate
                      ? `linear-gradient(to top, #ef4444, #f87171)`
                      : count > 0
                      ? `linear-gradient(to top, var(--color-accent), #60a5fa)`
                      : "var(--color-border)",
                    opacity: count > 0 ? 0.85 : 0.3,
                    minHeight: 4,
                  }}
                />
                <span
                  className="text-[8px] font-mono mt-1"
                  style={{ color: isLate && count > 0 ? "var(--color-red)" : "var(--color-text-4)" }}
                >
                  {h}
                </span>
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-between mt-2 text-[10px]" style={{ color: "var(--color-text-4)" }}>
          <span>🟦 Normal hours</span>
          <span>🟥 Late night (10PM–6AM)</span>
        </div>
      </div>

      {/* Day-by-day heatmap */}
      {dayEntries.length > 0 && (
        <div>
          <h4 className="font-bold text-xs mb-3 flex items-center gap-2" style={{ color: "var(--color-text-2)" }}>
            <span>📅</span> Daily Submission Volume
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {dayEntries.map(([date, count]) => {
              const intensity = count / maxDay;
              return (
                <div
                  key={date}
                  className="rounded-md flex items-center justify-center transition-all hover:scale-110"
                  style={{
                    width: 36,
                    height: 36,
                    background:
                      intensity > 0.75
                        ? "var(--color-accent)"
                        : intensity > 0.5
                        ? "#60a5fa"
                        : intensity > 0.25
                        ? "#93c5fd"
                        : "#dbeafe",
                    color: intensity > 0.5 ? "white" : "var(--color-text-2)",
                  }}
                  title={`${date}: ${count} submission${count !== 1 ? "s" : ""}`}
                >
                  <div className="text-center">
                    <span className="font-mono text-[10px] font-bold block leading-none">{count}</span>
                    <span className="text-[7px] block leading-none mt-0.5">
                      {new Date(date).toLocaleDateString("en", { month: "short", day: "numeric" })}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════ */
/* MAIN COMPONENT                                                  */
/* ═══════════════════════════════════════════════════════════════ */
export default function Reports() {
  const [assignments, setAssignments] = useState<any[]>([]);
  const [selectedAssignment, setSelectedAssignment] = useState("");
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [reportType, setReportType] = useState<ReportType>("comprehensive");
  const [reportTitle, setReportTitle] = useState("");
  const [state, setState] = useState<GenState>("idle");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [newReport, setNewReport] = useState<any>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("analytics");
  const [leaderboardSort, setLeaderboardSort] = useState<"risk" | "sim" | "ai" | "name">("risk");

  // Load assignments on mount
  useEffect(() => {
    async function loadAssignments() {
      try {
        const list = await api.assignments.list();
        setAssignments(list || []);
        if (list && list.length > 0) {
          setSelectedAssignment(list[0].id);
        }
      } catch (err) {
        console.error("Failed to load assignments", err);
      }
    }
    loadAssignments();
  }, []);

  // Load submissions and report history when assignment changes
  useEffect(() => {
    if (!selectedAssignment) return;

    async function loadAssignmentData() {
      setLoadingHistory(true);
      try {
        const [subs, repList] = await Promise.all([
          api.assignments.getSubmissions(selectedAssignment),
          api.reports.list(selectedAssignment),
        ]);
        setSubmissions(subs || []);
        setReports(repList || []);
      } catch (err) {
        console.error("Failed to load assignment data", err);
      } finally {
        setLoadingHistory(false);
      }
    }
    loadAssignmentData();
  }, [selectedAssignment]);

  async function handleGenerateReport() {
    if (!selectedAssignment) return;
    setState("generating");
    setNewReport(null);
    try {
      const current = assignments.find((a) => a.id === selectedAssignment);
      const title = reportTitle || `Integrity & Grading Report: ${current?.title || "Assignment"}`;
      const res = await api.reports.generate(selectedAssignment, {
        report_type: reportType,
        title,
      });
      setNewReport(res);
      setState("done");
      // Refresh report history
      const updatedList = await api.reports.list(selectedAssignment);
      setReports(updatedList || []);
    } catch (err: any) {
      alert(err?.message || "Failed to generate report.");
      setState("error");
    }
  }

  async function handleDownload(reportId: string, title: string) {
    setDownloading(reportId);
    try {
      await downloadReport(reportId, title);
    } catch (err: any) {
      alert(err?.message || "Download failed.");
    } finally {
      setDownloading(null);
    }
  }

  // Analytics Computation
  const analytics = useMemo(() => {
    const total = submissions.length;
    if (total === 0) {
      return {
        total: 0,
        avgSim: 0,
        avgAi: 0,
        complianceRate: 100,
        riskClean: 0,
        riskReview: 0,
        riskFlagged: 0,
        simHistogram: [0, 0, 0, 0, 0],
        aiHistogram: [0, 0, 0, 0, 0],
        flaggedList: [],
        avgGrade: 0,
        gradedCount: 0,
      };
    }

    let simSum = 0;
    let aiSum = 0;
    let gradeSum = 0;
    let gradedCount = 0;
    let cleanCount = 0;
    let reviewCount = 0;
    let flagCount = 0;
    const simHist = [0, 0, 0, 0, 0];
    const aiHist = [0, 0, 0, 0, 0];
    const flags: any[] = [];

    submissions.forEach((s) => {
      const sim = Number(s.max_similarity || s.similarity_score || 0);
      const ai = Number(s.ai_score || 0);
      simSum += sim;
      aiSum += ai;

      if (s.grade_score != null) {
        gradeSum += Number(s.grade_score);
        gradedCount++;
      }

      // Risk categories
      const maxScore = Math.max(sim, ai);
      if (maxScore > 50 || s.handwriting_match_flag || s.ai_match_flag) {
        flagCount++;
        flags.push({
          id: s.id,
          name: s.student?.full_name || s.student?.name || "Student",
          sim,
          ai,
          flag: s.handwriting_match_flag || s.ai_match_flag || "Elevated Similarity",
        });
      } else if (maxScore >= 25) {
        reviewCount++;
      } else {
        cleanCount++;
      }

      // Histogram buckets: 0-20, 21-40, 41-60, 61-80, 81-100
      const simBucket = Math.min(4, Math.floor(sim / 20));
      simHist[simBucket]++;

      const aiBucket = Math.min(4, Math.floor(ai / 20));
      aiHist[aiBucket]++;
    });

    const avgSim = Math.round(simSum / total);
    const avgAi = Math.round(aiSum / total);
    const complianceRate = Math.round((cleanCount / total) * 100);
    const avgGrade = gradedCount > 0 ? Math.round(gradeSum / gradedCount) : 0;

    return {
      total,
      avgSim,
      avgAi,
      complianceRate,
      riskClean: cleanCount,
      riskReview: reviewCount,
      riskFlagged: flagCount,
      simHistogram: simHist,
      aiHistogram: aiHist,
      flaggedList: flags,
      avgGrade,
      gradedCount,
    };
  }, [submissions]);

  // Sorted leaderboard
  const sortedSubmissions = useMemo(() => {
    const sorted = [...submissions];
    sorted.sort((a, b) => {
      const aSim = Number(a.max_similarity || a.similarity_score || 0);
      const bSim = Number(b.max_similarity || b.similarity_score || 0);
      const aAi = Number(a.ai_score || 0);
      const bAi = Number(b.ai_score || 0);

      switch (leaderboardSort) {
        case "risk":
          return Math.max(bSim, bAi) - Math.max(aSim, aAi);
        case "sim":
          return bSim - aSim;
        case "ai":
          return bAi - aAi;
        case "name":
          return (a.student?.full_name || a.student?.name || "").localeCompare(
            b.student?.full_name || b.student?.name || ""
          );
        default:
          return 0;
      }
    });
    return sorted;
  }, [submissions, leaderboardSort]);

  const selectedAssgnObj = assignments.find((a) => a.id === selectedAssignment);

  const maxHistCount = Math.max(1, ...analytics.simHistogram, ...analytics.aiHistogram);

  const TABS: { id: ActiveTab; label: string; icon: string; count?: number }[] = [
    { id: "analytics", label: "Analytics & Insights", icon: "📊" },
    { id: "leaderboard", label: "Class Leaderboard", icon: "🏆", count: submissions.length },
    { id: "timeline", label: "Timeline & Heatmap", icon: "📅" },
    { id: "archives", label: "PDF Reports", icon: "📑", count: reports.length },
  ];

  return (
    <div className="space-y-6">
      {/* ─── Hero Header ─── */}
      <div
        className="-mx-7 -mt-6 px-7 pt-7 pb-7 mb-2 animate-fade-in"
        style={{
          background: "linear-gradient(135deg, #09182E 0%, #112347 35%, #1A3260 65%, #2255D3 100%)",
          borderBottom: "1px solid var(--color-navy-border)",
        }}
      >
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                style={{
                  background: "rgba(255,255,255,0.1)",
                  color: "rgba(255,255,255,0.8)",
                  backdropFilter: "blur(8px)",
                  border: "1px solid rgba(255,255,255,0.1)",
                }}
              >
                <span
                  className="w-2 h-2 rounded-full bg-emerald-400"
                  style={{ animation: "pulse-glow 2s ease-in-out infinite" }}
                />
                Reports & Analytics
              </span>
            </div>
            <h1
              className="font-sans text-white font-bold tracking-tight"
              style={{ fontSize: 26 }}
            >
              Integrity Intelligence Dashboard
            </h1>
            <p
              className="mt-1.5"
              style={{
                fontSize: 13,
                color: "rgba(255,255,255,0.6)",
                lineHeight: 1.5,
                maxWidth: 520,
              }}
            >
              Visual integrity analytics, AI detection patterns, class-level plagiarism scatter analysis, and official PDF report generation.
            </p>
          </div>

          <select
            value={selectedAssignment}
            onChange={(e) => setSelectedAssignment(e.target.value)}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer outline-none"
            style={{
              background: "rgba(255,255,255,0.1)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "white",
              backdropFilter: "blur(8px)",
            }}
          >
            {assignments.map((a) => (
              <option key={a.id} value={a.id} style={{ background: "#09182E", color: "white" }}>
                {a.title} ({a.submission_count ?? 0} submissions)
              </option>
            ))}
          </select>
        </div>

        {/* ─── Hero Gauge Cluster ─── */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6 pt-5" style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <div className="flex flex-col items-center animate-fade-in-up anim-delay-1">
            <RadialGauge
              value={analytics.complianceRate}
              label="Integrity Score"
              color="#10b981"
              glowColor="rgba(16, 185, 129, 0.3)"
              icon="🛡️"
              subtext={`${analytics.riskClean} clean`}
            />
          </div>
          <div className="flex flex-col items-center animate-fade-in-up anim-delay-2">
            <RadialGauge
              value={analytics.avgSim}
              label="Avg. Similarity"
              color="#3b82f6"
              glowColor="rgba(59, 130, 246, 0.3)"
              icon="🔍"
              subtext="peer match"
            />
          </div>
          <div className="flex flex-col items-center animate-fade-in-up anim-delay-3">
            <RadialGauge
              value={analytics.avgAi}
              label="Avg. AI Score"
              color="#a855f7"
              glowColor="rgba(168, 85, 247, 0.3)"
              icon="🤖"
              subtext="detection"
            />
          </div>
          <div className="flex flex-col items-center animate-fade-in-up anim-delay-4">
            <RadialGauge
              value={analytics.total > 0 ? Math.round(((analytics.total - analytics.riskFlagged) / analytics.total) * 100) : 100}
              label="Pass Rate"
              color={analytics.riskFlagged > 0 ? "#f59e0b" : "#10b981"}
              glowColor={analytics.riskFlagged > 0 ? "rgba(245, 158, 11, 0.3)" : "rgba(16, 185, 129, 0.3)"}
              icon="✅"
              subtext={`${analytics.riskFlagged} flagged`}
            />
          </div>
          <div className="flex flex-col items-center animate-fade-in-up anim-delay-5">
            <RadialGauge
              value={analytics.avgGrade}
              label="Avg. Grade"
              color="#0ea5e9"
              glowColor="rgba(14, 165, 233, 0.3)"
              icon="📝"
              subtext={`${analytics.gradedCount} graded`}
            />
          </div>
        </div>
      </div>

      {/* ─── Tab Navigation ─── */}
      <div
        className="flex items-center gap-1 p-1 rounded-xl"
        style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-bold transition-all cursor-pointer"
            style={{
              background: activeTab === t.id ? "var(--color-surface)" : "transparent",
              color: activeTab === t.id ? "var(--color-accent)" : "var(--color-text-3)",
              boxShadow: activeTab === t.id ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
            }}
          >
            <span>{t.icon}</span>
            <span className="hidden sm:inline">{t.label}</span>
            {t.count != null && (
              <span
                className="px-1.5 py-0.5 rounded-md text-[10px] font-mono"
                style={{
                  background: activeTab === t.id ? "var(--color-accent-bg)" : "var(--color-canvas)",
                  color: activeTab === t.id ? "var(--color-accent)" : "var(--color-text-4)",
                }}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* TAB: ANALYTICS & INSIGHTS                                   */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {activeTab === "analytics" && (
        <div className="space-y-6 animate-fade-in">
          {/* Scatter Plot & Risk Donut Row */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Scatter Plot (3 cols) */}
            <div
              className="lg:col-span-3 p-5 rounded-2xl shadow-sm border"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: "var(--color-text-1)" }}>
                    <span>🎯</span> Integrity Scatter Analysis
                  </h3>
                  <p className="text-[11px] mt-0.5" style={{ color: "var(--color-text-4)" }}>
                    Each dot = one student. Hover to inspect. Top-right = high risk.
                  </p>
                </div>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Clean
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Review
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Flagged
                  </span>
                </div>
              </div>
              <ScatterPlot submissions={submissions} />
            </div>

            {/* Risk Donut (2 cols) */}
            <div
              className="lg:col-span-2 p-5 rounded-2xl shadow-sm border flex flex-col"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <h3 className="font-bold text-sm flex items-center gap-2 mb-4" style={{ color: "var(--color-text-1)" }}>
                <span>📊</span> Risk Breakdown
              </h3>

              {/* Donut */}
              {(() => {
                const donutR = 54;
                const donutCirc = 2 * Math.PI * donutR;
                const total = analytics.total || 1;
                const cleanPct = analytics.riskClean / total;
                const reviewPct = analytics.riskReview / total;
                const flagPct = analytics.riskFlagged / total;
                const cleanDash = cleanPct * donutCirc;
                const reviewDash = reviewPct * donutCirc;
                const flagDash = flagPct * donutCirc;

                return (
                  <div className="flex items-center justify-center my-4 relative">
                    <svg width="150" height="150" viewBox="0 0 150 150">
                      <circle cx="75" cy="75" r={donutR} fill="none" stroke="var(--color-border)" strokeWidth="16" />
                      {cleanDash > 0 && (
                        <circle cx="75" cy="75" r={donutR} fill="none" stroke="#10b981" strokeWidth="16"
                          strokeDasharray={`${cleanDash} ${donutCirc}`} strokeDashoffset="0"
                          transform="rotate(-90 75 75)" strokeLinecap="round"
                        />
                      )}
                      {reviewDash > 0 && (
                        <circle cx="75" cy="75" r={donutR} fill="none" stroke="#f59e0b" strokeWidth="16"
                          strokeDasharray={`${reviewDash} ${donutCirc}`} strokeDashoffset={`${-cleanDash}`}
                          transform="rotate(-90 75 75)" strokeLinecap="round"
                        />
                      )}
                      {flagDash > 0 && (
                        <circle cx="75" cy="75" r={donutR} fill="none" stroke="#ef4444" strokeWidth="16"
                          strokeDasharray={`${flagDash} ${donutCirc}`} strokeDashoffset={`${-(cleanDash + reviewDash)}`}
                          transform="rotate(-90 75 75)" strokeLinecap="round"
                        />
                      )}
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                      <span className="font-mono text-xl font-bold" style={{ color: "var(--color-text-1)" }}>
                        {analytics.complianceRate}%
                      </span>
                      <span className="text-[9.5px] uppercase tracking-wider font-semibold" style={{ color: "var(--color-text-3)" }}>
                        Authentic
                      </span>
                    </div>
                  </div>
                );
              })()}

              {/* Legend */}
              <div className="space-y-2 mt-auto pt-3 border-t" style={{ borderColor: "var(--color-border)" }}>
                {[
                  { label: "Clean / Verified (<25%)", color: "#10b981", count: analytics.riskClean, pct: analytics.total ? Math.round((analytics.riskClean / analytics.total) * 100) : 0 },
                  { label: "Moderate Review (25–50%)", color: "#f59e0b", count: analytics.riskReview, pct: analytics.total ? Math.round((analytics.riskReview / analytics.total) * 100) : 0 },
                  { label: "High Risk Flag (>50%)", color: "#ef4444", count: analytics.riskFlagged, pct: analytics.total ? Math.round((analytics.riskFlagged / analytics.total) * 100) : 0 },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ background: item.color }} />
                      <span style={{ color: "var(--color-text-2)" }}>{item.label}</span>
                    </div>
                    <span className="font-mono font-bold" style={{ color: item.color === "#ef4444" ? "var(--color-red)" : "var(--color-text-1)" }}>
                      {item.count} ({item.pct}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Histogram */}
          <div
            className="p-5 rounded-2xl shadow-sm border"
            style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: "var(--color-text-1)" }}>
                  <span>📈</span> Score Distribution Histogram
                </h3>
                <p className="text-[11px] mt-0.5" style={{ color: "var(--color-text-4)" }}>
                  Frequency of students across similarity and AI score bands
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded bg-blue-500" />
                  <span style={{ color: "var(--color-text-3)" }}>Peer Similarity</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded bg-purple-500" />
                  <span style={{ color: "var(--color-text-3)" }}>AI Probability</span>
                </div>
              </div>
            </div>

            <div className="h-48 w-full pt-4 flex items-end justify-between gap-3 px-2 border-b" style={{ borderColor: "var(--color-border)" }}>
              {["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"].map((band, i) => {
                const simCount = analytics.simHistogram[i];
                const aiCount = analytics.aiHistogram[i];
                const simH = Math.max(8, (simCount / maxHistCount) * 140);
                const aiH = Math.max(8, (aiCount / maxHistCount) * 140);

                return (
                  <div key={band} className="flex-1 flex flex-col items-center h-full justify-end group">
                    <div className="flex items-end gap-1.5 w-full justify-center">
                      <div
                        className="w-4 sm:w-6 rounded-t-md transition-all duration-500 hover:brightness-110 relative flex items-center justify-center text-[9px] font-mono text-white font-bold pb-1"
                        style={{
                          height: `${simH}px`,
                          background: i >= 3 ? "linear-gradient(to top, #3b82f6, #60a5fa)" : "#3b82f6",
                        }}
                        title={`${band} Peer Similarity: ${simCount} students`}
                      >
                        {simCount > 0 && <span className="opacity-90">{simCount}</span>}
                      </div>
                      <div
                        className="w-4 sm:w-6 rounded-t-md transition-all duration-500 hover:brightness-110 relative flex items-center justify-center text-[9px] font-mono text-white font-bold pb-1"
                        style={{
                          height: `${aiH}px`,
                          background: i >= 3 ? "linear-gradient(to top, #a855f7, #c084fc)" : "#a855f7",
                        }}
                        title={`${band} AI Probability: ${aiCount} students`}
                      >
                        {aiCount > 0 && <span className="opacity-90">{aiCount}</span>}
                      </div>
                    </div>
                    <span className="text-[10px] font-mono mt-2 truncate max-w-full" style={{ color: "var(--color-text-4)" }}>
                      {band}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Flagged Submissions Watchlist */}
          <div
            className="p-5 rounded-2xl shadow-sm border"
            style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: "var(--color-text-1)" }}>
                  <span>⚠️</span> Flagged Submissions Requiring Faculty Attention
                </h3>
                <p className="text-[11px] mt-0.5" style={{ color: "var(--color-text-4)" }}>
                  Submissions with &gt;50% match score or detected handwriting/AI stylometry flags
                </p>
              </div>
              <span
                className="font-mono text-xs px-2.5 py-1 rounded-full font-bold"
                style={{
                  background: analytics.flaggedList.length > 0 ? "var(--color-red-bg)" : "var(--color-green-bg)",
                  color: analytics.flaggedList.length > 0 ? "var(--color-red)" : "var(--color-green)",
                  border: `1px solid ${analytics.flaggedList.length > 0 ? "var(--color-red-border)" : "var(--color-green-border)"}`,
                }}
              >
                {analytics.flaggedList.length} Flagged
              </span>
            </div>

            {analytics.flaggedList.length === 0 ? (
              <div
                className="py-8 text-center rounded-xl border border-dashed text-xs"
                style={{
                  borderColor: "var(--color-green-border)",
                  background: "var(--color-green-bg)",
                  color: "var(--color-green)",
                }}
              >
                ✓ All submissions in this cohort meet academic originality thresholds (&lt;50% similarity).
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b text-[10px] font-semibold uppercase" style={{ borderColor: "var(--color-border)", color: "var(--color-text-4)" }}>
                      <th className="pb-2.5">Student</th>
                      <th className="pb-2.5">Similarity</th>
                      <th className="pb-2.5">AI Probability</th>
                      <th className="pb-2.5">Flag Reason</th>
                      <th className="pb-2.5 text-right">Audit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: "var(--color-border)" }}>
                    {analytics.flaggedList.map((item) => (
                      <tr key={item.id} className="hover:bg-stone-50/50 dark:hover:bg-stone-800/50">
                        <td className="py-3 font-semibold" style={{ color: "var(--color-text-1)" }}>{item.name}</td>
                        <td className="py-3 font-mono">
                          <span className={`px-2 py-0.5 rounded font-bold ${item.sim > 50 ? "bg-red-100 text-red-800" : "text-stone-600"}`}>
                            {item.sim}%
                          </span>
                        </td>
                        <td className="py-3 font-mono">
                          <span className={`px-2 py-0.5 rounded font-bold ${item.ai > 50 ? "bg-purple-100 text-purple-800" : "text-stone-600"}`}>
                            {item.ai}%
                          </span>
                        </td>
                        <td className="py-3 font-medium" style={{ color: "var(--color-text-3)" }}>{item.flag}</td>
                        <td className="py-3 text-right">
                          <a href={`/teacher/submissions/${item.id}`} className="font-semibold hover:underline" style={{ color: "var(--color-accent)" }}>
                            Inspect →
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* TAB: CLASS LEADERBOARD                                      */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {activeTab === "leaderboard" && (
        <div className="space-y-4 animate-fade-in">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: "var(--color-text-1)" }}>
                <span>🏆</span> Class Integrity Leaderboard
              </h3>
              <p className="text-[11px] mt-0.5" style={{ color: "var(--color-text-4)" }}>
                {submissions.length} students ranked by integrity scores. Expand any card for detailed breakdown.
              </p>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold uppercase" style={{ color: "var(--color-text-4)" }}>Sort:</span>
              {(["risk", "sim", "ai", "name"] as const).map((key) => (
                <button
                  key={key}
                  onClick={() => setLeaderboardSort(key)}
                  className="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase transition-all cursor-pointer"
                  style={{
                    background: leaderboardSort === key ? "var(--color-accent-bg)" : "transparent",
                    color: leaderboardSort === key ? "var(--color-accent)" : "var(--color-text-4)",
                    border: `1px solid ${leaderboardSort === key ? "var(--color-accent-ring)" : "var(--color-border)"}`,
                  }}
                >
                  {key === "risk" ? "Risk" : key === "sim" ? "Similarity" : key === "ai" ? "AI Score" : "Name"}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {sortedSubmissions.map((sub, i) => (
              <div key={sub.id} className={`animate-fade-in-up anim-delay-${Math.min(i + 1, 6)}`}>
                <StudentDetailCard sub={sub} rank={i + 1} />
              </div>
            ))}
            {submissions.length === 0 && (
              <div
                className="py-12 text-center rounded-xl"
                style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)", color: "var(--color-text-4)", fontSize: 13 }}
              >
                No submissions for this assignment yet.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* TAB: TIMELINE & HEATMAP                                     */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {activeTab === "timeline" && (
        <div className="animate-fade-in">
          <div
            className="p-6 rounded-2xl shadow-sm border"
            style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
          >
            <div className="mb-5">
              <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: "var(--color-text-1)" }}>
                <span>⏱️</span> Submission Timeline & Activity Heatmap
              </h3>
              <p className="text-[11px] mt-0.5" style={{ color: "var(--color-text-4)" }}>
                Analyze when students submit — late night submissions may indicate academic integrity concerns
              </p>
            </div>

            {submissions.length > 0 ? (
              <SubmissionTimeline submissions={submissions} />
            ) : (
              <div
                className="py-12 text-center rounded-xl"
                style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)", color: "var(--color-text-4)", fontSize: 13 }}
              >
                No submission data available for timeline analysis.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════ */}
      {/* TAB: PDF REPORTS & GENERATOR ARCHIVE                        */}
      {/* ═══════════════════════════════════════════════════════════ */}
      {activeTab === "archives" && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 animate-fade-in">
          {/* Left Column: Generator Form */}
          <div className="lg:col-span-2 space-y-5">
            <div
              className="rounded-2xl p-5 space-y-4 shadow-sm border"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <p className="font-bold text-sm" style={{ color: "var(--color-text-1)" }}>
                Generate Official PDF Report
              </p>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--color-text-4)" }}>
                  Report Type
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    {
                      id: "comprehensive",
                      label: "Comprehensive Audit",
                      desc: "Includes AI stylometry, pairwise cross-matching, handwriting CV, and full grades.",
                      icon: "📋",
                    },
                    {
                      id: "integrity_summary",
                      label: "Integrity & AI Scan Only",
                      desc: "Focuses exclusively on AI probability, handwriting flags, and similarity overlap.",
                      icon: "🔒",
                    },
                    {
                      id: "grading_breakdown",
                      label: "Gradebook & Rubrics",
                      desc: "Summarizes rubric scoring, deduction audits, and student feedbacks.",
                      icon: "📝",
                    },
                  ].map((item) => (
                    <div
                      key={item.id}
                      onClick={() => setReportType(item.id as ReportType)}
                      className="p-3 rounded-xl border cursor-pointer transition-all text-left group"
                      style={{
                        background: reportType === item.id ? "var(--color-navy)" : "var(--color-canvas)",
                        borderColor: reportType === item.id ? "var(--color-accent)" : "var(--color-border)",
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span>{item.icon}</span>
                        <p
                          className="font-semibold text-xs"
                          style={{ color: reportType === item.id ? "white" : "var(--color-text-1)" }}
                        >
                          {item.label}
                        </p>
                      </div>
                      <p
                        className="text-[11px] mt-0.5 ml-6"
                        style={{ color: reportType === item.id ? "rgba(255,255,255,0.7)" : "var(--color-text-4)" }}
                      >
                        {item.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: "var(--color-text-4)" }}>
                  Custom Title (Optional)
                </label>
                <input
                  type="text"
                  placeholder={selectedAssgnObj ? `Report: ${selectedAssgnObj.title}` : "e.g. Midterm Assignment Report"}
                  value={reportTitle}
                  onChange={(e) => setReportTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl text-xs"
                  style={{
                    background: "var(--color-canvas)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-1)",
                  }}
                />
              </div>

              <Btn
                variant="primary"
                size="md"
                disabled={state === "generating" || !selectedAssignment}
                onClick={handleGenerateReport}
                className="w-full justify-center"
                icon={state === "generating" ? <Spinner size={15} color="white" /> : undefined}
              >
                {state === "generating" ? "Compiling PDF Report…" : "Generate Official PDF Report"}
              </Btn>

              {state === "done" && newReport && (
                <div
                  className="rounded-xl p-4 mt-3 animate-fade-in-up"
                  style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}
                >
                  <p className="font-semibold text-xs" style={{ color: "var(--color-green)" }}>
                    ✓ Report Generated Successfully
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--color-text-3)" }}>{newReport.title}</p>
                  <div className="mt-2.5">
                    <button
                      onClick={() => handleDownload(newReport.id, newReport.title)}
                      disabled={downloading === newReport.id}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg text-white transition-colors cursor-pointer"
                      style={{ background: downloading === newReport.id ? "#6b7280" : "#14904A" }}
                    >
                      {downloading === newReport.id ? (
                        <><Spinner size={12} color="white" /> Downloading…</>
                      ) : (
                        <>⬇ Download Official PDF</>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Historical Reports */}
          <div className="lg:col-span-3 space-y-6">
            <div
              className="rounded-2xl p-5 shadow-sm border"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-sm" style={{ color: "var(--color-text-1)" }}>
                  Generated Reports Archive
                </h3>
                <span className="font-mono text-xs" style={{ color: "var(--color-text-4)" }}>
                  {reports.length} report{reports.length !== 1 ? "s" : ""}
                </span>
              </div>

              {loadingHistory ? (
                <div className="py-12 flex flex-col items-center justify-center gap-2">
                  <Spinner size={20} color="var(--color-accent)" />
                  <span className="text-xs" style={{ color: "var(--color-text-4)" }}>Loading historical reports…</span>
                </div>
              ) : reports.length === 0 ? (
                <div
                  className="py-10 rounded-xl text-center px-4"
                  style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
                >
                  <p className="text-xs" style={{ color: "var(--color-text-4)" }}>
                    No reports generated yet for this assignment. Click "Generate Official PDF Report" on the left.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {reports.map((rep, idx) => (
                    <div
                      key={rep.id}
                      className={`p-4 rounded-xl flex items-center justify-between gap-4 transition-all card-hover animate-fade-in-up anim-delay-${Math.min(idx + 1, 6)}`}
                      style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
                    >
                      <div>
                        <p className="font-semibold text-xs" style={{ color: "var(--color-text-1)" }}>{rep.title}</p>
                        <div className="flex items-center gap-3 mt-1 font-mono text-[11px]" style={{ color: "var(--color-text-4)" }}>
                          <span className="capitalize">{rep.report_type.replace("_", " ")}</span>
                          <span>•</span>
                          <span>{new Date(rep.created_at).toLocaleString()}</span>
                          {rep.summary_data?.total_submissions !== undefined && (
                            <>
                              <span>•</span>
                              <span>{rep.summary_data.total_submissions} students</span>
                            </>
                          )}
                        </div>
                      </div>

                      <button
                        onClick={() => handleDownload(rep.id, rep.title)}
                        disabled={downloading === rep.id}
                        className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer"
                        style={{
                          borderColor: "var(--color-accent-ring)",
                          color: downloading === rep.id ? "var(--color-text-4)" : "var(--color-accent)",
                          background: downloading === rep.id ? "var(--color-surface-2)" : "transparent",
                        }}
                      >
                        {downloading === rep.id ? (
                          <><Spinner size={12} color="var(--color-accent)" /> Downloading…</>
                        ) : (
                          <>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                              <polyline points="7 10 12 15 17 10"></polyline>
                              <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            Download PDF
                          </>
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
