import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import EmptyState from "../../components/EmptyState";
import Spinner from "../../components/Spinner";
import { api } from "../../lib/api";

interface Member { id: string; name: string; role: string; joinedAt: string }
interface Assignment { id: string; title: string; dueDate: string; status: string; submitted: boolean }

export default function TeamOverview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [team, setTeam] = useState<any>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    loadTeamData(id);
  }, [id]);

  async function loadTeamData(teamId: string) {
    setLoading(true);
    setError(null);
    try {
      const [tData, mData, aData] = await Promise.all([
        api.teams.get(teamId),
        api.teams.getMembers(teamId).catch(() => []),
        api.assignments.listByTeam(teamId).catch(() => []),
      ]);
      setTeam(tData);
      setMembers(
        (mData || []).map((m: any) => ({
          id: m.id || m.user_id,
          name: m.user?.full_name || m.full_name || "Member",
          role: m.user?.role || "student",
          joinedAt: m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "Recently",
        }))
      );
      setAssignments(
        (aData || []).map((a: any) => ({
          id: a.id,
          title: a.title,
          dueDate: a.due_date ? new Date(a.due_date).toLocaleDateString() : "No due date",
          status: a.is_active ? "open" : "closed",
          submitted: false,
        }))
      );
    } catch (err: any) {
      setError(err?.message || "Failed to load team details.");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size={28} color="var(--color-accent)" />
        <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading team information…</span>
      </div>
    );
  }

  if (error || !team) {
    return (
      <div>
        <PageHeader title="Team Overview" breadcrumbs={[{ label: "My Teams" }, { label: "Error" }]} />
        <div className="p-4 rounded-xl text-sm" style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", color: "var(--color-red)" }}>
          {error || "Team not found."}
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={team.name}
        breadcrumbs={[{ label: "My Teams", onClick: () => navigate("/student/teams") }, { label: team.name }]}
        subtitle={team.description || "Team details, members, and current assignments."}
      />

      {/* Team info card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <div className="lg:col-span-2 rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                style={{ background: "var(--color-accent-bg)", border: "1px solid var(--color-blue-border)" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M7 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 16s0-5 5-5 5 5 5 5M13 6a2 2 0 1 1 0 4M17 16s0-4-4-4" stroke="var(--color-accent)" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </div>
              <p className="font-semibold" style={{ fontSize: 18, color: "var(--color-text-1)" }}>{team.name}</p>
              <p style={{ fontSize: 13, color: "var(--color-text-3)", marginTop: 2 }}>Course: {team.course_code || "General"}</p>
            </div>
            <StatusBadge status="active" />
          </div>
          <div className="grid grid-cols-3 gap-4 pt-4" style={{ borderTop: "1px solid var(--color-border)" }}>
            {[
              { label: "Join code", value: team.join_code, mono: true },
              { label: "Members", value: team.member_count ?? members.length },
              { label: "Open assignments", value: assignments.length },
            ].map((stat) => (
              <div key={stat.label}>
                <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 3 }}>{stat.label}</p>
                <p className={stat.mono ? "font-mono font-semibold" : "font-semibold"} style={{ fontSize: 15, color: "var(--color-text-1)" }}>{stat.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <p className="font-semibold mb-3" style={{ fontSize: 13, color: "var(--color-text-1)" }}>Instructor</p>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-white flex-shrink-0"
              style={{ background: "var(--color-navy)", fontSize: 12, fontWeight: 600 }}>
              {(team.owner?.full_name || "I")[0].toUpperCase()}
            </div>
            <div>
              <p className="font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{team.owner?.full_name || "Instructor"}</p>
              <p style={{ fontSize: 12, color: "var(--color-text-3)" }}>{team.owner?.email || "—"}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Members */}
      <div className="rounded-xl overflow-hidden mb-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
          <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Members</p>
        </div>
        {members.length === 0 ? (
          <div className="py-10 text-center" style={{ color: "var(--color-text-4)", fontSize: 13 }}>No members data available.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                {["Name", "Role", "Joined"].map((h) => (
                  <th key={h} className="text-left px-5 py-3 font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td className="px-5 py-3" style={{ fontSize: 13, color: "var(--color-text-1)", fontWeight: 500 }}>{m.name}</td>
                  <td className="px-5 py-3"><StatusBadge status={m.role} /></td>
                  <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>{m.joinedAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Assignments */}
      <div className="rounded-xl overflow-hidden" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
        <div className="px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
          <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Assignments</p>
        </div>
        {assignments.length === 0 ? (
          <div className="py-10 text-center" style={{ color: "var(--color-text-4)", fontSize: 13 }}>No assignments in this team yet.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr style={{ background: "var(--color-surface-2)", borderBottom: "1px solid var(--color-border)" }}>
                {["Assignment", "Due", "Status", ""].map((h, i) => (
                  <th key={i} className="text-left px-5 py-3 font-semibold uppercase tracking-wider" style={{ fontSize: 10.5, color: "var(--color-text-3)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assignments.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td className="px-5 py-3 font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>{a.title}</td>
                  <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>{a.dueDate}</td>
                  <td className="px-5 py-3"><StatusBadge status={a.status} /></td>
                  <td className="px-5 py-3 text-right">
                    {!a.submitted && (
                      <button
                        onClick={() => navigate(`/student/submit/${a.id}`)}
                        className="font-medium transition-colors hover:underline"
                        style={{ fontSize: 12.5, color: "var(--color-accent)" }}
                      >
                        Submit →
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
