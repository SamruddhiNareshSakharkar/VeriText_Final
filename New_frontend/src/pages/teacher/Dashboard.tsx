import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import StatusBadge from "../../components/StatusBadge";
import { useApp } from "../../lib/context";
import { api } from "../../lib/api";

function KPI({
  label,
  value,
  sub,
  highlight,
  icon,
  delay,
}: {
  label: string;
  value: string | number;
  sub?: string;
  highlight?: "warn" | "danger";
  icon?: React.ReactNode;
  delay?: number;
}) {
  const vc =
    highlight === "danger"
      ? "var(--color-red)"
      : highlight === "warn"
      ? "var(--color-amber)"
      : "var(--color-text-1)";
  return (
    <div
      className={`rounded-xl p-5 cursor-default card-hover animate-fade-in-up anim-delay-${delay || 1}`}
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="uppercase tracking-wider font-medium" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>
          {label}
        </p>
        {icon && (
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: highlight === "danger" ? "var(--color-red-bg)" : highlight === "warn" ? "var(--color-amber-bg)" : "var(--color-accent-bg)", color: highlight === "danger" ? "var(--color-red)" : highlight === "warn" ? "var(--color-amber)" : "var(--color-accent)" }}
          >
            {icon}
          </div>
        )}
      </div>
      <p className="font-semibold font-mono" style={{ fontSize: 28, color: vc }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 12, color: "var(--color-text-4)", marginTop: 4 }}>{sub}</p>}
    </div>
  );
}

function QA({
  label,
  desc,
  href,
  icon,
  gradient,
  delay,
}: {
  label: string;
  desc: string;
  href: string;
  icon: React.ReactNode;
  gradient?: string;
  delay?: number;
}) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(href)}
      className={`rounded-xl p-4 text-left transition-all w-full cursor-pointer card-hover animate-fade-in-up anim-delay-${delay || 1}`}
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
        style={{ background: gradient || "var(--color-accent-bg)", color: gradient ? "white" : "var(--color-accent)" }}
      >
        {icon}
      </div>
      <p className="font-semibold" style={{ fontSize: 13, color: "var(--color-text-1)" }}>
        {label}
      </p>
      <p style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 3, lineHeight: 1.4 }}>
        {desc}
      </p>
    </button>
  );
}

