import { useRef, useState } from "react";

interface Props { onFile: (f: File) => void; accept?: string }

export default function UploadZone({ onFile, accept = ".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png" }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      onClick={() => ref.current?.click()}
      className="rounded-xl cursor-pointer transition-all flex flex-col items-center gap-4 py-12 px-8 text-center"
      style={{
        border: `2px dashed ${over ? "var(--color-accent)" : "var(--color-border-2)"}`,
        background: over ? "var(--color-accent-bg)" : "var(--color-surface-2)",
      }}
    >
      <div className="w-12 h-12 rounded-xl flex items-center justify-center transition-colors"
        style={{ background: over ? "var(--color-accent-bg)" : "var(--color-canvas)", border: `1px solid ${over ? "var(--color-accent)" : "var(--color-border)"}` }}>
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke={over ? "var(--color-accent)" : "var(--color-text-3)"} strokeWidth="1.5" strokeLinecap="round" />
          <path d="M11 15V5M7.5 8l3.5-3.5L14.5 8" stroke={over ? "var(--color-accent)" : "var(--color-text-3)"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div>
        <p className="font-semibold" style={{ fontSize: 14, color: over ? "var(--color-accent)" : "var(--color-text-1)" }}>
          {over ? "Drop to upload" : "Drop file here or browse"}
        </p>
        <p style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 4 }}>
          PDF · Word · plain text · JPEG · PNG — max 50 MB
        </p>
      </div>
      <input ref={ref} type="file" accept={accept} className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
    </div>
  );
}
