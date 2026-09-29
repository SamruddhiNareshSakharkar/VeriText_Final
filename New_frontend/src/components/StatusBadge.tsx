interface Props {
  status: string;
  size?: "xs" | "sm";
}

interface Cfg { label: string; color: string; bg: string; border: string }

const MAP: Record<string, Cfg> = {
  draft:               { label: "Draft",            color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  submitted:           { label: "Submitted",         color: "var(--color-blue)",   bg: "var(--color-blue-bg)",   border: "var(--color-blue-border)" },
  processing:          { label: "Processing",        color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  ocr_processing:      { label: "OCR",               color: "var(--color-violet)", bg: "var(--color-violet-bg)", border: "var(--color-violet-border)" },
  ai_analysis:         { label: "AI Analysis",       color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  similarity_check:    { label: "Similarity",        color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  handwriting_analysis:{ label: "Handwriting",       color: "var(--color-violet)", bg: "var(--color-violet-bg)", border: "var(--color-violet-border)" },
  grading:             { label: "Grading",           color: "var(--color-blue)",   bg: "var(--color-blue-bg)",   border: "var(--color-blue-border)" },
  complete:            { label: "Complete",          color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  completed:           { label: "Complete",          color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  analysed:            { label: "Analysed",          color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  queued:              { label: "Queued",            color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  failed:              { label: "Failed",            color: "var(--color-red)",    bg: "var(--color-red-bg)",    border: "var(--color-red-border)" },
  partial:             { label: "Partial",           color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  error:               { label: "Error",             color: "var(--color-red)",    bg: "var(--color-red-bg)",    border: "var(--color-red-border)" },
  flagged:             { label: "Flagged",           color: "var(--color-red)",    bg: "var(--color-red-bg)",    border: "var(--color-red-border)" },
  pending:             { label: "Pending",           color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  active:              { label: "Active",            color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  inactive:            { label: "Inactive",          color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  open:                { label: "Open",              color: "var(--color-blue)",   bg: "var(--color-blue-bg)",   border: "var(--color-blue-border)" },
  closed:              { label: "Closed",            color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  late:                { label: "Late",              color: "var(--color-red)",    bg: "var(--color-red-bg)",    border: "var(--color-red-border)" },
  graded:              { label: "Graded",            color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  student:             { label: "Student",           color: "var(--color-violet)", bg: "var(--color-violet-bg)", border: "var(--color-violet-border)" },
  teacher:             { label: "Teacher",           color: "var(--color-blue)",   bg: "var(--color-blue-bg)",   border: "var(--color-blue-border)" },
  admin:               { label: "Admin",             color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  low:                 { label: "Low",               color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
  medium:              { label: "Medium",            color: "var(--color-amber)",  bg: "var(--color-amber-bg)",  border: "var(--color-amber-border)" },
  high:                { label: "High",              color: "var(--color-red)",    bg: "var(--color-red-bg)",    border: "var(--color-red-border)" },
  skipped:             { label: "Skipped",           color: "var(--color-slate)",  bg: "var(--color-slate-bg)",  border: "var(--color-slate-border)" },
  overridden:          { label: "Overridden",        color: "var(--color-blue)",   bg: "var(--color-blue-bg)",   border: "var(--color-blue-border)" },
  finalised:           { label: "Finalised",         color: "var(--color-green)",  bg: "var(--color-green-bg)",  border: "var(--color-green-border)" },
};

export default function StatusBadge({ status, size = "sm" }: Props) {
  const key = String(status || "pending").toLowerCase();
  const cfg = MAP[key] ?? { label: String(status || "Unknown"), color: "var(--color-slate)", bg: "var(--color-slate-bg)", border: "var(--color-slate-border)" };
  const fs = size === "xs" ? 10.5 : 11.5;
  const px = size === "xs" ? "6px" : "8px";
  const py = size === "xs" ? "2px" : "3px";
  return (
    <span
      className="inline-flex items-center font-mono font-medium rounded-full border whitespace-nowrap"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border, fontSize: fs, padding: `${py} ${px}` }}
    >
      {cfg.label}
    </span>
  );
}