export default function TeacherDashboard() {
  const { user } = useApp();
  const navigate = useNavigate();
  const first = user?.name ? user.name.split(" ")[0] : "Instructor";

  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const data = await api.analytics.stats();
        setStats(data);
      } catch (err) {
        console.error("Failed to load dashboard stats", err);
      } finally {
        setLoading(false);
      }
    }
    loadStats();
  }, []);

  const ACTIONS = [
    {
      label: "Create Team",
      desc: "Set up a new course team and share the join code",
      href: "/teacher/teams/new",
      gradient: "linear-gradient(135deg, #2255D3, #1A45B8)",
      icon: (
        <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
          <path d="M7 8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 15s0-5 5-5 5 5 5 5M12 4.5a2.5 2.5 0 1 1 0 5M15.5 15s0-4.5-3.5-4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      label: "Create Assignment",
      desc: "Add a new assessment with rubrics and deadlines",
      href: "/teacher/assignments/new",
      gradient: "linear-gradient(135deg, #6025A0, #4E1D87)",
      icon: (
        <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
          <rect x="3" y="2" width="11" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
          <path d="M6 6.5h5M6 9h5M6 11.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      label: "Review Submissions",
      desc: "Grade pending submissions and review results",
      href: "/teacher/submissions",
      gradient: "linear-gradient(135deg, #14904A, #0E7A3B)",
      icon: (
        <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
          <path d="M4 15V7l4.5-4 4.5 4v8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6.5 15V10h4v5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      label: "Compare Documents",
      desc: "Side-by-side similarity and plagiarism analysis",
      href: "/teacher/compare",
      gradient: "linear-gradient(135deg, #B05A00, #965000)",
      icon: (
        <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
          <rect x="2" y="3" width="5.5" height="11" rx="1" stroke="currentColor" strokeWidth="1.4" />
          <rect x="9.5" y="3" width="5.5" height="11" rx="1" stroke="currentColor" strokeWidth="1.4" />
          <path d="M7.5 8.5h2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      ),
    },
  ];

  return (
    <div>
      {/* Hero Banner */}
      <div
        className="-mx-7 -mt-6 px-7 pt-7 pb-7 mb-6 animate-fade-in"
        style={{
          background: "linear-gradient(135deg, #09182E 0%, #112347 40%, #1A3260 70%, #2255D3 100%)",
          borderBottom: "1px solid var(--color-navy-border)",
        }}
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
                style={{ background: "rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.8)", backdropFilter: "blur(8px)", border: "1px solid rgba(255,255,255,0.1)" }}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400" style={{ animation: "pulse-glow 2s ease-in-out infinite" }} />
                Dashboard Active
              </span>
            </div>
            <h1 className="font-sans text-white font-bold tracking-tight" style={{ fontSize: 26 }}>
              Welcome back, {first}
            </h1>
            <p className="mt-1.5" style={{ fontSize: 13, color: "rgba(255,255,255,0.6)", lineHeight: 1.5, maxWidth: 460 }}>
              Overview of your course teams, assignments, and academic integrity verification pipelines.
            </p>
          </div>
          <div className="flex items-center gap-2">
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
              New Assignment
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => navigate("/teacher/reports")}
              style={{ background: "rgba(255,255,255,0.1)", color: "white", borderColor: "rgba(255,255,255,0.2)" }}
            >
              Reports
            </Btn>
          </div>
        </div>

        {/* Mini stats in hero */}
        {!loading && stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 pt-5" style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}>
            {[
              { label: "Teams", value: stats?.total_teams ?? 0 },
              { label: "Assignments", value: stats?.total_assignments ?? 0 },
              { label: "Submissions", value: stats?.total_submissions ?? 0 },
              { label: "AI Flags", value: stats?.high_ai_flags ?? 0, warn: (stats?.high_ai_flags ?? 0) > 0 },
            ].map((s, i) => (
              <div
                key={s.label}
                className={`rounded-xl px-4 py-3 animate-fade-in-up anim-delay-${i + 1}`}
                style={{ background: "rgba(255,255,255,0.06)", backdropFilter: "blur(8px)" }}
              >
                <p className="uppercase tracking-wider font-medium" style={{ fontSize: 10, color: "rgba(255,255,255,0.5)" }}>{s.label}</p>
                <p className="font-mono font-bold mt-1" style={{ fontSize: 22, color: s.warn ? "#f87171" : "white" }}>{s.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading live course telemetry…</span>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <KPI
              label="Active Teams"
              value={stats?.total_teams ?? 0}
              sub={`${stats?.total_teams ?? 0} courses instructed`}
              delay={1}
              icon={
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M5 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM1.5 12s0-3.5 3.5-3.5S8.5 12 8.5 12M10.5 4.5a1.5 1.5 0 1 1 0 3M12.5 12s0-3-2.5-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              }
            />
            <KPI
              label="Assignments"
              value={stats?.total_assignments ?? 0}
              sub={`${stats?.total_submissions ?? 0} total submissions`}
              delay={2}
              icon={
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <rect x="2.5" y="1.5" width="9" height="11" rx="1" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M4.5 5h5M4.5 7.5h5M4.5 10h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              }
            />
            <KPI
              label="Pending Review"
              value={stats?.pending_reviews ?? 0}
              sub="Awaiting evaluation"
              highlight={stats?.pending_reviews > 0 ? "warn" : undefined}
              delay={3}
              icon={
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.2" />
                  <path d="M7 4v3.5l2.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              }
            />
            <KPI
              label="High AI Flags"
              value={stats?.high_ai_flags ?? 0}
              sub="Above 50% AI confidence"
              highlight={stats?.high_ai_flags > 0 ? "danger" : undefined}
              delay={4}
              icon={
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1.5l5.5 10H1.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
                  <path d="M7 6v2.5M7 10v.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                </svg>
              }
            />
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            {ACTIONS.map((a, i) => (
              <QA key={a.href} {...a} delay={i + 1} />
            ))}
          </div>

          {/* Recent activity */}
          <div
            className="rounded-xl overflow-hidden shadow-sm animate-fade-in-up anim-delay-5"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{ borderBottom: "1px solid var(--color-border)" }}
            >
              <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>
                Recent submission activity
              </p>
              <button
                onClick={() => navigate("/teacher/submissions")}
                style={{ fontSize: 12.5, color: "var(--color-accent)" }}
                className="hover:underline cursor-pointer"
              >
                View all →
              </button>
            </div>

            {stats?.recent_submissions && stats.recent_submissions.length > 0 ? (
              <table className="w-full">
                <thead>
                  <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                    {["Student", "Assignment", "Submitted", "AI Score", "Status", ""].map((h) => (
                      <th
                        key={h}
                        className="text-left px-5 py-3 font-semibold uppercase tracking-wider"
                        style={{ fontSize: 10.5, color: "var(--color-text-3)" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_submissions.map((item: any) => (
                    <tr
                      key={item.submission_id}
                      style={{ borderBottom: "1px solid var(--color-border)" }}
                      className="cursor-pointer transition-colors"
                      onClick={() => navigate(`/teacher/submissions/${item.submission_id}`)}
                      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-canvas)")}
                      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "")}
                    >
                      <td className="px-5 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>
                        {item.student_name}
                      </td>
                      <td className="px-5 py-3" style={{ fontSize: 13, color: "var(--color-text-2)" }}>
                        {item.assignment_title}
                      </td>
                      <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                        {new Date(item.submitted_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 font-mono font-semibold" style={{ fontSize: 12 }}>
                        {item.ai_score != null ? (
                          <span style={{ color: item.ai_score >= 50 ? "var(--color-red)" : "var(--color-green)" }}>
                            {Math.round(item.ai_score)}%
                          </span>
                        ) : (
                          <span style={{ color: "var(--color-text-4)" }}>—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge status={item.status} size="xs" />
                      </td>
                      <td className="px-5 py-3 text-right">
                        <span style={{ fontSize: 12, color: "var(--color-accent)" }}>Inspect →</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-16 flex flex-col items-center text-center px-6">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
                  style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}
                >
                  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                    <rect x="3" y="2" width="16" height="18" rx="2" stroke="var(--color-text-4)" strokeWidth="1.4" />
                    <path d="M7 7h8M7 11h5" stroke="var(--color-text-4)" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                </div>
                <p className="font-medium mb-1" style={{ fontSize: 14, color: "var(--color-text-2)" }}>
                  No submission activity yet
                </p>
                <p style={{ fontSize: 13, color: "var(--color-text-4)", maxWidth: 320, lineHeight: 1.5 }}>
                  Create an assignment and share your team code to start receiving and verifying submissions.
                </p>
                <Btn
                  variant="primary"
                  size="sm"
                  className="mt-4"
                  onClick={() => navigate("/teacher/assignments/new")}
                >
                  Create First Assignment
                </Btn>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
