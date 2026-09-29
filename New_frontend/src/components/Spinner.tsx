interface Props { size?: number; color?: string }
export default function Spinner({ size = 18, color = "currentColor" }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" className="animate-spin flex-shrink-0">
      <circle cx="9" cy="9" r="7" stroke={color} strokeWidth="2" strokeOpacity="0.2" />
      <path d="M9 2a7 7 0 0 1 7 7" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
