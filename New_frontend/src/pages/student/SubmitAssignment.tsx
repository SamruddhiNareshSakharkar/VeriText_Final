import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "../../components/PageHeader";
import UploadZone from "../../components/UploadZone";
import ProcessingTracker from "../../components/ProcessingTracker";
import Btn from "../../components/Btn";
import Spinner from "../../components/Spinner";
import { Field, Textarea } from "../../components/Field";
import { api } from "../../lib/api";

type Phase = "loading" | "upload" | "confirm" | "processing" | "done" | "error";
type StepStatus = "pending" | "processing" | "complete" | "error" | "skipped";

interface Step { id: string; label: string; status: StepStatus; detail?: string }

const INITIAL_STEPS: Step[] = [
  { id: "upload",     label: "File upload",               status: "pending" },
  { id: "ocr",        label: "OCR Extraction",             status: "pending", detail: "Detecting text from document" },
  { id: "ai",         label: "AI Content Analysis",        status: "pending", detail: "Scanning for AI-generated patterns" },
  { id: "similarity", label: "Similarity Check",           status: "pending", detail: "Comparing against existing submissions" },
  { id: "handwriting",label: "Handwriting Analysis",       status: "pending", detail: "Analysing pen strokes and style" },
  { id: "grading",    label: "Queued for Grading",         status: "pending" },
];

