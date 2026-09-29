import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../../lib/context";
import Btn from "../../components/Btn";
import { Field, Input } from "../../components/Field";
import type { UserRole } from "../../lib/types";

const DEPARTMENTS = [
  "Computer Engineering",
  "Information Technology",
  "Electronics and Computer Science",
  "Electronics and Telecommunication",
  "Biomedical Engineering",
];

const STUDENT_AVATARS = [
  "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
];

const TEACHER_AVATARS = [
  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150&auto=format&fit=crop&q=80",
  "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
];

export default function SignUp() {
  const { register } = useApp();
  const navigate = useNavigate();
  const [role, setRole] = useState<UserRole>("student");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState(DEPARTMENTS[0]);
  const [rollNo, setRollNo] = useState("");
  const [facultyId, setFacultyId] = useState("");
  const [designation, setDesignation] = useState("Assistant Professor");
  const [photoUrl, setPhotoUrl] = useState(STUDENT_AVATARS[0]);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleRoleChange(newRole: UserRole) {
    setRole(newRole);
    if (newRole === "teacher") {
      setPhotoUrl(TEACHER_AVATARS[0]);
    } else {
      setPhotoUrl(STUDENT_AVATARS[0]);
    }
  }

  function handleCustomPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (typeof reader.result === "string") {
          setPhotoUrl(reader.result);
        }
      };
      reader.readAsDataURL(file);
    }
  }

  function validate() {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Full name is required.";
    if (!email.trim()) e.email = "Institutional email is required.";
    if (role === "student" && !rollNo.trim()) {
      e.rollNo = "Roll number is required for students.";
    }
    if (role === "teacher" && !facultyId.trim()) {
      e.facultyId = "Faculty / Staff ID is required.";
    }
    if (password.length < 6) e.password = "Password must be at least 6 characters.";
    return e;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setLoading(true);
    try {
      const user = await register({
        email: email.trim(),
        password,
        fullName: name.trim(),
        role,
        department,
        roll_no: role === "student" ? rollNo.trim() : undefined,
        faculty_id: role === "teacher" ? facultyId.trim() : undefined,
        designation: role === "teacher" ? designation : undefined,
        photo_url: photoUrl,
      });
      navigate(user.role === "teacher" || user.role === "admin" ? "/teacher" : "/student");
    } catch (err: any) {
      setErrors({ form: err?.message || "Registration failed. Please try again." });
    } finally {
      setLoading(false);
    }
  }

  const currentAvatars = role === "teacher" ? TEACHER_AVATARS : STUDENT_AVATARS;

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-[#0b192e] overflow-x-hidden">
      {/* Left Side: Form */}
      <div className="lg:w-7/12 min-h-screen p-6 sm:p-10 md:p-12 lg:p-16 flex flex-col justify-between bg-[#f8fafc] border-r border-stone-200">
        <div>
          <Link to="/login" className="inline-flex items-center gap-2 mb-6 hover:opacity-75 transition-opacity">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: "var(--color-navy)" }}>
              <svg width="14" height="14" viewBox="0 0 18 18" fill="none">
                <rect x="2" y="2" width="5" height="14" rx="0.5" fill="white" fillOpacity="0.95" />
                <rect x="9.5" y="2" width="6.5" height="6.5" rx="0.5" fill="white" fillOpacity="0.95" />
                <rect x="9.5" y="10" rx="0.5" width="6.5" height="6" fill="white" fillOpacity="0.6" />
              </svg>
            </div>
            <span className="font-sans font-extrabold text-lg tracking-tight" style={{ color: "var(--color-navy)" }}>VERITEXT</span>
          </Link>

          <h1 className="text-2xl font-bold font-sans tracking-tight" style={{ color: "var(--color-text-1)" }}>Create Academic Profile</h1>
          <p className="text-xs mt-1 mb-6" style={{ color: "var(--color-text-3)" }}>
            Enter your institutional details. Information differs between students and faculty members.
          </p>

          {/* Role selector buttons */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            <button
              type="button"
              onClick={() => handleRoleChange("student")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-3 ${
                role === "student" 
                  ? "border-blue-600 bg-blue-50/70 ring-2 ring-blue-500/20 shadow-sm" 
                  : "border-stone-200 bg-stone-50 hover:bg-white"
              }`}
            >
              <span className="text-2xl">🎓</span>
              <div>
                <p className="text-xs font-bold text-stone-900">Student Profile</p>
                <p className="text-[10.5px] text-stone-500">Roll No & Department</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleRoleChange("teacher")}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-3 ${
                role === "teacher" 
                  ? "border-emerald-600 bg-emerald-50/70 ring-2 ring-emerald-500/20 shadow-sm" 
                  : "border-stone-200 bg-stone-50 hover:bg-white"
              }`}
            >
              <span className="text-2xl">🏫</span>
              <div>
                <p className="text-xs font-bold text-stone-900">Faculty / Teacher</p>
                <p className="text-[10.5px] text-stone-500">Faculty ID & Designation</p>
              </div>
            </button>
          </div>

          {errors.form && (
            <div className="p-3 mb-5 rounded-xl text-xs flex items-center gap-2" style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)", color: "var(--color-red)" }}>
              <span>⚠️</span>
              <span>{errors.form}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Full Name & Email */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={role === "teacher" ? "Full Name (with Title)" : "Student Full Name"} error={errors.name} required>
                <Input 
                  value={name} 
                  onChange={(e) => setName(e.target.value)} 
                  placeholder={role === "teacher" ? "Prof. / Dr. Full Name" : "e.g. Samruddhi Sakharkar"} 
                  error={!!errors.name} 
                />
              </Field>

              <Field label="Institutional Email" error={errors.email} required>
                <Input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  placeholder="name@vit.edu.in" 
                  error={!!errors.email} 
                />
              </Field>
            </div>

            {/* Department Dropdown */}
            <Field label="Engineering Department" required>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border text-sm transition focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                style={{ 
                  background: "var(--color-surface)", 
                  borderColor: "var(--color-border)", 
                  color: "var(--color-text-1)" 
                }}
              >
                {DEPARTMENTS.map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>
            </Field>

            {/* Differentiated Student vs Teacher Fields */}
            {role === "student" ? (
              <Field label="Student Roll Number" error={errors.rollNo} hint="Official university identification roll number" required>
                <Input 
                  value={rollNo} 
                  onChange={(e) => setRollNo(e.target.value.toUpperCase())} 
                  placeholder="e.g. 24102A0074" 
                  error={!!errors.rollNo} 
                />
              </Field>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Faculty / Employee ID" error={errors.facultyId} required>
                  <Input 
                    value={facultyId} 
                    onChange={(e) => setFacultyId(e.target.value.toUpperCase())} 
                    placeholder="e.g. FAC-COMP-01" 
                    error={!!errors.facultyId} 
                  />
                </Field>

                <Field label="Academic Designation" required>
                  <select
                    value={designation}
                    onChange={(e) => setDesignation(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                    style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
                  >
                    <option value="Assistant Professor">Assistant Professor</option>
                    <option value="Associate Professor">Associate Professor</option>
                    <option value="Professor">Professor</option>
                    <option value="Head of Department (HOD)">Head of Department (HOD)</option>
                    <option value="Visiting Faculty">Visiting Faculty</option>
                  </select>
                </Field>
              </div>
            )}

            {/* Profile Photo / Avatar Picker */}
            <div>
              <label className="block text-xs font-semibold mb-2" style={{ color: "var(--color-text-1)" }}>
                Profile Photo / Avatar
              </label>
              <div className="flex items-center gap-3">
                {currentAvatars.map((url, idx) => (
                  <img
                    key={idx}
                    src={url}
                    alt="Preset Avatar"
                    onClick={() => setPhotoUrl(url)}
                    className={`w-10 h-10 rounded-full object-cover cursor-pointer transition-all ${
                      photoUrl === url 
                        ? "ring-3 ring-blue-600 scale-110 shadow-sm" 
                        : "opacity-60 hover:opacity-100"
                    }`}
                  />
                ))}
                <label className="ml-2 px-2.5 py-1.5 rounded-lg border text-xs cursor-pointer hover:bg-stone-100 transition font-medium" style={{ borderColor: "var(--color-border)" }}>
                  <span>Upload Photo</span>
                  <input type="file" accept="image/*" onChange={handleCustomPhoto} className="hidden" />
                </label>
              </div>
            </div>

            {/* Password */}
            <Field label="Password" error={errors.password} hint="Minimum 6 characters" required>
              <Input 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)} 
                placeholder="••••••••" 
                error={!!errors.password} 
              />
            </Field>

            <Btn variant="primary" size="lg" loading={loading} type="submit" style={{ width: "100%", marginTop: 8 }}>
              {loading ? "Registering Profile…" : `Create ${role === "student" ? "Student" : "Faculty"} Account`}
            </Btn>
          </form>

          <p className="text-center mt-5 text-xs" style={{ color: "var(--color-text-3)" }}>
            Already have an account?{" "}
            <Link to="/login" style={{ color: "var(--color-accent)", fontWeight: 600 }} className="hover:underline">Sign in</Link>
          </p>
        </div>
      </div>

        {/* Right Side: Live Academic ID Card Preview */}
        <div className="lg:w-5/12 min-h-screen p-8 sm:p-12 lg:p-14 flex flex-col justify-between relative overflow-hidden bg-stone-100/90 border-l border-stone-200">
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-bold uppercase tracking-wider text-stone-500">Live Academic ID Card Preview</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-blue-100 text-blue-800">
                {role === "student" ? "STUDENT PASS" : "FACULTY BADGE"}
              </span>
            </div>

            {/* ID Card Display */}
            <div className="rounded-2xl border bg-white shadow-lg overflow-hidden border-stone-200 transition-all hover:shadow-xl">
              {/* Card Institute Header */}
              <div 
                className="p-4 text-white flex items-center justify-between"
                style={{ 
                  background: role === "student" 
                    ? "linear-gradient(135deg, #1e3a8a 0%, #172554 100%)" 
                    : "linear-gradient(135deg, #065f46 0%, #022c22 100%)" 
                }}
              >
                <div>
                  <div className="text-[10px] uppercase font-bold tracking-widest text-sky-200">
                    Vidyalankar Institute of Technology
                  </div>
                  <div className="text-xs font-sans font-bold text-white tracking-wide">
                    {role === "student" ? "Student Identity Card" : "Faculty & Staff Credential"}
                  </div>
                </div>
                <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center font-bold text-sm">
                  {role === "student" ? "🎓" : "🏛️"}
                </div>
              </div>

              {/* Card Body */}
              <div className="p-5 flex gap-4 items-center">
                <img 
                  src={photoUrl} 
                  alt="ID Preview" 
                  className="w-20 h-24 rounded-lg object-cover border-2 border-stone-200 shadow-sm flex-shrink-0"
                />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="text-sm font-bold text-stone-900 truncate">
                    {name || (role === "student" ? "Student Name" : "Faculty Name")}
                  </div>
                  <div className="text-[11px] font-semibold text-blue-800 bg-blue-50 px-2 py-0.5 rounded inline-block truncate max-w-full">
                    {department}
                  </div>
                  
                  {role === "student" ? (
                    <div className="text-xs text-stone-600 pt-1">
                      <span className="font-mono font-bold text-stone-900">Roll: {rollNo || "24102A00XX"}</span>
                    </div>
                  ) : (
                    <div className="text-xs text-stone-600 pt-1">
                      <div className="font-mono font-bold text-emerald-800">ID: {facultyId || "FAC-XXXX-01"}</div>
                      <div className="text-[10px] text-stone-500 font-medium">{designation}</div>
                    </div>
                  )}

                  <div className="text-[10px] text-stone-400 truncate pt-1">
                    {email || "user@vit.edu.in"}
                  </div>
                </div>
              </div>

              {/* Card Footer with Barcode Effect */}
              <div className="px-5 py-2.5 bg-stone-50 border-t border-stone-100 flex items-center justify-between">
                <div className="text-[9.5px] font-mono text-stone-400">
                  AUT-VERIFIED • {new Date().getFullYear()}
                </div>
                <div className="flex gap-0.5 items-center">
                  {[2, 4, 1, 3, 2, 4, 1, 2, 3, 4, 1, 3, 2].map((w, i) => (
                    <span key={i} className="bg-stone-700 h-4 block" style={{ width: `${w * 1.5}px` }} />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Department Features Note */}
          <div className="mt-8 p-4 rounded-xl border bg-white/70 text-xs text-stone-600 space-y-1" style={{ borderColor: "var(--color-border)" }}>
            <p className="font-bold text-stone-800 text-[11px] uppercase tracking-wider">Department Features</p>
            <p className="text-[11.5px] leading-relaxed">
              Your assignments, similarity comparisons, and grading rubrics will be automatically segmented by <strong>{department}</strong>.
            </p>
          </div>
        </div>
      </div>
  );
}
