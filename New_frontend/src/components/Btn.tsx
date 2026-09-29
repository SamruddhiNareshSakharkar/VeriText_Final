import Spinner from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "xs" | "sm" | "md" | "lg";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

const STYLES: Record<Variant, { bg: string; color: string; border: string; hoverBg?: string }> = {
  primary:   { bg: "var(--color-accent)",    color: "white",                    border: "transparent", hoverBg: "var(--color-accent-h)" },
  secondary: { bg: "var(--color-surface)",   color: "var(--color-text-2)",      border: "var(--color-border)", hoverBg: "var(--color-surface-2)" },
  outline:   { bg: "transparent",            color: "var(--color-accent)",      border: "var(--color-accent)", hoverBg: "var(--color-accent-bg)" },
  ghost:     { bg: "transparent",            color: "var(--color-text-2)",      border: "transparent", hoverBg: "var(--color-canvas)" },
  danger:    { bg: "var(--color-red-bg)",    color: "var(--color-red)",         border: "var(--color-red-border)", hoverBg: "#fee2e2" },
};

const SIZES: Record<Size, { px: string; py: string; fontSize: number; gap: number }> = {
  xs:  { px: "8px",  py: "3px",   fontSize: 11.5, gap: 4 },
  sm:  { px: "10px", py: "5px",   fontSize: 12.5, gap: 5 },
  md:  { px: "14px", py: "8px",   fontSize: 13.5, gap: 6 },
  lg:  { px: "18px", py: "11px",  fontSize: 14,   gap: 7 },
};

export default function Btn({ variant = "secondary", size = "md", loading, icon, children, disabled, style, ...rest }: Props) {
  const v = STYLES[variant] ?? STYLES.secondary;
  const s = SIZES[size] ?? SIZES.md;
  // #region agent log
  if (!(size in SIZES) || !(variant in STYLES)) {
    fetch('http://127.0.0.1:7269/ingest/5765b5d4-be54-401c-a6dd-2cbc0c00d0c0',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'7d2f9e'},body:JSON.stringify({sessionId:'7d2f9e',runId:'pre-fix',hypothesisId:'A',location:'Btn.tsx',message:'Btn missing style/size',data:{size,variant,hasSize:size in SIZES,hasStyle:variant in STYLES},timestamp:Date.now()})}).catch(()=>{});
  }
  // #endregion
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: s.gap,
        background: v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        borderRadius: 8,
        fontFamily: "inherit",
        fontWeight: 500,
        fontSize: s.fontSize,
        padding: `${s.py} ${s.px}`,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.55 : 1,
        transition: "background 0.14s, box-shadow 0.14s",
        lineHeight: 1.4,
        ...style,
      }}
      onMouseEnter={(e) => { if (!disabled && !loading && v.hoverBg) (e.currentTarget as HTMLElement).style.background = v.hoverBg; }}
      onMouseLeave={(e) => { if (!disabled && !loading) (e.currentTarget as HTMLElement).style.background = v.bg; }}
    >
      {loading ? <Spinner size={s.fontSize + 2} color={v.color} /> : icon}
      {children}
    </button>
  );
}
