import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import ScoreRing from "../../components/ScoreRing";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

interface Result {
  id: string; assignment: string; team: string; submittedAt: string;
  grade?: string; aiScore?: number; similarityScore?: number; handwritingScore?: number;
  status: string; flags: string[];
}

export default function StudentResults() {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadResults();
  }, []);

  async function loadResults() {
    setLoading(true);
    try {
      const [submissions, grades, teams, assignments] = await Promise.all([
        api.submissions.mySubmissions().catch(() => []),
        api.grading.myGrades().catch(() => []),
        api.teams.list().catch(() => []),
        api.assignments.list().catch(() => []),
      ]);

      const teamMap = new Map<string, string>();
      (teams || []).forEach((t: any) => teamMap.set(t.id, t.name));

      const assignMap = new Map<string, any>();
      (assignments || []).forEach((a: any) => assignMap.set(a.id, a));

      const gradeMap = new Map<string, any>();
      (grades || []).forEach((g: any) => gradeMap.set(g.submission_id, g));

      const mapped: Result[] = await Promise.all(
        (submissions || []).map(async (s: any) => {
          let aiScore: number | undefined;
          let similarityScore: number | undefined;
          let handwritingScore: number | undefined;
          const flags: string[] = [];

          try {
            const analysis = await api.submissions.getAnalysis(s.id);
            if (analysis?.ai_analysis) {
              aiScore = analysis.ai_analysis.score;
              if (aiScore !== undefined && aiScore >= 50) flags.push(`AI content detected: ${Math.round(aiScore)}%`);
            }
            if (analysis?.max_similarity_score != null) {
              similarityScore = analysis.max_similarity_score;
              if (similarityScore >= 60) flags.push(`High similarity: ${Math.round(similarityScore)}%`);
            }
            if (analysis?.handwriting_analysis) {
              handwritingScore = analysis.handwriting_analysis.confidence * 100;
            }
          } catch {
            // Analysis not available yet
          }

          const grade = gradeMap.get(s.id);
          const assignObj = assignMap.get(s.assignment_id);
          const aTitle = s.assignment_title || assignObj?.title || "Assignment";
          const tName = s.team_name || teamMap.get(assignObj?.team_id) || "Course";

          return {
            id: s.id,
            assignment: aTitle,
            team: tName,
            submittedAt: s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : "Recently",
            grade: grade ? `${grade.final_score}/${grade.max_marks}` : undefined,
            aiScore,
            similarityScore,
            handwritingScore,
            status: grade ? "graded" : s.status === "completed" ? "analysed" : s.status,
            flags,
          };
        })
      );

      setResults(mapped);
    } catch (err: any) {
      console.error("Failed to load results:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="My Results"
        subtitle="Analysis results and grades for your submissions."
      />

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading results…</span>
        </div>
      ) : results.length === 0 ? (
        <EmptyState
          icon={<svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M2 16l5-5 3 3 7-9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /><circle cx="19" cy="4" r="2" stroke="currentColor" strokeWidth="1.4" /></svg>}
          title="No results yet"
          description="Results will appear here after your submissions have been analysed and your instructor has released grades."
        />
      ) : (
        <div className="space-y-3">
          {results.map((r) => (
            <div key={r.id} className="rounded-xl overflow-hidden" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <div
                className="flex items-start gap-4 px-5 py-4 cursor-pointer"
                onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                style={{ borderBottom: expanded === r.id ? "1px solid var(--color-border)" : "none" }}
              >
                <div className="flex-1 min-w-0">
                  <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>{r.assignment}</p>
                  <p style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 2 }}>
                    {r.team} · Submitted {r.submittedAt}
                  </p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <StatusBadge status={r.status} />
                  {r.grade && (
                    <span className="font-semibold font-mono" style={{ fontSize: 18, color: "var(--color-text-1)" }}>{r.grade}</span>
                  )}
                  <svg
                    width="14" height="14" viewBox="0 0 14 14" fill="none"
                    style={{ transform: expanded === r.id ? "rotate(180deg)" : "none", transition: "transform 0.15s", color: "var(--color-text-3)" }}
                  >
                    <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </div>

              {expanded === r.id && (
                <div className="px-5 py-5">
                  <div className="flex items-center gap-8 mb-5">
                    <ScoreRing value={r.aiScore ?? null} label="AI Content" size={64} />
                    <ScoreRing value={r.similarityScore ?? null} label="Similarity" size={64} />
                    <ScoreRing value={r.handwritingScore ?? null} label="Handwriting" size={64} />
                  </div>
                  {r.flags.length > 0 && (
                    <div className="rounded-lg p-3" style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)" }}>
                      <p className="font-semibold mb-1.5" style={{ fontSize: 12, color: "var(--color-red)" }}>Flags raised</p>
                      {r.flags.map((f) => (
                        <p key={f} style={{ fontSize: 12.5, color: "var(--color-red)", lineHeight: 1.6 }}>• {f}</p>
                      ))}
                    </div>
                  )}
                  <div className="mt-4 pt-3 flex items-center justify-between border-t border-slate-700/40">
                    <span className="text-xs text-slate-400">Review processing pipeline & verified document</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/student/submission-status/${r.id}`); }}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                    >
                      View Submission Details →
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
