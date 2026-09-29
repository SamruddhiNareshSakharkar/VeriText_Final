import { useState } from "react";
import { Link } from "react-router-dom";
import Btn from "../../components/Btn";
import { Field, Input } from "../../components/Field";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    await new Promise((r) => setTimeout(r, 900));
    setLoading(false);
    setSent(true);
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--color-canvas)" }}>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <Link to="/login" className="inline-flex items-center gap-2 mb-10 hover:opacity-70 transition-opacity">
          <div className="w-7 h-7 rounded-xl flex items-center justify-center" style={{ background: "var(--color-navy)" }}>
            <svg width="12" height="12" viewBox="0 0 18 18" fill="none">
              <rect x="2" y="2" width="5" height="14" rx="0.5" fill="white" fillOpacity="0.9" />
              <rect x="9.5" y="2" width="6.5" height="6.5" rx="0.5" fill="white" fillOpacity="0.9" />
              <rect x="9.5" y="10" rx="0.5" width="6.5" height="6" fill="white" fillOpacity="0.55" />
            </svg>
          </div>
          <span className="font-sans font-extrabold tracking-tight" style={{ fontSize: 18, color: "var(--color-navy)" }}>VERITEXT</span>
        </Link>

        {sent ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5"
              style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M3 8l9 6 9-6" stroke="var(--color-green)" strokeWidth="1.5" strokeLinecap="round" />
                <rect x="2" y="6" width="20" height="14" rx="2" stroke="var(--color-green)" strokeWidth="1.5" />
              </svg>
            </div>
            <h2 className="font-semibold mb-2" style={{ fontSize: 20, color: "var(--color-text-1)" }}>Check your inbox</h2>
            <p style={{ fontSize: 13.5, color: "var(--color-text-3)", lineHeight: 1.6 }}>
              If an account exists for <strong style={{ color: "var(--color-text-2)" }}>{email}</strong>, you'll receive a password reset link within a few minutes.
            </p>
            <div className="mt-6">
              <Link to="/login">
                <Btn variant="secondary" size="md" style={{ width: "100%" }}>Back to sign in</Btn>
              </Link>
            </div>
          </div>
        ) : (
          <>
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 mb-6 transition-colors hover:opacity-70"
              style={{ fontSize: 13, color: "var(--color-text-3)" }}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M8 2L3 6.5 8 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Back to sign in
            </Link>

            <h1 className="font-semibold mb-1" style={{ fontSize: 22, color: "var(--color-text-1)" }}>Reset password</h1>
            <p style={{ fontSize: 13.5, color: "var(--color-text-3)", marginBottom: 24, lineHeight: 1.6 }}>
              Enter your institutional email and we'll send a secure reset link.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <Field label="Email address" required>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@university.edu" />
              </Field>
              <Btn variant="primary" size="lg" loading={loading} disabled={!email} type="submit" style={{ width: "100%" }}>
                {loading ? "Sending…" : "Send reset link"}
              </Btn>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
