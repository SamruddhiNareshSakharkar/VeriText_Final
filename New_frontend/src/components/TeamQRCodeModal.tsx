import { useState, useEffect } from "react";
import QRCode from "qrcode";
import Btn from "./Btn";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  team: {
    id: string;
    name: string;
    course: string;
    code: string;
  } | null;
}

export default function TeamQRCodeModal({ isOpen, onClose, team }: Props) {
  const [qrDataUrl, setQrDataUrl] = useState<string>("");
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!isOpen || !team || !team.code) return;

    // Direct enrollment link format
    const joinUrl = `${window.location.origin}/student/teams?join=${encodeURIComponent(team.code)}`;

    QRCode.toDataURL(joinUrl, {
      width: 320,
      margin: 2,
      color: {
        dark: "#0f172a", // slate-900
        light: "#ffffff",
      },
      errorCorrectionLevel: "H",
    })
      .then((url) => setQrDataUrl(url))
      .catch((err) => console.error("QR Code generation error:", err));
  }, [isOpen, team]);

  if (!isOpen || !team) return null;

  function handleCopyCode() {
    if (!team) return;
    navigator.clipboard.writeText(team.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleCopyLink() {
    if (!team) return;
    const joinUrl = `${window.location.origin}/student/teams?join=${encodeURIComponent(team.code)}`;
    navigator.clipboard.writeText(joinUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  }

  function handleDownloadQR() {
    if (!qrDataUrl || !team) return;
    const a = document.createElement("a");
    a.href = qrDataUrl;
    a.download = `QR_${team.name.replace(/\s+/g, "_")}_${team.code}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-md rounded-2xl overflow-hidden shadow-2xl border flex flex-col animate-scale-in"
        style={{
          background: "var(--color-surface)",
          borderColor: "var(--color-border)",
        }}
      >
        {/* Header with gradient badge */}
        <div
          className="p-5 text-white flex items-center justify-between"
          style={{
            background: "linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #2563eb 100%)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-md flex items-center justify-center font-bold text-lg">
              📱
            </div>
            <div>
              <h3 className="font-serif font-bold text-base leading-tight">Classroom Join QR Pass</h3>
              <p className="text-xs text-sky-200 mt-0.5">{team.name} • {team.course}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center text-white text-sm cursor-pointer transition-colors"
          >
            ✕
          </button>
        </div>

        {/* QR Code Presentation Box */}
        <div className="p-6 flex flex-col items-center text-center">
          <p className="text-xs text-stone-500 mb-4 max-w-xs">
            Project this QR code in class or share it with students to let them instantly join this team.
          </p>

          {/* QR Display Card */}
          <div className="p-4 bg-white rounded-2xl border-2 border-stone-200 shadow-md flex flex-col items-center">
            {qrDataUrl ? (
              <img
                src={qrDataUrl}
                alt={`QR code to join ${team.name}`}
                className="w-56 h-56 rounded-lg object-contain"
              />
            ) : (
              <div className="w-56 h-56 flex items-center justify-center text-stone-400 text-xs">
                Generating QR code…
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-stone-200 w-full flex items-center justify-between px-2">
              <span className="text-[11px] uppercase tracking-wider text-stone-500 font-semibold">Join Code</span>
              <span className="font-mono text-base font-bold text-blue-900 tracking-wider bg-blue-50 px-3 py-0.5 rounded-lg border border-blue-200">
                {team.code}
              </span>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-3 w-full mt-6">
            <button
              onClick={handleCopyCode}
              className="py-2.5 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer hover:bg-stone-50"
              style={{ borderColor: "var(--color-border)", color: "var(--color-text-1)" }}
            >
              {copied ? "✓ Copied Code" : "📋 Copy Code"}
            </button>

            <button
              onClick={handleCopyLink}
              className="py-2.5 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer hover:bg-stone-50"
              style={{ borderColor: "var(--color-border)", color: "var(--color-text-1)" }}
            >
              {copiedLink ? "✓ Copied Link" : "🔗 Copy Join Link"}
            </button>
          </div>

          <div className="w-full mt-3">
            <Btn
              variant="primary"
              size="md"
              onClick={handleDownloadQR}
              className="w-full justify-center gap-2"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              Download Scannable QR (PNG)
            </Btn>
          </div>
        </div>

        {/* Modal Footer */}
        <div
          className="px-6 py-3 border-t text-center text-[11px] text-stone-400"
          style={{ background: "var(--color-canvas)", borderColor: "var(--color-border)" }}
        >
          Students can scan using any smartphone camera or iPad to open the portal.
        </div>
      </div>
    </div>
  );
}
