import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";

interface GradingItem { id: string; student: string; assignment: string; submittedAt: string; autoScore: number | null; teacherScore: number | null; maxMarks: number; status: string }

const ITEMS: GradingItem[] = [];

export default function Grading() {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader
        title="Grading"
        subtitle="Review auto-graded submissions and apply teacher overrides."
      />

      {ITEMS.length === 0 ? (
        <EmptyState
          icon={<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2l2.5 5 5.5.8-4 3.9.95 5.5L10 14.75 5.05 17.2 6 11.7 2 7.8l5.5-.8z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>}
          title="Nothing to grade"
          description="Submissions that have completed integrity analysis will appear here for grading."
        />
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <table className="w-full">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                {["Student", "Assignment", "Submitted", "Auto Score", "Override", "Max", "Status", ""].map((h, i) => (
                  <th key={i} className={`px-5 py-3 font-semibold uppercase tracking-wider ${i >= 3 ? "text-right" : "text-left"}`}
                    style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ITEMS.map((item) => (
                <tr key={item.id} className="cursor-pointer" style={{ borderBottom: "1px solid var(--color-border)" }}
                  onClick={() => navigate(`/teacher/grading/${item.id}`)}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}>
                  <td className="px-5 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{item.student}</td>
                  <td className="px-5 py-3" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{item.assignment}</td>
                  <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>{item.submittedAt}</td>
                  <td className="px-5 py-3 text-right font-mono" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{item.autoScore ?? "—"}</td>
                  <td className="px-5 py-3 text-right font-mono font-semibold" style={{ fontSize: 13, color: "var(--color-accent)" }}>{item.teacherScore ?? "—"}</td>
                  <td className="px-5 py-3 text-right font-mono" style={{ fontSize: 13, color: "var(--color-text-4)" }}>{item.maxMarks}</td>
                  <td className="px-5 py-3"><StatusBadge status={item.status} size="xs" /></td>
                  <td className="px-5 py-3" style={{ fontSize: 12, color: "var(--color-accent)" }}>Grade →</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
