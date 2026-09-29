import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import EmptyState from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import TeamQRCodeModal from "../../components/TeamQRCodeModal";
import { api } from "../../lib/api";

interface TeamItem {
  id: string;
  name: string;
  code: string;
  course: string;
  memberCount: number;
  assignmentCount: number;
  status: string;
  createdAt: string;
}

const CARD_GRADIENTS = [
  "linear-gradient(135deg, #2255D3 0%, #1A45B8 100%)",
  "linear-gradient(135deg, #6025A0 0%, #4E1D87 100%)",
  "linear-gradient(135deg, #0B6CCB 0%, #0958A8 100%)",
  "linear-gradient(135deg, #14904A 0%, #0E7A3B 100%)",
  "linear-gradient(135deg, #B05A00 0%, #965000 100%)",
  "linear-gradient(135deg, #CC1E1E 0%, #A51919 100%)",
];

export default function TeacherTeams() {
  const navigate = useNavigate();
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedQrTeam, setSelectedQrTeam] = useState<{ id: string; name: string; course: string; code: string } | null>(null);

  useEffect(() => {
    loadTeams();
  }, []);

  async function loadTeams() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.teams.list();
      const mapped: TeamItem[] = (data || []).map((t: any) => ({
        id: t.id,
        name: t.name,
        code: t.join_code || "—",
        course: t.course_code || t.description || "Course Team",
        memberCount: t.member_count ?? 0,
        assignmentCount: t.assignment_count ?? 0,
        status: "active",
        createdAt: t.created_at ? new Date(t.created_at).toLocaleDateString() : "—",
      }));
      setTeams(mapped);
    } catch (err: any) {
      setError(err?.message || "Failed to load teams.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = teams.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.course.toLowerCase().includes(search.toLowerCase()) ||
      t.code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Teams"
        subtitle="Manage course teams and enrolled students."
        actions={
          <Btn
            variant="primary"
            size="sm"
            onClick={() => navigate("/teacher/teams/new")}
            icon={
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            }
          >
            Create team
          </Btn>
        }
      />

      {/* Search Bar */}
      {!loading && !error && teams.length > 0 && (
        <div className="mb-5 animate-fade-in">
          <div className="relative" style={{ maxWidth: 380 }}>
            <svg
              width="15" height="15" viewBox="0 0 15 15" fill="none"
              className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: "var(--color-text-4)" }}
            >
              <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.4" />
              <path d="M10 10l3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search teams by name, course, or code…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                color: "var(--color-text-1)",
                outline: "none",
                fontFamily: "var(--font-sans)",
                transition: "border-color 0.2s, box-shadow 0.2s",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--color-accent)";
                e.currentTarget.style.boxShadow = "0 0 0 3px var(--color-accent-ring)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border)";
                e.currentTarget.style.boxShadow = "none";
              }}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size={24} color="var(--color-accent)" />
          <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading teams…</span>
        </div>
      ) : error ? (
        <div
          className="p-4 rounded-xl mb-6 text-sm flex items-center justify-between"
          style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", color: "var(--color-red)" }}
        >
          <span>{error}</span>
          <Btn variant="ghost" size="xs" onClick={loadTeams}>Retry</Btn>
        </div>
      ) : teams.length === 0 ? (
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
          title="No teams yet"
          description="Create your first team and share the join code with your students."
          action={{ label: "Create team", onClick: () => navigate("/teacher/teams/new") }}
        />
      ) : filtered.length === 0 ? (
        <div className="py-16 flex flex-col items-center text-center animate-fade-in">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" className="mb-4" style={{ color: "var(--color-text-4)" }}>
            <circle cx="18" cy="18" r="12" stroke="currentColor" strokeWidth="2" />
            <path d="M27 27l7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <p className="font-medium" style={{ fontSize: 14, color: "var(--color-text-2)" }}>No teams match "{search}"</p>
          <p style={{ fontSize: 13, color: "var(--color-text-4)", marginTop: 4 }}>Try a different search term</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((t, idx) => (
            <div
              key={t.id}
              onClick={() => navigate(`/teacher/teams/${t.id}/members`)}
              className={`rounded-xl overflow-hidden cursor-pointer card-hover animate-fade-in-up anim-delay-${Math.min(idx + 1, 6)}`}
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
              }}
            >
              {/* Gradient header stripe */}
              <div
                className="px-5 py-4 flex items-center justify-between"
                style={{
                  background: CARD_GRADIENTS[idx % CARD_GRADIENTS.length],
                  minHeight: 56,
                }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: "rgba(255,255,255,0.2)", backdropFilter: "blur(8px)" }}
                  >
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                      <path
                        d="M6 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM1.5 16s0-4.5 4.5-4.5S10.5 16 10.5 16M13 6.5a2.5 2.5 0 1 1 0 5M16.5 16s0-4-3.5-4"
                        stroke="white"
                        strokeWidth="1.3"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="font-semibold text-white" style={{ fontSize: 15 }}>{t.name}</p>
                    <p style={{ fontSize: 11.5, color: "rgba(255,255,255,0.75)" }}>{t.course}</p>
                  </div>
                </div>
                <StatusBadge status={t.status} size="xs" />
              </div>

              {/* Card body */}
              <div className="px-5 py-4">
                {/* Join code & QR Option */}
                <div className="flex items-center justify-between gap-2 mb-4">
                  <div className="flex items-center gap-2">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ color: "var(--color-text-4)" }}>
                      <rect x="2" y="6" width="10" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
                      <path d="M4.5 6V4a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </svg>
                    <span
                      className="font-mono px-2.5 py-1 rounded-lg text-xs font-semibold"
                      style={{ background: "var(--color-accent-bg)", color: "var(--color-accent)" }}
                    >
                      {t.code}
                    </span>
                  </div>

                  {/* QR Code Trigger Button */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedQrTeam({ id: t.id, name: t.name, course: t.course, code: t.code });
                    }}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition-all cursor-pointer hover:shadow-sm"
                    style={{
                      background: "var(--color-canvas)",
                      borderColor: "var(--color-border)",
                      color: "var(--color-text-2)",
                    }}
                    title="Generate & View Classroom QR Pass"
                  >
                    <span>📱</span>
                    <span>QR Pass</span>
                  </button>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-2.5 rounded-lg text-center" style={{ background: "var(--color-canvas)" }}>
                    <p className="font-mono font-bold" style={{ fontSize: 18, color: "var(--color-text-1)" }}>{t.memberCount}</p>
                    <p className="uppercase tracking-wider" style={{ fontSize: 9.5, color: "var(--color-text-4)", marginTop: 2 }}>Members</p>
                  </div>
                  <div className="p-2.5 rounded-lg text-center" style={{ background: "var(--color-canvas)" }}>
                    <p className="font-mono font-bold" style={{ fontSize: 18, color: "var(--color-text-1)" }}>{t.assignmentCount}</p>
                    <p className="uppercase tracking-wider" style={{ fontSize: 9.5, color: "var(--color-text-4)", marginTop: 2 }}>Assignments</p>
                  </div>
                  <div className="p-2.5 rounded-lg text-center" style={{ background: "var(--color-canvas)" }}>
                    <p className="font-mono" style={{ fontSize: 11, color: "var(--color-text-3)" }}>{t.createdAt}</p>
                    <p className="uppercase tracking-wider" style={{ fontSize: 9.5, color: "var(--color-text-4)", marginTop: 2 }}>Created</p>
                  </div>
                </div>

                {/* Action footer */}
                <div className="flex items-center justify-between mt-4 pt-3" style={{ borderTop: "1px solid var(--color-border)" }}>
                  <span style={{ fontSize: 12, color: "var(--color-text-4)" }}>Click to manage →</span>
                  <button
                    style={{ fontSize: 12, color: "var(--color-accent)" }}
                    className="hover:underline font-semibold"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/teacher/teams/${t.id}/members`);
                    }}
                  >
                    View Members
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Classroom Join QR Pass Modal */}
      <TeamQRCodeModal
        isOpen={Boolean(selectedQrTeam)}
        onClose={() => setSelectedQrTeam(null)}
        team={selectedQrTeam}
      />
    </div>
  );
}
