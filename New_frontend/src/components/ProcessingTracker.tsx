import Spinner from "./Spinner";

type StepStatus = "pending" | "processing" | "complete" | "error" | "skipped";
interface Step { id: string; label: string; status: StepStatus; detail?: string }
interface Props { steps: Step[] }

function Icon({ s }: { s: StepStatus }) {
  if (s === "complete") return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: "var(--color-green-bg)", border: "1.5px solid var(--color-green)" }}>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M2 5l2.5 2.5L8 3" stroke="var(--color-green)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
  if (s === "error") return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: "var(--color-red-bg)", border: "1.5px solid var(--color-red)" }}>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M3 3l4 4M7 3l-4 4" stroke="var(--color-red)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  );
  if (s === "processing") return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: "var(--color-accent-bg)", border: "1.5px solid var(--color-accent)" }}>
      <Spinner size={12} color="var(--color-accent)" />
    </div>
  );
  if (s === "skipped") return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: "var(--color-slate-bg)", border: "1.5px solid var(--color-slate-border)" }}>
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M2 5h6" stroke="var(--color-slate)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  );
  return (
    <div className="w-6 h-6 rounded-full flex-shrink-0" style={{ background: "var(--color-surface)", border: "1.5px solid var(--color-border-2)" }} />
  );
}

export default function ProcessingTracker({ steps }: Props) {
  return (
    <div>
      {steps.map((step, i) => (
        <div key={step.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <Icon s={step.status} />
            {i < steps.length - 1 && (
              <div className="w-px flex-1 my-1" style={{ background: step.status === "complete" ? "var(--color-green-border)" : "var(--color-border)", minHeight: 16 }} />
            )}
          </div>
          <div className="pb-4 min-w-0">
            <p className="font-medium" style={{
              fontSize: 13,
              color: step.status === "pending" ? "var(--color-text-4)"
                : step.status === "error" ? "var(--color-red)"
                : step.status === "skipped" ? "var(--color-text-3)"
                : "var(--color-text-1)"
            }}>
              {step.label}
            </p>
            {step.detail && (
              <p style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 1 }}>{step.detail}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