export default function SubmitAssignment() {
  const { id: assignmentId } = useParams();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>(assignmentId ? "loading" : "upload");
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [steps, setSteps] = useState<Step[]>(INITIAL_STEPS);
  const [assignmentsList, setAssignmentsList] = useState<any[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string>(assignmentId || "");
  const [assignment, setAssignment] = useState<any>(null);
  const [submissionId, setSubmissionId] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const pollingRef = useRef<any>(null);

  // Load assignment details or list of available assignments
  useEffect(() => {
    if (!assignmentId) {
      async function loadAllAssignments() {
        try {
          const list = await api.assignments.list();
          setAssignmentsList(list || []);
          if (list && list.length > 0) {
            setSelectedAssignmentId(list[0].id);
            setAssignment(list[0]);
          }
          setPhase("upload");
        } catch {
          setPhase("upload");
        }
      }
      loadAllAssignments();
      return;
    }
    async function loadAssignment() {
      try {
        const data = await api.assignments.get(assignmentId!);
        setAssignment(data);
        setSelectedAssignmentId(assignmentId!);
        setPhase("upload");
      } catch (err: any) {
        setErrorMsg(err?.message || "Could not load assignment details.");
        setPhase("error");
      }
    }
    loadAssignment();
  }, [assignmentId]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  function handleFile(f: File) {
    setFile(f);
    setPhase("confirm");
  }

  function updateStep(stepId: string, status: StepStatus, detail?: string) {
    setSteps((prev) => prev.map((s) => 
      s.id === stepId ? { ...s, status, ...(detail !== undefined ? { detail } : {}) } : s
    ));
  }

  function handleSelectAssignment(newId: string) {
    setSelectedAssignmentId(newId);
    const found = assignmentsList.find((a) => a.id === newId);
    if (found) setAssignment(found);
  }

  async function runPipeline() {
    const activeAssignmentId = assignmentId || selectedAssignmentId;
    if (!file || !activeAssignmentId) {
      setErrorMsg("Please select an assignment before submitting.");
      setPhase("error");
      return;
    }
    setPhase("processing");
    setSteps(INITIAL_STEPS);
    setErrorMsg("");

    // Step 1: Upload file to backend
    updateStep("upload", "processing");
    try {
      const submission = await api.assignments.uploadSubmission(activeAssignmentId, file);
      setSubmissionId(submission.id);
      updateStep("upload", "complete", "File uploaded successfully");

      // Step 2: Poll for analysis progress
      updateStep("ocr", "processing");
      
      pollingRef.current = setInterval(async () => {
        try {
          const analysis = await api.submissions.getAnalysis(submission.id);
          const jobStatus = analysis.job_status;
          const currentStep = analysis.current_step || "";

          // Update steps based on job progress
          if (analysis.ocr_result) {
            updateStep("ocr", "complete", `${analysis.ocr_result.word_count} words extracted`);
          }
          
          if (jobStatus === "processing_ai" || analysis.ai_analysis) {
            if (!analysis.ocr_result) {
              updateStep("ocr", "complete", "Text extraction complete");
            }
            if (analysis.ai_analysis) {
              updateStep("ai", "complete", `AI score: ${Math.round(analysis.ai_analysis.score)}%`);
            } else {
              updateStep("ai", "processing");
            }
          }

          if (jobStatus === "processing_similarity" || analysis.max_similarity_score != null) {
            updateStep("ai", analysis.ai_analysis ? "complete" : "complete");
            if (analysis.max_similarity_score != null) {
              updateStep("similarity", "complete", `Max similarity: ${Math.round(analysis.max_similarity_score)}%`);
            } else {
              updateStep("similarity", "processing");
            }
          }

          if (jobStatus === "processing_handwriting" || analysis.handwriting_analysis) {
            updateStep("similarity", "complete");
            const isImage = file?.type.startsWith("image/") ?? false;
            if (analysis.handwriting_analysis) {
              updateStep("handwriting", "complete", `Confidence: ${Math.round(analysis.handwriting_analysis.confidence * 100)}%`);
            } else if (!isImage) {
              updateStep("handwriting", "skipped", "Not applicable — digital document");
            } else {
              updateStep("handwriting", "processing");
            }
          }

          if (jobStatus === "completed") {
            // Mark all remaining steps as complete
            updateStep("ocr", analysis.ocr_result ? "complete" : "complete");
            updateStep("ai", "complete");
            updateStep("similarity", "complete");
            
            const isImage = file?.type.startsWith("image/") ?? false;
            if (analysis.handwriting_analysis) {
              updateStep("handwriting", "complete");
            } else if (!isImage) {
              updateStep("handwriting", "skipped", "Not applicable — digital document");
            } else {
              updateStep("handwriting", "complete");
            }
            
            updateStep("grading", "complete", "Submission queued for instructor review");
            
            if (pollingRef.current) clearInterval(pollingRef.current);
            setPhase("done");
          }

          if (jobStatus === "failed") {
            if (pollingRef.current) clearInterval(pollingRef.current);
            const failStep = currentStep.toLowerCase();
            if (failStep.includes("ocr")) updateStep("ocr", "error", analysis.error_message || "OCR failed");
            else if (failStep.includes("ai")) updateStep("ai", "error", analysis.error_message || "AI analysis failed");
            else if (failStep.includes("similarity")) updateStep("similarity", "error");
            else if (failStep.includes("handwriting")) updateStep("handwriting", "error");
            
            // Even on failure, mark as done so user can navigate
            updateStep("grading", "complete", "Submitted — some analysis steps had errors");
            setPhase("done");
          }
        } catch {
          // Analysis endpoint may not be ready yet, keep polling
        }
      }, 2000);

      // Timeout: stop polling after 2 minutes and show done
      setTimeout(() => {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          setPhase((prev) => {
            if (prev === "processing") {
              updateStep("grading", "complete", "Submission received — analysis continuing in background");
              return "done";
            }
            return prev;
          });
        }
      }, 120000);

    } catch (err: any) {
      updateStep("upload", "error", err?.message || "Upload failed");
      setErrorMsg(err?.message || "Failed to upload submission. Please try again.");
      setPhase("error");
    }
  }

  if (phase === "loading") {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size={28} color="var(--color-accent)" />
        <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>Loading assignment…</span>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div>
        <PageHeader title="Submit Assignment" breadcrumbs={[{ label: "Assignments" }, { label: "Submit" }]} />
        <div style={{ maxWidth: 520 }}>
          <div className="rounded-xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <div className="rounded-lg p-3 mb-4" style={{ background: "var(--color-red-bg)", border: "1px solid var(--color-red-border)" }}>
              <p className="font-semibold" style={{ fontSize: 13, color: "var(--color-red)" }}>Submission Error</p>
              <p style={{ fontSize: 12, color: "var(--color-red)", opacity: 0.85, marginTop: 2 }}>{errorMsg}</p>
            </div>
            <div className="flex gap-2">
              <Btn variant="secondary" size="md" onClick={() => { setPhase("upload"); setSteps(INITIAL_STEPS); setErrorMsg(""); }}>
                Try again
              </Btn>
              <Btn variant="secondary" size="md" onClick={() => navigate("/student/assignments")}>
                Back to assignments
              </Btn>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (phase === "processing" || phase === "done") {
    return (
      <div>
        <PageHeader
          title="Processing Submission"
          breadcrumbs={[{ label: "Assignments" }, { label: assignment?.title || "Submit" }]}
        />
        <div style={{ maxWidth: 520 }}>
          <div className="rounded-xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
            <div className="flex items-center gap-3 mb-6 pb-5" style={{ borderBottom: "1px solid var(--color-border)" }}>
              <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <rect x="3" y="2" width="12" height="14" rx="1.5" stroke="var(--color-text-3)" strokeWidth="1.4" />
                  <path d="M6 7h6M6 10h4" stroke="var(--color-text-3)" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="font-medium truncate" style={{ fontSize: 14, color: "var(--color-text-1)" }}>{file?.name}</p>
                <p style={{ fontSize: 12, color: "var(--color-text-4)" }}>{file ? `${(file.size / 1024).toFixed(1)} KB` : ""}</p>
              </div>
            </div>

            <ProcessingTracker steps={steps} />

            {phase === "done" && (
              <div className="mt-5 pt-5" style={{ borderTop: "1px solid var(--color-border)" }}>
                <div className="rounded-lg p-3 mb-4" style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}>
                  <p className="font-semibold" style={{ fontSize: 13, color: "var(--color-green)" }}>Submission received</p>
                  <p style={{ fontSize: 12, color: "var(--color-green)", opacity: 0.85, marginTop: 2 }}>
                    Analysis is complete. Your instructor will be notified to review your work.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Btn variant="primary" size="md" onClick={() => navigate("/student/results")} style={{ flex: 1 }}>View results</Btn>
                  <Btn variant="secondary" size="md" onClick={() => navigate("/student/assignments")} style={{ flex: 1 }}>Assignments</Btn>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Submit Assignment"
        breadcrumbs={[{ label: "Assignments" }, { label: assignment?.title || "Submit" }]}
        subtitle={assignment ? `${assignment.title} — Upload your work for integrity analysis.` : "Upload your work. It will be processed for integrity analysis."}
      />
      <div style={{ maxWidth: 520 }}>
        <div className="rounded-xl p-6" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          {phase === "upload" && (
            <>
              {!assignmentId && assignmentsList.length > 0 && (
                <div className="mb-4">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                    Select Assignment To Submit Work For
                  </label>
                  <select
                    value={selectedAssignmentId}
                    onChange={(e) => handleSelectAssignment(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg text-sm"
                    style={{
                      background: "var(--color-canvas)",
                      border: "1px solid var(--color-border)",
                      color: "var(--color-text-1)",
                    }}
                  >
                    {assignmentsList.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {assignment && (
                <div className="rounded-lg px-4 py-3 mb-4" style={{ background: "var(--color-accent-bg)", border: "1px solid var(--color-blue-border)" }}>
                  <p className="font-semibold" style={{ fontSize: 13, color: "var(--color-accent)" }}>{assignment.title}</p>
                  {assignment.description && (
                    <p style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 3 }}>{assignment.description}</p>
                  )}
                  {assignment.due_date && (
                    <p className="font-mono" style={{ fontSize: 11.5, color: "var(--color-text-4)", marginTop: 4 }}>
                      Due: {new Date(assignment.due_date).toLocaleString()}
                    </p>
                  )}
                </div>
              )}
              <div className="rounded-lg px-4 py-3 mb-5 flex items-start gap-2.5"
                style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="flex-shrink-0 mt-0.5">
                  <circle cx="7" cy="7" r="5.5" stroke="var(--color-text-3)" strokeWidth="1.3" />
                  <path d="M7 6.5V9.5M7 4.5v.5" stroke="var(--color-text-3)" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
                <p style={{ fontSize: 12.5, color: "var(--color-text-3)", lineHeight: 1.5 }}>
                  Accepted: {assignment?.allowed_file_types?.toUpperCase() || "PDF, DOCX, TXT, PNG, JPG"} — max 25 MB.
                  Handwritten documents will be processed via OCR.
                </p>
              </div>
              <UploadZone onFile={handleFile} />
            </>
          )}

          {phase === "confirm" && file && (
            <>
              <div className="rounded-lg p-4 mb-5 flex items-center gap-3"
                style={{ background: "var(--color-green-bg)", border: "1px solid var(--color-green-border)" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="flex-shrink-0">
                  <rect x="2" y="2" width="14" height="14" rx="2" stroke="var(--color-green)" strokeWidth="1.4" />
                  <path d="M5 9l3 3 5-5" stroke="var(--color-green)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <div className="min-w-0">
                  <p className="font-medium truncate" style={{ fontSize: 14, color: "var(--color-text-1)" }}>{file.name}</p>
                  <p style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                    {(file.size / 1024).toFixed(1)} KB · {file.type || "unknown type"}
                  </p>
                </div>
                <button
                  onClick={() => { setFile(null); setPhase("upload"); }}
                  style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-text-3)" }}
                  className="hover:underline"
                >
                  Change
                </button>
              </div>

              <Field label="Notes for instructor" hint="Optional — any context about this submission">
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="Any context about this submission…"
                />
              </Field>

              <div className="rounded-lg px-4 py-3 mt-4 mb-5"
                style={{ background: "var(--color-amber-bg)", border: "1px solid var(--color-amber-border)", fontSize: 12.5, color: "var(--color-amber)", lineHeight: 1.5 }}>
                By submitting, you confirm this work is your own and complies with your institution's academic integrity policy.
              </div>

              <div className="flex gap-2">
                <Btn variant="secondary" size="md" onClick={() => { setFile(null); setPhase("upload"); }}>
                  Change file
                </Btn>
                <Btn variant="primary" size="md" style={{ flex: 1 }} onClick={runPipeline}>
                  Submit for analysis
                </Btn>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
