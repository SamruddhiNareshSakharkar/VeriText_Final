interface Props {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  required?: boolean;
}

export function Field({ label, error, hint, children, required }: Props) {
  return (
    <div>
      <label className="flex items-center gap-1 font-medium mb-1.5" style={{ fontSize: 12, color: "var(--color-text-2)" }}>
        {label}
        {required && <span style={{ color: "var(--color-red)" }}>*</span>}
      </label>
      {children}
      {hint && !error && <p style={{ fontSize: 11, color: "var(--color-text-3)", marginTop: 4 }}>{hint}</p>}
      {error && <p style={{ fontSize: 11, color: "var(--color-red)", marginTop: 4 }}>{error}</p>}
    </div>
  );
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export function Input({ error, style, ...rest }: InputProps) {
  return (
    <input
      {...rest}
      style={{
        width: "100%",
        border: `1px solid ${error ? "var(--color-red)" : "var(--color-border-2)"}`,
        borderRadius: 8,
        padding: "9px 12px",
        fontSize: 13.5,
        fontFamily: "inherit",
        color: "var(--color-text-1)",
        background: "var(--color-surface)",
        outline: "none",
        transition: "border-color 0.14s, box-shadow 0.14s",
        boxSizing: "border-box",
        ...style,
      }}
      onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--color-accent)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 3px var(--color-accent-ring)"; }}
      onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = error ? "var(--color-red)" : "var(--color-border-2)"; (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
    />
  );
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

export function Textarea({ error, style, ...rest }: TextareaProps) {
  return (
    <textarea
      {...rest}
      style={{
        width: "100%",
        border: `1px solid ${error ? "var(--color-red)" : "var(--color-border-2)"}`,
        borderRadius: 8,
        padding: "9px 12px",
        fontSize: 13.5,
        fontFamily: "inherit",
        color: "var(--color-text-1)",
        background: "var(--color-surface)",
        outline: "none",
        resize: "vertical",
        transition: "border-color 0.14s, box-shadow 0.14s",
        boxSizing: "border-box",
        ...style,
      }}
      onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--color-accent)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 3px var(--color-accent-ring)"; }}
      onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = error ? "var(--color-red)" : "var(--color-border-2)"; (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
    />
  );
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
}

export function Select({ error, style, children, ...rest }: SelectProps) {
  return (
    <select
      {...rest}
      style={{
        width: "100%",
        border: `1px solid ${error ? "var(--color-red)" : "var(--color-border-2)"}`,
        borderRadius: 8,
        padding: "9px 12px",
        fontSize: 13.5,
        fontFamily: "inherit",
        color: "var(--color-text-1)",
        background: "var(--color-surface)",
        outline: "none",
        appearance: "none",
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%237A8FAB' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 12px center",
        paddingRight: 32,
        transition: "border-color 0.14s, box-shadow 0.14s",
        boxSizing: "border-box",
        ...style,
      }}
      onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--color-accent)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 3px var(--color-accent-ring)"; }}
      onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = error ? "var(--color-red)" : "var(--color-border-2)"; (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
    >
      {children}
    </select>
  );
}
