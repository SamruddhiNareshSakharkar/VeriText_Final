import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

interface Assignment {
  id: string;
  title: string;
  team: string;
  teamId: string;
  type: string;
  dueDate: string;
  status: string;
  submitted: boolean;
}

const FILTERS = ["all", "open", "submitted", "late"] as const;

export default function StudentAssignments() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<typeof FILTERS[number]>("all");
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAssignments();
  }, []);

  async function loadAssignments() {
    setLoading(true);
    setError(null);
    try {
      const [assignmentsData, teamsData, mySubmissions] = await Promise.all([
        api.assignments.list(),
        api.teams.list().catch(() => []),
        api.submissions.mySubmissions().catch(() => []),
      ]);

      const teamMap = new Map<string, string>();
      (teamsData || []).forEach((t: any) => teamMap.set(t.id, t.name));

      const submittedAssignmentIds = new Set(
        (mySubmissions || []).map((s: any) => s.assignment_id)
      );

      const mapped: Assignment[] = (assignmentsData || []).map((a: any) => {
        const isPastDue = a.due_date ? new Date(a.due_date) < new Date() : false;
        const isSubmitted = submittedAssignmentIds.has(a.id);
        let status = "open";
        if (isSubmitted) status = "submitted";
        else if (isPastDue) status = "late";
        else if (!a.is_active) status = "closed";

        return {
          id: a.id,
          title: a.title,
          team: teamMap.get(a.team_id) || "Course Team",
          teamId: a.team_id,
          type: a.allowed_file_types || "Document",
          dueDate: a.due_date ? new Date(a.due_date).toLocaleDateString() : "No deadline",
          status,
          submitted: isSubmitted,
        };
      });

      setAssignments(mapped);
    } catch (err: any) {
      setError(err?.message || "Failed to load assignments.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = assignments.filter((a) => {
    if (filter === "open") return !a.submitted && a.status !== "late" && a.status !== "closed";
    if (filter === "submitted") return a.submitted;
    if (filter === "late") return a.status === "late";
    return true;
  });

  return (
    <div>
      <PageHeader title="Assignments" subtitle="All assessments across your enrolled teams." />

      <div className="flex gap-1.5 mb-5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="px-3 py-1.5 rounded-lg font-medium capitalize transition-colors"
            style={{
              fontSize: 12.5,
              background: filter === f ? "var(--color-navy)" : "var(--color-surface)",
              color: filter === f ? "white" : "var(--color-text-2)",
              border: `1px solid ${filter === f ? "var(--color-navy)" : "var(--color-border)"}`,
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading assignments…</span>
        </div>
      ) : error ? (
        <div
          className="p-4 rounded-xl mb-6 text-sm flex items-center justify-between"
          style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", color: "var(--color-red)" }}
        >
          <span>{error}</span>
          <Btn variant="ghost" size="xs" onClick={loadAssignments}>Retry</Btn>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="1.5" stroke="currentColor" strokeWidth="1.4" /><path d="M7 7h6M7 10h4M7 13h2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>}
          title={assignments.length === 0 ? "No assignments yet" : "No results for this filter"}
          description={assignments.length === 0 ? "Assignments will appear here when your instructor creates them." : "Try a different filter."}
        />
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <table className="w-full">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                {["Assignment", "Team", "Type", "Due", "Status", ""].map((h, i) => (
                  <th key={i} className="text-left px-4 py-3 font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr
                  key={a.id}
                  className="cursor-pointer"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                  onClick={() => navigate(`/student/submission-status/${a.id}`)}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}
                >
                  <td className="px-4 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{a.title}</td>
                  <td className="px-4 py-3" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{a.team}</td>
                  <td className="px-4 py-3 capitalize" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{a.type}</td>
                  <td className="px-4 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>{a.dueDate}</td>
                  <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                  <td className="px-4 py-3 text-right">
                    {!a.submitted && (
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/student/submit/${a.id}`); }}
                        className="font-medium rounded-lg px-3 py-1.5 transition-colors"
                        style={{ fontSize: 12, background: "var(--color-accent)", color: "white" }}
                      >
                        Submit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
