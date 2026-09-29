import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import Btn from "../../components/Btn";
import { Field, Input, Textarea, Select } from "../../components/Field";

import { api } from "../../lib/api";

import TeamQRCodeModal from "../../components/TeamQRCodeModal";

export default function CreateTeam() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [course, setCourse] = useState("");
  const [description, setDescription] = useState("");
  const [maxMembers, setMaxMembers] = useState("30");
  const [joinMode, setJoinMode] = useState("code");
  const [createdTeam, setCreatedTeam] = useState<any>(null);
  const [showQrModal, setShowQrModal] = useState(false);
  const [copied, setCopied] = useState(false);

  function validate() {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Team name is required.";
    if (!course.trim()) e.course = "Course name or code is required.";
    return e;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { return; }
    setLoading(true);
    try {
      const res = await api.teams.create({
        name,
        course_code: course,
        description: description || undefined,
      });
      if (res && res.join_code) {
        setCreatedTeam(res);
      } else {
        navigate("/teacher/teams");
      }
    } catch (err: any) {
      alert(err?.message || "Failed to create team. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Create Team"
        breadcrumbs={[{ label: "Teams" }, { label: "New Team" }]}
        subtitle="Set up a new course team and generate classroom join credentials."
      />

      {createdTeam ? (
        <div style={{ maxWidth: 560 }} className="animate-fade-in-up">
          <div
            className="rounded-2xl p-6 shadow-md space-y-6 text-center"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}
          >
            <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-2xl shadow-sm">
              ✓
            </div>

            <div>
              <h2 className="text-xl font-serif font-bold text-stone-900 dark:text-white">
                Team Created Successfully!
              </h2>
              <p className="text-xs text-stone-500 mt-1">
                "{createdTeam.name}" has been registered. Share the join credentials below with your students.
              </p>
            </div>

            {/* Join Code Presentation Card */}
            <div
              className="p-5 rounded-xl border flex flex-col items-center gap-2"
              style={{ background: "var(--color-canvas)", borderColor: "var(--color-border)" }}
            >
              <span className="text-[10px] uppercase font-bold tracking-wider text-stone-400">
                Official Classroom Join Code
              </span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-2xl font-bold tracking-widest text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 px-4 py-1.5 rounded-xl border border-blue-200 dark:border-blue-800">
                  {createdTeam.join_code}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(createdTeam.join_code);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="px-3 py-2 rounded-xl text-xs font-semibold border cursor-pointer hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  {copied ? "✓ Copied" : "📋 Copy"}
                </button>
              </div>
            </div>

            {/* QR Option Highlight */}
            <div className="p-4 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 flex items-center justify-between gap-4 text-left">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center text-lg shrink-0">
                  📱
                </div>
                <div>
                  <h4 className="text-xs font-bold text-blue-900 dark:text-blue-200">
                    Classroom QR Pass Available
                  </h4>
                  <p className="text-[11px] text-blue-700/80 dark:text-blue-300/80">
                    Project or print a high-resolution QR code for quick student mobile enrollment.
                  </p>
                </div>
              </div>
              <Btn
                variant="primary"
                size="sm"
                onClick={() => setShowQrModal(true)}
                className="shrink-0"
              >
                View QR Pass
              </Btn>
            </div>

            <div className="flex gap-3 pt-3 border-t" style={{ borderColor: "var(--color-border)" }}>
              <Btn
                variant="secondary"
                size="md"
                onClick={() => navigate("/teacher/teams")}
                style={{ flex: 1 }}
              >
                All Teams
              </Btn>
              <Btn
                variant="primary"
                size="md"
                onClick={() => navigate(`/teacher/teams/${createdTeam.id}/members`)}
                style={{ flex: 1 }}
              >
                Manage Team Roster →
              </Btn>
            </div>
          </div>

          <TeamQRCodeModal
            isOpen={showQrModal}
            onClose={() => setShowQrModal(false)}
            team={{
              id: createdTeam.id,
              name: createdTeam.name,
              course: createdTeam.course_code || course,
              code: createdTeam.join_code,
            }}
          />
        </div>
      ) : (
        <div style={{ maxWidth: 520 }}>
          <form onSubmit={handleSubmit} className="rounded-xl p-6 space-y-5"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <Field label="Team name" required>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Advanced Research Methods — Group A" />
            </Field>
            <Field label="Course name / code" required>
              <Input value={course} onChange={(e) => setCourse(e.target.value)} placeholder="e.g. CS301 or Introduction to Computer Science" />
            </Field>
            <Field label="Description" hint="Optional — appears to students when browsing">
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Brief description of this team's scope…" />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Max members">
                <Input type="number" value={maxMembers} onChange={(e) => setMaxMembers(e.target.value)} min="1" style={{ fontFamily: "var(--font-mono)" }} />
              </Field>
              <Field label="Join mode">
                <Select value={joinMode} onChange={(e) => setJoinMode(e.target.value)}>
                  <option value="code">Join code & QR</option>
                  <option value="invite">Invite only</option>
                </Select>
              </Field>
            </div>
            <div className="flex gap-2.5 pt-2" style={{ borderTop: "1px solid var(--color-border)" }}>
              <Btn variant="ghost" size="md" type="button" onClick={() => navigate("/teacher/teams")}>Cancel</Btn>
              <Btn variant="primary" size="md" type="submit" loading={loading} style={{ flex: 1 }}>
                {loading ? "Creating…" : "Create team & generate code"}
              </Btn>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
