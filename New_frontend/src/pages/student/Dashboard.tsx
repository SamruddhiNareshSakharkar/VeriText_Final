import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useApp } from "../../lib/context";
import { api } from "../../lib/api";

function Stat({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: boolean }) {
  return (
    <div className="rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
      <p className="font-medium uppercase tracking-wider mb-2" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{label}</p>
      <p className="font-semibold font-mono" style={{ fontSize: 26, color: accent ? "var(--color-accent)" : "var(--color-text-1)" }}>{value}</p>
      {note && <p style={{ fontSize: 12, color: "var(--color-text-4)", marginTop: 4 }}>{note}</p>}
    </div>
  );
}

export default function StudentDashboard() {
  const { user } = useApp();
  const navigate = useNavigate();
  const first = user?.name.split(" ")[0] ?? "there";

  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const data = await api.analytics.studentDashboard();
        setStats(data);
      } catch (err) {
        console.error("Failed to load student dashboard:", err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div>
      <PageHeader
        title={`${greeting}, ${first}`}
        subtitle="Your academic activity at a glance."
        actions={
          <Btn variant="primary" size="sm" onClick={() => navigate("/student/assignments")}
            icon={<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}>
            View assignments
          </Btn>
        }
      />

      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading dashboard…</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Stat
              label="Teams enrolled"
              value={String(stats?.enrolled_teams ?? 0)}
              note={stats?.enrolled_teams ? `${stats.enrolled_teams} active team${stats.enrolled_teams > 1 ? "s" : ""}` : "Join a team to get started"}
            />
            <Stat
              label="Assignments due"
              value={String(stats?.pending_assignments_count ?? 0)}
              note={stats?.pending_assignments_count ? "Pending submission" : "No upcoming deadlines"}
            />
            <Stat
              label="Submissions made"
              value={String(stats?.completed_submissions_count ?? 0)}
              note="This semester"
            />
            <Stat
              label="Results available"
              value={String(stats?.graded_count ?? 0)}
              note={stats?.average_grade_percentage ? `Avg: ${stats.average_grade_percentage}%` : "Ready to view"}
              accent
            />
          </div>

          {/* Pending assignments */}
          {stats?.pending_assignments && stats.pending_assignments.length > 0 && (
            <div className="rounded-xl overflow-hidden mb-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
              <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
                <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Upcoming assignments</p>
                <button onClick={() => navigate("/student/assignments")} style={{ fontSize: 12.5, color: "var(--color-accent)" }} className="hover:underline">
                  View all →
                </button>
              </div>
              <table className="w-full">
                <thead>
                  <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                    {["Assignment", "Course", "Due Date", "Max Marks", ""].map((h, i) => (
                      <th key={i} className="text-left px-5 py-3 font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.pending_assignments.map((a: any) => (
                    <tr
                      key={a.id}
                      className="cursor-pointer transition-colors"
                      style={{ borderBottom: "1px solid var(--color-border)" }}
                      onClick={() => navigate(`/student/submit/${a.id}`)}
                      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}
                    >
                      <td className="px-5 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{a.title}</td>
                      <td className="px-5 py-3" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{a.course_name}</td>
                      <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                        {a.due_date ? new Date(a.due_date).toLocaleDateString() : "No deadline"}
                      </td>
                      <td className="px-5 py-3 font-mono" style={{ fontSize: 13, color: "var(--color-text-2)" }}>{a.max_marks}</td>
                      <td className="px-5 py-3 text-right">
                        <span style={{ fontSize: 12, color: "var(--color-accent)" }}>Submit →</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Recent submissions */}
          <div className="rounded-xl overflow-hidden mb-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
              <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Recent submissions</p>
              <button onClick={() => navigate("/student/assignments")} style={{ fontSize: 12.5, color: "var(--color-accent)" }} className="hover:underline">
                View all →
              </button>
            </div>

            {stats?.recent_submissions && stats.recent_submissions.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                    {["Assignment", "File", "Submitted", "Grade", "Status"].map((h, i) => (
                      <th key={i} className="text-left px-5 py-3 font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_submissions.map((s: any, idx: number) => (
                    <tr key={idx} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td className="px-5 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{s.assignment_title}</td>
                      <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>{s.file_name}</td>
                      <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                        {new Date(s.submitted_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 font-mono font-semibold" style={{ fontSize: 13 }}>
                        {s.grade != null ? (
                          <span style={{ color: "var(--color-accent)" }}>{s.grade}/{s.max_marks}</span>
                        ) : (
                          <span style={{ color: "var(--color-text-4)" }}>—</span>
                        )}
                      </td>
                      <td className="px-5 py-3"><StatusBadge status={s.status} size="xs" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-16 flex flex-col items-center text-center px-6">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4"
                  style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <rect x="3" y="2" width="14" height="16" rx="1.5" stroke="var(--color-text-4)" strokeWidth="1.4" />
                    <path d="M7 7h6M7 10h4" stroke="var(--color-text-4)" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                </div>
                <p className="font-medium mb-1" style={{ fontSize: 14, color: "var(--color-text-2)" }}>No submissions yet</p>
                <p style={{ fontSize: 13, color: "var(--color-text-4)", maxWidth: 280, lineHeight: 1.5 }}>
                  Once you join a team and submit an assignment, your activity will appear here.
                </p>
                <div className="flex gap-2 mt-5">
                  <Btn variant="secondary" size="sm" onClick={() => navigate("/student/teams")}>Join a team</Btn>
                  <Btn variant="secondary" size="sm" onClick={() => navigate("/student/assignments")}>View assignments</Btn>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Policy notice */}
      <div className="rounded-xl px-5 py-4 flex gap-3 items-start"
        style={{ background: "var(--color-blue-bg)", border: "1px solid var(--color-blue-border)" }}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="flex-shrink-0 mt-0.5">
          <circle cx="8" cy="8" r="6.5" stroke="var(--color-blue)" strokeWidth="1.4" />
          <path d="M8 7.5V11M8 5.5v-.5" stroke="var(--color-blue)" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        <div>
          <p className="font-semibold mb-0.5" style={{ fontSize: 13, color: "var(--color-blue)" }}>Academic Integrity Policy</p>
          <p style={{ fontSize: 12.5, color: "var(--color-blue)", opacity: 0.8, lineHeight: 1.5 }}>
            All submissions are automatically analysed for AI-generated content, text similarity, and handwriting patterns.
            Ensure your work complies with your institution's academic integrity guidelines.
          </p>
        </div>
      </div>
    </div>
  );
}
