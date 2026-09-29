import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import Btn from "../../components/Btn";
import { Field, Textarea } from "../../components/Field";

interface Criterion { id: string; label: string; max: number; auto: number | null; override: number | null; note: string }

const DEFAULT: Criterion[] = [
  { id: "content",    label: "Content & Argument",     max: 40, auto: null, override: null, note: "" },
  { id: "structure",  label: "Structure & Coherence",   max: 25, auto: null, override: null, note: "" },
  { id: "references", label: "References & Sources",    max: 20, auto: null, override: null, note: "" },
  { id: "language",   label: "Language & Style",        max: 15, auto: null, override: null, note: "" },
];

export default function EditGrading() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [criteria, setCriteria] = useState<Criterion[]>(DEFAULT);
  const [deduction, setDeduction] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [finalising, setFinalising] = useState(false);

  function update(cid: string, field: "override" | "note", value: string | number | null) {
    setCriteria((prev) => prev.map((c) => c.id === cid ? { ...c, [field]: value } : c));
  }

  const totalMax = criteria.reduce((s, c) => s + c.max, 0);
  const totalAuto = criteria.reduce((s, c) => s + (c.auto ?? 0), 0);
  const totalFinal = criteria.reduce((s, c) => s + (c.override ?? c.auto ?? 0), 0) - deduction;

  async function save() {
    setSaving(true);
    await new Promise((r) => setTimeout(r, 800));
    setSaving(false);
    setSaved(true);
  }

  async function finalise() {
    setFinalising(true);
    await new Promise((r) => setTimeout(r, 1000));
    setFinalising(false);
    navigate("/teacher/grading");
  }

  return (
    <div>
      <PageHeader
        title="Grade Submission"
        breadcrumbs={[{ label: "Grading" }, { label: "Edit" }]}
        subtitle="Review auto-generated scores, apply overrides, and release the grade."
      />

      <div className="max-w-2xl space-y-5">
        {/* Criteria */}
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid var(--color-border)" }}>
            <p className="font-semibold" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Grading Criteria</p>
            <div className="flex items-center gap-4 font-mono" style={{ fontSize: 12 }}>
              <span style={{ color: "var(--color-text-3)" }}>Auto: <strong style={{ color: "var(--color-text-1)" }}>{totalAuto}/{totalMax}</strong></span>
              <span style={{ color: "var(--color-text-3)" }}>
                Final: <strong style={{ color: totalFinal < totalAuto ? "var(--color-red)" : "var(--color-green)" }}>{totalFinal}/{totalMax}</strong>
              </span>
            </div>
          </div>

          <div>
            {criteria.map((c, i) => (
              <div key={c.id} className="px-5 py-4" style={{ borderBottom: i < criteria.length - 1 ? "1px solid var(--color-border)" : "none" }}>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <p className="font-medium" style={{ fontSize: 13.5, color: "var(--color-text-1)" }}>{c.label}</p>
                    <p style={{ fontSize: 12, color: "var(--color-text-4)", marginTop: 1 }}>Max {c.max} pts</p>
                  </div>
                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="text-right">
                      <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 3 }}>Auto</p>
                      <p className="font-mono font-semibold" style={{ fontSize: 16, color: "var(--color-text-3)" }}>
                        {c.auto != null ? c.auto : "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p style={{ fontSize: 11, color: "var(--color-text-4)", marginBottom: 3 }}>Override</p>
                      <input
                        type="number"
                        min="0"
                        max={c.max}
                        value={c.override ?? ""}
                        onChange={(e) => update(c.id, "override", e.target.value === "" ? null : Number(e.target.value))}
                        placeholder={c.auto != null ? String(c.auto) : "—"}
                        style={{
                          width: 60,
                          border: "1.5px solid var(--color-border-2)",
                          borderRadius: 8,
                          padding: "5px 8px",
                          fontSize: 14,
                          fontFamily: "var(--font-mono)",
                          fontWeight: 600,
                          textAlign: "right",
                          color: "var(--color-accent)",
                          outline: "none",
                          background: c.override != null ? "var(--color-accent-bg)" : "var(--color-surface)",
                        }}
                        onFocus={(e) => { (e.target as HTMLElement).style.borderColor = "var(--color-accent)"; }}
                        onBlur={(e) => { (e.target as HTMLElement).style.borderColor = "var(--color-border-2)"; }}
                      />
                    </div>
                  </div>
                </div>
                <input
                  type="text"
                  value={c.note}
                  onChange={(e) => update(c.id, "note", e.target.value)}
                  placeholder="Add annotation for this criterion…"
                  style={{
                    width: "100%",
                    border: "1px solid var(--color-border)",
                    borderRadius: 6,
                    padding: "6px 10px",
                    fontSize: 12.5,
                    fontFamily: "inherit",
                    color: "var(--color-text-2)",
                    background: "var(--color-canvas)",
                    outline: "none",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => { (e.target as HTMLElement).style.borderColor = "var(--color-accent)"; }}
                  onBlur={(e) => { (e.target as HTMLElement).style.borderColor = "var(--color-border)"; }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Integrity deduction */}
        <div className="rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <p className="font-semibold mb-3" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Academic Integrity Deduction</p>
          <div className="flex items-center gap-4">
            <label style={{ fontSize: 13, color: "var(--color-text-2)" }}>Deduction (pts)</label>
            <input
              type="number"
              min="0"
              max={totalMax}
              value={deduction}
              onChange={(e) => setDeduction(Number(e.target.value))}
              style={{
                width: 72,
                border: "1.5px solid var(--color-border-2)",
                borderRadius: 8,
                padding: "5px 8px",
                fontSize: 14,
                fontFamily: "var(--font-mono)",
                textAlign: "right",
                color: "var(--color-red)",
                background: deduction > 0 ? "var(--color-red-bg)" : "var(--color-surface)",
                outline: "none",
              }}
            />
            {deduction > 0 && (
              <span className="font-medium font-mono" style={{ fontSize: 13, color: "var(--color-red)" }}>−{deduction} pts deducted</span>
            )}
          </div>
        </div>

        {/* Feedback */}
        <div className="rounded-xl p-5" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <p className="font-semibold mb-3" style={{ fontSize: 14, color: "var(--color-text-1)" }}>Student Feedback</p>
          <Field label="Comments" hint="Visible to the student after grade release">
            <Textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={5}
              placeholder="Write feedback for the student…"
            />
          </Field>
        </div>

        {saved && (
          <div className="rounded-lg px-4 py-3" style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)", fontSize: 13, color: "var(--color-green)" }}>
            Draft saved successfully.
          </div>
        )}

        <div className="flex gap-2.5">
          <Btn variant="ghost" size="md" onClick={() => navigate("/teacher/grading")}>Cancel</Btn>
          <Btn variant="outline" size="md" loading={saving} onClick={save}>Save draft</Btn>
          <Btn variant="primary" size="md" loading={finalising} onClick={finalise} style={{ flex: 1, maxWidth: 220 }}>
            {finalising ? "Finalising…" : "Finalise & release"}
          </Btn>
        </div>
      </div>
    </div>
  );
}
