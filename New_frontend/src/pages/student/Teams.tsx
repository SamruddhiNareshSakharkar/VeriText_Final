import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { Input } from "../../components/Field";
import { api } from "../../lib/api";

interface TeamItem {
  id: string;
  name: string;
  code: string;
  course: string;
  instructor: string;
  memberCount: number;
  status: string;
  openAssignments: number;
}

export default function StudentTeams() {
  const navigate = useNavigate();
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [loadingTeams, setLoadingTeams] = useState(true);
  const [showJoin, setShowJoin] = useState(false);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [joinSuccess, setJoinSuccess] = useState("");

  useEffect(() => {
    loadTeams();
  }, []);

  async function loadTeams() {
    setLoadingTeams(true);
    try {
      const data = await api.teams.list();
      const mapped: TeamItem[] = (data || []).map((t: any) => ({
        id: t.id,
        name: t.name,
        code: t.join_code,
        course: t.course_code || t.description || "Course Team",
        instructor: t.owner?.full_name || "Instructor",
        memberCount: t.member_count ?? 1,
        status: "active",
        openAssignments: t.assignment_count ?? 0,
      }));
      setTeams(mapped);
    } catch (err: any) {
      console.error("Failed to load student teams:", err);
    } finally {
      setLoadingTeams(false);
    }
  }

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setJoinError("");
    setJoinSuccess("");
    setLoading(true);
    try {
      const joinedTeam = await api.teams.join(code.trim());
      setJoinSuccess(`Successfully joined ${joinedTeam.name}!`);
      setCode("");
      await loadTeams();
      setTimeout(() => {
        setShowJoin(false);
        setJoinSuccess("");
      }, 1000);
    } catch (err: any) {
      setJoinError(err?.message || "Failed to join team. Please check the code and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="My Teams"
        subtitle="Teams you have joined this semester."
        actions={
          <Btn
            variant="primary"
            size="sm"
            onClick={() => { setShowJoin(true); setJoinError(""); setJoinSuccess(""); }}
            icon={<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}
          >
            Join team
          </Btn>
        }
      />

      {/* Join modal */}
      {showJoin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(9,24,46,0.5)" }}>
          <div className="rounded-2xl p-6 w-full" style={{ maxWidth: 420, background: "var(--color-surface)", boxShadow: "0 25px 50px rgba(0,0,0,0.18)" }}>
            <h2 className="font-semibold mb-1" style={{ fontSize: 17, color: "var(--color-text-1)" }}>Join a team</h2>
            <p style={{ fontSize: 13, color: "var(--color-text-3)", marginBottom: 20 }}>
              Enter the join code your instructor provided (e.g. <code>VTX-AWF4HH</code> or <code>AWF4HH</code>).
            </p>
            <form onSubmit={handleJoin} className="space-y-3">
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="e.g. VTX-AWF4HH"
                autoFocus
                style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em", fontSize: 15 }}
              />
              {joinError && <p style={{ fontSize: 12, color: "var(--color-red)" }}>{joinError}</p>}
              {joinSuccess && <p style={{ fontSize: 12, color: "var(--color-green, #10b981)" }}>{joinSuccess}</p>}
              <div className="flex gap-2 pt-1">
                <Btn
                  variant="secondary"
                  size="md"
                  type="button"
                  style={{ flex: 1 }}
                  onClick={() => { setShowJoin(false); setCode(""); setJoinError(""); setJoinSuccess(""); }}
                >
                  Cancel
                </Btn>
                <Btn variant="primary" size="md" type="submit" loading={loading} style={{ flex: 1 }}>
                  {loading ? "Joining…" : "Join"}
                </Btn>
              </div>
            </form>
          </div>
        </div>
      )}

      {loadingTeams ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading your teams…</span>
        </div>
      ) : teams.length === 0 ? (
        <EmptyState
          icon={<svg width="22" height="22" viewBox="0 0 22 22" fill="none"><path d="M8 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 18s0-5 5-5 5 5 5 5M14 7a3 3 0 1 1 0 6M19 18s0-4-5-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>}
          title="No teams yet"
          description="Join a team using the code your instructor provided to start receiving assignments."
          action={{ label: "Join a team", onClick: () => { setShowJoin(true); setJoinError(""); } }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {teams.map((team) => (
            <div
              key={team.id}
              onClick={() => navigate(`/student/teams/${team.id}`)}
              className="rounded-xl p-5 cursor-pointer transition-all hover:shadow-md"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.borderColor = "var(--color-accent)")}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)")}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>{team.name}</p>
                  <p style={{ fontSize: 12.5, color: "var(--color-text-3)", marginTop: 2 }}>{team.course}</p>
                </div>
                <StatusBadge status={team.status} />
              </div>
              <p style={{ fontSize: 12, color: "var(--color-text-4)", marginBottom: 14 }}>Instructor: {team.instructor}</p>
              <div className="flex items-center justify-between pt-3" style={{ borderTop: "1px solid var(--color-border)" }}>
                <span className="font-mono" style={{ fontSize: 11.5, color: "var(--color-text-4)" }}>{team.code}</span>
                <div className="flex items-center gap-3">
                  <span style={{ fontSize: 12, color: "var(--color-text-3)" }}>{team.memberCount} members</span>
                  {team.openAssignments > 0 && (
                    <span className="font-medium font-mono" style={{ fontSize: 11.5, color: "var(--color-accent)", background: "var(--color-accent-bg)", padding: "2px 7px", borderRadius: 20 }}>
                      {team.openAssignments} open
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

