import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getJob, reviewJob } from "../api";
import type { Job, ReviewStatus } from "../types";
import SummaryCard from "../components/SummaryCard";
import BrandTimeline from "../components/BrandTimeline";
import ViolationsList from "../components/ViolationsList";
import { JobStatusBadge, ReviewBadge, SourceBadge } from "../components/StatusBadge";

const POLL_INTERVAL_MS = 4000;
const STEP_ORDER = ["queued", "indexing", "analyzing", "complete"];

function ProgressSteps({ status }: { status: Job["status"] }) {
  const currentIdx = STEP_ORDER.indexOf(status === "failed" ? "queued" : status);
  const steps = [
    { key: "queued",    label: "Queued" },
    { key: "indexing",  label: "Indexing" },
    { key: "analyzing", label: "Analysing" },
    { key: "complete",  label: "Complete" },
  ];

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, i) => {
        const done   = currentIdx > i;
        const active = currentIdx === i && status !== "failed";
        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                done    ? "bg-teal text-obs-base" :
                active  ? "bg-vio-deep text-white ring-4 ring-vio/20" :
                status === "failed" && i === 0 ? "bg-rose-dark text-rose" :
                "bg-obs-top text-muted"
              }`}>
                {done ? "✓" : i + 1}
              </div>
              <span className={`text-xs mt-1 ${active ? "text-vio" : done ? "text-teal" : "text-muted/40"}`}>
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-0.5 w-16 mx-1 mb-4 transition-all ${done ? "bg-teal" : "bg-obs-top"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Review Decision Panel
// ---------------------------------------------------------------------------

const DECISIONS: { key: ReviewStatus; label: string; icon: string; style: string; activeStyle: string }[] = [
  {
    key: "approved",
    label: "Approve for Delivery",
    icon: "check_circle",
    style: "bg-teal-dark/40 hover:bg-teal-dark text-teal hover:text-obs-base",
    activeStyle: "bg-teal text-obs-base ring-2 ring-teal ring-offset-2 ring-offset-obs-low",
  },
  {
    key: "rejected",
    label: "Reject Content",
    icon: "cancel",
    style: "bg-rose-dark/30 hover:bg-rose-dark text-rose",
    activeStyle: "bg-rose-dark text-white ring-2 ring-rose ring-offset-2 ring-offset-obs-low",
  },
  {
    key: "escalated",
    label: "Escalate for Review",
    icon: "escalator_warning",
    style: "bg-obs-top hover:bg-obs-bright text-muted hover:text-vio-text",
    activeStyle: "bg-vio-deep text-white ring-2 ring-vio ring-offset-2 ring-offset-obs-low",
  },
];

function ReviewPanel({ job, onUpdate }: { job: Job; onUpdate: (j: Job) => void }) {
  const [selected, setSelected] = useState<ReviewStatus | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already reviewed
  if (job.review_status) {
    const d = DECISIONS.find(d => d.key === job.review_status)!;
    return (
      <div className="bg-obs-low rounded-xl p-6">
        <p className="text-[11px] font-bold text-muted uppercase tracking-widest mb-4">Compliance Decision</p>
        <div className="flex items-center gap-3 mb-3">
          <span className={`material-symbols-outlined ${d.key === "approved" ? "text-teal" : d.key === "rejected" ? "text-rose" : "text-[#c4c0ff]"}`} style={{ fontSize: "24px" }}>
            {d.icon}
          </span>
          <div>
            <p className="font-bold text-vio-text">{d.label}</p>
            {job.reviewed_at && (
              <p className="text-xs text-muted">{new Date(job.reviewed_at).toLocaleString()}</p>
            )}
          </div>
          <div className="ml-auto">
            <ReviewBadge status={job.review_status} />
          </div>
        </div>
        {job.review_notes && (
          <p className="text-sm text-muted bg-obs-mid rounded-lg px-4 py-3 leading-relaxed">
            "{job.review_notes}"
          </p>
        )}
        {job.frame_io_asset_id && (
          <p className="text-xs text-muted/40 mt-3 flex items-center gap-1">
            <span className="material-symbols-outlined" style={{ fontSize: "13px" }}>hub</span>
            Decision posted to Frame.io asset
          </p>
        )}
      </div>
    );
  }

  const handleSubmit = async () => {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await reviewJob(job.job_id, selected, notes || undefined);
      onUpdate(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit decision.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-obs-low rounded-xl p-6">
      <p className="text-[11px] font-bold text-muted uppercase tracking-widest mb-4">Compliance Decision</p>
      <div className="flex flex-col gap-2 mb-4">
        {DECISIONS.map((d) => (
          <button
            key={d.key}
            onClick={() => setSelected(d.key)}
            className={`w-full py-3.5 px-5 rounded-xl font-bold text-sm flex items-center justify-between transition-all active:scale-[0.98] ${
              selected === d.key ? d.activeStyle : d.style
            }`}
          >
            <span>{d.label}</span>
            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
              {selected === d.key ? "task_alt" : d.icon}
            </span>
          </button>
        ))}
      </div>

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Add notes for the editor (optional)…"
        rows={3}
        className="w-full bg-obs-mid rounded-lg px-3 py-2.5 text-sm text-vio-text placeholder:text-muted/30 focus:outline-none focus:ring-1 focus:ring-vio/30 resize-none mb-3"
      />

      {error && (
        <p className="text-rose text-xs mb-3 flex items-center gap-1">
          <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>error</span>
          {error}
        </p>
      )}

      <button
        onClick={handleSubmit}
        disabled={!selected || submitting}
        className="w-full py-3 rounded-xl font-bold text-sm text-[#0e006a] transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
        style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
      >
        {submitting ? "Submitting…" : "Submit Decision"}
        {job.frame_io_asset_id && !submitting && (
          <span className="ml-2 text-[#0e006a]/60 text-xs font-normal">· posts to Frame.io</span>
        )}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function JobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJob = async () => {
    if (!jobId) return;
    try {
      const j = await getJob(jobId);
      setJob(j);
      if (j.status === "complete" || j.status === "failed") {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load job.");
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  };

  useEffect(() => {
    fetchJob();
    intervalRef.current = setInterval(fetchJob, POLL_INTERVAL_MS);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [jobId]);

  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-rose">{error}</p>
        <Link to="/" className="text-vio hover:underline mt-4 inline-block">← Back to Upload</Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="p-8 text-center text-muted animate-pulse">Loading…</div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 max-w-5xl">
        <div>
          <Link
            to="/jobs"
            className="text-muted/50 hover:text-muted text-[10px] uppercase tracking-widest flex items-center gap-1 mb-2 transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>arrow_back</span>
            Audit Log
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-vio-text">{job.brand}</h1>
          <p className="text-sm text-muted mt-0.5">{job.video_filename}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <SourceBadge source={job.source} />
          {job.review_status && <ReviewBadge status={job.review_status} />}
          <JobStatusBadge status={job.status} />
          {job.status === "complete" && job.report && (
            <button
              onClick={() => {
                const blob = new Blob(
                  [JSON.stringify({ job_id: job.job_id, brand: job.brand, video_filename: job.video_filename, created_at: job.created_at, completed_at: job.completed_at, review_status: job.review_status, review_notes: job.review_notes, report: job.report }, null, 2)],
                  { type: "application/json" },
                );
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `obsidian-lens-report-${job.job_id.slice(0, 8)}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-muted hover:text-vio-text bg-obs-low hover:bg-obs-mid transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "15px" }}>download</span>
              Download Report
            </button>
          )}
        </div>
      </div>

      {/* Progress */}
      {job.status !== "complete" && job.status !== "failed" && (
        <div className="bg-obs-low rounded-xl p-6 mb-6 max-w-2xl">
          <div className="flex justify-center mb-6">
            <ProgressSteps status={job.status} />
          </div>
          <p className="text-center text-muted text-sm animate-pulse">
            {job.progress_message}
          </p>
        </div>
      )}

      {/* Failed */}
      {job.status === "failed" && (
        <div
          className="rounded-xl p-5 mb-6 flex items-start gap-3 max-w-2xl"
          style={{ background: "rgba(147,0,10,0.2)" }}
        >
          <span className="material-symbols-outlined text-rose mt-0.5" style={{ fontSize: "18px" }}>error</span>
          <div>
            <p className="text-rose font-semibold text-sm">Audit failed</p>
            <p className="text-muted text-sm mt-1">{job.error}</p>
          </div>
        </div>
      )}

      {/* Results — two-column when complete */}
      {job.status === "complete" && job.report && (
        <div className="flex gap-6 items-start max-w-6xl">
          {/* Left: audit details */}
          <div className="flex-1 min-w-0 space-y-6">
            <SummaryCard report={job.report} />
            <BrandTimeline report={job.report} videoUrl={job.video_url ?? ""} />
            <ViolationsList violations={job.report.violations} />
          </div>

          {/* Right: decision panel (sticky) */}
          <div className="w-72 shrink-0 sticky top-6">
            <ReviewPanel job={job} onUpdate={setJob} />
          </div>
        </div>
      )}

      {/* Meta */}
      <div className="mt-6 text-xs text-muted/30 space-y-0.5 max-w-5xl">
        <p>Job ID: {job.job_id}</p>
        <p>Guidelines: {job.guidelines_filename}</p>
        {job.frame_io_asset_id && <p>Frame.io asset: {job.frame_io_asset_id}</p>}
        <p>Started: {new Date(job.created_at).toLocaleString()}</p>
        {job.completed_at && <p>Completed: {new Date(job.completed_at).toLocaleString()}</p>}
      </div>
    </div>
  );
}
