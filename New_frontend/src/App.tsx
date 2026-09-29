import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppProvider, useApp } from "./lib/context";
import AppLayout from "./components/AppLayout";

// Auth
import Login from "./pages/auth/Login";
import SignUp from "./pages/auth/SignUp";
import ForgotPassword from "./pages/auth/ForgotPassword";

// Student
import StudentDashboard from "./pages/student/Dashboard";
import StudentTeams from "./pages/student/Teams";
import TeamOverview from "./pages/student/TeamOverview";
import StudentAssignments from "./pages/student/Assignments";
import SubmitAssignment from "./pages/student/SubmitAssignment";
import SubmissionStatus from "./pages/student/SubmissionStatus";
import StudentResults from "./pages/student/Results";

// Teacher
import TeacherDashboard from "./pages/teacher/Dashboard";
import TeacherTeams from "./pages/teacher/Teams";
import CreateTeam from "./pages/teacher/CreateTeam";
import Members from "./pages/teacher/Members";
import TeacherAssignments from "./pages/teacher/Assignments";
import CreateAssignment from "./pages/teacher/CreateAssignment";
import Submissions from "./pages/teacher/Submissions";
import SubmissionDetail from "./pages/teacher/SubmissionDetail";
import Compare from "./pages/teacher/Compare";
import Reports from "./pages/teacher/Reports";
import Grading from "./pages/teacher/Grading";
import EditGrading from "./pages/teacher/EditGrading";

import Spinner from "./components/Spinner";

function Guard({ children, role }: { children: React.ReactNode; role?: "student" | "teacher" }) {
  const { user, isLoading } = useApp();

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3" style={{ background: "var(--color-canvas)" }}>
        <Spinner size={28} color="var(--color-accent)" />
        <p style={{ fontSize: 13, color: "var(--color-text-3)", fontFamily: "var(--font-sans)" }}>
          Authenticating session...
        </p>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (role === "student" && user.role !== "student") return <Navigate to="/teacher" replace />;
  if (role === "teacher" && user.role === "student") return <Navigate to="/student" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useApp();

  return (
    <Routes>
      {/* Auth */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<SignUp />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />

      {/* Student */}
      <Route element={<Guard role="student"><AppLayout /></Guard>}>
        <Route path="/student" element={<StudentDashboard />} />
        <Route path="/student/teams" element={<StudentTeams />} />
        <Route path="/student/teams/:id" element={<TeamOverview />} />
        <Route path="/student/assignments" element={<StudentAssignments />} />
        <Route path="/student/submit" element={<SubmitAssignment />} />
        <Route path="/student/submit/:id" element={<SubmitAssignment />} />
        <Route path="/student/submission-status/:id" element={<SubmissionStatus />} />
        <Route path="/student/results" element={<StudentResults />} />
      </Route>

      {/* Teacher / Admin */}
      <Route element={<Guard role="teacher"><AppLayout /></Guard>}>
        <Route path="/teacher" element={<TeacherDashboard />} />
        <Route path="/teacher/teams" element={<TeacherTeams />} />
        <Route path="/teacher/teams/new" element={<CreateTeam />} />
        <Route path="/teacher/teams/:id/members" element={<Members />} />
        <Route path="/teacher/assignments" element={<TeacherAssignments />} />
        <Route path="/teacher/assignments/new" element={<CreateAssignment />} />
        <Route path="/teacher/submissions" element={<Submissions />} />
        <Route path="/teacher/submissions/:id" element={<SubmissionDetail />} />
        <Route path="/teacher/compare" element={<Compare />} />
        <Route path="/teacher/reports" element={<Reports />} />
        <Route path="/teacher/grading" element={<Grading />} />
        <Route path="/teacher/grading/:id" element={<EditGrading />} />
      </Route>

      {/* Root */}
      <Route
        path="/"
        element={user
          ? <Navigate to={user.role === "student" ? "/student" : "/teacher"} replace />
          : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppRoutes />
      </AppProvider>
    </BrowserRouter>
  );
}
