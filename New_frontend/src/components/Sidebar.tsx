import { NavLink, useNavigate } from "react-router-dom";
import { useApp } from "../lib/context";

type Role = "student" | "teacher" | "admin";

interface NavItem { label: string; href: string; end?: boolean; icon: React.ReactNode }
interface NavSection { heading?: string; items: NavItem[] }

const ico = (d: string) => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none" className="flex-shrink-0">
    <path d={d} stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ICONS = {
  home:       ico("M1.5 6L7.5 1.5 13.5 6v8H9.5v-5h-4v5H1.5z"),
  teams:      ico("M5.5 5.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM1 13.5s0-3.5 4.5-3.5S10 13.5 10 13.5M11.5 4a2 2 0 1 1 0 4M14 13.5s0-3-2.5-3"),
  docs:       ico("M3 1.5h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1zM4.5 5.5h6M4.5 8h6M4.5 10.5h4"),
  submit:     ico("M7.5 10V2M4.5 5 7.5 2 10.5 5M3 12h9a.5.5 0 0 1 .5.5v.5a.5.5 0 0 1-.5.5H3a.5.5 0 0 1-.5-.5v-.5A.5.5 0 0 1 3 12z"),
  results:    ico("M2 11L5.5 7 8 9.5 12 4"),
  compare:    ico("M1.5 2.5h5v10h-5zM8.5 2.5h5v10h-5zM6.5 7.5h2"),
  analysis:   ico("M2 10.5L5 7l2.5 2 5-6M12.5 12v-2M9.5 12v-4M6.5 12v-3M3.5 12V9"),
  reports:    ico("M4.5 5h6M4.5 7.5h6M4.5 10h4M11.5 9l2 2-3 3"),
  grading:    ico("M7.5 1l1.8 3.6 4 .6L10.2 8l.7 4L7.5 10.1 4.1 12l.7-4L1.7 5.2l4-.6z"),
  settings:   ico("M7.5 1.5C6.7 1.5 6 2.2 6 3v.4c-.3.1-.6.3-.9.5l-.3-.3c-.6-.6-1.5-.6-2.1 0l-.7.7c-.6.6-.6 1.5 0 2.1l.3.3c-.2.3-.4.6-.5.9H1.5c-.8 0-1.5.7-1.5 1.5v1c0 .8.7 1.5 1.5 1.5h.3c.1.3.3.6.5.9l-.3.3c-.6.6-.6 1.5 0 2.1l.7.7c.6.6 1.5.6 2.1 0l.3-.3c.3.2.6.4.9.5v.4c0 .8.7 1.5 1.5 1.5h1c.8 0 1.5-.7 1.5-1.5v-.4c.3-.1.6-.3.9-.5l.3.3c.6.6 1.5.6 2.1 0l.7-.7c.6-.6.6-1.5 0-2.1l-.3-.3c.2-.3.4-.6.5-.9h.3c.8 0 1.5-.7 1.5-1.5v-1c0-.8-.7-1.5-1.5-1.5h-.3c-.1-.3-.3-.6-.5-.9l.3-.3c.6-.6.6-1.5 0-2.1l-.7-.7c-.6-.6-1.5-.6-2.1 0l-.3.3c-.3-.2-.6-.4-.9-.5V3c0-.8-.7-1.5-1.5-1.5h-1zM8 10a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"),
  logout:     ico("M5.5 2H2.5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3M9.5 10.5l3-3-3-3M12.5 7.5H5.5"),
};

const NAV: Record<Role, NavSection[]> = {
  student: [
    { items: [
      { label: "Dashboard", href: "/student", end: true, icon: ICONS.home },
      { label: "My Teams", href: "/student/teams", icon: ICONS.teams },
      { label: "Assignments", href: "/student/assignments", icon: ICONS.docs },
      { label: "Results", href: "/student/results", icon: ICONS.results },
    ]},
  ],
  teacher: [
    { items: [
      { label: "Dashboard", href: "/teacher", end: true, icon: ICONS.home },
      { label: "Teams", href: "/teacher/teams", icon: ICONS.teams },
    ]},
    { heading: "Assignments", items: [
      { label: "All Assignments", href: "/teacher/assignments", icon: ICONS.docs },
      { label: "Submissions", href: "/teacher/submissions", icon: ICONS.submit },
      { label: "Grading", href: "/teacher/grading", icon: ICONS.grading },
    ]},
    { heading: "Analysis", items: [
      { label: "Compare", href: "/teacher/compare", icon: ICONS.compare },
      { label: "Reports", href: "/teacher/reports", icon: ICONS.reports },
    ]},
  ],
  admin: [
    { items: [
      { label: "Dashboard", href: "/teacher", end: true, icon: ICONS.home },
      { label: "Teams", href: "/teacher/teams", icon: ICONS.teams },
      { label: "Submissions", href: "/teacher/submissions", icon: ICONS.submit },
      { label: "Reports", href: "/teacher/reports", icon: ICONS.reports },
    ]},
  ],
};

