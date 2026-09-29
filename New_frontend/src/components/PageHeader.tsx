interface Breadcrumb { label: string; onClick?: () => void }

interface Props {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  breadcrumbs?: Breadcrumb[];
}

export default function PageHeader({ title, subtitle, actions, breadcrumbs }: Props) {
  return (
    <div
      className="mb-6 -mx-7 -mt-6 px-7 pt-6 pb-5 animate-fade-in"
      style={{
        background: "linear-gradient(135deg, #EEF4FF 0%, #F5F7FA 50%, #F0F3F7 100%)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-1 mb-2">
          {breadcrumbs.map((b, i) => (
            <span
              key={i}
              className={`flex items-center gap-1 ${b.onClick ? "cursor-pointer hover:underline" : ""}`}
              style={{ color: i === breadcrumbs.length - 1 ? "var(--color-text-2)" : "var(--color-text-4)", fontSize: 12 }}
              onClick={b.onClick}
            >
              {i > 0 && <span style={{ color: "var(--color-border-2)" }}>/</span>}
              {b.label}
            </span>
          ))}
        </nav>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-semibold tracking-tight" style={{ fontSize: 22, color: "var(--color-text-1)" }}>{title}</h1>
          {subtitle && <p className="mt-1" style={{ fontSize: 13, color: "var(--color-text-3)", lineHeight: 1.5 }}>{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
      </div>
    </div>
  );
}
