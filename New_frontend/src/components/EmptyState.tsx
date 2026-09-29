interface Props {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({ icon, title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
      {icon && (
        <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
          style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
          <span style={{ color: "var(--color-text-4)" }}>{icon}</span>
        </div>
      )}
      <p className="font-semibold mb-1" style={{ color: "var(--color-text-1)", fontSize: 14 }}>{title}</p>
      <p className="max-w-xs" style={{ color: "var(--color-text-3)", fontSize: 13 }}>{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 px-4 py-2 rounded-lg font-medium text-white transition-colors"
          style={{ background: "var(--color-accent)", fontSize: 13 }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-accent-h)")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--color-accent)")}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