export default function Sidebar() {
  const { user, setUser, sidebarOpen, setSidebarOpen } = useApp();
  const navigate = useNavigate();
  const role = user?.role ?? "student";
  const sections = NAV[role] ?? NAV.student;
  const initials = (user?.name || "?")
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("") || "?";

  function logout() {
    setUser(null);
    navigate("/login");
  }

  return (
    <>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 lg:hidden"
          style={{ background: "rgba(9,24,46,0.55)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed top-0 left-0 h-screen z-30 flex flex-col select-none transition-transform duration-200
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:relative lg:translate-x-0 lg:z-auto`}
        style={{ width: 224, background: "var(--color-navy)", flexShrink: 0 }}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5 px-5 h-14 border-b" style={{ borderColor: "var(--color-navy-border)" }}>
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "var(--color-accent)" }}>
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <rect x="2" y="2" width="4" height="11" rx="0.5" fill="white" fillOpacity="0.9" />
              <rect x="8" y="2" width="5" height="5" rx="0.5" fill="white" fillOpacity="0.9" />
              <rect x="8" y="9" width="5" height="4" rx="0.5" fill="white" fillOpacity="0.65" />
            </svg>
          </div>
          <span className="font-sans font-extrabold text-white tracking-tight" style={{ fontSize: 16 }}>VERITEXT</span>
          <span className="ml-auto text-xs font-mono font-semibold px-1.5 py-0.5 rounded" style={{ background: "var(--color-navy-2)", color: "var(--color-text-3)", fontSize: 10 }}>
            v2.4
          </span>
        </div>

        {/* User card */}
        {user && (
          <div className="mx-3 mt-3 mb-1 px-3 py-2.5 rounded-lg" style={{ background: "var(--color-navy-2)" }}>
            <div className="flex items-center gap-2.5">
              {user.photo_url ? (
                <img 
                  src={user.photo_url} 
                  alt={user.name} 
                  className="w-8 h-8 rounded-full object-cover border border-white/20 flex-shrink-0" 
                />
              ) : (
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold flex-shrink-0"
                  style={{ background: "var(--color-accent)", fontSize: 11 }}>
                  {initials}
                </div>
              )}
              <div className="min-w-0">
                <p className="text-white font-semibold truncate" style={{ fontSize: 12 }}>{user.name}</p>
                <p className="truncate text-[10.5px] text-sky-200/80 font-mono">
                  {user.role === "student" ? (user.roll_no ? `Roll: ${user.roll_no}` : "Student") : (user.faculty_id ? `ID: ${user.faculty_id}` : "Faculty")}
                </p>
                <p className="truncate text-[10px]" style={{ color: "var(--color-text-3)" }}>
                  {user.department || user.institution}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
          {sections.map((section, si) => (
            <div key={si}>
              {section.heading && (
                <p className="px-3 mb-1 uppercase tracking-widest font-semibold"
                  style={{ color: "var(--color-navy-border)", fontSize: 9.5 }}>
                  {section.heading}
                </p>
              )}
              <ul className="space-y-0.5">
                {section.items.map((item) => (
                  <li key={item.href}>
                    <NavLink
                      to={item.href}
                      end={item.end}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-[#2255D3] text-white"
                            : "text-[#7A8FAB] hover:text-[#C8D6E8] hover:bg-[#112347]"
                        }`
                      }
                    >
                      {item.icon}
                      <span style={{ fontSize: 13 }}>{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {/* Bottom */}
        <div className="px-2 pb-3 space-y-0.5 border-t" style={{ borderColor: "var(--color-navy-border)", paddingTop: 10 }}>
          <button
            onClick={logout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ color: "var(--color-text-3)" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "#C8D6E8"; (e.currentTarget as HTMLElement).style.background = "var(--color-navy-2)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--color-text-3)"; (e.currentTarget as HTMLElement).style.background = "transparent"; }}
          >
            {ICONS.logout}
            <span style={{ fontSize: 13 }}>Sign out</span>
          </button>
        </div>
      </aside>
    </>
  );
}
