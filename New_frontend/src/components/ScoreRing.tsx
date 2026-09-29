interface Props {
  value: number | null;
  label: string;
  size?: number;
  thresholds?: [number, number];
  colorScheme?: "danger-high" | "good-high" | "info-blue";
  tooltip?: string;
}

export default function ScoreRing({
  value,
  label,
  size = 60,
  thresholds = [40, 70],
  colorScheme,
  tooltip,
}: Props) {
  const r = (size - 7) / 2;
  const circ = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.min(100, Math.max(0, value));
  const offset = circ - (pct / 100) * circ;

  // Determine effective scheme:
  // If label is "Handwriting" and no explicit colorScheme given, treat as info/authenticity (blue/emerald)
  const isHandwriting = label.toLowerCase().includes("handwriting");
  const effectiveScheme = colorScheme || (isHandwriting ? "info-blue" : "danger-high");

  let color = "var(--color-border)";
  if (value != null) {
    if (effectiveScheme === "info-blue") {
      color = pct >= 70 ? "#0284c7" : pct >= 40 ? "#38bdf8" : "#94a3b8"; // Sky/Blue for handwriting detection
    } else if (effectiveScheme === "good-high") {
      // High is good (e.g. Grades, Authenticity)
      color = pct >= thresholds[1] ? "var(--color-green)" : pct >= thresholds[0] ? "var(--color-amber)" : "var(--color-red)";
    } else {
      // High is bad/risk (e.g. AI score, Plagiarism similarity)
      color = pct >= thresholds[1] ? "var(--color-red)" : pct >= thresholds[0] ? "var(--color-amber)" : "var(--color-green)";
    }
  }

  const defaultTooltip = isHandwriting
    ? `Handwriting Verification: ${pct}% of document analyzed and verified as authentic pen-and-paper handwriting.`
    : `${label}: ${value == null ? "Not analyzed" : `${pct}%`}`;

  return (
    <div
      className="flex flex-col items-center gap-1.5 group relative cursor-help"
      title={tooltip || defaultTooltip}
    >
      <div style={{ width: size, height: size, position: "relative" }}>
        <svg width={size} height={size}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-border)"
            strokeWidth="5.5"
          />
          {value != null && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={color}
              strokeWidth="5.5"
              strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              className="transition-all duration-700"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="font-mono font-bold"
            style={{
              fontSize: size > 55 ? 13 : 11,
              color: value == null ? "var(--color-text-4)" : "var(--color-text-1)",
            }}
          >
            {value == null ? "—" : `${pct}%`}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <span style={{ fontSize: 11, color: "var(--color-text-3)" }}>{label}</span>
        {isHandwriting && (
          <span className="text-[10px] text-sky-500 font-mono" title="Optical Handwriting Verification">ℹ️</span>
        )}
      </div>
    </div>
  );
}
