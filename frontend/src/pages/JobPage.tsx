import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getJob } from "../api";
import type { Job } from "../types";
import NavBar from "../components/NavBar";
import SummaryCard from "../components/SummaryCard";
import BrandTimeline from "../components/BrandTimeline";
import ViolationsList from "../components/ViolationsList";
import { JobStatusBadge } from "../components/StatusBadge";

const POLL_INTERVAL_MS = 4000;

const STEP_ORDER = ["queued", "indexing", "analyzing", "complete"];

function ProgressSteps({ status }: { status: Job["status"] }) {
  const currentIdx = STEP_ORDER.indexOf(status === "failed" ? "queued" : status);
  const steps = [
    { key: "queued",    label: "Queued" },
    { key: "indexing",  label: "Indexing Video" },
    { key: "analyzing", label: "Analysing" },
    { key: "complete",  label: "Complete" },
  ];

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, i) => {
        const done = currentIdx > i;
        const active = currentIdx === i && status !== "failed";
        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                done    ? "bg-green-500 text-white" :
                active  ? "bg-blue-500 text-white ring-4 ring-blue-500/20" :
                status === "failed" && i === 0 ? "bg-red-500 text-white" :
                "bg-[#2a2d3a] text-slate-500"
              }`}>
                {done ? "✓" : i + 1}
              </div>
              <span className={`text-xs mt-1 ${active ? "text-white" : done ? "text-green-400" : "text-slate-500"}`}>
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-0.5 w-16 mx-1 mb-4 transition-all ${done ? "bg-green-500" : "bg-[#2a2d3a]"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

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
      <div className="min-h-screen bg-[#0f1117]">
        <NavBar />
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <p className="text-red-400">{error}</p>
          <Link to="/" className="text-blue-400 hover:underline mt-4 inline-block">← Back to Upload</Link>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen bg-[#0f1117]">
        <NavBar />
        <div className="max-w-3xl mx-auto px-4 py-20 text-center text-slate-400">
          Loading…
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f1117]">
      <NavBar />
      <div className="max-w-4xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link to="/" className="text-slate-500 hover:text-slate-300 text-sm">← New Audit</Link>
            </div>
            <h1 className="text-2xl font-bold text-white">{job.brand}</h1>
            <p className="text-slate-400 text-sm mt-0.5">{job.video_filename}</p>
          </div>
          <JobStatusBadge status={job.status} />
        </div>

        {/* Progress (while running) */}
        {job.status !== "complete" && job.status !== "failed" && (
          <div className="bg-[#1a1d27] border border-[#2a2d3a] rounded-xl p-6 mb-6">
            <div className="flex justify-center mb-6">
              <ProgressSteps status={job.status} />
            </div>
            <p className="text-center text-slate-400 text-sm animate-pulse">
              {job.progress_message}
            </p>
          </div>
        )}

        {/* Failed state */}
        {job.status === "failed" && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 mb-6">
            <p className="text-red-400 font-semibold mb-1">Audit failed</p>
            <p className="text-slate-400 text-sm">{job.error}</p>
          </div>
        )}

        {/* Results */}
        {job.status === "complete" && job.report && (
          <div className="space-y-6">
            <SummaryCard report={job.report} />
            <BrandTimeline
              report={job.report}
              videoUrl={job.video_url ?? ""}
            />
            <ViolationsList violations={job.report.violations} />
          </div>
        )}

        {/* Meta */}
        <div className="mt-6 text-xs text-slate-600 space-y-0.5">
          <p>Job ID: {job.job_id}</p>
          <p>Guidelines: {job.guidelines_filename}</p>
          <p>Started: {new Date(job.created_at).toLocaleString()}</p>
          {job.completed_at && (
            <p>Completed: {new Date(job.completed_at).toLocaleString()}</p>
          )}
        </div>
      </div>
    </div>
  );
}
