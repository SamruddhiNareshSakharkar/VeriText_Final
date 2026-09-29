import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../../lib/context";
import Btn from "../../components/Btn";
import { Field, Input } from "../../components/Field";

export default function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [activePortal, setActivePortal] = useState<"student" | "teacher">("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setLoading(true);
    try {
      const user = await login(email, password);
      navigate(user.role === "teacher" || user.role === "admin" ? "/teacher" : "/student");
    } catch (err: any) {
      setError(err?.message || "Invalid email or password. Please verify your academic credentials.");
    } finally {
      setLoading(false);
    }
  }

  function applyDemo(role: "student" | "teacher") {
    if (role === "student") {
      setEmail("student@uni.edu");
      setPassword("password123");
      setActivePortal("student");
    } else {
      setEmail("t.chen@uni.edu");
      setPassword("password123");
      setActivePortal("teacher");
    }
    setError("");
  }

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 sm:p-6 lg:p-8 overflow-x-hidden">
      {/* ============================================================ */}
      {/* BACKSIDE FULL-COVERAGE CAMPUS IMAGE & OVERLAY                */}
      {/* ============================================================ */}
      <div className="fixed inset-0 w-full h-full pointer-events-none z-0">
        <img
          src="/campus_hero.jpg"
          alt="Campus Atrium Background"
          className="w-full h-full object-cover object-center scale-105"
        />
        {/* Deep atmospheric overlay for high contrast & elegance */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(circle at center, rgba(10, 24, 48, 0.78) 0%, rgba(7, 18, 38, 0.92) 100%)",
            backdropFilter: "blur(4px)",
          }}
        />
      </div>

      {/* ============================================================ */}
      {/* CENTERED ELEVATED AUTHENTICATION CARD (WIDER CONTAINER)      */}
      {/* ============================================================ */}
      <div className="relative z-10 w-full max-w-3xl lg:max-w-4xl animate-scale-in my-8">
        <div
          className="rounded-3xl shadow-2xl overflow-hidden border border-slate-200 bg-white p-8 sm:p-12 lg:p-14"
          style={{
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.05)",
          }}
        >
          {/* Header at Middle */}
          <div className="text-center flex flex-col items-center max-w-xl mx-auto">
            {/* Logo Crest */}
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-600/30 mb-3 ring-2 ring-white/60"
              style={{ background: "linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)" }}
            >
              <svg width="28" height="28" viewBox="0 0 18 18" fill="none">
                <rect x="2" y="2" width="5" height="14" rx="0.5" fill="white" fillOpacity="0.95" />
                <rect x="9.5" y="2" width="6.5" height="6.5" rx="0.5" fill="white" fillOpacity="0.95" />
                <rect x="9.5" y="10" rx="0.5" width="6.5" height="6" fill="white" fillOpacity="0.6" />
              </svg>
            </div>

            <h1 className="text-3xl sm:text-4xl font-extrabold font-sans text-slate-900 tracking-tight">
              VERITEXT
            </h1>
            <p className="text-xs uppercase tracking-[0.25em] font-bold text-blue-600 mt-1">
              Academic Integrity & Verification Suite
            </p>

            <div className="mt-3.5 inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700 font-medium shadow-inner">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Campus Portal Connected • Academic Session 2026</span>
            </div>
          </div>

          <div className="max-w-2xl mx-auto">
            {/* Portal Switcher Tabs */}
            <div className="grid grid-cols-2 gap-2 p-1.5 rounded-2xl my-6 bg-slate-100 border border-slate-200">
            <button
              type="button"
              onClick={() => {
                setActivePortal("student");
                applyDemo("student");
              }}
              className={`py-2.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                activePortal === "student"
                  ? "bg-white shadow-sm text-blue-900 font-bold ring-1 ring-slate-300"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span className="text-base">🎓</span>
              <span>Student Portal</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActivePortal("teacher");
                applyDemo("teacher");
              }}
              className={`py-2.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                activePortal === "teacher"
                  ? "bg-white shadow-sm text-blue-900 font-bold ring-1 ring-slate-300"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span className="text-base">🏫</span>
              <span>Faculty / Teacher</span>
            </button>
          </div>

          {error && (
            <div className="mb-5 px-4 py-3 rounded-xl flex items-center gap-3 text-xs bg-red-50 border border-red-200 text-red-700">
              <span className="text-base">⚠️</span>
              <span className="font-medium">{error}</span>
            </div>
          )}

          {/* Login Credentials Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Institutional Email" required>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={activePortal === "student" ? "student@uni.edu" : "faculty@uni.edu"}
                autoComplete="email"
              />
            </Field>

            <Field label="Password" required>
              <div>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600 text-xs font-medium cursor-pointer"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                <div className="flex justify-end mt-1.5">
                  <Link
                    to="/forgot-password"
                    style={{ fontSize: 12, color: "var(--color-accent)" }}
                    className="hover:underline font-medium"
                  >
                    Forgot password?
                  </Link>
                </div>
              </div>
            </Field>

            <Btn
              variant="primary"
              size="lg"
              loading={loading}
              type="submit"
              style={{ width: "100%", marginTop: 8 }}
            >
              {loading
                ? "Verifying Institutional Credentials…"
                : `Sign In to ${activePortal === "student" ? "Student" : "Faculty"} Portal →`}
            </Btn>
          </form>

          {/* Quick Demo Access (ID Cards) */}
          <div className="mt-8 pt-6 border-t border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                Instant Demo Access (ID Cards)
              </span>
              <span className="text-[10px] text-blue-600 font-medium bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                Click to Auto-fill
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Student Demo ID Card */}
              <div
                onClick={() => applyDemo("student")}
                className={`p-3 rounded-xl border transition-all cursor-pointer text-left relative flex items-center gap-3 hover:shadow-md ${
                  activePortal === "student"
                    ? "ring-2 ring-blue-500/50 border-blue-500 bg-blue-50/50"
                    : "bg-slate-50 hover:bg-white border-slate-200"
                }`}
              >
                <div className="relative">
                  <img
                    src="https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=120&auto=format&fit=crop&q=80"
                    alt="Student Alex Rivera"
                    className="w-11 h-11 rounded-full object-cover border-2 border-blue-500/30 flex-shrink-0"
                  />
                  <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs font-bold text-slate-900 truncate">Alex Rivera</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase bg-blue-100 text-blue-800">
                      Student
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono truncate">
                    Roll: 24102A0074
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">Computer Engg.</div>
                </div>
              </div>

              {/* Faculty Demo ID Card */}
              <div
                onClick={() => applyDemo("teacher")}
                className={`p-3 rounded-xl border transition-all cursor-pointer text-left relative flex items-center gap-3 hover:shadow-md ${
                  activePortal === "teacher"
                    ? "ring-2 ring-emerald-500/50 border-emerald-500 bg-emerald-50/50"
                    : "bg-slate-50 hover:bg-white border-slate-200"
                }`}
              >
                <div className="relative">
                  <img
                    src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                    alt="Prof. T. Chen"
                    className="w-11 h-11 rounded-full object-cover border-2 border-emerald-500/30 flex-shrink-0"
                  />
                  <span className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-emerald-500 border-2 border-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs font-bold text-slate-900 truncate">Prof. T. Chen</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase bg-emerald-100 text-emerald-800">
                      Faculty
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono truncate">
                    ID: FAC-COMP-01
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">Computer Engg.</div>
                </div>
              </div>
            </div>

            <div className="text-center mt-5">
              <p className="text-xs text-slate-600">
                Need a new academic account?{" "}
                <Link
                  to="/signup"
                  style={{ color: "var(--color-accent)", fontWeight: 600 }}
                  className="hover:underline font-semibold"
                >
                  Register as Student or Faculty →
                </Link>
              </p>
            </div>
          </div>
        </div>

        {/* Footer inside card */}
          <div className="max-w-2xl mx-auto mt-6 pt-4 border-t border-slate-200 flex items-center justify-between text-[11px] text-slate-400">
            <span>🔒 256-bit Institutional TLS</span>
            <span>Alan Turing Hall Portal</span>
          </div>
        </div>
      </div>
    </div>
  );
}
