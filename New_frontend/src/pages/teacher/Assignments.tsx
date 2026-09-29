import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

interface AssignmentItem {
  id: string;
  title: string;
  team: string;
  teamId: string;
  type: string;
  dueDate: string;
  submissionCount: number;
  maxMarks: number;
  status: string;
}

const FILTERS = ["all", "open", "closed"] as const;

export default function TeacherAssignments() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<typeof FILTERS[number]>("all");
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAssignments();
  }, []);

  async function loadAssignments() {
    setLoading(true);
    setError(null);
    try {
      const [assignmentsData, teamsData] = await Promise.all([
        api.assignments.list(),
        api.teams.list().catch(() => []),
      ]);

      const teamMap = new Map<string, string>();
      (teamsData || []).forEach((t: any) => teamMap.set(t.id, t.name));

      const mapped: AssignmentItem[] = (assignmentsData || []).map((a: any) => {
        const isPastDue = a.due_date ? new Date(a.due_date) < new Date() : false;
        return {
          id: a.id,
          title: a.title,
          team: teamMap.get(a.team_id) || "Course Team",
          teamId: a.team_id,
          type: a.allowed_file_types || "Document",
          dueDate: a.due_date ? new Date(a.due_date).toLocaleDateString() : "No deadline",
          submissionCount: a.submission_count ?? 0,
          maxMarks: a.max_marks ?? 100,
          status: !a.is_active ? "closed" : isPastDue ? "closed" : "open",
        };
      });

      setAssignments(mapped);
    } catch (err: any) {
      setError(err?.message || "Failed to load assignments.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = assignments.filter(
    (a) => filter === "all" || a.status === filter
  );

  return (
    <div>
      <PageHeader
        title="Assignments"
        subtitle="Create and manage assessments across your teams."
        actions={
          <Btn
            variant="primary"
            size="sm"
            onClick={() => navigate("/teacher/assignments/new")}
            icon={
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            }
          >
            New assignment
          </Btn>
        }
      />

      <div className="flex gap-1.5 mb-5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="px-3 py-1.5 rounded-lg font-medium capitalize transition-all cursor-pointer"
            style={{
              fontSize: 12.5,
              fontFamily: "inherit",
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
          icon={
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="3" y="2" width="14" height="16" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
              <path d="M7 7h6M7 10h4M7 13h2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          }
          title={assignments.length === 0 ? "No assignments yet" : "No results"}
          description={
            assignments.length === 0
              ? "Create your first assignment to start collecting submissions."
              : "No assignments match this filter."
          }
          action={
            assignments.length === 0
              ? { label: "Create assignment", onClick: () => navigate("/teacher/assignments/new") }
              : undefined
          }
        />
      ) : (
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
        >
          <table className="w-full">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                {["Assignment", "Team", "File Types", "Due Date", "Max Marks", "Submissions", "Status", ""].map((h, i) => (
                  <th
                    key={i}
                    className={`px-4 py-3 font-semibold uppercase tracking-wider ${
                      i >= 4 && i <= 5 ? "text-right" : "text-left"
                    }`}
                    style={{ fontSize: 10.5, color: "var(--color-text-3)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr
                  key={a.id}
                  className="cursor-pointer transition-colors"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                  onClick={() => navigate(`/teacher/submissions?assignmentId=${a.id}`)}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>
                      {a.title}
                    </p>
                  </td>
                  <td className="px-4 py-3" style={{ fontSize: 13, color: "var(--color-text-2)" }}>
                    {a.team}
                  </td>
                  <td className="px-4 py-3 uppercase font-mono" style={{ fontSize: 11, color: "var(--color-text-3)" }}>
                    {a.type}
                  </td>
                  <td className="px-4 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                    {a.dueDate}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ fontSize: 13, color: "var(--color-text-2)" }}>
                    {a.maxMarks}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ fontSize: 13, color: "var(--color-accent)" }}>
                    {a.submissionCount}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={a.status} size="xs" />
                  </td>
                  <td className="px-4 py-3 text-right" style={{ fontSize: 12, color: "var(--color-accent)" }}>
                    Submissions →
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
