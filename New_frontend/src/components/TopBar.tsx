import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../lib/context";
import { api } from "../lib/api";

interface SearchResult {
  type: "team" | "assignment" | "submission";
  id: string;
  title: string;
  subtitle: string;
  href: string;
}

function SearchModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const q = query.toLowerCase();
        const items: SearchResult[] = [];

        // Search teams
        try {
          const teams = await api.teams.list();
          (teams || []).forEach((t: any) => {
            const name = (t.name || "").toLowerCase();
            const code = (t.join_code || "").toLowerCase();
            const course = (t.course_code || t.description || "").toLowerCase();
            if (name.includes(q) || code.includes(q) || course.includes(q)) {
              items.push({
                type: "team",
                id: t.id,
                title: t.name,
                subtitle: `${t.course_code || t.description || "Team"} · ${t.member_count ?? 0} members`,
                href: `/teacher/teams/${t.id}/members`,
              });
            }
          });
        } catch {}

        // Search assignments
        try {
          const assignments = await api.assignments.list();
          (assignments || []).forEach((a: any) => {
            const title = (a.title || "").toLowerCase();
            const desc = (a.description || "").toLowerCase();
            if (title.includes(q) || desc.includes(q)) {
              items.push({
                type: "assignment",
                id: a.id,
                title: a.title,
                subtitle: `${a.submission_count ?? 0} submissions · Max ${a.max_marks || 100} marks`,
                href: `/teacher/assignments`,
              });
            }
          });
        } catch {}

        setResults(items.slice(0, 8));
        setSelected(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter" && results[selected]) {
      navigate(results[selected].href);
      onClose();
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  const typeIcon = (type: string) => {
    if (type === "team") return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M5 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM1.5 12s0-3.5 3.5-3.5S8.5 12 8.5 12M10.5 4.5a1.5 1.5 0 1 1 0 3M12.5 12s0-3-2.5-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    );
    if (type === "assignment") return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <rect x="2.5" y="1.5" width="9" height="11" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <path d="M4.5 5h5M4.5 7.5h5M4.5 10h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    );
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M7 10V3M4.5 5.5 7 3 9.5 5.5M2 11h10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4 search-backdrop"
      onClick={onClose}
    >
      <div
        className="w-full rounded-2xl overflow-hidden search-modal"
        style={{ maxWidth: 560, background: "var(--color-surface)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-5 py-4" style={{ borderBottom: "1px solid var(--color-border)" }}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" style={{ color: "var(--color-accent)", flexShrink: 0 }}>
            <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M12.5 12.5L16 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search teams, assignments, submissions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 text-sm bg-transparent outline-none"
            style={{ color: "var(--color-text-1)", fontFamily: "var(--font-sans)" }}
          />
          <kbd
            className="text-xs font-mono px-1.5 py-0.5 rounded"
            style={{ background: "var(--color-surface-2)", color: "var(--color-text-4)", border: "1px solid var(--color-border)", fontSize: 10 }}
          >
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 360, overflowY: "auto" }}>
          {loading && (
            <div className="flex items-center justify-center py-8 gap-2">
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: "var(--color-border)", borderTopColor: "var(--color-accent)" }} />
              <span className="text-xs" style={{ color: "var(--color-text-4)" }}>Searching…</span>
            </div>
          )}

          {!loading && query && results.length === 0 && (
            <div className="py-10 text-center">
              <svg width="36" height="36" viewBox="0 0 36 36" fill="none" className="mx-auto mb-3" style={{ color: "var(--color-text-4)" }}>
                <circle cx="16" cy="16" r="10" stroke="currentColor" strokeWidth="1.5" />
                <path d="M24 24l7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                <path d="M12 16h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <p className="text-xs font-medium" style={{ color: "var(--color-text-3)" }}>No results for "{query}"</p>
              <p className="text-xs mt-1" style={{ color: "var(--color-text-4)" }}>Try a different search term</p>
            </div>
          )}

          {!loading && !query && (
            <div className="py-8 text-center">
              <p className="text-xs" style={{ color: "var(--color-text-4)" }}>Start typing to search across your workspace</p>
              <div className="flex items-center justify-center gap-3 mt-3">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md" style={{ background: "var(--color-accent-bg)", color: "var(--color-accent)" }}>Teams</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md" style={{ background: "var(--color-violet-bg)", color: "var(--color-violet)" }}>Assignments</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md" style={{ background: "var(--color-green-bg)", color: "var(--color-green)" }}>Submissions</span>
              </div>
            </div>
          )}

          {results.map((r, i) => (
            <button
              key={`${r.type}-${r.id}`}
              className={`w-full flex items-center gap-3 px-5 py-3 text-left search-result-item cursor-pointer transition-colors`}
              style={{
                background: i === selected ? "var(--color-accent-bg)" : "transparent",
                borderBottom: "1px solid var(--color-surface-2)",
              }}
              onMouseEnter={() => setSelected(i)}
              onClick={() => { navigate(r.href); onClose(); }}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{
                  background: r.type === "team" ? "var(--color-accent-bg)" : r.type === "assignment" ? "var(--color-violet-bg)" : "var(--color-green-bg)",
                  color: r.type === "team" ? "var(--color-accent)" : r.type === "assignment" ? "var(--color-violet)" : "var(--color-green)",
                }}
              >
                {typeIcon(r.type)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate" style={{ color: "var(--color-text-1)" }}>{r.title}</p>
                <p className="text-xs truncate" style={{ color: "var(--color-text-4)" }}>{r.subtitle}</p>
              </div>
              <span className="text-[10px] uppercase tracking-wider font-semibold flex-shrink-0 px-2 py-0.5 rounded"
                style={{
                  background: r.type === "team" ? "var(--color-accent-bg)" : r.type === "assignment" ? "var(--color-violet-bg)" : "var(--color-green-bg)",
                  color: r.type === "team" ? "var(--color-accent)" : r.type === "assignment" ? "var(--color-violet)" : "var(--color-green)",
                }}
              >{r.type}</span>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-2.5" style={{ borderTop: "1px solid var(--color-border)", background: "var(--color-surface-2)" }}>
          <div className="flex items-center gap-3 text-[10px]" style={{ color: "var(--color-text-4)" }}>
            <span>↑↓ Navigate</span>
            <span>↵ Open</span>
            <span>Esc Close</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TopBar() {
  const { user, sidebarOpen, setSidebarOpen } = useApp();
  const [showSearch, setShowSearch] = useState(false);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      setShowSearch(true);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      <header
        className="h-14 flex items-center justify-between px-5 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--color-border)", background: "var(--color-surface)" }}
      >
        <div className="flex items-center gap-3">
          {/* Mobile toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-1.5 rounded-md transition-colors"
            style={{ color: "var(--color-text-2)" }}
          >
            <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
              <path d="M2 4h13M2 8.5h13M2 13h13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>

          {/* Search trigger */}
          <button
            onClick={() => setShowSearch(true)}
            className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm w-56 cursor-pointer transition-all"
            style={{
              border: "1px solid var(--color-border)",
              background: "var(--color-surface-2)",
              color: "var(--color-text-4)",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--color-accent)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 2px var(--color-accent-ring)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)"; (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" strokeWidth="1.4" />
              <path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <span style={{ fontSize: 13 }}>Search…</span>
            <kbd className="ml-auto text-xs font-mono px-1 rounded" style={{ background: "var(--color-border)", color: "var(--color-text-4)", fontSize: 10 }}>Ctrl+K</kbd>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Bell */}
          <button
            className="relative p-2 rounded-lg transition-colors"
            style={{ color: "var(--color-text-2)" }}
            title="Notifications"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 1.5a5 5 0 0 0-5 5V10l-1 1.5h12L13 10V6.5a5 5 0 0 0-5-5z" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              <path d="M6.5 13a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </button>

          {/* User Profile Badge */}
          {user && (
            <div
              className="flex items-center gap-2.5 pl-3 ml-1"
              style={{ borderLeft: "1px solid var(--color-border)" }}
            >
              {user.photo_url ? (
                <img 
                  src={user.photo_url} 
                  alt={user.name} 
                  className="w-8 h-8 rounded-full object-cover border border-stone-300 shadow-xs flex-shrink-0"
                />
              ) : (
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0"
                  style={{ background: "var(--color-navy)", fontSize: 11, fontWeight: 600 }}
                >
                  {user.name.split(" ").map((n: string) => n[0]).slice(0, 2).join("")}
                </div>
              )}
              <div className="hidden sm:block leading-tight">
                <div className="flex items-center gap-1.5">
                  <p className="font-semibold text-xs" style={{ color: "var(--color-text-1)" }}>{user.name}</p>
                  <span className="text-[10px] px-1.5 py-0.2 rounded font-semibold bg-blue-50 text-blue-800 border border-blue-100">
                    {user.role === "student" ? (user.roll_no ? `Roll: ${user.roll_no}` : "Student") : (user.faculty_id ? `ID: ${user.faculty_id}` : "Faculty")}
                  </span>
                </div>
                <p className="text-[10.5px] truncate max-w-[180px]" style={{ color: "var(--color-text-3)" }}>
                  {user.department || user.institution}
                </p>
              </div>
            </div>
          )}
        </div>
      </header>

      {showSearch && <SearchModal onClose={() => setShowSearch(false)} />}
    </>
  );
}
