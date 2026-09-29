import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import type { UserRole } from "./types";
import { api, apiRequest } from "./api";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  department?: string;
  roll_no?: string;
  faculty_id?: string;
  designation?: string;
  photo_url?: string;
  institution?: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  fullName: string;
  role: string;
  department?: string;
  roll_no?: string;
  faculty_id?: string;
  designation?: string;
  photo_url?: string;
}

interface AppContextValue {
  user: AuthUser | null;
  setUser: (u: AuthUser | null) => void;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => void;
  sidebarOpen: boolean;
  setSidebarOpen: (v: boolean) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

function mapBackendUser(u: any): AuthUser {
  return {
    id: u.id,
    name: u.full_name || u.name || "User",
    email: u.email,
    role: (u.role?.toLowerCase() === "teacher" || u.role?.toLowerCase() === "admin" ? u.role.toLowerCase() : "student") as UserRole,
    department: u.department || "Computer Engineering",
    roll_no: u.roll_no,
    faculty_id: u.faculty_id,
    designation: u.designation,
    photo_url: u.photo_url || (u.role === "teacher"
      ? "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80"
      : "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80"),
    institution: u.institution || "Vidyalankar Institute of Technology",
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const saved = localStorage.getItem("veritext_user");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem("veritext_token");
  });

  const [isLoading, setIsLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    async function verifySession() {
      const storedToken = localStorage.getItem("veritext_token");
      if (!storedToken) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await apiRequest("/auth/me");
        const mapped = mapBackendUser(profile);
        setUser(mapped);
        localStorage.setItem("veritext_user", JSON.stringify(mapped));
      } catch {
        localStorage.removeItem("veritext_token");
        localStorage.removeItem("veritext_user");
        setUser(null);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    }
    verifySession();
  }, []);

  const login = async (email: string, password: string): Promise<AuthUser> => {
    const res = await api.auth.login({ email, password });
    const mapped = mapBackendUser(res.user);
    localStorage.setItem("veritext_token", res.access_token);
    localStorage.setItem("veritext_user", JSON.stringify(mapped));
    setToken(res.access_token);
    setUser(mapped);
    return mapped;
  };

  const register = async (payload: RegisterPayload): Promise<AuthUser> => {
    const res = await api.auth.register({
      email: payload.email,
      password: payload.password,
      full_name: payload.fullName,
      role: payload.role.toLowerCase(),
      department: payload.department,
      roll_no: payload.roll_no,
      faculty_id: payload.faculty_id,
      designation: payload.designation,
      photo_url: payload.photo_url,
    });
    const mapped = mapBackendUser(res.user);
    localStorage.setItem("veritext_token", res.access_token);
    localStorage.setItem("veritext_user", JSON.stringify(mapped));
    setToken(res.access_token);
    setUser(mapped);
    return mapped;
  };

  const logout = () => {
    localStorage.removeItem("veritext_token");
    localStorage.removeItem("veritext_user");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AppContext.Provider
      value={{
        user,
        setUser,
        token,
        isLoading,
        login,
        register,
        logout,
        sidebarOpen,
        setSidebarOpen,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be inside AppProvider");
  return ctx;
}
