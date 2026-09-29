import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import StatusBadge from "../../components/StatusBadge";
import EmptyState from "../../components/EmptyState";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import TeamQRCodeModal from "../../components/TeamQRCodeModal";
import { api } from "../../lib/api";

interface MemberItem {
  id: string;
  name: string;
  email: string;
  role: "student" | "teacher" | "admin";
  joinedAt: string;
}

export default function Members() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [team, setTeam] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQr, setShowQr] = useState(false);

  const [assignments, setAssignments] = useState<any[]>([]);

  useEffect(() => {
    if (id) {
      loadData(id);
    }
  }, [id]);

  async function loadData(teamId: string) {
    setLoading(true);
    setError(null);
    try {
      const [teamData, membersData, assignmentsData] = await Promise.all([
        api.teams.get(teamId).catch(() => null),
        api.teams.getMembers(teamId),
        api.assignments.listByTeam(teamId).catch(() => []),
      ]);
      setTeam(teamData);
      setAssignments(assignmentsData || []);
      const mapped: MemberItem[] = (membersData || []).map((m: any) => ({
        id: m.id || m.user_id,
        name: m.user?.full_name || m.user?.name || "Student",
        email: m.user?.email || "—",
        role: (m.user?.role || "student") as "student" | "teacher" | "admin",
        joinedAt: m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—",
      }));
      setMembers(mapped);
    } catch (err: any) {
      setError(err?.message || "Failed to load team data.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(memberId: string) {
    if (!id || !confirm("Are you sure you want to remove this member from the team?")) return;
    try {
      await api.teams.removeMember(id, memberId);
      setMembers((prev) => prev.filter((m) => m.id !== memberId));
    } catch (err: any) {
      alert(err?.message || "Failed to remove member.");
    }
  }

  return (
    <div>
      <PageHeader
        title={team ? `${team.name}` : "Team Details"}
        breadcrumbs={[{ label: "Teams", onClick: () => navigate("/teacher/teams") }, { label: team?.name || "Team" }]}
        subtitle={team?.join_code ? `Join code: ${team.join_code} · Share with students to enroll.` : "Manage assignments and enrolled students."}
        actions={
          <div className="flex items-center gap-2">
            <Btn
              variant="primary"
              size="sm"
              onClick={() => navigate(`/teacher/assignments/new?teamId=${id}`)}
              icon={
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              }
            >
              + Add Assignment
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => setShowQr(true)}
              icon={<span>📱</span>}
            >
              Classroom QR Pass
            </Btn>
            <Btn
              variant="secondary"
              size="sm"
              onClick={() => {
                if (team?.join_code) {
                  navigator.clipboard.writeText(team.join_code);
                  alert(`Join code ${team.join_code} copied to clipboard!`);
                }
              }}
              icon={
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <rect x="2" y="2" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.4" />
                </svg>
              }
            >
              Copy Code ({team?.join_code || "..."})
            </Btn>
          </div>
        }
      />

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading team roster…</span>
        </div>
      ) : error ? (
        <div
          className="p-4 rounded-xl mb-6 text-sm flex items-center justify-between"
          style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", color: "var(--color-red)" }}
        >
          <span>{error}</span>
          <Btn variant="ghost" size="xs" onClick={() => id && loadData(id)}>Retry</Btn>
        </div>
      ) : members.length === 0 ? (
        <EmptyState
          icon={
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M7 9a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2 18s0-5 5-5 5 5 5 5M14 7.5a3 3 0 1 1 0 6M18 18s0-4.5-4-4.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
          }
          title="No members yet"
          description={
            team?.join_code
              ? `Share join code ${team.join_code} with your students. Members will appear here immediately after joining.`
              : "No members enrolled yet."
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
                {["Member", "Email", "Role", "Joined", ""].map((h) => (
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
              {members.map((m) => (
                <tr key={m.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{
                          background: "var(--color-accent-bg)",
                          color: "var(--color-accent)",
                          fontSize: 11,
                          fontWeight: 600,
                        }}
                      >
                        {m.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                      </div>
                      <span className="font-medium" style={{ fontSize: 13, color: "var(--color-text-1)" }}>
                        {m.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3 font-mono" style={{ fontSize: 12.5, color: "var(--color-text-2)" }}>
                    {m.email}
                  </td>
                  <td className="px-5 py-3">
                    <StatusBadge status={m.role} size="xs" />
                  </td>
                  <td className="px-5 py-3 font-mono" style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                    {m.joinedAt}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleRemove(m.id)}
                      style={{ fontSize: 12, color: "var(--color-red)" }}
                      className="hover:underline cursor-pointer font-medium"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Classroom Join QR Pass Modal */}
      <TeamQRCodeModal
        isOpen={showQr}
        onClose={() => setShowQr(false)}
        team={team ? { id: team.id, name: team.name, course: team.course_code || team.course || "", code: team.join_code } : null}
      />
    </div>
  );
}
