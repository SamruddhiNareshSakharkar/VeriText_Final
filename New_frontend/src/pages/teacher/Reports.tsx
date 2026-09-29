import { useState, useEffect, useMemo } from "react";
import Btn from "../../components/Btn";
import PageHeader from "../../components/PageHeader";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

type ReportType = "comprehensive" | "integrity_summary" | "grading_breakdown";
type GenState = "idle" | "generating" | "done" | "error";

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
  const [activeTab, setActiveTab] = useState<"analytics" | "archives">("analytics");

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
      };
    }

    let simSum = 0;
    let aiSum = 0;
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
    };
  }, [submissions]);

  const selectedAssgnObj = assignments.find((a) => a.id === selectedAssignment);

  // SVG Donut calculation
  const donutR = 54;
  const donutCirc = 2 * Math.PI * donutR;
  const cleanPct = analytics.total ? analytics.riskClean / analytics.total : 1;
  const reviewPct = analytics.total ? analytics.riskReview / analytics.total : 0;
  const flagPct = analytics.total ? analytics.riskFlagged / analytics.total : 0;

  const cleanDash = cleanPct * donutCirc;
  const reviewDash = reviewPct * donutCirc;
  const flagDash = flagPct * donutCirc;

  const maxHistCount = Math.max(1, ...analytics.simHistogram, ...analytics.aiHistogram);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports & Analytics"
        subtitle="Visual integrity analytics, cohort score distribution graphs, and official cryptographic PDF reports."
        actions={
          <div className="flex items-center gap-2">
            <select
              value={selectedAssignment}
              onChange={(e) => setSelectedAssignment(e.target.value)}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold border shadow-sm cursor-pointer outline-none"
              style={{
                background: "var(--color-surface)",
                borderColor: "var(--color-border)",
                color: "var(--color-text-1)",
              }}
            >
              {assignments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title} ({a.submission_count ?? 0} submissions)
                </option>
              ))}
            </select>
          </div>
        }
      />

      {/* Tabs for switching between Visual Analytics & PDF Archives */}
      <div className="flex items-center justify-between border-b" style={{ borderColor: "var(--color-border)" }}>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setActiveTab("analytics")}
            className={`pb-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 cursor-pointer flex items-center gap-2 ${
              activeTab === "analytics"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
          >
            <span>📊</span>
            <span>Visual Analytics & Graphs</span>
          </button>
          <button
            onClick={() => setActiveTab("archives")}
            className={`pb-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 cursor-pointer flex items-center gap-2 ${
              activeTab === "archives"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
          >
            <span>📑</span>
            <span>PDF Reports & Download ({reports.length})</span>
          </button>
        </div>

        {selectedAssgnObj && (
          <span className="text-xs font-mono text-slate-500 hidden sm:inline-block">
            {selectedAssgnObj.title}
          </span>
        )}
      </div>

      {activeTab === "analytics" ? (
        /* ============================================================ */
        /* VISUAL ANALYTICS & GRAPHS SECTION                            */
        /* ============================================================ */
        <div className="space-y-6 animate-fade-in">
          {/* Executive Cohort KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div
              className="p-4 rounded-2xl shadow-sm border flex items-center gap-4"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="w-12 h-12 rounded-xl bg-blue-500/15 text-blue-600 dark:text-blue-400 flex items-center justify-center text-xl font-bold">
                👥
              </div>
              <div>
                <p className="text-[10.5px] uppercase font-bold tracking-wider text-slate-600">Total Submissions</p>
                <h3 className="text-2xl font-bold font-mono text-stone-900 dark:text-white">
                  {analytics.total}
                </h3>
              </div>
            </div>

            <div
              className="p-4 rounded-2xl shadow-sm border flex items-center gap-4"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="w-12 h-12 rounded-xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-xl font-bold">
                🛡️
              </div>
              <div>
                <p className="text-[10.5px] uppercase font-bold tracking-wider text-slate-600">Integrity Compliance</p>
                <h3 className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                  {analytics.complianceRate}%
                </h3>
              </div>
            </div>

            <div
              className="p-4 rounded-2xl shadow-sm border flex items-center gap-4"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="w-12 h-12 rounded-xl bg-sky-500/15 text-sky-600 dark:text-sky-400 flex items-center justify-center text-xl font-bold">
                🔍
              </div>
              <div>
                <p className="text-[10.5px] uppercase font-bold tracking-wider text-slate-600">Avg. Cross-Peer Match</p>
                <h3 className="text-2xl font-bold font-mono text-stone-900 dark:text-white">
                  {analytics.avgSim}%
                </h3>
              </div>
            </div>

            <div
              className="p-4 rounded-2xl shadow-sm border flex items-center gap-4"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div className="w-12 h-12 rounded-xl bg-purple-500/15 text-purple-600 dark:text-purple-400 flex items-center justify-center text-xl font-bold">
                🤖
              </div>
              <div>
                <p className="text-[10.5px] uppercase font-bold tracking-wider text-slate-600">Avg. AI Probability</p>
                <h3 className="text-2xl font-bold font-mono text-stone-900 dark:text-white">
                  {analytics.avgAi}%
                </h3>
              </div>
            </div>
          </div>

          {/* Graphs Row: Risk Donut Chart & Dual Bar Histogram */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Chart 1: Donut Risk Breakdown (2 cols) */}
            <div
              className="lg:col-span-2 p-5 rounded-2xl shadow-sm border flex flex-col justify-between"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-sm text-stone-900 dark:text-white flex items-center gap-2">
                    <span>🎯</span>
                    <span>Cohort Risk Distribution</span>
                  </h3>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600">
                    N = {analytics.total}
                  </span>
                </div>

                {/* SVG Donut Chart */}
                <div className="flex items-center justify-center my-4 relative">
                  <svg width="150" height="150" viewBox="0 0 150 150">
                    {/* Background track */}
                    <circle cx="75" cy="75" r={donutR} fill="none" stroke="var(--color-border)" strokeWidth="16" />

                    {/* Clean segment (Green) */}
                    {cleanDash > 0 && (
                      <circle
                        cx="75"
                        cy="75"
                        r={donutR}
                        fill="none"
                        stroke="#10b981"
                        strokeWidth="16"
                        strokeDasharray={`${cleanDash} ${donutCirc}`}
                        strokeDashoffset="0"
                        transform="rotate(-90 75 75)"
                        strokeLinecap="round"
                      />
                    )}

                    {/* Review segment (Amber) */}
                    {reviewDash > 0 && (
                      <circle
                        cx="75"
                        cy="75"
                        r={donutR}
                        fill="none"
                        stroke="#f59e0b"
                        strokeWidth="16"
                        strokeDasharray={`${reviewDash} ${donutCirc}`}
                        strokeDashoffset={`${-cleanDash}`}
                        transform="rotate(-90 75 75)"
                        strokeLinecap="round"
                      />
                    )}

                    {/* Flagged segment (Red) */}
                    {flagDash > 0 && (
                      <circle
                        cx="75"
                        cy="75"
                        r={donutR}
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="16"
                        strokeDasharray={`${flagDash} ${donutCirc}`}
                        strokeDashoffset={`${-(cleanDash + reviewDash)}`}
                        transform="rotate(-90 75 75)"
                        strokeLinecap="round"
                      />
                    )}
                  </svg>

                  {/* Center percentage label */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="font-mono text-xl font-bold text-stone-900 dark:text-white">
                      {analytics.complianceRate}%
                    </span>
                    <span className="text-[9.5px] uppercase tracking-wider text-slate-600 font-semibold">
                      Authentic
                    </span>
                  </div>
                </div>

                {/* Legend & Breakdown */}
                <div className="space-y-2 mt-4 pt-3 border-t" style={{ borderColor: "var(--color-border)" }}>
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                      <span className="text-slate-700">Clean / Verified (&lt;25%)</span>
                    </div>
                    <span className="font-mono font-bold text-stone-900 dark:text-white">
                      {analytics.riskClean} ({Math.round(cleanPct * 100)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                      <span className="text-slate-700">Moderate Review (25–50%)</span>
                    </div>
                    <span className="font-mono font-bold text-stone-900 dark:text-white">
                      {analytics.riskReview} ({Math.round(reviewPct * 100)}%)
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                      <span className="text-slate-700">High Risk Flag (&gt;50%)</span>
                    </div>
                    <span className="font-mono font-bold text-red-600 dark:text-red-400">
                      {analytics.riskFlagged} ({Math.round(flagPct * 100)}%)
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Chart 2: Double Bar Histogram Graph (3 cols) */}
            <div
              className="lg:col-span-3 p-5 rounded-2xl shadow-sm border flex flex-col justify-between"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-sm text-stone-900 dark:text-white flex items-center gap-2">
                      <span>📈</span>
                      <span>Similarity & AI Score Frequency</span>
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Histogram of student papers distributed across score bands
                    </p>
                  </div>

                  {/* Series Legend */}
                  <div className="flex items-center gap-3 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-3 rounded bg-blue-500" />
                      <span className="text-slate-600">Peer Similarity</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-3 h-3 rounded bg-purple-500" />
                      <span className="text-slate-600">AI Probability</span>
                    </div>
                  </div>
                </div>

                {/* SVG Bar Chart Visualization */}
                <div className="h-48 w-full pt-4 flex items-end justify-between gap-3 px-2 border-b border-stone-200 dark:border-stone-800">
                  {["0–20%", "21–40%", "41–60%", "61–80%", "81–100%"].map((band, i) => {
                    const simCount = analytics.simHistogram[i];
                    const aiCount = analytics.aiHistogram[i];
                    const simH = Math.max(8, (simCount / maxHistCount) * 140);
                    const aiH = Math.max(8, (aiCount / maxHistCount) * 140);

                    return (
                      <div key={band} className="flex-1 flex flex-col items-center h-full justify-end group">
                        <div className="flex items-end gap-1.5 w-full justify-center">
                          {/* Similarity Bar */}
                          <div
                            className="w-4 sm:w-6 bg-blue-500 rounded-t-md transition-all duration-500 hover:brightness-110 relative flex items-center justify-center text-[9px] font-mono text-white font-bold pb-1"
                            style={{ height: `${simH}px` }}
                            title={`${band} Peer Similarity: ${simCount} students`}
                          >
                            {simCount > 0 && <span className="opacity-90">{simCount}</span>}
                          </div>

                          {/* AI Bar */}
                          <div
                            className="w-4 sm:w-6 bg-purple-500 rounded-t-md transition-all duration-500 hover:brightness-110 relative flex items-center justify-center text-[9px] font-mono text-white font-bold pb-1"
                            style={{ height: `${aiH}px` }}
                            title={`${band} AI Probability: ${aiCount} students`}
                          >
                            {aiCount > 0 && <span className="opacity-90">{aiCount}</span>}
                          </div>
                        </div>

                        {/* Band label */}
                        <span className="text-[10px] font-mono text-slate-500 mt-2 truncate max-w-full">
                          {band}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Chart Insights footer */}
              <div className="mt-4 pt-3 flex items-center justify-between text-xs text-slate-600">
                <span>Mean cohort distribution reflects standard academic normality.</span>
                <button
                  onClick={() => setActiveTab("archives")}
                  className="text-blue-600 dark:text-blue-400 font-semibold hover:underline cursor-pointer"
                >
                  Generate Full Audit PDF →
                </button>
              </div>
            </div>
          </div>

          {/* Top Integrity Flags Watchlist */}
          <div
            className="p-5 rounded-2xl shadow-sm border"
            style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-sm text-stone-900 dark:text-white flex items-center gap-2">
                  <span>⚠️</span>
                  <span>Flagged Submissions Requiring Faculty Attention</span>
                </h3>
                <p className="text-[11px] text-stone-400 mt-0.5">
                  Submissions with &gt;50% match score or detected handwriting/AI stylometry flags
                </p>
              </div>
              <span className="font-mono text-xs px-2.5 py-1 rounded-full font-bold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                {analytics.flaggedList.length} Flagged
              </span>
            </div>

            {analytics.flaggedList.length === 0 ? (
              <div
                className="py-8 text-center rounded-xl border border-dashed text-xs text-emerald-600 dark:text-emerald-400"
                style={{ borderColor: "var(--color-border)", background: "var(--color-canvas)" }}
              >
                ✓ All submissions in this cohort meet academic originality thresholds (&lt;50% similarity).
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b text-stone-400 uppercase text-[10px] font-semibold" style={{ borderColor: "var(--color-border)" }}>
                      <th className="pb-2.5">Student</th>
                      <th className="pb-2.5">Similarity Score</th>
                      <th className="pb-2.5">AI Probability</th>
                      <th className="pb-2.5">Flag Reason</th>
                      <th className="pb-2.5 text-right">Audit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: "var(--color-border)" }}>
                    {analytics.flaggedList.map((item) => (
                      <tr key={item.id} className="hover:bg-stone-50/50 dark:hover:bg-stone-800/50">
                        <td className="py-3 font-semibold text-stone-900 dark:text-white">
                          {item.name}
                        </td>
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
                        <td className="py-3 text-stone-500 font-medium">
                          {item.flag}
                        </td>
                        <td className="py-3 text-right">
                          <a
                            href={`/teacher/submissions/${item.id}`}
                            className="text-blue-600 hover:underline font-semibold"
                          >
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
      ) : (
        /* ============================================================ */
        /* PDF REPORTS & GENERATOR ARCHIVE SECTION                      */
        /* ============================================================ */
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 animate-fade-in">
          {/* Left Column: Generator Form */}
          <div className="lg:col-span-2 space-y-5">
            <div
              className="rounded-2xl p-5 space-y-4 shadow-sm border"
              style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
            >
              <p className="font-bold text-sm text-stone-900 dark:text-white">
                Generate Official PDF Report
              </p>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Report Type
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    {
                      id: "comprehensive",
                      label: "Comprehensive Audit",
                      desc: "Includes AI stylometry, pairwise cross-matching, handwriting CV, and full grades.",
                    },
                    {
                      id: "integrity_summary",
                      label: "Integrity & AI Scan Only",
                      desc: "Focuses exclusively on AI probability, handwriting flags, and similarity overlap.",
                    },
                    {
                      id: "grading_breakdown",
                      label: "Gradebook & Rubrics",
                      desc: "Summarizes rubric scoring, deduction audits, and student feedbacks.",
                    },
                  ].map((item) => (
                    <div
                      key={item.id}
                      onClick={() => setReportType(item.id as ReportType)}
                      className="p-3 rounded-xl border cursor-pointer transition-all text-left"
                      style={{
                        background: reportType === item.id ? "var(--color-navy)" : "var(--color-canvas)",
                        borderColor: reportType === item.id ? "var(--color-accent)" : "var(--color-border)",
                      }}
                    >
                      <p
                        className="font-semibold text-xs"
                        style={{ color: reportType === item.id ? "white" : "var(--color-text-1)" }}
                      >
                        {item.label}
                      </p>
                      <p
                        className="text-[11px] mt-0.5"
                        style={{ color: reportType === item.id ? "rgba(255,255,255,0.7)" : "var(--color-text-4)" }}
                      >
                        {item.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
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
                <h3 className="font-bold text-sm text-stone-900 dark:text-white">
                  Generated Reports Archive
                </h3>
                <span className="font-mono text-xs text-stone-400">
                  {reports.length} report{reports.length !== 1 ? "s" : ""}
                </span>
              </div>

              {loadingHistory ? (
                <div className="py-12 flex flex-col items-center justify-center gap-2">
                  <Spinner size={20} color="var(--color-accent)" />
                  <span className="text-xs text-stone-400">Loading historical reports…</span>
                </div>
              ) : reports.length === 0 ? (
                <div
                  className="py-10 rounded-xl text-center px-4"
                  style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
                >
                  <p className="text-xs text-stone-400">
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
                        <p className="font-semibold text-xs text-stone-900 dark:text-white">{rep.title}</p>
                        <div className="flex items-center gap-3 mt-1 font-mono text-[11px] text-stone-400">
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
